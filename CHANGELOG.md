# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed

- **BREAKING**: Removed Next.js frontend (`src/` directory)
- **BREAKING**: Removed all frontend dependencies (Node.js, Bun, npm packages)
- **BREAKING**: Removed web UI at `http://localhost:3000`
- Removed `package.json`, `package-lock.json`, `bun.lock`
- Removed `next.config.ts`, `tsconfig.json`, `tailwind.config.js`, `postcss.config.mjs`, `eslint.config.mjs`
- Removed `public/` directory
- Removed frontend-related Makefile targets (`install/frontend`, `dev/frontend`, `dev/bun`)
- Removed frontend-related entries from `.gitignore`
- Removed Node.js installation from Dockerfile
- Removed frontend build stages from Dockerfile
- Removed port 3000 from docker-compose.yml

### Changed

- **BREAKING**: Project is now CLI-first, web UI no longer available
- **BREAKING**: Default mode is standalone (no server required)
- Updated `README.md` for CLI-only usage
- Updated `docs/architecture.md` to reflect CLI-first architecture
- Updated `Makefile` to remove frontend targets
- Updated `Dockerfile` to Python-only (no Node.js)
- Updated `docker-compose.yml` to remove frontend service
- Updated `.gitignore` to remove frontend-related entries
- Updated `api/pyproject.toml` description to reflect CLI focus
- Documented `api/websocket_wiki.py` as optional service

### Added

- Created `.github/workflows/test.yml` for Python testing
- Created `docs/migration-guide.md` for users migrating from previous version
- Created `docs/performance.md` for performance characteristics
- Created integration test files:
  - `tests/integration/test_standalone_mode.py`
  - `tests/integration/test_server_mode.py`
  - `tests/integration/test_fallback.py`
- Added comprehensive documentation for optional services (FastAPI server, WebSocket server)
- Added logging documentation in README

### Fixed

- Docker build now only includes Python dependencies
- CI/CD workflows updated for Python-only project

## Migration Notes

This release represents a major architectural change. See `docs/migration-guide.md` for detailed migration instructions.

Key changes:
- Web UI removed - use CLI instead
- Frontend dependencies removed - only Python required
- Default mode is standalone - no server needed
- Server mode is optional - can be enabled via configuration

## Previous Versions

Previous versions included a Next.js frontend. This has been completely removed in favor of a CLI-first approach.

