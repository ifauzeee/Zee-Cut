"""
Cross-platform detection and OS-specific system utilities.
All functions return platform-appropriate values without side effects.
"""

import os
import platform
import re
import subprocess
import sys
from typing import Optional

SYSTEM: str = platform.system().lower()
IS_WINDOWS: bool = SYSTEM == "windows"
IS_LINUX: bool = SYSTEM == "linux"
IS_MACOS: bool = SYSTEM == "darwin"

if IS_WINDOWS:
    import ctypes

    _CREATE_NO_WINDOW = 0x08000000
else:
    _CREATE_NO_WINDOW = 0


# ── Subprocess helpers ─────────────────────────────────────────────

def subprocess_run(
    args: list[str],
    capture_output: bool = True,
    text: bool = True,
    timeout: int = 10,
    **kwargs,
) -> subprocess.CompletedProcess:
    """Run a subprocess with platform-appropriate CREATE_NO_WINDOW."""
    kwargs.setdefault("creationflags", 0)
    if IS_WINDOWS:
        kwargs["creationflags"] |= _CREATE_NO_WINDOW
    return subprocess.run(
        args,
        capture_output=capture_output,
        text=text,
        timeout=timeout,
        **kwargs,
    )


# ── Admin / elevation ──────────────────────────────────────────────

def is_admin() -> bool:
    """Check whether the current process has admin/root privileges."""
    if IS_WINDOWS:
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    return os.geteuid() == 0


def run_as_admin(entry_file: str) -> bool:
    """Re-launch the current script with elevated privileges."""
    if IS_WINDOWS:
        try:
            if getattr(sys, "frozen", False):
                script = sys.executable
                params = ""
            else:
                script = sys.executable
                params = f'"{os.path.abspath(entry_file)}"'
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", script, params, None, 1
            )
            return result > 32
        except Exception:
            return False
    try:
        subprocess_run(["sudo", sys.executable] + sys.argv, capture_output=False)
        return True
    except Exception:
        return False


# ── Ping ───────────────────────────────────────────────────────────

def ping_command(ip: str, timeout_ms: int) -> list[str]:
    """Return platform-appropriate ping args."""
    if IS_WINDOWS:
        return ["ping", "-n", "1", "-w", str(timeout_ms), ip]
    timeout_s = str(max(1, timeout_ms // 1000))
    return ["ping", "-c", "1", "-W", timeout_s, ip]


# ── ARP table ──────────────────────────────────────────────────────

def read_arp_table(subnet_prefix: str) -> list[tuple[str, str]]:
    """
    Read the system ARP table and return (ip, mac) pairs that match the
    given subnet prefix (e.g. '192.168.1.').
    """
    if IS_LINUX:
        return _parse_linux_arp_table(subnet_prefix)
    if IS_MACOS:
        return _parse_macos_arp_table(subnet_prefix)
    return _parse_windows_arp_table(subnet_prefix)


def _parse_windows_arp_table(subnet_prefix: str) -> list[tuple[str, str]]:
    try:
        result = subprocess_run(["arp", "-a"], timeout=4)
        if result.returncode != 0:
            return []
        entries: list[tuple[str, str]] = []
        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()
            m = re.match(
                r"(\d+\.\d+\.\d+\.\d+)\s+"
                r"([\da-fA-F]{2}[:-][\da-fA-F]{2}[:-][\da-fA-F]{2}[:-]"
                r"[\da-fA-F]{2}[:-][\da-fA-F]{2}[:-][\da-fA-F]{2})\s+(\w+)",
                line,
            )
            if not m:
                continue
            ip = m.group(1)
            mac = m.group(2).replace("-", ":").lower()
            etype = m.group(3).lower()
            if mac == "ff:ff:ff:ff:ff:ff":
                continue
            if not ip.startswith(subnet_prefix):
                continue
            if etype not in ("dynamic", "dinamis", "static", "statis"):
                continue
            entries.append((ip, mac))
        return entries
    except Exception:
        return []


def _parse_linux_arp_table(subnet_prefix: str) -> list[tuple[str, str]]:
    try:
        with open("/proc/net/arp", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return []
    entries: list[tuple[str, str]] = []
    for line in lines[1:]:  # skip header
        parts = line.split()
        if len(parts) < 4:
            continue
        ip = parts[0]
        hw_type = parts[1]
        flags = parts[2]
        mac = parts[3]
        if hw_type in ("0x0",) or flags in ("0x0",):
            continue
        if mac in ("00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff"):
            continue
        if not ip.startswith(subnet_prefix):
            continue
        entries.append((ip, mac.lower()))
    return entries


def _parse_macos_arp_table(subnet_prefix: str) -> list[tuple[str, str]]:
    try:
        result = subprocess_run(["arp", "-a"], timeout=4)
        if result.returncode != 0:
            return []
        entries: list[tuple[str, str]] = []
        # macOS arp -a output:  ? (192.168.1.1) at aa:bb:cc:dd:ee:01 on en0 ...
        for line in result.stdout.splitlines():
            m = re.search(
                r"\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+"
                r"([\da-fA-F]{2}:[\da-fA-F]{2}:[\da-fA-F]{2}:[\da-fA-F]{2}:"
                r"[\da-fA-F]{2}:[\da-fA-F]{2})",
                line,
            )
            if not m:
                continue
            ip = m.group(1)
            mac = m.group(2).lower()
            if mac in ("00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff"):
                continue
            if not ip.startswith(subnet_prefix):
                continue
            entries.append((ip, mac))
        return entries
    except Exception:
        return []


# ── ARP cache flush ────────────────────────────────────────────────

def flush_arp_cache() -> tuple[bool, str]:
    """Flush the system ARP cache. Returns (success, message)."""
    if IS_WINDOWS:
        for cmd in [
            ["cmd", "/c", "arp -d *"],
            ["netsh", "interface", "ip", "delete", "arpcache"],
        ]:
            try:
                result = subprocess_run(cmd, timeout=10)
                if result.returncode == 0:
                    return True, "ARP cache flushed."
            except Exception:
                continue
        return False, "Failed to flush ARP cache. Run as Administrator."

    # Linux / macOS
    try:
        if IS_LINUX:
            subprocess_run(["ip", "-s", "-s", "neigh", "flush", "all"], timeout=10)
        else:
            subprocess_run(["arp", "-a", "-d"], timeout=10)
        return True, "ARP cache flushed."
    except Exception:
        return False, "Failed to flush ARP cache. Run as root."


# ── Default gateway ────────────────────────────────────────────────

def get_default_gateway(interface_ip: str) -> str:
    """Detect the default gateway IP for the given interface."""
    gw = _windows_gateway(interface_ip)
    if gw:
        return gw
    gw = _unix_gateway(interface_ip)
    if gw:
        return gw
    parts = interface_ip.split(".")
    return f"{parts[0]}.{parts[1]}.{parts[2]}.1"


def _windows_gateway(interface_ip: str) -> Optional[str]:
    for method in [_gateway_powershell, _gateway_ipconfig, _gateway_route_print]:
        try:
            gw = method(interface_ip)
            if gw:
                return gw
        except Exception:
            continue
    return None


def _gateway_powershell(interface_ip: str) -> Optional[str]:
    result = subprocess_run(
        [
            "powershell",
            "-Command",
            "Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Select-Object -ExpandProperty NextHop",
        ],
        timeout=5,
    )
    if result.returncode != 0:
        return None
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if line and _same_subnet(interface_ip, line):
            return line
    lines = result.stdout.strip().split("\n")
    if lines and lines[0].strip():
        return lines[0].strip()
    return None


def _gateway_ipconfig(interface_ip: str) -> Optional[str]:
    result = subprocess_run(["ipconfig"], timeout=5)
    if result.returncode != 0:
        return None
    found_ip = False
    for line in result.stdout.split("\n"):
        if interface_ip in line:
            found_ip = True
        if found_ip and ("gateway" in line.lower() or "gerbang" in line.lower()):
            m = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
            if m:
                return m.group(1)
    return None


def _gateway_route_print(interface_ip: str) -> Optional[str]:
    result = subprocess_run(["route", "print", "0.0.0.0"], timeout=5)
    if result.returncode != 0:
        return None
    for line in result.stdout.split("\n"):
        if line.strip().startswith("0.0.0.0"):
            parts = line.split()
            if len(parts) >= 3:
                gw = parts[2].strip()
                if gw and _same_subnet(interface_ip, gw):
                    return gw
    return None


def _unix_gateway(interface_ip: str) -> Optional[str]:
    """Read gateway from 'ip route' (Linux) or 'route -n get default' (macOS)."""
    try:
        if IS_LINUX:
            result = subprocess_run(["ip", "route", "show", "default"], timeout=5)
            if result.returncode == 0:
                m = re.search(r"via\s+(\d+\.\d+\.\d+\.\d+)", result.stdout)
                if m:
                    return m.group(1)
        else:
            result = subprocess_run(
                ["route", "-n", "get", "default"], timeout=5
            )
            if result.returncode == 0:
                m = re.search(r"gateway:\s+(\d+\.\d+\.\d+\.\d+)", result.stdout)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return None


# ── Subnet helper ──────────────────────────────────────────────────

def _same_subnet(ip1: str, ip2: str, mask: str = "255.255.255.0") -> bool:
    try:
        ip1_int = struct_unpack_ip(ip1)
        ip2_int = struct_unpack_ip(ip2)
        mask_int = struct_unpack_ip(mask)
        return (ip1_int & mask_int) == (ip2_int & mask_int)
    except Exception:
        return False


def struct_unpack_ip(ip: str) -> int:
    import socket
    import struct
    return struct.unpack("!I", socket.inet_aton(ip))[0]


# ── IP forwarding ──────────────────────────────────────────────────

def read_ip_forwarding_state() -> Optional[int]:
    """Return current IP forwarding state (0=off, 1=on) or None."""
    if IS_WINDOWS:
        return _windows_ip_forwarding()
    if IS_LINUX:
        return _linux_ip_forwarding()
    if IS_MACOS:
        return _macos_ip_forwarding()
    return None


def _windows_ip_forwarding() -> Optional[int]:
    try:
        result = subprocess_run(
            [
                "reg", "query",
                "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters",
                "/v", "IPEnableRouter",
            ],
            timeout=10,
        )
        if result.returncode != 0:
            return None
        m = re.search(r"IPEnableRouter\s+REG_DWORD\s+0x([0-9a-fA-F]+)", result.stdout)
        return int(m.group(1), 16) if m else None
    except Exception:
        return None


def _linux_ip_forwarding() -> Optional[int]:
    try:
        with open("/proc/sys/net/ipv4/ip_forward") as f:
            return int(f.read().strip())
    except Exception:
        return None


def _macos_ip_forwarding() -> Optional[int]:
    try:
        result = subprocess_run(
            ["sysctl", "-n", "net.inet.ip.forwarding"], timeout=5
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except Exception:
        pass
    return None


def enable_ip_forwarding() -> tuple[bool, str]:
    """Enable IP forwarding. Returns (success, message)."""
    if IS_WINDOWS:
        return _enable_windows_ip_forwarding()
    if IS_LINUX:
        return _enable_linux_ip_forwarding()
    if IS_MACOS:
        return _enable_macos_ip_forwarding()
    return False, "IP forwarding not supported on this platform."


def _enable_windows_ip_forwarding() -> tuple[bool, str]:
    try:
        subprocess_run(
            [
                "powershell", "-Command",
                "Set-NetIPInterface -Forwarding Enabled -ErrorAction SilentlyContinue",
            ],
            timeout=10,
        )
        result = subprocess_run(
            [
                "reg", "add",
                "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters",
                "/v", "IPEnableRouter", "/t", "REG_DWORD", "/d", "1", "/f",
            ],
            timeout=10,
        )
        if result.returncode == 0:
            return True, "IP Forwarding enabled"
        return False, "Failed to enable IP Forwarding"
    except Exception as e:
        return False, f"Failed to enable IP forwarding: {e}"


def _enable_linux_ip_forwarding() -> tuple[bool, str]:
    try:
        with open("/proc/sys/net/ipv4/ip_forward", "w") as f:
            f.write("1")
        return True, "IP Forwarding enabled"
    except Exception as e:
        return False, f"Failed to enable IP forwarding: {e}"


def _enable_macos_ip_forwarding() -> tuple[bool, str]:
    try:
        subprocess_run(["sysctl", "-w", "net.inet.ip.forwarding=1"], timeout=5)
        return True, "IP Forwarding enabled"
    except Exception as e:
        return False, f"Failed to enable IP forwarding: {e}"


def disable_ip_forwarding() -> tuple[bool, str]:
    """Disable IP forwarding. Returns (success, message)."""
    if IS_WINDOWS:
        return _disable_windows_ip_forwarding()
    if IS_LINUX:
        return _disable_linux_ip_forwarding()
    if IS_MACOS:
        return _disable_macos_ip_forwarding()
    return False, "IP forwarding not supported on this platform."


def _disable_windows_ip_forwarding() -> tuple[bool, str]:
    try:
        subprocess_run(
            [
                "powershell", "-Command",
                "Set-NetIPInterface -Forwarding Disabled -ErrorAction SilentlyContinue",
            ],
            timeout=10,
        )
        return True, "IP Forwarding disabled"
    except Exception:
        return False, "Failed to disable IP Forwarding"


def _disable_linux_ip_forwarding() -> tuple[bool, str]:
    try:
        with open("/proc/sys/net/ipv4/ip_forward", "w") as f:
            f.write("0")
        return True, "IP Forwarding disabled"
    except Exception:
        return False, "Failed to disable IP Forwarding"


def _disable_macos_ip_forwarding() -> tuple[bool, str]:
    try:
        subprocess_run(["sysctl", "-w", "net.inet.ip.forwarding=0"], timeout=5)
        return True, "IP Forwarding disabled"
    except Exception:
        return False, "Failed to disable IP Forwarding"
