"""
Core network models.
"""

from dataclasses import dataclass


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
