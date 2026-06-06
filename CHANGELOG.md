# Changelog

All notable changes to this project are documented in this file.

## [0.2.0] - 2026-06-06

### Added
- Bandwidth monitoring per device via scapy sniff — real-time ↑↓ KB/s displayed per row.
- OUI/Vendor lookup from MAC address — identifies device manufacturer automatically.
- Persistent session config saved to `%LOCALAPPDATA%/ZeeCut/config.json` (safe list, theme, interface, lag settings, window size).
- Auto-scan berkala with configurable interval (2/3/5/10 min) using `after()` loop.
- New device notification via Windows native alert when unknown MAC appears on network.
- "DL OUI DB" button to download full IEEE OUI database on demand.
- Bandwidth monitor lifecycle tied to interface selection and scan completion.

### Changed
- Device list columns reorganized: Vendor (new), Type, Lag %, Status, ↑↓ KB/s (new).
- Interface selection now restores last-used interface from saved config.
- Admin permission controls extended to auto-scan toggle and interval dropdown.
- Theme engine covers all new toolbar elements (auto-scan switch, interval picker, OUI button).

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
