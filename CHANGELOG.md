# Changelog

All notable changes to this project are documented in this file.

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

