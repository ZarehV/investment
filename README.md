# investment

Investment analysis and portfolio management.

## Requirements

- [uv](https://docs.astral.sh/uv/) package manager

## Setup

```bash
uv sync --all-groups
```

## Development

See [CLAUDE.md](./CLAUDE.md) for full development standards, including code style,
type annotation rules, testing requirements, logging, and security guidelines.

### Common Commands

```bash
# Run tests with coverage
uv run pytest

# Format code
uv run ruff format .

# Lint
uv run ruff check --fix .

# Type check
uv run mypy src/

# Security audit
uv run pip-audit
```

## Project Structure

```
src/investment/   # Main package
tests/
├── unit/         # Unit tests (pure logic)
└── integration/  # Integration tests (I/O, external systems)
```
