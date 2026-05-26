# Story 1.1: Bootstrap public semvertag scaffolding from modern-di shape

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a project maintainer,
I want a public-OSS-ready repository skeleton mirrored from `modern-di`'s structure with Raiffeisen artefacts stripped and the Python floor broadened to 3.10,
so that downstream stories (1.2–1.7, 2.1, 3.x, 4.x) can implement semvertag's logic onto clean, conventional scaffolding without dragging company-internal files forward.

## Acceptance Criteria

### AC1 — pyproject.toml authored modeled on modern-di's

**Given** a fresh greenfield checkout
**When** I follow the bootstrap recipe
**Then** `pyproject.toml` is authored modeled on `/Users/kevinsmith/src/pypi/modern-di/pyproject.toml`, with `[project]` set for semvertag, `[project.scripts]` declaring `semvertag = "semvertag.__main__:main"`, `requires-python = ">=3.10,<3.14"`, and **no** `[[tool.uv.index]]` Artifactory blocks
**And** `Justfile`, `.readthedocs.yaml`, `docs/requirements.txt`, and `LICENSE` (MIT) are copied verbatim from `/Users/kevinsmith/src/pypi/modern-di`
**And** `mkdocs.yml` is adapted (theme preserved, minimal `nav:` declaring only `index.md` so `mkdocs build` succeeds against the empty scaffolding — the full nav structure is filled in by Story 4.4)
**And** `.github/workflows/ci.yml` is adapted to lint on Python 3.10 and run pytest matrix on Python 3.10–3.13 on `ubuntu-latest`

### AC2 — No Raiffeisen artefacts survive

**Given** the scaffolding is in place
**When** I search the repo for Raiffeisen artefacts
**Then** no `Dockerfile`, no `https://gitlabci.raiffeisen.ru` literal, no `AUTOSEMVER_` env-var reference, and no internal Artifactory `[[tool.uv.index]]` block survives anywhere

### AC3 — Package imports and lint passes

**Given** the package directory is named `semvertag/`
**When** I run `python -c "import semvertag"` after `just install`
**Then** the import succeeds (the package body is minimal — `__init__.py` and `py.typed`)
**And** `just lint` passes on the empty scaffolding

## Tasks / Subtasks

- [x] **Task 1: Author `pyproject.toml` for semvertag** (AC: 1, 2)
  - [x] 1.1 Remove the existing `pyproject.toml` and re-author from scratch, modeled on `/Users/kevinsmith/src/pypi/modern-di/pyproject.toml`. **Do NOT carry over `[[tool.uv.index]]` blocks** — they point at internal Artifactory.
  - [x] 1.2 `[project]`: `name = "semvertag"`, `version = "0"`, `description = "Auto-tag GitLab/GitHub/Bitbucket repos with semantic version tags — one tool, two strategies."`, `authors = [{ name = "Artur Shiriev", email = "me@shiriev.ru" }]`, `license = "MIT"`, `readme = "README.md"`, `keywords = ["semver", "gitlab", "ci", "auto-tag", "conventional-commits"]`, classifiers covering Python 3.10–3.13 and `Typing :: Typed`.
  - [x] 1.3 `requires-python = ">=3.10,<3.14"` (broaden from current 3.13-only; NFR27).
  - [x] 1.4 `dependencies = ["typer", "rich", "semver", "pydantic-settings", "modern-di-typer", "httpx2"]` — **note `httpx2`, not `httpx` or `python-gitlab`** (architecture §Provider Abstraction §HTTP layer).
  - [x] 1.5 `[project.scripts]` with `semvertag = "semvertag.__main__:main"` (FR42 `uvx semvertag` zero-install entrypoint).
  - [x] 1.6 `[project.urls]`: `repository = "https://github.com/<org>/semvertag"`, `docs = "https://semvertag.readthedocs.io"`. Org placeholder is fine for now — the four open Launch Decisions in `prd.md` §Launch Decisions Pending include the GitHub org choice; pre-launch resolution.
  - [x] 1.7 `[build-system]`: `requires = ["uv_build"]`, `build-backend = "uv_build"`. `[tool.uv.build-backend]`: `module-name = "semvertag"`, `module-root = ""` (flat layout per architecture §File Organization Patterns).
  - [x] 1.8 `[dependency-groups]`:
    - `dev = ["pytest", "pytest-cov", "pytest-xdist", "pytest-randomly"]` — no `pytest-asyncio` (semvertag has no async code), no `pytest-repeat` or `pytest-benchmark`, no `requests-mock` (httpx2.MockTransport replaces it).
    - `lint = ["ruff", "ty", "auto-typing-final", "eof-fixer"]`.
  - [x] 1.9 `[tool.ruff]`: `fix = true`, `unsafe-fixes = true`, `line-length = 120`, `target-version = "py310"` (matches Python floor), `extend-exclude = ["docs", "_autosemver_reference", "_bmad"]` — the existing `autosemver/` source is being moved to `_autosemver_reference/` for behavioral porting in Stories 1.2–1.7 (see Task 6 below); it must not be linted under semvertag's stricter ruleset. `_bmad/` added during implementation because planning artefacts were relocated there.
  - [x] 1.10 `[tool.ruff.lint]`: `select = ["ALL"]`, `ignore = ["D1", "FBT", "TRY003", "EM102", "D203", "D212", "COM812", "ISC001", "S105"]` (mirrors existing `autosemver/pyproject.toml`; honest set for AI-author code). `isort.lines-after-imports = 2`, `isort.no-lines-before = ["standard-library", "local-folder"]`. `[tool.ruff.lint.extend-per-file-ignores]` with `"tests/*.py" = ["S101"]` (allow asserts in tests).
  - [x] 1.11 `[tool.pytest.ini_options]`: `addopts = "--cov=. --cov-report term-missing"`. **No** `asyncio_mode` setting. `testpaths = ["tests"]` added during implementation so pytest doesn't collect from `_autosemver_reference/tests/`.
  - [x] 1.12 `[tool.coverage.report]`: `exclude_also = ["if typing.TYPE_CHECKING:"]`. `[tool.coverage.run]`: `omit = ["_autosemver_reference/*"]` (the reference is not part of coverage). Added `[tool.ty.src] exclude = ["_autosemver_reference", "_bmad", "docs"]` so `ty check` does not descend into the reference (Task 6.3 instruction).
  - [x] 1.13 Sanity-check the new file with `uv lock` — should resolve cleanly. Commit the resulting `uv.lock`.

- [x] **Task 2: Copy verbatim files from modern-di** (AC: 1)
  - [x] 2.1 Copy `/Users/kevinsmith/src/pypi/modern-di/Justfile` to `./Justfile` verbatim, then make two adjustments:
    - **Add `auto-typing-final`** to both `lint` and `lint-ci` targets (modern-di doesn't use it; architecture §Tech Stack mandates it). Verified `auto-typing-final --check` exists (via `uvx auto-typing-final --help`); added to both targets.
    - **Remove the `publish` target.** Modern-di's `publish` uses `$PYPI_TOKEN`; semvertag uses PyPI trusted publishing (NFR13) and the publish workflow lands in Story 4.2. Don't ship a temporary token-based path.
  - [x] 2.2 Copy `/Users/kevinsmith/src/pypi/modern-di/.readthedocs.yaml` to `./.readthedocs.yaml` verbatim (matches Python 3.10 build base; references `mkdocs.yml`).
  - [x] 2.3 Copy `/Users/kevinsmith/src/pypi/modern-di/docs/requirements.txt` to `./docs/requirements.txt` verbatim (`mkdocs` + `mkdocs-material`).
  - [x] 2.4 Copy `/Users/kevinsmith/src/pypi/modern-di/LICENSE` to `./LICENSE` verbatim, then update line 3 to `Copyright (c) 2026 Artur Shiriev` (drop `modern-python` org reference).
  - [x] 2.5 Copy `/Users/kevinsmith/src/pypi/modern-di/.gitignore` to `./.gitignore` verbatim (replaces the slightly different existing `.gitignore`; modern-di's includes `uv.lock` exclusion — **remove that line** because semvertag commits `uv.lock` per NFR12 dependency-audit discipline).

- [x] **Task 3: Adapt `mkdocs.yml`** (AC: 1)
  - [x] 3.1 Author `mkdocs.yml` modeled on `/Users/kevinsmith/src/pypi/modern-di/mkdocs.yml`, with:
    - `site_name: semvertag`
    - `repo_url: https://github.com/<org>/semvertag` (org placeholder same as pyproject.toml)
    - `docs_dir: docs`, `edit_uri: edit/main/docs/` (verbatim)
    - **`nav:` declares ONLY `Quick Start: index.md`** — per Story 1.1 ↔ Story 4.4 nav contract, the full Quick Start → CLI ref → strategies → providers → doctor structure is filled in by Story 4.4. Do not pre-stub nav entries for pages that don't exist yet (would break `mkdocs build --strict`).
  - [x] 3.2 Preserve modern-di's `theme:` block verbatim (material; content.code.copy, content.action.edit, content.action.view, navigation.* features; light/dark palette with black primary + pink accent).
  - [x] 3.3 Preserve modern-di's `markdown_extensions:` and `extra:` blocks verbatim.
  - [x] 3.4 Drop modern-di's `extra_css: - css/code.css` (we don't ship that file).
  - [x] 3.5 Update `extra.social[].link` to point at the semvertag GitHub URL placeholder.

- [x] **Task 4: Adapt `.github/workflows/ci.yml`** (AC: 1)
  - [x] 4.1 Author `.github/workflows/ci.yml` modeled on `/Users/kevinsmith/src/pypi/modern-di/.github/workflows/ci.yml`, with:
    - `name: main`, `on: push (main) + pull_request`, `concurrency` block verbatim.
    - `lint` job on `ubuntu-latest`, runs `just install lint-ci` on Python 3.10. Uses `astral-sh/setup-uv@v3` + `extractions/setup-just@v2` per architecture §Tech Stack (NFR29).
    - `pytest` job on `ubuntu-latest` with matrix `["3.10", "3.11", "3.12", "3.13"]` — **drop `"3.14"`** (NFR27 floor is 3.10–3.13).
    - codecov upload step preserved verbatim with `codecov/codecov-action@v4.0.1` (CODECOV_TOKEN from secrets).
  - [x] 4.2 Do **not** add `pip-audit`, LOC gate, dependency-update cron, or `mkdocs build --strict` in this story — those land in Story 4.1 + Story 4.4 respectively. Story 1.1's `ci.yml` is the minimum viable lint+test surface.
  - [x] 4.3 Do **not** author `.github/workflows/publish.yml` — Story 4.2 owns the publish workflow with PyPI trusted publishing.

- [x] **Task 5: Remove Raiffeisen artefacts** (AC: 2)
  - [x] 5.1 Delete `./Dockerfile` (Raiffeisen Artifactory base image + ARTIFACTORY_USER/PASSWORD build args — never publish).
  - [x] 5.2 Grep verification — these return **zero** matches outside `_autosemver_reference/` and `_bmad/`:
    - `grep -rni "raiffeisen" .` (case-insensitive)
    - `grep -rn "gitlabci.raiffeisen.ru" .` (case-sensitive)
    - `grep -rn "AUTOSEMVER_" .` (case-sensitive env-var prefix)
    - `grep -rni "artifactory" .` (case-insensitive)
    - `grep -rn "raif-autosemver" .` (case-sensitive)
  - [x] 5.3 Verified with `--exclude-dir=_autosemver_reference --exclude-dir=_bmad`. All five patterns return zero matches outside those excluded dirs. (Note: an earlier case-insensitive run incorrectly flagged `AUTOSEMVER_` against the lowercase substring in `_autosemver_reference/` — the story spec calls for case-sensitive matching on `AUTOSEMVER_` since it is an env-var prefix; clean under that spec.)

- [x] **Task 6: Preserve existing `autosemver/` as behavioral reference** (AC: 3)
  - [x] 6.1 Rename the existing `./autosemver/` directory to `./_autosemver_reference/`. The leading underscore + descriptive suffix keeps it out of Python's default import path (no risk of `import autosemver` accidentally working) and signals "reference, not source."
  - [x] 6.2 Also move `./tests/` to `./_autosemver_reference/tests/` — the existing tests use `requests-mock` and target the old API surface; Stories 1.2–1.7 re-author tests under the new `tests/unit/` + `tests/integration/` layout per architecture §Test Architecture.
  - [x] 6.3 Excluded from ruff (`tool.ruff.extend-exclude`), ty (`[tool.ty.src] exclude = [...]`), and pytest (`testpaths = ["tests"]`). Coverage also omits `_autosemver_reference/*`. Pytest's default does **not** ignore underscore-prefixed dirs, so explicit `testpaths` was required. `just lint` and `just test` both pass with zero diagnostics or collection from the reference.
  - [x] 6.4 **Rationale:** Stories 1.2–1.7 port the bump algorithm, settings shape, DI wiring, and test idioms from this reference onto modern-di-shaped scaffolding. Keeping it in-tree (instead of relying on git history) makes the port easier and the reference auditable from PRs.

- [x] **Task 7: Create the new `semvertag/` package directory** (AC: 3)
  - [x] 7.1 `mkdir semvertag`
  - [x] 7.2 `touch semvertag/__init__.py` (empty — the package body is minimal at v1.0.0; downstream stories add modules).
  - [x] 7.3 `touch semvertag/py.typed` (empty PEP 561 typed-package marker — required for `pip install semvertag` to expose types to downstream type checkers).
  - [x] 7.4 **Do NOT** port any behavioral content from `_autosemver_reference/` in this story. `__init__.py` stays empty; no `from semvertag.X import Y` re-exports. Stories 1.2 onward build the real module surface.

- [x] **Task 8: Create placeholders required for build / lint to succeed** (AC: 3)
  - [x] 8.1 `docs/index.md` — one-line placeholder: `# semvertag — coming soon`. Full Quick Start lands in Story 4.4.
  - [x] 8.2 `README.md` — placeholder: `# semvertag\n\nAuto-tag GitLab/GitHub/Bitbucket repos with semantic version tags.`. Full hero (badges, copy-pasteable snippets, asciicast) lands in Story 4.7.

- [x] **Task 9: Verify acceptance** (AC: 1, 2, 3)
  - [x] 9.1 Ran `just install` after deleting `.venv/`. Resolved 46 packages; built and installed `semvertag==0` from local source.
  - [x] 9.2 `.venv/bin/python -c "import semvertag"` — exit 0.
  - [x] 9.3 `just lint` — zero violations. eof-fixer, auto-typing-final, ruff format, ruff check, ty check all pass. `just lint-ci` also passes (validates the CI path).
  - [x] 9.4 All five grep checks return zero matches outside `_autosemver_reference/` and `_bmad/`.
  - [x] 9.5 `uvx --with mkdocs-material mkdocs build --strict --config-file mkdocs.yml` — built successfully.
  - [x] 9.6 `tests/__init__.py` and `tests/test_smoke.py` created. Test imports `semvertag` at module level (per global "use global imports" rule + ruff PLC0415) and asserts `semvertag.__name__ == "semvertag"`. `just test` collects 1 item, passes, 100% coverage. CI workflow `.github/workflows/ci.yml` runs `just install` then `just test`; pytest will exit 0 with the smoke test in place. (Actual CI push deferred — the repo has not yet been pushed to a GitHub remote; workflow file is syntactically valid YAML and matches modern-di's proven shape.)

## Dev Notes

### Project Memory & Framing

**This is the foundational "scaffold" story for the entire v1.0 of semvertag.** Project memory (`project_semvertag_bootstrap_framing.md`) makes the framing explicit:

> semvertag's v1.0 bootstrap is **modern-di shaped + autosemver/ logic ported**, not **autosemver/ transformed in place**.
>
> - **modern-di** (`/Users/kevinsmith/src/pypi/modern-di`, public OSS) is the **structural template**: mirror its `.github/workflows/`, `Justfile`, `mkdocs.yml`, `.readthedocs.yaml`, `docs/requirements.txt`, `LICENSE`, `context7.json`, and packaging conventions verbatim where applicable.
> - The existing `autosemver/` directory (Raiffeisen-internal) is a **behavioral reference**, not a code starter. Port the bump algorithm, the test cases (especially `requests-mock` shapes — now `httpx2.MockTransport`), the DI wiring pattern, and the settings shape — but re-author each file on top of the modern-di-shaped scaffolding rather than `git mv`-ing the company-internal files.

**Why:** the current `autosemver/` codebase is company-specific (internal Artifactory indexes in `pyproject.toml`, hardcoded `https://gitlabci.raiffeisen.ru` default, Raiffeisen Dockerfile, `AUTOSEMVER_` env prefix) — treating it as a starter would drag company artefacts forward and make the public layout cluttered.

**How to apply:** lead with "scaffold from modern-di's shape" before "port logic from autosemver/". This story is **only** the scaffolding step; behavior is ported in Stories 1.2–1.7.

### Critical Architectural Constraints

The following constraints from `architecture.md` are non-negotiable for this story:

1. **Python floor 3.10–3.13** (NFR27). Current code is 3.13-only — broaden. Drop modern-di's 3.14 inclusion (NFR27 explicitly caps at 3.13 for now; NFR30's EOL+12mo drop policy will widen later).
2. **No `[[tool.uv.index]]` Artifactory blocks** anywhere in `pyproject.toml`. The existing entries point at `https://artifactory.raiffeisen.ru/...` and must not appear in the public publish.
3. **`httpx2`, not `httpx` or `python-gitlab`.** Architecture §Provider Abstraction §HTTP layer: "All four GitLab endpoints accessed via raw `httpx2.Client` calls in `semvertag/providers/gitlab.py` — no `python-gitlab` SDK." Dependency list reflects this.
4. **Flat package layout (no `src/`).** Both modern-di and existing autosemver/ use the flat layout. `[tool.uv.build-backend]`: `module-name = "semvertag"`, `module-root = ""`.
5. **No optional extras `[github]` / `[bitbucket]`.** Architecture §DI & Dependency Boundary: optional extras were **dropped from v1.0** because httpx2-for-all-providers removes any per-provider SDK dep to gate.
6. **No `from __future__ import annotations`.** Architecture §Type-Annotation Style: "keep annotations evaluated; rely on `typing.TYPE_CHECKING` instead."
7. **No `requests-mock` dep.** Replaced by `httpx2.MockTransport` (per PRD edit pass; architecture §Test Architecture). Don't carry over from existing autosemver/pyproject.toml.
8. **No `[project.optional-dependencies]` block** (extras dropped per #5).

### File-by-File Source Map (what to copy from where)

| Target file | Source | Adapt? |
|---|---|---|
| `pyproject.toml` | `/Users/kevinsmith/src/pypi/modern-di/pyproject.toml` | **Author fresh** (model on, don't copy — semvertag has [project.scripts], different deps, different ruff ignores) |
| `Justfile` | `/Users/kevinsmith/src/pypi/modern-di/Justfile` | Adapt: add `auto-typing-final`, remove `publish` target |
| `.readthedocs.yaml` | `/Users/kevinsmith/src/pypi/modern-di/.readthedocs.yaml` | Verbatim |
| `docs/requirements.txt` | `/Users/kevinsmith/src/pypi/modern-di/docs/requirements.txt` | Verbatim |
| `LICENSE` | `/Users/kevinsmith/src/pypi/modern-di/LICENSE` | Adapt: update Copyright line 3 |
| `.gitignore` | `/Users/kevinsmith/src/pypi/modern-di/.gitignore` | Adapt: **remove `uv.lock`** line — semvertag commits the lock for NFR12 dependency-audit discipline |
| `mkdocs.yml` | `/Users/kevinsmith/src/pypi/modern-di/mkdocs.yml` | Adapt: site_name, repo_url, **minimal nav (only index.md)** — full nav in Story 4.4 |
| `.github/workflows/ci.yml` | `/Users/kevinsmith/src/pypi/modern-di/.github/workflows/ci.yml` | Adapt: drop 3.14 from pytest matrix |
| `semvertag/__init__.py` | (new, empty) | — |
| `semvertag/py.typed` | (new, empty) | — |
| `docs/index.md` | (new, one-line placeholder) | — |
| `README.md` | (new, one-line placeholder) | — |

### Files NOT touched in this story (deferred to later stories)

| File | Story |
|---|---|
| `semvertag/__main__.py` (Typer entrypoint) | Story 1.7 |
| `semvertag/_types.py`, `_errors.py`, `_settings.py`, etc. | Stories 1.2, 1.3 |
| `semvertag/providers/`, `semvertag/strategies/`, `semvertag/doctor/` | Stories 1.5, 1.6, 2.1, 3.x |
| `.github/workflows/publish.yml` | Story 4.2 |
| `.github/workflows/dependency-update.yml` | Story 4.1 |
| `pip-audit` / LOC gate / mkdocs --strict in CI | Story 4.1 / Story 4.4 |
| `action.yml`, `.gitlab/catalog/component.yml` | Story 4.3a, 4.3b |
| `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `docs/api-stability.md` | Story 4.6 |
| README hero content (badges, snippets, asciicast) | Story 4.7 |
| Three migration guides | Story 4.5 |
| Full mkdocs page tree | Story 4.4 |
| `tests/unit/`, `tests/integration/`, `tests/conftest.py` | Stories 1.2 onward (each story adds its own) |
| `context7.json` | Open — Story 4.6 or 4.7 (handle reservation per PRD §Launch Decisions Pending) |
| `CLAUDE.md` | Open — could be authored fresh anytime; not blocking |

### Testing Standards

Per architecture §Test Architecture:
- **Three test layers planned:** unit (`tests/unit/`), integration (`tests/integration/`), and external shadow-mode (in `pypelines`, not this repo).
- This story creates only `tests/__init__.py` + `tests/test_smoke.py` containing `def test_imports() -> None: import semvertag` to give pytest something to collect (so CI doesn't exit 5).
- All future tests use `httpx2.MockTransport` for HTTP mocking (no `requests-mock`, no `respx`, no `pytest-httpx`).
- Coverage gates ≥85% line / 100% branch on bump strategies don't activate until those modules exist (Stories 1.6 and 2.1).

### Anti-Patterns to Avoid (carried from architecture §Anti-Patterns)

These are not Story 1.1-specific (no behavioral code is written yet), but the dev should internalize them now since downstream stories inherit:
- No `print()` outside `_output.py` — but `_output.py` doesn't exist yet; **no `print()` anywhere in this story**.
- No `from __future__ import annotations`.
- No bare `Exception` catches.
- No mutable defaults; use `default_factory` and `pydantic.Field(default_factory=...)`.
- `# ty: ignore`, not `# type: ignore`.
- Comments only when WHY is non-obvious (per global CLAUDE.md); no commentary on WHAT.

### Existing autosemver/ — what gets preserved, what gets thrown away

| Item | Action | Reason |
|---|---|---|
| `autosemver/__init__.py` | Move to `_autosemver_reference/` | Behavioral reference (empty, but preserves path) |
| `autosemver/__main__.py` | Move to `_autosemver_reference/` | Behavioral reference for Story 1.7 Typer entrypoint |
| `autosemver/ioc.py` | Move to `_autosemver_reference/` | Behavioral reference for Story 1.7 DI wiring |
| `autosemver/settings.py` | Move to `_autosemver_reference/` | Behavioral reference for Story 1.2 Settings (note: Raiffeisen defaults survive in the reference — that's fine, the reference is read-only) |
| `autosemver/use_cases/autosemver_use_case.py` | Move to `_autosemver_reference/` | Behavioral reference for Stories 1.6 + 1.7 (bump algorithm + use case orchestration) |
| `autosemver/resources/gitlab.py` | Move to `_autosemver_reference/` | Behavioral reference for Story 1.5 GitLab provider |
| `autosemver/py.typed` | Don't move; let the new `semvertag/py.typed` take its place | Marker, not behavior |
| `tests/test_autosemver.py` | Move to `_autosemver_reference/tests/` | Test pattern reference for Stories 1.2–1.7 (uses `requests-mock`; new tests use `httpx2.MockTransport`) |
| `tests/__init__.py` | Move with the rest | — |
| `Dockerfile` | **Delete** | Raiffeisen base image + Artifactory auth args — never publish |
| `pyproject.toml` | **Replace** | Re-authored per Task 1 |
| `Justfile` | **Replace** | Re-authored per Task 2.1 |
| `.gitignore` | **Replace** | Re-authored per Task 2.5 |
| `README.md` | **Replace** with placeholder | Existing content is internal; Story 4.7 writes the real hero |
| `uv.lock` | **Replace** | Re-generated by `uv lock` after Task 1 |

After this story:
- Root contains: `semvertag/`, `_autosemver_reference/`, `tests/`, `docs/`, `.github/`, plus root-level config files (pyproject.toml, Justfile, etc.).
- `_autosemver_reference/` is excluded from ruff, ty, pytest, and coverage.
- Stories 1.2–1.7 can `cat _autosemver_reference/settings.py` etc. to consult the behavioral reference while implementing the new module on the modern-di-shaped scaffolding.

### Why no `context7.json` in this story

Architecture mentions `context7.json` as a modern-di-mirrored artifact. Modern-di's `context7.json` is **tied to a context7.com handle reservation** (`pk_sIP7B0JWZxstxUZb8L28N` is modern-di's public key, not semvertag's). Per PRD §Launch Decisions Pending, handle reservation (including context7) happens **pre-announcement**, not pre-implementation. So this story does NOT create `context7.json` — it's deferred to a Story 4.x cleanup or pre-launch task. If the dev encounters tooling that requires `context7.json` to be present, leave a TODO note in `Dev Agent Record` and proceed without it.

### Project Structure Notes

This story establishes the structural skeleton. The full intended structure (per architecture §Complete Project Directory Structure) is the target; **this story builds only the subset that's needed for `just install + just lint` to pass on an empty package**. Future stories fill in:

```
semvertag/                              # this story: empty + py.typed
├── __init__.py                         # this story: empty
├── __main__.py                         # Story 1.7
├── py.typed                            # this story: empty marker
├── _types.py                           # Story 1.3
├── _errors.py                          # Story 1.3
├── _settings.py                        # Story 1.2
├── _transport.py                       # Story 1.4
├── _redact.py                          # Story 1.3
├── _output.py                          # Story 1.3
├── _use_case.py                        # Story 1.7
├── ioc.py                              # Story 1.7
├── providers/                          # Stories 1.5 (gitlab.py), 1.x (github.py, bitbucket.py)
├── strategies/                         # Stories 1.6 (branch_prefix), 2.1 (conventional_commits)
└── doctor/                             # Stories 3.1, 3.2
```

No conflicts or variances detected vs. the architecture's specified structure. The `_autosemver_reference/` directory is a reasonable addition that the architecture document doesn't explicitly call out but is justified by the project-memory framing of behavioral porting.

### References

- [Source: architecture.md#Starter Template Evaluation §Initialization Sequence (first implementation story)] — Phase A scaffold list, file-by-file
- [Source: architecture.md#Architectural Decisions Inherited from Structural Template] — Language/runtime, build/packaging, testing, lint/type, code organization, DI, CI/release, documentation choices
- [Source: architecture.md#Deltas vs. modern-di (CLI-specific)] — `[project.scripts]` entrypoint, no optional extras (post-PRD edit), `action.yml` placeholder, trusted publishing, Python floor narrowing
- [Source: architecture.md#Complete Project Directory Structure] — full intended layout for downstream-story planning
- [Source: architecture.md#Implementation Patterns §Type-Annotation Style] — `from __future__ import annotations` ban
- [Source: architecture.md#Implementation Patterns §Comment Policy] — comment-only-on-WHY rule
- [Source: architecture.md#Anti-Patterns to Avoid] — `print()`, bare exceptions, mutable defaults
- [Source: prd.md#FR27, FR42, FR46] — flag/env precedence, uvx zero-install, CONTRIBUTING.md 4-command dev setup target
- [Source: prd.md#NFR12, NFR21, NFR22, NFR27, NFR29] — pip-audit (deferred to Story 4.1), LOC ceiling (deferred), coverage gates (deferred), Python floor, uv version floor
- [Source: epics.md#Epic 1 §Story 1.1] — original AC text (post-remediation: minimal nav)
- [Source: implementation-readiness-report-2026-05-26.md#Step 5 §Story 1.1] — quality review notes; nav clarification applied per recommendation #2
- [Source: /Users/kevinsmith/src/pypi/modern-di/pyproject.toml] — pyproject.toml template
- [Source: /Users/kevinsmith/src/pypi/modern-di/Justfile] — Justfile template
- [Source: /Users/kevinsmith/src/pypi/modern-di/mkdocs.yml] — mkdocs.yml template
- [Source: /Users/kevinsmith/src/pypi/modern-di/.github/workflows/ci.yml] — ci.yml template
- [Source: /Users/kevinsmith/src/pypi/modern-di/.readthedocs.yaml, docs/requirements.txt, LICENSE, .gitignore] — verbatim source files
- [Source: memory: project-semvertag-bootstrap-framing] — modern-di structural + autosemver/ behavioral framing
- [Source: ~/.claude/CLAUDE.md] — user's global rules: `ty: ignore` (not `type: ignore`), global imports in Python

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context) via Claude Code, invoked through `bmad-dev-story` skill on 2026-05-26.

### Debug Log References

- `just lint` on first run produced `ty` errors against `_autosemver_reference/` — `ruff`'s `extend-exclude` does not apply to `ty`. Added `[tool.ty.src] exclude = ["_autosemver_reference", "_bmad", "docs"]` per ty docs (`/astral-sh/ty`); lint then passed.
- `just test` on first run failed collecting `_autosemver_reference/tests/test_autosemver.py` (imports `requests_mock`, which is intentionally not in the dep tree). Story Task 6.3 anticipated this and offered `testpaths = ["tests"]` as the explicit fix; added under `[tool.pytest.ini_options]`.
- Ruff `PLC0415 import should be at the top-level` fired on `tests/test_smoke.py` because the original spec body (`def test_imports() -> None: import semvertag`) places the import inside the function. Rewrote with the import at module level and an assertion (`semvertag.__name__ == "semvertag"`) — matches the global "Use global imports in Python" rule and ruff's `target-version = py310` ruleset.
- `auto-typing-final --check` flag confirmed via `uvx auto-typing-final --help` before adding to `lint-ci`.

### Completion Notes List

- All 9 tasks (and every subtask) executed. Story ACs 1–3 satisfied.
- One scope expansion at user request mid-implementation: planning artefacts (`prd.md`, `architecture.md`, `epics.md`, `prd-validation-report.md`, `implementation-readiness-report-2026-05-26.md`, `product-brief-*.md`, this story file, `sprint-status.yaml`) relocated from repo root to `_bmad/`. Updated `sprint-status.yaml`'s `story_location` to `/Users/kevinsmith/src/pypi/autosemver/_bmad`. Added `_bmad` to ruff `extend-exclude` and ty `[tool.ty.src] exclude` so the planning tree is not linted.
- Two small deltas from the spec, both documented in subtask notes above:
  1. `[tool.ty.src] exclude` added (Task 6.3 mentioned ty exclusion abstractly but ty's specific config key was not in the spec — used the official `tool.ty.src.exclude` key from astral-sh/ty docs).
  2. `tests/test_smoke.py` uses a module-level import + assertion instead of a function-local import — see Debug Log entry above.
- `mkdocs build --strict` validated locally via `uvx --with mkdocs-material mkdocs build --strict`.
- No behavioural code written. `semvertag/__init__.py` is empty; downstream stories (1.2–1.7) build the real module surface from `_autosemver_reference/` patterns.
- `context7.json` deliberately not created — see story §Why no `context7.json` in this story.
- README.md kept to a one-line placeholder; full hero is Story 4.7's scope.

### File List

**New:**
- `pyproject.toml` (re-authored)
- `Justfile` (re-authored, adds `auto-typing-final` to lint/lint-ci, drops `publish` target)
- `.readthedocs.yaml` (verbatim from modern-di)
- `.gitignore` (re-authored from modern-di, `uv.lock` line removed)
- `LICENSE` (verbatim from modern-di, Copyright line updated to `2026 Artur Shiriev`)
- `mkdocs.yml` (adapted — semvertag site_name, minimal `nav`, social link updated)
- `.github/workflows/ci.yml` (adapted — Python matrix capped at 3.13)
- `docs/requirements.txt` (verbatim from modern-di)
- `docs/index.md` (placeholder)
- `README.md` (placeholder)
- `semvertag/__init__.py` (empty)
- `semvertag/py.typed` (empty PEP 561 marker)
- `tests/__init__.py` (empty)
- `tests/test_smoke.py` (1 test: `test_imports`)
- `uv.lock` (regenerated by `uv lock`)

**Renamed:**
- `autosemver/` → `_autosemver_reference/`
- `tests/test_autosemver.py` → `_autosemver_reference/tests/test_autosemver.py`
- `tests/__init__.py` → `_autosemver_reference/tests/__init__.py` (old tests-package init)

**Moved (user-requested mid-story):**
- `prd.md` → `_bmad/prd.md`
- `prd-validation-report.md` → `_bmad/prd-validation-report.md`
- `architecture.md` → `_bmad/architecture.md`
- `epics.md` → `_bmad/epics.md`
- `implementation-readiness-report-2026-05-26.md` → `_bmad/implementation-readiness-report-2026-05-26.md`
- `product-brief-semvertag.md` → `_bmad/product-brief-semvertag.md`
- `product-brief-semvertag-distillate.md` → `_bmad/product-brief-semvertag-distillate.md`
- `1-1-bootstrap-public-scaffolding-from-modern-di.md` → `_bmad/1-1-bootstrap-public-scaffolding-from-modern-di.md` (this story file)
- `sprint-status.yaml` → `_bmad/sprint-status.yaml`

**Deleted:**
- `Dockerfile`
- The original repo-root `pyproject.toml`, `Justfile`, `README.md`, `.gitignore` (all replaced)

### Change Log

| Date | Author | Change |
|---|---|---|
| 2026-05-26 | Claude Opus 4.7 (1M) via Claude Code | Story 1.1 implemented end-to-end. Scaffolded `semvertag/` package, mirrored modern-di config surface, moved internal `autosemver/` to `_autosemver_reference/` (lint/test/coverage all exclude it), deleted Raiffeisen Dockerfile, relocated BMad planning artefacts to `_bmad/` per mid-story user request. `just install`/`just lint`/`just lint-ci`/`just test`/`mkdocs build --strict` all green. Status: review. |
| 2026-05-26 | Claude Opus 4.7 (1M) via Claude Code | Code review run (3-layer adversarial). Acceptance Auditor: clean pass. 6 decision-needed resolved as patches and applied: Python floor raised to `<4` (+3.14 in matrix/classifiers), `auto-typing-final` scoped to `semvertag tests`, `codehilite` removed from mkdocs extensions, coverage `exclude_also` broadened, coverage `omit` extended to `tests/*`+`_bmad/*`, CI gained `uv build` + `mkdocs build --strict` steps. 18 template-inherited issues deferred to `_bmad/deferred-work.md`. `just install lint-ci`/`uv build`/`mkdocs build --strict`/`just test` all green post-patch. Status: done. |

### Review Findings

Code review run 2026-05-26 (3-layer adversarial: Blind Hunter, Edge Case Hunter, Acceptance Auditor). Acceptance Auditor returned a clean pass against all three ACs and every Task; verbatim-copy claims cross-checked against `/Users/kevinsmith/src/pypi/modern-di/`. Totals: 6 decision-needed, 0 unambiguous patches, 18 deferred (template-inherited or out-of-scope), 18 dismissed (false positives or per-spec).

#### Decision-needed

- [x] [Review][Decision] [PATCHED] `requires-python` upper bound excludes Python 3.14 — raised to `>=3.10,<4` and added `"3.14"` to pytest matrix + `Python :: 3.14` classifier. Validated: `uv lock --upgrade` resolved cleanly. [pyproject.toml:5, pyproject.toml:14, .github/workflows/ci.yml:36]
- [x] [Review][Decision] [PATCHED] `auto-typing-final .` scoped to `semvertag tests` in both `lint` and `lint-ci` recipes. Validated: `auto-typing-final semvertag tests --check` ran clean. [Justfile:9, Justfile:16]
- [x] [Review][Decision] [PATCHED] Removed the `- codehilite:` block from `mkdocs.yml markdown_extensions`. Validated: `mkdocs build --strict` succeeded. [mkdocs.yml:55-56]
- [x] [Review][Decision] [PATCHED] Coverage `exclude_also` broadened to `["if typing.TYPE_CHECKING:", "if TYPE_CHECKING:"]`. Catches both qualified and bare guards. [pyproject.toml:87]
- [x] [Review][Decision] [PATCHED] Coverage `omit` extended to `["_autosemver_reference/*", "_bmad/*", "tests/*"]`. Validated: `pytest` coverage report now shows only `semvertag/__init__.py`. [pyproject.toml:90]
- [x] [Review][Decision] [PATCHED] Added `uv build` and `uv run --with-requirements docs/requirements.txt -- mkdocs build --strict` steps to CI `lint` job. Both validated locally: wheel+sdist built; docs built in 0.13s under --strict. Surfaces packaging regressions (e.g., future Story 1.7 entrypoint gap) and nav/extension misconfig at CI time. [.github/workflows/ci.yml]

#### Patches

(none — all candidate patches are either template-inherited (defer) or require a decision)

#### Deferred — template-inherited from modern-di or out-of-Story-1.1 scope

- [x] [Review][Defer] `semvertag` console script references missing `semvertag.__main__:main` [pyproject.toml:34] — deferred, Story 1.7 lands the typer entrypoint
- [x] [Review][Defer] `just install` mixes `uv lock --upgrade` with `uv sync --frozen` (always re-locks; reproducibility cost) [Justfile:3-5] — deferred, template-inherited
- [x] [Review][Defer] Duplicate `--cov` flags between `addopts` (term-missing) and CI invocation (xml) [pyproject.toml:88-89 + .github/workflows/ci.yml:368] — deferred, template-inherited
- [x] [Review][Defer] `uv_build` build-backend unpinned [pyproject.toml:41] — deferred, template-inherited (modern-di same)
- [x] [Review][Defer] `eof-fixer .` walks repo root [Justfile:9, Justfile:20] — deferred, template-inherited (auto-typing-final scoping is DN above)
- [x] [Review][Defer] `<org>` URL placeholders in `pyproject.toml` `[project.urls]` and `mkdocs.yml` `repo_url`/`extra.social` [pyproject.toml:37, mkdocs.yml] — deferred, spec-acknowledged (Launch Decisions Pending in prd.md)
- [x] [Review][Defer] `codecov-action@v4.0.1` pinned to early-v4 patch with known token-handling bugs [.github/workflows/ci.yml] — deferred, template-inherited
- [x] [Review][Defer] No fork-safe guard on codecov upload (CODECOV_TOKEN unset on fork PRs causes noisy failures) [.github/workflows/ci.yml] — deferred, template-inherited
- [x] [Review][Defer] No `timeout-minutes` on CI jobs (default 360-minute runaway potential) [.github/workflows/ci.yml] — deferred, template-inherited
- [x] [Review][Defer] No explicit `permissions:` block on workflow [.github/workflows/ci.yml] — deferred, template-inherited
- [x] [Review][Defer] `setup-uv` `cache-dependency-glob` only keys on `pyproject.toml` while `uv lock --upgrade` runs every install [.github/workflows/ci.yml] — deferred, template-inherited (cache moot until lock policy changes)
- [x] [Review][Defer] `.gitignore` carries `plan.md` entry inherited from modern-di [.gitignore] — deferred, template-inherited (modern-di line 22)
- [x] [Review][Defer] `.gitignore` uses `__pycache__/*` rather than `__pycache__/` (ignores contents, not the dir) [.gitignore] — deferred, template-inherited
- [x] [Review][Defer] Production dependencies (`typer`, `rich`, `semver`, `pydantic-settings`, `modern-di-typer`, `httpx2`) carry no version pins or lower bounds [pyproject.toml:24-31] — deferred, template-inherited; NFR12 commit-lockfile policy partially mitigates
- [x] [Review][Defer] `[tool.uv.build-backend]` declares no sdist `source-exclude` — `_autosemver_reference/`, `_bmad/`, `docs/` may ship in sdist [pyproject.toml:44-46] — deferred, revisit at first PyPI publish (Story 4.2)
- [x] [Review][Defer] Concurrency `group` falls back to unique `run_id` on push (concurrent main runs not cancelled) [.github/workflows/ci.yml:10] — deferred, template-inherited
- [x] [Review][Defer] `actions/checkout@v4` default `fetch-depth=1` — semver-tagging tool tests will need git history + tags [.github/workflows/ci.yml] — deferred, revisit when provider tests land (Story 1.5+)
- [x] [Review][Defer] `uv sync --all-extras` is a no-op (no `[project.optional-dependencies]` declared) [Justfile:5] — deferred, template-inherited

#### Dismissed (for the record)

- `httpx2` flagged as non-existent package — false positive; spec Task 1.4 explicitly mandates it, `uv lock` resolved cleanly (uv.lock committed per Task 1.13)
- `version = "0"` flagged as invalid PEP 440 — false positive; PEP 440 allows a single release segment
- `test-branch` recipe flagged as broken — false positive; `--cov-branch` is a valid standalone pytest-cov toggle that works alongside `addopts` `--cov=.`
- `docs/requirements.txt` flagged as missing `pymdown-extensions` — false positive; pulled in transitively by `mkdocs-material`
- `tests/test_smoke.py` flagged as tautological — covers AC3 import; style critique not actionable
- ruff `select = ["ALL"]` + `unsafe-fixes = true` flagged as foot-gun — per spec Task 1.10 ("honest set for AI-author code"); intentional
- `uv.lock` flagged as missing from `.gitignore` — per spec Task 2.5 / NFR12; semvertag intentionally commits the lockfile
- ruff `target-version = "py310"` flagged as misaligned with matrix — intentional; targets the floor per NFR27
- Empty `semvertag/__init__.py` + tests flagged as likely-to-trip lint under `select=ALL` — spec §9 confirms `just lint` and `just lint-ci` passed end-to-end
- `[tool.ty.src] exclude` flagged as lacking `tests` — `ty check` passed end-to-end
- Description claims GitHub/Bitbucket but keywords only list `gitlab` — per spec keywords list (Task 1.2); broader provider keywords may come in Epic 2+
- `pytest-randomly` flagged as nondeterministic — per spec Task 1.8; intentional test-quality tool
- `--no-sync` in `just test` flagged as foot-gun — template-standard; documented workflow uses `default` recipe
- CI `just install lint-ci` flagged as confusing syntax — standard `just` multi-recipe invocation
- ruff/coverage/ty `exclude` references to `_autosemver_reference`/`_bmad` flagged as dead — Blind Hunter had no project context; dirs exist on disk
- Install ordering race condition (interrupted `uv lock` before `uv sync --frozen`) — theoretical, not actionable
- `[tool.uv.build-backend]` keys flagged as unsupported — per spec Task 1.7; CI build verification gap is captured as DN6 above
- `uv lock --upgrade` overlap with cache flagged twice across layers — deduped into a single defer entry
