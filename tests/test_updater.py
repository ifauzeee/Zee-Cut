import unittest
from unittest.mock import MagicMock, patch

from core.updater import check_for_update, is_newer


class VersionCompareTests(unittest.TestCase):
    def test_is_newer_true(self):
        self.assertTrue(is_newer("v0.5.0", "0.4.0"))
        self.assertTrue(is_newer("1.0.0", "0.9.9"))
        self.assertTrue(is_newer("0.4.1", "0.4.0"))

    def test_is_newer_false(self):
        self.assertFalse(is_newer("0.4.0", "0.5.0"))
        self.assertFalse(is_newer("0.4.0", "0.4.0"))

    def test_is_newer_handles_prefixes(self):
        self.assertTrue(is_newer("v0.5.0", "v0.4.0"))
        self.assertTrue(is_newer("0.5", "0.4.0"))


class CheckForUpdateTests(unittest.TestCase):
    def _fake_response(self, payload: dict) -> MagicMock:
        resp = MagicMock()
        resp.read.return_value = str.encode(__import__("json").dumps(payload))
        return resp

    def _patch_response(self, mock_open, payload):
        resp = self._fake_response(payload)
        mock_open.return_value.__enter__.return_value = resp

    @patch("core.updater.urllib.request.OpenerDirector.open")
    def test_update_available(self, mock_open):
        self._patch_response(
            mock_open,
            {"tag_name": "v0.5.0", "html_url": "https://example.com/0.5.0"},
        )
        result = check_for_update("0.4.0")
        self.assertTrue(result["available"])
        self.assertEqual(result["latest"], "v0.5.0")
        self.assertEqual(result["url"], "https://example.com/0.5.0")

    @patch("core.updater.urllib.request.OpenerDirector.open")
    def test_no_update(self, mock_open):
        self._patch_response(
            mock_open,
            {"tag_name": "v0.4.0", "html_url": "https://example.com/0.4.0"},
        )
        result = check_for_update("0.4.0")
        self.assertFalse(result["available"])

    @patch("core.updater.urllib.request.OpenerDirector.open")
    def test_network_error_is_safe(self, mock_open):
        mock_open.side_effect = OSError("offline")
        result = check_for_update("0.4.0")
        self.assertFalse(result["available"])
        self.assertIsNotNone(result["error"])


if __name__ == "__main__":
    unittest.main()
