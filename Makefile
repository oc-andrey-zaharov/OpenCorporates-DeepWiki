.PHONY: help install install/frontend install/backend dev dev/frontend dev/backend dev/bun stop clean cli

# Default target
help:
	@echo "OpenCorporates-DeepWiki Development Commands"
	@echo "============================================="
	@echo ""
	@echo "Installation:"
	@echo "  make install           - Install all dependencies (frontend + backend)"
	@echo "  make install/frontend  - Install frontend dependencies only"
	@echo "  make install/backend   - Install backend dependencies only"
	@echo ""
	@echo "Development:"
	@echo "  make dev              - Start both frontend and backend servers"
	@echo "  make dev/frontend     - Start frontend dev server only (port 3000)"
	@echo "  make dev/backend      - Start backend API server only (port 8001)"
	@echo "  make dev/bun          - Start frontend with bun runtime"
	@echo ""
	@echo "Maintenance:"
	@echo "  make stop             - Stop all running servers"
	@echo "  make clean            - Clean build artifacts and caches"
	@echo ""
	@echo "CLI:"
	@echo "  make cli              - Run DeepWiki CLI (pass arguments after '--')"
	@echo "                        Example: make cli -- wiki list"
	@echo ""

# Install all dependencies
install: install/backend install/frontend
	@echo "✓ All dependencies installed successfully!"

# Install frontend dependencies
install/frontend:
	@echo "Installing frontend dependencies..."
	@if command -v bun >/dev/null 2>&1; then \
		bun install; \
	else \
		npm install; \
	fi
	@echo "✓ Frontend dependencies installed"

# Install backend dependencies using poetry v2
install/backend:
	@echo "Installing backend dependencies..."
	@if command -v poetry >/dev/null 2>&1; then \
		cd api && poetry install; \
	else \
		echo "Error: Poetry is not installed. Please install Poetry v2 first."; \
		echo "Visit: https://python-poetry.org/docs/#installation"; \
		exit 1; \
	fi
	@echo "✓ Backend dependencies installed"

# Start both frontend and backend
dev:
	@echo "Starting both frontend and backend servers..."
	@echo "Frontend will be available at: http://localhost:3000"
	@echo "Backend will be available at: http://localhost:8001"
	@echo ""
	@echo "Press Ctrl+C to stop both servers"
	@trap 'kill 0' EXIT; \
		$(MAKE) dev/backend & \
		$(MAKE) dev/frontend

# Start frontend only
dev/frontend:
	@echo "Starting frontend server on port 3000..."
	npm run dev

# Start frontend with bun
dev/bun:
	@echo "Starting frontend server with bun on port 3000..."
	bun run dev:bun

# Start backend only
dev/backend:
	@echo "Starting backend server on port 8001..."
	@api/.venv/bin/python -m api.main

# Stop all servers (kill processes on ports 3000 and 8001)
stop:
	@echo "Stopping servers..."
	@-lsof -ti:3000 | xargs kill -9 2>/dev/null || true
	@-lsof -ti:8001 | xargs kill -9 2>/dev/null || true
	@echo "✓ Servers stopped"

# Clean build artifacts and caches
clean:
	@echo "Cleaning build artifacts and caches..."
	@rm -rf .next .turbo dist coverage .mypy_cache .pytest_cache
	@rm -rf node_modules/.cache
	@rm -rf api/.pytest_cache api/.mypy_cache
	@rm -rf api/logs/*
	@rm -rf test/__pycache__ tests/__pycache__
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✓ Cleaned successfully"

# Run CLI tool
cli:
	@cd api && ./deepwiki $(ARGS)
