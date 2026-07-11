import sys
import unittest
from unittest.mock import MagicMock


class ThemeTests(unittest.TestCase):
    def test_all_themes_have_same_keys(self):
        from ui.theme import THEMES

        key_sets = [set(theme.keys()) for theme in THEMES.values()]
        self.assertEqual(len({frozenset(keys) for keys in key_sets}), 1)

    def test_colors_match_amoled_theme(self):
        from ui.theme import COLORS, THEMES

        self.assertEqual(COLORS, THEMES["amoled"])

    def test_required_theme_keys_present(self):
        from ui.theme import THEMES

        required = {"bg_dark", "accent_primary", "text_primary", "border"}
        for name, theme in THEMES.items():
            self.assertTrue(required.issubset(theme.keys()), name)

    def test_fonts_have_expected_keys(self):
        from ui.theme import FONTS

        expected = {"title", "body", "small", "mono"}
        self.assertTrue(expected.issubset(FONTS.keys()))


class UiImportTests(unittest.TestCase):
    """Ensure UI modules import cleanly — module-level code must not crash.

    customtkinter is mocked for these tests only so no display is required.
    """

    def setUp(self):
        self._had_ctk = "customtkinter" in sys.modules
        if not self._had_ctk:
            sys.modules["customtkinter"] = MagicMock()
        for mod in list(sys.modules):
            if mod == "ui" or mod.startswith("ui."):
                del sys.modules[mod]

    def tearDown(self):
        if not self._had_ctk:
            sys.modules.pop("customtkinter", None)
        for mod in list(sys.modules):
            if mod == "ui" or mod.startswith("ui."):
                del sys.modules[mod]

    def test_import_ui_modules(self):
        import ui.app  # noqa: F401
        import ui.device_list  # noqa: F401
        import ui.dialogs  # noqa: F401
        import ui.header  # noqa: F401
        import ui.toolbar  # noqa: F401


if __name__ == "__main__":
    unittest.main()
