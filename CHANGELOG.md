# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

The next release is planned as version 2.0.0 because configuration, installation, and module
import paths changed.

### Added

- Environment-based credential and runtime configuration.
- Persistent browser profile and optional proxy support.
- Explicit live login validation command.
- Makefile targets for installation, validation, testing, and maintenance.
- Automated tests, type checking, formatting, and pre-commit secret scanning.

### Changed

- Reorganized database and parsing modules under `upwork_scraper`.
- CI now uses the Makefile quality gate.
- SQLite is the only supported persistence format.

### Removed

- Legacy `settings/config.py`.
- `requirements.txt`.
- Obsolete CSV output artifacts and undocumented CSV behavior.
