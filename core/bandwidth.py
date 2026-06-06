"""
Bandwidth monitoring per device using scapy sniff.
Tracks ↑/↓ KB/s for each MAC address on the network.
"""

import logging
import threading
from collections import defaultdict
from typing import Optional

logger = logging.getLogger("zee_cut.bandwidth")

SAMPLE_INTERVAL = 2.0


class BandwidthMonitor:
    """Captures traffic and tracks per-MAC throughput."""

    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._sniff_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._bytes_up: dict[str, int] = defaultdict(int)
        self._bytes_down: dict[str, int] = defaultdict(int)
        self._up_rate: dict[str, float] = {}
        self._down_rate: dict[str, float] = {}
        self._iface = None
        self._local_mac = ""
        self._subnet_prefix = ""

        self._last_sample_time = 0.0
        self._prev_bytes_up: dict[str, int] = defaultdict(int)
        self._prev_bytes_down: dict[str, int] = defaultdict(int)

    @property
    def is_running(self) -> bool:
        return self._running

    def set_interface(self, iface, local_mac: str, subnet_prefix: str):
        with self._lock:
            self._iface = iface
            self._local_mac = local_mac
            self._subnet_prefix = subnet_prefix

    def start(self):
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._bytes_up.clear()
        self._bytes_down.clear()
        self._up_rate.clear()
        self._down_rate.clear()
        self._prev_bytes_up.clear()
        self._prev_bytes_down.clear()

        self._sniff_thread = threading.Thread(target=self._sniff_loop, daemon=True, name="bw-sniff")
        self._sniff_thread.start()

        self._thread = threading.Thread(target=self._calculate_loop, daemon=True, name="bw-calc")
        self._thread.start()

        logger.info("Bandwidth monitoring started")

    def stop(self):
        self._running = False
        self._stop_event.set()
        self._sniff_thread = None
        self._thread = None
        logger.info("Bandwidth monitoring stopped")

    def get_rates(self, mac: str = "") -> dict:
        """Get bandwidth rates. Returns {mac: {'up_kbps': x, 'down_kbps': y}}.

        If mac is given, returns only that device's rates.
        If mac is empty, returns all rates.
        """
        with self._lock:
            if mac:
                mac_key = mac.lower().replace("-", ":")
                return {
                    "up_kbps": self._up_rate.get(mac_key, 0.0),
                    "down_kbps": self._down_rate.get(mac_key, 0.0),
                }

            result = {}
            all_macs = set(self._up_rate.keys()) | set(self._down_rate.keys())
            for m in all_macs:
                result[m] = {
                    "up_kbps": self._up_rate.get(m, 0.0),
                    "down_kbps": self._down_rate.get(m, 0.0),
                }
            return result

    def _sniff_loop(self):
        """Continuously sniff packets and track byte counts per MAC."""
        try:
            from scapy.all import sniff
        except ImportError:
            logger.warning("Scapy not available for bandwidth monitoring")
            self._running = False
            return

        while self._running and not self._stop_event.is_set():
            try:
                with self._lock:
                    iface = self._iface
                if not iface:
                    self._stop_event.wait(1)
                    continue

                sniff(
                    iface=iface,
                    prn=self._packet_handler,
                    store=0,
                    timeout=2,
                    count=200,  # Limit packets per sniff batch to control CPU
                )
            except Exception as e:
                logger.debug("Sniff error: %s", e)
                self._stop_event.wait(1)

    def _packet_handler(self, pkt):
        """Process each sniffed packet - track bytes per MAC."""
        try:
            if not hasattr(pkt, 'len') and hasattr(pkt, 'wirelen'):
                pkt_len = pkt.wirelen
            elif hasattr(pkt, 'len'):
                pkt_len = pkt.len
            else:
                pkt_len = len(pkt)

            src_mac = pkt.src.lower() if hasattr(pkt, 'src') else ""
            dst_mac = pkt.dst.lower() if hasattr(pkt, 'dst') else ""

            if not src_mac or not dst_mac:
                return

            with self._lock:
                # Skip broadcast/multicast as dst for down count
                if not dst_mac.startswith("ff:ff:ff") and not dst_mac.startswith("01:00:5e"):
                    self._bytes_down[dst_mac] += pkt_len
                if not src_mac.startswith("ff:ff:ff") and not src_mac.startswith("01:00:5e"):
                    self._bytes_up[src_mac] += pkt_len
        except Exception:
            pass

    def _calculate_loop(self):
        """Periodically calculate KB/s rates from byte counters."""
        while self._running and not self._stop_event.is_set():
            self._stop_event.wait(SAMPLE_INTERVAL)
            if not self._running:
                break

            try:
                with self._lock:
                    current_up = dict(self._bytes_up)
                    current_down = dict(self._bytes_down)

                    all_macs = set(current_up.keys()) | set(current_down.keys())
                    all_macs |= set(self._prev_bytes_up.keys())
                    all_macs |= set(self._prev_bytes_down.keys())

                    for mac in all_macs:
                        up_delta = current_up.get(mac, 0) - self._prev_bytes_up.get(mac, 0)
                        down_delta = current_down.get(mac, 0) - self._prev_bytes_down.get(mac, 0)

                        self._up_rate[mac] = max(0.0, up_delta / 1024.0 / SAMPLE_INTERVAL)
                        self._down_rate[mac] = max(0.0, down_delta / 1024.0 / SAMPLE_INTERVAL)

                    self._prev_bytes_up = current_up
                    self._prev_bytes_down = current_down
            except Exception as e:
                logger.debug("Rate calculation error: %s", e)
