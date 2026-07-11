"""
Bandwidth shaper (experimental).

Provides per-destination bandwidth limiting. The primary throttling mechanism
remains ARP spoofing; this shaper is an OPTIONAL, opt-in layer for platforms
that support traffic control:

  - Linux  : uses `tc` (HTB + u32 filter by destination IP)
  - Windows: not yet supported (would require WFP native code) — no-op
  - macOS  : not yet supported — no-op

All operations are best-effort and never raise. Enable via
`NetworkEngine.bandwidth_shaping_enabled = True` (default False).
"""

from __future__ import annotations

import logging
from typing import Optional

from core.platform import IS_LINUX, subprocess_run

logger = logging.getLogger("zee_cut.shaper")

# Handle/namespace ids for the tc hierarchy (fixed, single-app assumption).
_QDISC_PARENT = "1:"
_CLASS_ID = "1:10"
_RATE_DEFAULT = "1mbit"


def _linux_shape(ip: str, limit_kbps: int, iface: Optional[str]) -> bool:
    """Limit egress traffic to `ip` on `iface` using tc. Returns success."""
    dev = iface or _default_linux_iface()
    if not dev:
        logger.warning("Shaper: could not determine interface for tc")
        return False

    rate = f"{max(1, limit_kbps)}kbit"
    try:
        subprocess_run(
            ["tc", "qdisc", "add", "dev", dev, "root", "handle", "1:", "htb"],
            timeout=10,
        )
        subprocess_run(
            [
                "tc", "class", "add", "dev", dev, "parent", _QDISC_PARENT,
                "classid", _CLASS_ID, "htb", "rate", rate, "ceil", rate,
            ],
            timeout=10,
        )
        subprocess_run(
            [
                "tc", "filter", "add", "dev", dev, "parent", _QDISC_PARENT,
                "protocol", "ip", "u32", "match", "ip", "dst", ip,
                "flowid", _CLASS_ID,
            ],
            timeout=10,
        )
        logger.info("Shaper: limited %s to %s on %s", ip, rate, dev)
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("Shaper: failed to shape %s: %s", ip, e)
        return False


def _linux_unshape(ip: str, iface: Optional[str]) -> bool:
    """Remove the tc qdisc (clears all shaping on the interface)."""
    dev = iface or _default_linux_iface()
    if not dev:
        return False
    try:
        subprocess_run(["tc", "qdisc", "del", "dev", dev, "root"], timeout=10)
        logger.info("Shaper: cleared tc qdisc on %s", dev)
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("Shaper: failed to unshape %s: %s", dev, e)
        return False


def _default_linux_iface() -> Optional[str]:
    try:
        result = subprocess_run(
            ["ip", "route", "show", "default"], timeout=5
        )
        for line in result.stdout.split("\n"):
            if "dev" in line:
                return line.split("dev")[1].split()[0]
    except Exception:
        pass
    return None


def shape_device(ip: str, limit_kbps: int, iface: Optional[str] = None) -> bool:
    """Limit bandwidth for `ip`. Returns True on success (Linux only)."""
    if IS_LINUX:
        return _linux_shape(ip, limit_kbps, iface)
    logger.debug("Shaper: not supported on this platform for %s", ip)
    return False


def unshape_device(ip: str, iface: Optional[str] = None) -> bool:
    """Remove bandwidth limit for `ip`."""
    if IS_LINUX:
        return _linux_unshape(ip, iface)
    return False
