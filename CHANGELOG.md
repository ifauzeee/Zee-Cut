# Changelog

All notable changes to this project are documented in this file.

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
