default: install lint test

install:
    uv lock --upgrade
    uv sync --all-extras --frozen --group lint

lint:
    uv run eof-fixer .
    uv run ruff format
    uv run ruff check --fix
    uv run ty check

lint-ci:
    uv run eof-fixer . --check
    uv run ruff format --check
    uv run ruff check --no-fix
    uv run ty check

test *args:
    uv run --no-sync pytest {{ args }}

test-branch:
    @just test --cov-branch

test-branch-strategies:
    uv run --no-sync pytest -o "addopts=" --cov=semvertag.strategies.branch_prefix --cov-branch --cov-fail-under=100 --cov-report=term-missing tests/unit/test_branch_prefix_strategy.py

test-cc-strategies:
    uv run --no-sync pytest -o "addopts=" --cov=semvertag.strategies.conventional_commits --cov-branch --cov-fail-under=100 --cov-report=term-missing tests/unit/test_conventional_commits_strategy.py

test-doctor:
    uv run --no-sync pytest -o "addopts=" --cov=semvertag.doctor --cov-branch --cov-fail-under=100 --cov-report=term-missing tests/unit/test_doctor_checks.py
