.PHONY: help install format lint mypy test test/unit test/integration test/coverage all-checks clean cli publish docs

# Default number of test workers (auto = parallel, 1 = sequential, or specific number)
TEST_WORKERS ?= auto

help:
	@echo "OpenCorporates DeepWiki CLI"
	@echo "==========================="
	@echo "make install            Install dependencies via Poetry"
	@echo "make format             Format code with Ruff"
	@echo "make lint               Run Ruff lint checks"
	@echo "make mypy               Run MyPy type checking"
	@echo "make test               Run entire pytest suite (parallel by default)"
	@echo "make test/unit          Run unit tests"
	@echo "make test/integration   Run integration tests"
	@echo "make test/coverage      Run tests with coverage reporting"
	@echo "make all-checks         Run format + lint + mypy + test/coverage"
	@echo "make cli [ARGS=...]     Run the DeepWiki CLI (e.g. make cli list or make cli ARGS=\"list\")"
	@echo "make publish            Publish package to ocpy repository"
	@echo "make docs               Generate documentation (if configured)"
	@echo "make clean              Remove caches and build artifacts"
	@echo ""
	@echo "Test parallelization:"
	@echo "  TEST_WORKERS=auto     Run tests in parallel (auto-detect CPU count, default)"
	@echo "  TEST_WORKERS=4        Run tests with 4 workers"
	@echo "  TEST_WORKERS=1        Run tests sequentially"

install:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry install; \
	else \
		echo "Error: Poetry is not installed. See https://python-poetry.org/docs/#installation"; \
		exit 1; \
	fi

format:
	@poetry run ruff format .

lint:
	@poetry run ruff check .

mypy:
	@poetry run mypy src/deepwiki_cli

test:
	@if [ "$(TEST_WORKERS)" = "auto" ]; then \
		poetry run pytest tests -n auto; \
	elif [ "$(TEST_WORKERS)" = "1" ]; then \
		poetry run pytest tests; \
	else \
		poetry run pytest tests -n $(TEST_WORKERS); \
	fi

test/unit:
	@if [ "$(TEST_WORKERS)" = "auto" ]; then \
		poetry run pytest tests/unit -n auto; \
	elif [ "$(TEST_WORKERS)" = "1" ]; then \
		poetry run pytest tests/unit; \
	else \
		poetry run pytest tests/unit -n $(TEST_WORKERS); \
	fi

test/integration:
	@if [ "$(TEST_WORKERS)" = "auto" ]; then \
		poetry run pytest tests/integration -n auto; \
	elif [ "$(TEST_WORKERS)" = "1" ]; then \
		poetry run pytest tests/integration; \
	else \
		poetry run pytest tests/integration -n $(TEST_WORKERS); \
	fi

test/coverage:
	@if [ "$(TEST_WORKERS)" = "auto" ]; then \
		poetry run pytest tests --cov=src/deepwiki_cli --cov-report=term-missing --cov-report=html -n auto; \
	elif [ "$(TEST_WORKERS)" = "1" ]; then \
		poetry run pytest tests --cov=src/deepwiki_cli --cov-report=term-missing --cov-report=html; \
	else \
		poetry run pytest tests --cov=src/deepwiki_cli --cov-report=term-missing --cov-report=html -n $(TEST_WORKERS); \
	fi

all-checks: format lint mypy test/coverage
	@echo "All checks completed successfully"

clean:
	@rm -rf dist build .mypy_cache .pytest_cache .ruff_cache
	@rm -rf .coverage htmlcov coverage .hypothesis .deepeval
	@find . -type d \( -name '.venv' -o -name 'venv' -o -name 'env' \) -prune -o -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	@find . -type d \( -name '.venv' -o -name 'venv' -o -name 'env' \) -prune -o -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
	@find . -type d \( -name '.venv' -o -name 'venv' -o -name 'env' \) -prune -o -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true

cli:
	@./deepwiki $(if $(ARGS),$(ARGS),$(filter-out $@,$(MAKECMDGOALS)))

# Catch-all target to prevent Make from complaining about unknown targets
# when using make cli <command>
%:
	@:

publish:
	@if [ -f tmp/.env_credentials ]; then \
		source tmp/.env_credentials && poetry publish --repository ocpyupload; \
	else \
		echo "Error: tmp/.env_credentials not found. Please source AWS repo credentials first."; \
		exit 1; \
	fi

docs:
	@echo "Documentation generation not yet configured"
	@echo "To configure, add mkdocs and update this target"
