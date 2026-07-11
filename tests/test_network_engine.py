import unittest
from threading import Event
from unittest.mock import MagicMock, call, patch

from core.models import NetworkDevice, NetworkInterface
from core.network import NetworkEngine

try:
    import customtkinter  # noqa: F401

    HAS_UI = True
except ImportError:
    HAS_UI = False


def _make_interface(
    ip="192.168.1.10",
    mac="aa:bb:cc:dd:ee:10",
    gateway_ip="192.168.1.1",
    gateway_mac="aa:bb:cc:dd:ee:01",
):
    return NetworkInterface(
        name="Wi-Fi",
        display_name="Wi-Fi",
        ip=ip,
        mac=mac,
        gateway_ip=gateway_ip,
        gateway_mac=gateway_mac,
        scapy_iface=MagicMock(),
    )


def _make_device(
    ip="192.168.1.55",
    mac="aa:bb:cc:dd:ee:55",
    is_gateway=False,
    is_self=False,
    is_throttled=False,
    throttle_level=100,
):
    return NetworkDevice(
        ip=ip,
        mac=mac,
        is_gateway=is_gateway,
        is_self=is_self,
        is_throttled=is_throttled,
        throttle_level=throttle_level,
    )


class NetworkEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = NetworkEngine()

    def tearDown(self):
        try:
            self.engine._hostname_executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    # ── Existing tests ───────────────────────────────────────────────

    def test_platform_parse_arp_table_windows(self):
        """Windows arp -a parsing logic."""
        from core.platform import _parse_windows_arp_table
        with patch("core.platform.subprocess_run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = (
                "\n"
                "Interface: 192.168.1.10 --- 0x7\n"
                "  Internet Address      Physical Address      Type\n"
                "  192.168.1.1           aa-bb-cc-dd-ee-01     dynamic\n"
                "  192.168.1.55          aa-bb-cc-dd-ee-55     static\n"
                "  192.168.1.255         ff-ff-ff-ff-ff-ff     static\n"
                "  10.0.0.1              aa-bb-cc-dd-ee-02     dynamic\n"
                "  192.168.1.77          aa-bb-cc-dd-ee-77     invalid\n"
            )
            entries = _parse_windows_arp_table("192.168.1.")
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
        self.engine.interface = _make_interface()
        self.engine.interface.scapy_iface = object()
        self.engine.devices["192.168.1.11"] = NetworkDevice(
            ip="192.168.1.11",
            mac="aa:bb:cc:dd:ee:11",
            is_throttled=True,
        )
        snapshot = self.engine.get_diagnostics_snapshot(log_tail_lines=1)
        self.assertIn("interface", snapshot)
        self.assertIsInstance(snapshot["interface"]["scapy_iface"], str)
        self.assertEqual(snapshot["throttled_count"], 1)
        self.assertIn("ap_isolation_detected", snapshot)

    def test_scan_network_updates_last_scan_summary(self):
        self.engine.interface = _make_interface()
        scan_done = Event()
        with patch.object(self.engine, "_scan_arp_table"), patch.object(
            self.engine, "_scan_scapy_arp"
        ), patch.object(self.engine, "_resolve_gateway_mac"), patch.object(
            self.engine, "_ping_sweep"
        ), patch.object(
            self.engine, "flush_arp_cache", return_value=(True, "ok")
        ), patch.object(
            self.engine, "_detect_ap_isolation"
        ):
            self.engine.scan_network(callback=scan_done.set, fast_mode=True)
            self.assertTrue(scan_done.wait(timeout=5))
        summary = self.engine.get_last_scan_summary()
        self.assertIn("scan_id", summary)
        self.assertIn("elapsed_s", summary)
        self.assertIsInstance(summary["device_count"], int)

    # ── throttle_device tests ────────────────────────────────────────

    def test_throttle_device_skips_gateway(self):
        self.engine.interface = _make_interface()
        gw_ip = "192.168.1.1"
        self.engine.devices[gw_ip] = _make_device(ip=gw_ip, is_gateway=True)
        with patch.object(self.engine, "_send_arp_reply") as send:
            self.engine.throttle_device(gw_ip, level=50)
            self.assertNotIn(gw_ip, self.engine._throttle_threads)
            send.assert_not_called()

    def test_throttle_device_skips_self(self):
        self.engine.interface = _make_interface()
        my_ip = "192.168.1.10"
        self.engine.devices[my_ip] = _make_device(ip=my_ip, is_self=True)
        with patch.object(self.engine, "_send_arp_reply") as send:
            self.engine.throttle_device(my_ip, level=50)
            self.assertNotIn(my_ip, self.engine._throttle_threads)
            send.assert_not_called()

    def test_throttle_device_requires_gateway_mac(self):
        self.engine.interface = _make_interface(gateway_mac="")
        ip = "192.168.1.55"
        self.engine.devices[ip] = _make_device(ip=ip)
        with patch.object(self.engine, "_notify_status") as notify:
            self.engine.throttle_device(ip, level=50)
            notify.assert_any_call("ERROR: Gateway MAC not found. Scan first!")

    def test_throttle_device_requires_scapy(self):
        self.engine.interface = _make_interface()
        ip = "192.168.1.55"
        self.engine.devices[ip] = _make_device(ip=ip)
        with patch("core.network.SCAPY_AVAILABLE", False):
            with patch.object(self.engine, "_notify_status") as notify:
                self.engine.throttle_device(ip, level=50)
                notify.assert_any_call("ERROR: Scapy not available!")

    def test_throttle_device_level_100_is_noop(self):
        ip = "192.168.1.55"
        self.engine.devices[ip] = _make_device(ip=ip)
        self.engine.throttle_device(ip, level=100)
        self.assertNotIn(ip, self.engine._throttle_threads)

    def test_throttle_device_sets_flags_and_starts_thread(self):
        self.engine.interface = _make_interface()
        ip = "192.168.1.55"
        self.engine.devices[ip] = _make_device(ip=ip, throttle_level=100)

        with patch.object(self.engine, "_send_arp_reply"):
            self.engine.throttle_device(ip, level=50)
        self.assertIn(ip, self.engine._throttle_threads)
        self.assertIn(ip, self.engine._throttle_stop_events)
        dev = self.engine.devices[ip]
        self.assertTrue(dev.is_throttled)
        self.assertEqual(dev.throttle_level, 50)
        self.engine.restore_device(ip)

    def test_throttle_device_spoof_loop_calls_send_arp_reply(self):
        self.engine.interface = _make_interface()
        ip = "192.168.1.55"
        target_mac = "aa:bb:cc:dd:ee:55"
        self.engine.devices[ip] = _make_device(ip=ip, mac=target_mac)

        with patch.object(self.engine, "_send_arp_reply") as send:
            with patch.object(self.engine, "_notify_status"):
                self.engine.throttle_device(ip, level=50)
                stop = self.engine._throttle_stop_events[ip]
                stop.wait(0.3)
                self.engine.restore_device(ip)
        self.assertGreater(send.call_count, 0)

    def test_restore_device_stops_throttle_thread(self):
        self.engine.interface = _make_interface()
        ip = "192.168.1.55"
        self.engine.devices[ip] = _make_device(ip=ip)

        with patch.object(self.engine, "_send_arp_reply"):
            with patch.object(self.engine, "_notify_status"):
                self.engine.throttle_device(ip, level=50)
                thread = self.engine._throttle_threads.get(ip)
                self.assertIsNotNone(thread)
                self.assertTrue(thread.is_alive())
                self.engine.restore_device(ip)
                thread.join(timeout=3)
                self.assertFalse(thread.is_alive())
                self.assertNotIn(ip, self.engine._throttle_threads)
                self.assertNotIn(ip, self.engine._throttle_stop_events)

    def test_throttle_device_unknown_ip_does_nothing(self):
        self.engine.interface = _make_interface()
        self.engine.throttle_device("192.168.1.99", level=50)
        self.assertNotIn("192.168.1.99", self.engine._throttle_threads)

    def test_restore_all_parallel_calls_all_throttled(self):
        ips = [f"192.168.1.{i}" for i in range(10, 15)]
        for ip in ips:
            self.engine.devices[ip] = _make_device(ip=ip, is_throttled=True)
        with patch.object(self.engine, "restore_device") as restore:
            self.engine.restore_all()
            expected_calls = [call(ip) for ip in ips]
            restore.assert_has_calls(expected_calls, any_order=True)
            self.assertEqual(restore.call_count, len(ips))

    # ── AP isolation ─────────────────────────────────────────────────

    def test_ap_isolation_detected_reset_on_scan(self):
        self.engine._ap_isolation_detected = True
        self.engine.interface = _make_interface()
        with patch.object(self.engine, "_scan_arp_table"), patch.object(
            self.engine, "_scan_scapy_arp"
        ), patch.object(self.engine, "_resolve_gateway_mac"), patch.object(
            self.engine, "_ping_sweep"
        ), patch.object(
            self.engine, "flush_arp_cache", return_value=(True, "ok")
        ), patch.object(
            self.engine, "_detect_ap_isolation"
        ):
            self.engine.scan_network(callback=lambda: None, fast_mode=True)
        self.assertFalse(self.engine._ap_isolation_detected)

    # ── GUI callback helpers ─────────────────────────────────────────

    @unittest.skipIf(not HAS_UI, "customtkinter not available")
    def test_lag_percent_to_level_conversion(self):
        from ui.app import WiFiThrottlerApp
        app = WiFiThrottlerApp
        self.assertEqual(app._lag_percent_to_level(None, 0), 100)
        self.assertEqual(app._lag_percent_to_level(None, 50), 50)
        self.assertEqual(app._lag_percent_to_level(None, 100), 0)
        self.assertEqual(app._lag_percent_to_level(None, -10), 100)
        self.assertEqual(app._lag_percent_to_level(None, 150), 0)

    @unittest.skipIf(not HAS_UI, "customtkinter not available")
    def test_is_target_device_filters_self_and_gateway(self):
        from ui.app import WiFiThrottlerApp

        target = _make_device(ip="192.168.1.55")
        self_dev = _make_device(ip="192.168.1.10", is_self=True)
        gw_dev = _make_device(ip="192.168.1.1", is_gateway=True)

        app = WiFiThrottlerApp.__new__(WiFiThrottlerApp)
        app.engine = self.engine
        app.custom_protected_ips = set()

        self.assertTrue(app._is_target_device(target))
        self.assertFalse(app._is_target_device(self_dev))
        self.assertFalse(app._is_target_device(gw_dev))

    @unittest.skipIf(not HAS_UI, "customtkinter not available")
    def test_is_protected_device_includes_custom_and_system(self):
        from ui.app import WiFiThrottlerApp

        app = WiFiThrottlerApp.__new__(WiFiThrottlerApp)
        app.custom_protected_ips = {"192.168.1.99"}

        self_dev = _make_device(ip="192.168.1.10", is_self=True)
        gw_dev = _make_device(ip="192.168.1.1", is_gateway=True)
        custom_dev = _make_device(ip="192.168.1.99")
        normal_dev = _make_device(ip="192.168.1.55")

        self.assertTrue(app._is_protected_device(self_dev))
        self.assertTrue(app._is_protected_device(gw_dev))
        self.assertTrue(app._is_protected_device(custom_dev))
        self.assertFalse(app._is_protected_device(normal_dev))


if __name__ == "__main__":
    unittest.main()
