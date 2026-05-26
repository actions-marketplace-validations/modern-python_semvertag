default: install lint test

install:
    uv lock --upgrade
    uv sync --all-extras --frozen --group lint

lint:
    uv run eof-fixer .
    uv run auto-typing-final semvertag tests
    uv run ruff format
    uv run ruff check --fix
    uv run ty check

lint-ci:
    uv run eof-fixer . --check
    uv run auto-typing-final semvertag tests --check
    uv run ruff format --check
    uv run ruff check --no-fix
    uv run ty check

test *args:
    uv run --no-sync pytest {{ args }}

test-branch:
    @just test --cov-branch
