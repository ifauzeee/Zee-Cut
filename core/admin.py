"""
Windows administrator privilege helpers.
"""

import ctypes
import os
import sys


def is_admin() -> bool:
    """Check if running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_as_admin(entry_file: str) -> bool:
    """Relaunch current app with administrator privileges."""
    try:
        if getattr(sys, "frozen", False):
            script = sys.executable
            params = ""
        else:
            script = sys.executable
            params = f'"{os.path.abspath(entry_file)}"'

        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", script, params, None, 1
        )
        return result > 32
    except Exception:
        return False
