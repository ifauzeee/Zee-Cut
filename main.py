"""
Zee-Cut - Main Entry Point
Advanced WiFi Network Device Controller.

DISCLAIMER: This tool is intended for use ONLY on networks you own and manage.
Unauthorized use on networks you don't own is illegal.
"""

import ctypes
import sys

from core.admin import is_admin, run_as_admin


def main():
    """Application entry point."""
    # Auto-elevate to admin if not already
    if not is_admin():
        response = ctypes.windll.user32.MessageBoxW(
            0,
            "Zee-Cut membutuhkan hak Administrator untuk berfungsi.\n\n"
            "Klik 'Yes' untuk menjalankan sebagai Administrator.\n"
            "Klik 'No' untuk menjalankan tanpa hak admin (fungsi terbatas).",
            "Zee-Cut - Administrator Required",
            0x00000034  # MB_YESNO | MB_ICONQUESTION
        )
        if response == 6:  # IDYES
            if run_as_admin(__file__):
                sys.exit(0)
            return

    from gui import WiFiThrottlerApp
    app = WiFiThrottlerApp()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        # Graceful exit when user stops from terminal (Ctrl+C)
        try:
            app.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    main()
