# AGENTS.md - Consolidated Development Standards

This file consolidates project rules into simple, actionable guidelines for code quality, functional programming, Python standards, architecture, testing, workflow, and compliance. Follow these for all development. For domain-specific rules, see nested AGENTS.md files if present.

## Code Style and Quality

- Follow Google Style Guides for Python, Shell.
- Use snake_case for variables/functions, PascalCase for classes, UPPER_CASE for constants.
- Comprehensive type hints mandatory.
- Docstrings: Google format with Args, Returns, Raises, Examples.
- Tools: Ruff (formatting), Ruff (linting), MyPy (type checking), pre-commit hooks, gh (commits and PR's).

Example docstring:

```python
def process_data(data: List[Dict[str, Any]]) -> Result[List[Dict[str, Any]], str]:
    """Process input data.

    Args:
        data: List of dictionaries.

    Returns:
        Processed data or error.

    Example:
        >>> process_data([{'key': 'value'}]).unwrap()
        [{'key': 'value', 'processed': True}]
    """
    pass
```

## Python Standards

- Python 3.13+; use Poetry 2.0+ for dependencies.
- Install packages using `poetry add` command
- Structure: src/project_name/, tests/, docs/.
- Logging: structlog with JSON for observability; include correlation_id, operation, status.
- Config: Pydantic BaseSettings with env vars.
- Errors: Prefer Result types; use custom exceptions for exceptional cases.
- Security: Validate inputs (OWASP Top 10), encrypt sensitive data (cryptography lib), use JWT for auth.

### Project Configuration (pyproject.toml)

- Use Poetry for dependency management; include name, dynamic version (via poetry-dynamic-versioning), description, authors, readme, packages from src/.
- Add internal "ocpy" source: `[[tool.poetry.source]] name = "ocpy" url = "https://open-corporates-089449186373.d.codeartifact.eu-west-2.amazonaws.com/pypi/dev/simple/" priority = "supplemental"`.
- Dependencies: Pin versions; use internal packages like oc-data-python-pipeline from ocpy.
- Scripts: Define entry points e.g., `data-stager = "module.main:main"`.
- Dev dependencies: Include testing (pytest, hypothesis, moto), linting (ruff, mypy), docs (mkdocs), stubs (boto3-stubs).
- Build-system: `requires = ["poetry-core", "poetry-dynamic-versioning"] build-backend = "poetry.core.masonry.api"`.
- For build/publish: Use `poetry build` and `poetry publish --repository ocpy` with credentials from tmp/.env_credentials (sourced via AWS repo creds); target internal ocpy URL.

Example pyproject.toml sections:

```toml
[tool.poetry]
name = "data-pipeline-stager"
version = "0.2.6.dev208+a40bc76"  # Dynamic via git plugin
description = "data-pipeline-stager service"
authors = ["Ben Ellis <ben.ellis@opencorporates.com>"]
readme = "README.md"
packages = [{ include = "data_stager_app", from = "src" }]

[[tool.poetry.source]]
name = "ocpy"
url = "https://open-corporates-089449186373.d.codeartifact.eu-west-2.amazonaws.com/pypi/dev/simple/"
priority = "supplemental"

[tool.poetry.dependencies]
python = "^3.13,<3.14"
boto3 = "^1.34.70"
# Internal deps from ocpy

[tool.poetry.scripts]
data-stager = "data_stager_app.main:main"

[tool.poetry.group.dev.dependencies]
pytest = "8.3.5"
mypy = "1.18.2"
ruff = "0.14.2"
# ... other dev tools

[build-system]
requires = ["poetry-core", "poetry-dynamic-versioning"]
build-backend = "poetry.core.masonry.api"
```

Example config:

```python
from pydantic import BaseSettings

class Config(BaseSettings):
    debug: bool = False
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
```

Example error handling:

```python
from returns.result import Result, Success, Failure

def safe_parse(data: str) -> Result[Dict[str, Any], str]:
    try:
        return Success(json.loads(data))
    except json.JSONDecodeError as e:
        return Failure(f"Invalid JSON: {e}")
```

Example logging:

```python
import structlog

logger = structlog.get_logger()
logger.info("Processing started", correlation_id="uuid", operation="process_data", status="started")
```

## Functional Programming Principles

- Mandatory for data processing, ETL, APIs.
- Use pure functions, immutability (frozen dataclasses), Result types for errors.
- Compose functions using pipelines and partial application for reusable code and batch processing.
- Avoid side effects; separate I/O from logic.

Example pipeline:

```python
from toolz import pipe, curry
from returns.result import Result, Success, Failure

@curry
def validate(data: Dict) -> Result[Dict, str]:
    return Success(data) if 'name' in data else Failure('Missing name')

def process_data(data: List[Dict]) -> Result[List[Dict], str]:
    return pipe(data, map(validate), list)
```

Advanced currying example:

```python
@curry
def filter_by_field(field: str, pred: Callable, records: List[Dict]) -> List[Dict]:
    return [r for r in records if pred(r.get(field))]

filter_active = filter_by_field("status", lambda s: s == "active")
```

## Architecture and Patterns

- Clean architecture: Domain > Application (use cases) > Infrastructure.
- SOLID adapted to FP: Protocols for interfaces, composition over inheritance.
- Patterns: Strategy (curried functions), Factory (config-based), Observer (EventBus), Command (functional).

Example use case:

```python
from typing import Protocol

class Repository(Protocol):
    def save(self, entity) -> Result[str, str]: ...

class CreateUser:
    def __init__(self, repo: Repository):
        self.repo = repo

    def execute(self, data: Dict) -> Result[str, str]:
        return self.repo.save(data)
```

## Testing Standards

- TDD: Red-Green-Refactor cycle mandatory.
- pytest for unit/integration; Hypothesis for properties.
- Coverage >80%; include performance, security tests.
- Markers: unit, integration, property, slow.

Example property test:

```python
from hypothesis import given, strategies as st

@given(st.text())
def test_normalize(name: str):
    result = normalize_company_name(name)
    assert result == result.strip()  # No whitespace
```

## Development Workflow

- Branch: feature/<name>; commit after green tests.
- Pre-commit: Run before commit (formatting, linting, secrets).
- Dependencies: Use Renovate for automated updates; group by type (e.g., Python deps), assign to teams.
- CI: pytest, coverage, pre-commit on push/PR.
- Review: Check FP compliance, tests, docs, security.

Daily cycle:

1. Write failing test.
2. Implement minimally.
3. Refactor with FP principles.
4. Run full tests: `poetry run pytest --cov`.

Example Renovate group:

```json
{
  "packageRules": [
    {
      "matchManagers": ["poetry"],
      "groupName": "Python dependencies",
      "labels": ["python"]
    }
  ]
}
```

### Makefile Standards

- Use Makefile for consistent workflows across local and container environments.
- Detect mode: local (Poetry) or container (Docker Compose with dev-container).
- Handle credentials securely via tmp/.env_credentials (source AWS repo creds).
- Key targets: all-checks (format, lint, test/coverage), build/for-deployment (multi-arch Docker), publish (Poetry to repo), format (Ruff), lint (Ruff/MyPy), test (unit/component/system with parallelization via xdist, coverage), run (app with args), docs, pre-commit (install/run), help.
- Support parallel tests: TEST_WORKERS=auto (default), override for sequential (1) or specific count.
- Ensure Docker Compose for container mode; rebuild images with no-cache if needed.
- Integrate observability: run/with-observability for container mode.
- Examples: `make test/unit`, `make run ARGS=us-il`, `make docs/serve`.

## Compliance (ISO 27001)

- Embed controls: A.8 (Assets), A.9 (Access), A.10 (Crypto), A.12 (Ops), A.14 (Dev), A.16 (Incidents).
- Classify data; use secure patterns (e.g., encryption, logging).
- Review assets quarterly; test security in CI.

For specifics, reference domain files (e.g., AWS in infrastructure/AGENTS.md).

Keep changes small, testable, and documented.
