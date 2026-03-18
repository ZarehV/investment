# Development Standards

This document defines the coding standards, conventions, and requirements for this project.
All contributors (human and AI) must follow these standards.

## Code Style

### Formatting
- Line length: **100 characters** maximum (enforced by ruff)
- Indentation: 4 spaces (never tabs)
- Quotes: **double quotes** required for strings
- Trailing commas: required in all multi-line structures (function arguments, lists, dicts, imports)
- String interpolation: **f-strings preferred** over `.format()` or `%` formatting

### Type Annotations
- Full type annotations are required on all public API functions and methods
- Prefer built-in generics: `list[str]` over `List[str]`, `dict[str, int]` over `Dict[str, int]`
- Use `X | Y` union syntax over `Optional[X]` or `Union[X, Y]`
- Return types must always be annotated, including `-> None`

### Naming
- Modules and packages: `snake_case`
- Classes: `PascalCase`
- Functions, methods, variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private attributes/methods: prefix with single underscore `_name`

## Architecture

### Package Structure
This project uses the **src-layout**:
```
src/investment/   # importable package
tests/            # test suite (never inside src/)
```

### Validation
- Use **Pydantic v2** models at all trust boundaries (API inputs, config, external data)
- Never trust external data without parsing it through a Pydantic model first
- Use `pydantic-settings` for environment variable configuration

## Testing

- **Minimum 80% test coverage** with branch coverage enabled
- Tests live in `tests/unit/` (pure logic) and `tests/integration/` (I/O, external systems)
- Use `pytest-asyncio` with `asyncio_mode = "auto"` for async tests
- Fixtures belong in `tests/conftest.py` (shared) or local `conftest.py` files
- Never use `unittest.TestCase` — use plain `pytest` functions and fixtures
- Test names: `test_<what>_<condition>_<expected_outcome>`

Run tests:
```bash
uv run pytest
```

Run with explicit coverage report:
```bash
uv run pytest --cov=src/investment --cov-report=html
```

## Linting and Formatting

```bash
# Format code
uv run ruff format .

# Lint (check only)
uv run ruff check .

# Lint with auto-fix
uv run ruff check --fix .

# Type check
uv run mypy src/
```

## Security

- **Parameterized queries only** — never use string interpolation to build SQL or shell commands
- **`hmac.compare_digest()`** for all secret/token comparison (prevents timing attacks)
- **Never use `pickle`** with data from untrusted sources
- **Never use `shell=True`** in `subprocess` calls
- **`pip-audit`** must pass before merging to main:
  ```bash
  uv run pip-audit
  ```
- Secrets and credentials must never be committed — use `.env` (gitignored) and `.env.example`

## Logging

- **Never call `logging.getLogger()` directly** in application code
- Use the project's ECS (Elastic Common Schema) logger:
  ```python
  from investment.logging import get_logger

  logger = get_logger(__name__)
  logger.info("Processing request", extra={"user_id": user_id})
  ```
- Log at appropriate levels:
  - `DEBUG`: detailed diagnostic information
  - `INFO`: normal operational events
  - `WARNING`: unexpected but recoverable situations
  - `ERROR`: errors that prevent a specific operation from completing
  - `CRITICAL`: system-level failures

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_ENV` | No | `development` | Runtime environment |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |
| `ELASTIC_APM_SERVICE_NAME` | No | — | APM service identifier |
| `ELASTIC_APM_SECRET_TOKEN` | No | — | APM authentication token |
| `ELASTIC_APM_SERVER_URL` | No | — | APM server endpoint |
| `ELASTIC_APM_ENVIRONMENT` | No | — | APM environment tag |

## Development Setup

```bash
# Install all dependencies including dev tools
uv sync --all-groups

# Run all checks (format, lint, type-check, test, security)
uv run ruff format .
uv run ruff check --fix .
uv run mypy src/
uv run pytest
uv run pip-audit
```

## Git Workflow

- Branch naming: `<type>/<description>` (e.g., `feat/add-portfolio-model`, `fix/null-check`)
- Commit messages: imperative mood, concise (`Add portfolio valuation model`)
- Never commit directly to `main` — open a pull request
- All CI checks must pass before merging
