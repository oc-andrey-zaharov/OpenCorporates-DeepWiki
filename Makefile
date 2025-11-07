.PHONY: help install install/backend dev dev/backend stop clean cli test test/unit test/integration test/api

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
	@echo "Testing:"
	@echo "  make test             - Run all tests"
	@echo "  make test/unit        - Run unit tests only"
	@echo "  make test/integration - Run integration tests only"
	@echo "  make test/api         - Run API tests only"
	@echo ""
	@echo "CLI:"
	@echo "  make cli              - Run DeepWiki CLI (pass arguments after '--')"
	@echo "                        Example: make cli -- wiki list"
	@echo ""

# Install backend dependencies
install: install/backend
	@echo "✓ Dependencies installed successfully!"

# Install backend dependencies using poetry v2
install/backend:
	@echo "Installing backend dependencies..."
	@if command -v poetry >/dev/null 2>&1; then \
		poetry install; \
	else \
		echo "Error: Poetry is not installed. Please install Poetry v2 first."; \
		echo "Visit: https://python-poetry.org/docs/#installation"; \
		exit 1; \
	fi
	@echo "✓ Backend dependencies installed"

# Start backend server
dev: dev/backend

# Start backend only
dev/backend:
	@echo "Starting backend server on port 8001..."
	@poetry run python -m api.server.main

# Stop backend server
stop:
	@echo "Stopping backend server..."
	@-lsof -ti:8001 | xargs kill -9 2>/dev/null || true
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

# Run API tests only
test/api:
	@echo "Running API tests..."
	@poetry run pytest tests/api -v

# Run CLI tool
cli:
	@./deepwiki $(ARGS)
