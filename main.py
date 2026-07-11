"""
Zee-Cut - Main Entry Point
Advanced WiFi Network Device Controller.

DISCLAIMER: This tool is intended for use ONLY on networks you own and manage.
Unauthorized use on networks you don't own is illegal.
"""

import sys

from core.admin import is_admin, run_as_admin
from core.platform import IS_WINDOWS


def _confirm_elevate() -> bool:
    """Show platform-appropriate elevation prompt and return True if re-launching."""
    if IS_WINDOWS:
        import ctypes
        response = ctypes.windll.user32.MessageBoxW(
            0,
            "Zee-Cut membutuhkan hak Administrator untuk berfungsi.\n\n"
            "Klik 'Yes' untuk menjalankan sebagai Administrator.\n"
            "Klik 'No' untuk menjalankan tanpa hak admin (fungsi terbatas).",
            "Zee-Cut - Administrator Required",
            0x00000034
        )
        return bool(response == 6)
    # Linux/macOS: no GUI prompt — let user decide from terminal.
    print(
        "Zee-Cut requires root privileges for full functionality.\n"
        "Re-run with: sudo python -m main",
        file=sys.stderr,
    )
    return True  # always attempt sudo re-launch


def main():
    """Application entry point."""
    if not is_admin():
        if _confirm_elevate():
            if run_as_admin(__file__):
                sys.exit(0)

    from ui.app import WiFiThrottlerApp
    app = WiFiThrottlerApp()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        try:
            app.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    main()
