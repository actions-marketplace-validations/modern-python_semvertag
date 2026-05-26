# Deferred Work

Tracking issues raised during code review that were intentionally not fixed in-cycle. Each entry has a one-line reason for deferral so future reviews and planning can decide when to act.

## Deferred from: code review of 1-1-bootstrap-public-scaffolding-from-modern-di (2026-05-26)

- `semvertag` console script references missing `semvertag.__main__:main` [pyproject.toml:34] — Story 1.7 lands the typer entrypoint; bootstrap intentionally ships package skeleton only.
- `just install` mixes `uv lock --upgrade` with `uv sync --frozen` — every install re-locks, hurting reproducibility for new contributors. Template-inherited from modern-di; revisit if/when semvertag diverges from template's install policy.
- Duplicate `--cov` flags between `addopts = "--cov=. --cov-report term-missing"` and CI's `just test . --cov=. --cov-report xml`. Reports merge into both `term-missing` and `xml` outputs; positional `.` also overrides `testpaths = ["tests"]`. Template-inherited.
- `uv_build` build-backend unpinned (`requires = ["uv_build"]`) — future major release can break reproducible builds. Template-inherited.
- `eof-fixer .` walks repo root (`.venv/`, `_autosemver_reference/`, `_bmad/`) [Justfile:9, Justfile:20] — relies on the tool's default exclude behavior. Template-inherited; `auto-typing-final` scoping is a separate decision in the story.
- `<org>` URL placeholders in `pyproject.toml [project.urls]` and `mkdocs.yml repo_url`/`extra.social` — spec-acknowledged; pre-launch resolution per Launch Decisions Pending in prd.md.
- `codecov-action@v4.0.1` pinned to an early-v4 patch with known token-handling bugs. Template-inherited; consider bumping when next touching CI.
- No fork-safe guard on codecov upload — fork PRs lack `CODECOV_TOKEN` and the action fails noisily on every external contribution. Template-inherited.
- No `timeout-minutes` on CI jobs — runaway jobs default to GitHub's 360-minute limit. Template-inherited.
- No explicit `permissions:` block on the workflow — defaults to repo-configured `GITHUB_TOKEN` permissions; broader-than-needed blast radius. Template-inherited.
- `setup-uv` `cache-dependency-glob: "**/pyproject.toml"` misaligned with `uv lock --upgrade` running every install — cache key doesn't change on lock-only updates. Template-inherited; moot until install/lock policy changes.
- `.gitignore` carries `plan.md` entry inherited from modern-di — leaks template author's personal workflow into every downstream project. Template-inherited.
- `.gitignore` uses `__pycache__/*` rather than `__pycache__/` — ignores contents but leaves empty `__pycache__` dirs stageable. Template-inherited.
- Production dependencies (`typer`, `rich`, `semver`, `pydantic-settings`, `modern-di-typer`, `httpx2`) carry no version pins or lower bounds. NFR12 commit-lockfile policy partially mitigates installation drift but does not protect against breaking upstream releases when consumers install fresh.
- `[tool.uv.build-backend]` declares no sdist `source-exclude` — `_autosemver_reference/`, `_bmad/`, `docs/`, top-level dotfiles may all ship inside the sdist when `uv build` runs. Revisit at first PyPI publish (Story 4.2).
- Concurrency `group: ${{ github.head_ref || github.run_id }}` falls back to unique `run_id` on push events — concurrent main-branch runs are never cancelled. Template-inherited.
- `actions/checkout@v4` default `fetch-depth: 1` and no `fetch-tags: true` — fine while only the smoke test exists, but a semver-tagging tool will need git history + tags once provider tests land (Story 1.5+).
- `uv sync --all-extras` is a no-op (no `[project.optional-dependencies]` declared) [Justfile:5]. Template-inherited; harmless today but confusing for new contributors.
