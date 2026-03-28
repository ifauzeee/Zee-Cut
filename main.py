"""
Zee-Cut - Main Entry Point
Advanced WiFi Network Device Controller.

DISCLAIMER: This tool is intended for use ONLY on networks you own and manage.
Unauthorized use on networks you don't own is illegal.
"""

import sys
import os
import ctypes


def is_admin():
    """Check if running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_as_admin():
    """Relaunch the application with administrator privileges."""
    try:
        if getattr(sys, 'frozen', False):
            script = sys.executable
            params = ""
        else:
            script = sys.executable
            params = f'"{os.path.abspath(__file__)}"'

        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", script, params, None, 1
        )
        sys.exit(0)
    except Exception:
        pass


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
            run_as_admin()
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
