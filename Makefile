.PHONY: help install install/backend dev dev/backend stop clean cli test test/unit test/integration lint format build deploy

# Default target
help:
	@echo "OpenCorporates-DeepWiki Development Commands"
	@echo "============================================="
	@echo ""
	@echo "Installation:"
	@echo "  make install           - Install backend dependencies"
	@echo "  make install/backend   - Install backend dependencies only"
	@echo ""
	@echo "Development:"
	@echo "  make dev              - Start backend API server (port 8001)"
	@echo "  make dev/backend      - Start backend API server only (port 8001)"
	@echo ""
	@echo "Maintenance:"
	@echo "  make stop             - Stop backend server"
	@echo "  make clean            - Clean build artifacts and caches"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint             - Run ruff linter"
	@echo "  make format           - Format code with ruff"
	@echo ""
	@echo "Build & Deploy:"
	@echo "  make build            - Build package with poetry"
	@echo "  make deploy           - Publish package to ocpyupload repository"
	@echo ""
	@echo "Testing:"
	@echo "  make test             - Run all tests"
	@echo "  make test/unit        - Run unit tests only"
	@echo "  make test/integration - Run integration tests only"
	@echo ""
	@echo "CLI:"
	@echo "  make cli [COMMAND]    - Run DeepWiki CLI command"
	@echo "                        Example: make cli generate"
	@echo "                        Example: make cli list"
	@echo ""

# Install backend dependencies
install: install/backend
	@echo "✓ Dependencies installed successfully!"

# Install backend dependencies using poetry v2
install/backend:
	@echo "Installing backend dependencies..."
	@if command -v poetry >/dev/null 2>&1; then \
		. bin/aws-repo-credentials.sh && poetry install; \
	else \
		echo "Error: Poetry is not installed. Please install Poetry v2 first."; \
		echo "Visit: https://python-poetry.org/docs/#installation"; \
		exit 1; \
	fi
	@echo "✓ Backend dependencies installed"

# Start backend server
dev: dev/backend

# Start backend only
# Runs server in background and saves PID to .deepwiki-server.pid for safe termination
dev/backend:
	@echo "Starting backend server on port 8001..."
	@poetry run python -m api.server.main & \
		SERVER_PID=$$!; \
		echo $$SERVER_PID > .deepwiki-server.pid; \
		echo "✓ Server started (PID: $$SERVER_PID, saved to .deepwiki-server.pid)"; \
		echo "  Use 'make stop' to stop the server"

# Stop backend server
# Uses PID file to safely terminate only the expected backend process.
# If PID file is missing or stale, falls back to port-based termination.
stop:
	@echo "Stopping backend server..."
	@if [ -f .deepwiki-server.pid ]; then \
		PID=$$(cat .deepwiki-server.pid); \
		if ps -p $$PID > /dev/null 2>&1; then \
			# Verify it's the expected process (check command contains python and api.server.main) \
			CMD=$$(ps -p $$PID -o command= 2>/dev/null || echo ""); \
			if echo "$$CMD" | grep -q "api.server.main"; then \
				kill -9 $$PID 2>/dev/null && echo "✓ Stopped server (PID: $$PID)" || echo "✗ Failed to stop server"; \
			else \
				echo "⚠ PID file exists but process doesn't match expected backend. Using port-based fallback."; \
				-lsof -ti:8001 | xargs kill -9 2>/dev/null || true; \
			fi; \
		else \
			echo "⚠ PID file exists but process not found (may have already stopped). Cleaning up PID file."; \
		fi; \
		rm -f .deepwiki-server.pid; \
	else \
		echo "⚠ PID file not found. Using port-based termination (may affect other services on port 8001)."; \
		-lsof -ti:8001 | xargs kill -9 2>/dev/null || echo "No process found on port 8001"; \
	fi
	@echo "✓ Server stopped"

# Clean build artifacts and caches
clean:
	@echo "Cleaning build artifacts and caches..."
	@rm -rf dist coverage .mypy_cache .pytest_cache
	@rm -rf api/.pytest_cache api/.mypy_cache
	@rm -rf api/logs/*
	@rm -rf tests/__pycache__
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✓ Cleaned successfully"

# Run all tests
test:
	@echo "Running all tests..."
	@poetry run pytest tests -v

# Run unit tests only
test/unit:
	@echo "Running unit tests..."
	@poetry run pytest tests/unit -v

# Run integration tests only
test/integration:
	@echo "Running integration tests..."
	@poetry run pytest tests/integration -v

# Run CLI tool
cli:
	@./deepwiki $(filter-out $@,$(MAKECMDGOALS))

# Run ruff linter
lint:
	@echo "Running ruff linter..."
	@poetry run ruff check .
	@echo "✓ Linting complete"

# Format code with ruff
format:
	@echo "Formatting code with ruff..."
	@poetry run ruff format .
	@echo "✓ Formatting complete"

# Build package with poetry
build:
	@echo "Building package with poetry..."
	@. bin/aws-repo-credentials.sh && poetry build
	@echo "✓ Build complete"

# Deploy package to ocpyupload repository
deploy:
	@echo "Publishing package to ocpyupload repository..."
	@. bin/aws-repo-credentials.sh && poetry publish --repository ocpyupload
	@echo "✓ Deployment complete"

# Catch-all target to prevent Make from treating CLI arguments as targets
%:
	@:
