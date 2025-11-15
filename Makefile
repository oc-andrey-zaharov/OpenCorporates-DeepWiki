.PHONY: help install format lint test test/unit test/integration clean cli

help:
	@echo "OpenCorporates DeepWiki CLI"
	@echo "==========================="
	@echo "make install            Install dependencies via Poetry"
	@echo "make format             Format code with Ruff"
	@echo "make lint               Run Ruff lint checks"
	@echo "make test               Run entire pytest suite"
	@echo "make test/unit          Run unit tests"
	@echo "make test/integration   Run integration tests"
	@echo "make cli [ARGS=...]     Run the DeepWiki CLI (e.g. make cli ARGS=\"wiki list\")"
	@echo "make clean              Remove caches and build artifacts"

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

test:
	@poetry run pytest tests -v

test/unit:
	@poetry run pytest tests/unit -v

test/integration:
	@poetry run pytest tests/integration -v

clean:
	@rm -rf dist build .mypy_cache .pytest_cache .ruff_cache
	@find . -type d -name '__pycache__' -exec rm -rf {} +

cli:
	@./deepwiki $(ARGS)
