"""
Cross-platform administrator privilege helpers.
Dispatches to OS-specific implementations via core.platform.
"""
from core.platform import is_admin as _is_admin
from core.platform import run_as_admin as _run_as_admin

# Re-export with same names so existing imports continue to work.
is_admin = _is_admin
run_as_admin = _run_as_admin
