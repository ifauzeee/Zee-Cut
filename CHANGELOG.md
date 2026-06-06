# Changelog

All notable changes to this project are documented in this file.

## [0.3.0] - 2026-06-06

### Added
- Smarter throttling with variable poison timing and corrective pulses for natural "lag" feel at level 50.
- AP isolation detection after scan — warns if router blocks client-to-client ARP.
- Route print as third fallback in gateway detection for more reliable Windows discovery.
- Parallel restore for all throttled devices using `ThreadPoolExecutor`.
- Cross-platform abstraction layer (`core/platform.py`) — detects Windows/Linux/macOS and dispatches admin, ARP table, ping, IP forwarding, and gateway detection accordingly.
- Linux `/proc/net/arp` and macOS `arp -a` ARP table parsing.
- Linux `ip route` and macOS `route -n get` gateway detection.
- IP forwarding support via sysctl (macOS) and `/proc/sys/net/ipv4/ip_forward` (Linux).
- Column sorting — click Device/IP/MAC/Vendor/Type headers to toggle sort direction (▴/▾).
- Search/filter input in toolbar — filters by hostname, IP, MAC, or vendor.
- New device highlight — rows glow with distinct background for 3.5 seconds after scan.
- Export device list to CSV via toolbar button.
- Python 3.12 added to CI matrix.
- Full `[project]` metadata, `[project.urls]`, and `[tool.mypy]` config in `pyproject.toml`.
- Test coverage expanded to 21 tests: throttle_device (8 tests), GUI callback helpers (3 tests), AP isolation reset, parallel restore, cross-platform ARP parsing.

### Changed
- `core/admin.py` reduced to 4-line re-export; all logic moved to `core/platform.py`.
- `_scan_arp_table()`, `_ping_sweep()`, `_get_default_gateway()`, `flush_arp_cache()`, `_read_ip_forwarding_state()`, `enable_ip_forwarding()`, `disable_ip_forwarding()` all delegate to `core.platform`.
- `main.py` uses `IS_WINDOWS` for elevation prompt; falls back to `sudo` on Unix.
- `ui/app.py` notification falls back to `print()` on non-Windows.
- `_refresh_device_list()` now applies sort + search filter in addition to mode filter.

### Fixed
- `_parse_windows_arp_table` missing `line.strip()` caused regex to never match (bug introduced during refactor).

## [0.1.2] - 2026-03-29

### Added
- Aggressive realtime scan flow with pre-scan ARP flush.
- Multi-pass discovery sequence (ping warm-up + ARP/scapy refresh).
- Stale hostname/cache cleanup after each scan cycle.

### Changed
- Default GUI scan now runs in realtime aggressive mode for better first-scan accuracy.
- Scan telemetry now records `flush_before_scan` and flush success in summary logs.

## [0.1.1] - 2026-03-29

### Added
- Safe target list controls in UI (`Protect Selected`, `Clear Safe List`).
- Lag preset profiles for bulk operations (`Normal`, `Gaming`, `Meeting`, `Block`).
- Diagnostics export from UI to JSON.
- Structured scan observability events (`scan.start`, `scan.finish`, `scan.error`).
- Diagnostic snapshot API in network engine.
- CI workflow for lint + unit tests on Python 3.10 and 3.11.
- Development tooling files (`requirements-dev.txt`, `pyproject.toml`, `docs/DEVELOPMENT.md`).

### Changed
- Runtime dependency constraints are now version-bounded in `requirements.txt`.
- Unit test coverage expanded for scan summary and diagnostics snapshot paths.
