"""
Auto-update checker.

Queries the GitHub "latest release" endpoint and reports whether a newer
version is available. Network access is best-effort and never raises — callers
should invoke this from a background thread so the UI never blocks.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger("zee_cut.updater")

# Fallback used when the VERSION file is not bundled (e.g. frozen EXE build).
# Kept in sync with the VERSION file at release time.
FALLBACK_VERSION = "0.5.1"

DEFAULT_REPO = "ifauzeee/Zee-Cut"
API_URL = f"https://api.github.com/repos/{DEFAULT_REPO}/releases/latest"
USER_AGENT = "Zee-Cut-Updater"


def _parse_version(version: str) -> tuple[int, int, int]:
    """Parse 'v1.2.3' or '1.2.3' into a comparable tuple."""
    cleaned = version.lstrip("vV").strip()
    parts: list[int] = []
    for piece in cleaned.split(".")[:3]:
        num = ""
        for ch in piece:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    while len(parts) < 3:
        parts.append(0)
    return (parts[0], parts[1], parts[2])


def is_newer(latest: str, current: str) -> bool:
    """Return True if `latest` is strictly newer than `current`."""
    try:
        return _parse_version(latest) > _parse_version(current)
    except Exception:
        return False


def check_for_update(
    current_version: str,
    repo: str = DEFAULT_REPO,
    timeout: int = 5,
    proxy: Optional[str] = None,
) -> dict[str, object]:
    """
    Check GitHub for a newer release.

    Returns a dict with keys:
        available (bool), latest (str), current (str), url (str), error (str|None)
    """
    result: dict[str, object] = {
        "available": False,
        "latest": "",
        "current": current_version,
        "url": "",
        "error": None,
    }
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    handlers: list = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"https": proxy}))
    opener = urllib.request.build_opener(*handlers)
    try:
        with opener.open(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 - best-effort network call
        logger.warning("Update check failed: %s", e)
        result["error"] = str(e)
        return result

    tag = str(payload.get("tag_name", "")).strip()
    html_url = str(payload.get("html_url", ""))
    if not tag:
        result["error"] = "no tag_name in response"
        return result

    result["latest"] = tag
    result["url"] = html_url
    result["available"] = is_newer(tag, current_version)
    return result


def get_current_version() -> str:
    """Read the version from the VERSION file, falling back to a constant."""
    version_file = Path(__file__).resolve().parent.parent / "VERSION"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip() or FALLBACK_VERSION
    return FALLBACK_VERSION
