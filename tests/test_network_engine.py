import unittest
from threading import Event
from unittest.mock import patch

from core.models import NetworkDevice, NetworkInterface
from core.network import NetworkEngine


class NetworkEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = NetworkEngine()

    def tearDown(self):
        try:
            self.engine._hostname_executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    def test_parse_arp_table_entries_filters_invalid_records(self):
        arp_output = """
Interface: 192.168.1.10 --- 0x7
  Internet Address      Physical Address      Type
  192.168.1.1           aa-bb-cc-dd-ee-01     dynamic
  192.168.1.55          aa-bb-cc-dd-ee-55     static
  192.168.1.255         ff-ff-ff-ff-ff-ff     static
  10.0.0.1              aa-bb-cc-dd-ee-02     dynamic
  192.168.1.77          aa-bb-cc-dd-ee-77     invalid
"""
        entries = self.engine._parse_arp_table_entries(arp_output, "192.168.1.")

        self.assertEqual(
            entries,
            [
                ("192.168.1.1", "aa:bb:cc:dd:ee:01"),
                ("192.168.1.55", "aa:bb:cc:dd:ee:55"),
            ],
        )

    def test_is_same_subnet_honors_mask(self):
        self.assertTrue(self.engine._is_same_subnet("192.168.1.10", "192.168.1.254"))
        self.assertFalse(self.engine._is_same_subnet("192.168.1.10", "192.168.2.1"))
        self.assertTrue(
            self.engine._is_same_subnet("10.0.0.10", "10.0.1.20", "255.255.254.0")
        )

    def test_get_network_range_uses_interface_subnet(self):
        self.engine.interface = NetworkInterface(
            name="Wi-Fi",
            display_name="Wi-Fi",
            ip="192.168.50.23",
            mac="aa:bb:cc:dd:ee:ff",
            subnet_mask="255.255.255.0",
        )
        self.assertEqual(self.engine._get_network_range(), "192.168.50.0/24")

    def test_restore_device_resets_throttle_flags(self):
        ip = "192.168.1.25"
        self.engine.devices[ip] = NetworkDevice(
            ip=ip,
            mac="aa:bb:cc:dd:ee:25",
            is_self=True,
            is_throttled=True,
            throttle_level=0,
        )

        self.engine.restore_device(ip)
        restored = self.engine.devices[ip]
        self.assertFalse(restored.is_throttled)
        self.assertEqual(restored.throttle_level, 100)

    def test_restore_all_calls_restore_on_throttled_devices_only(self):
        self.engine.devices = {
            "192.168.1.11": NetworkDevice(
                ip="192.168.1.11",
                mac="aa:bb:cc:dd:ee:11",
                is_throttled=True,
            ),
            "192.168.1.12": NetworkDevice(
                ip="192.168.1.12",
                mac="aa:bb:cc:dd:ee:12",
                is_throttled=False,
            ),
        }

        with patch.object(self.engine, "restore_device") as restore_device:
            self.engine.restore_all()
            restore_device.assert_called_once_with("192.168.1.11")

    def test_get_diagnostics_snapshot_serializes_interface(self):
        self.engine.interface = NetworkInterface(
            name="Wi-Fi",
            display_name="Wi-Fi",
            ip="192.168.1.10",
            mac="aa:bb:cc:dd:ee:10",
            scapy_iface=object(),
        )
        self.engine.devices["192.168.1.11"] = NetworkDevice(
            ip="192.168.1.11",
            mac="aa:bb:cc:dd:ee:11",
            is_throttled=True,
        )
        snapshot = self.engine.get_diagnostics_snapshot(log_tail_lines=1)

        self.assertIn("interface", snapshot)
        self.assertIsInstance(snapshot["interface"]["scapy_iface"], str)
        self.assertEqual(snapshot["throttled_count"], 1)

    def test_scan_network_updates_last_scan_summary(self):
        self.engine.interface = NetworkInterface(
            name="Wi-Fi",
            display_name="Wi-Fi",
            ip="192.168.1.10",
            mac="aa:bb:cc:dd:ee:10",
            gateway_ip="192.168.1.1",
            gateway_mac="aa:bb:cc:dd:ee:01",
        )
        scan_done = Event()

        with patch.object(self.engine, "_scan_arp_table"), patch.object(
            self.engine, "_scan_scapy_arp"
        ), patch.object(self.engine, "_resolve_gateway_mac"), patch.object(
            self.engine, "_ping_sweep"
        ), patch.object(self.engine, "flush_arp_cache", return_value=(True, "ok")):
            self.engine.scan_network(callback=scan_done.set, fast_mode=True)
            self.assertTrue(scan_done.wait(timeout=5))

        summary = self.engine.get_last_scan_summary()
        self.assertIn("scan_id", summary)
        self.assertIn("elapsed_s", summary)
        self.assertIsInstance(summary["device_count"], int)


if __name__ == "__main__":
    unittest.main()
