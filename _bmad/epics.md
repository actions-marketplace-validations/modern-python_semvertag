---
stepsCompleted: ['step-01-extract-requirements', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
inputDocuments:
  - "prd.md"
  - "architecture.md"
workflowType: 'epics'
project_name: 'semvertag'
user_name: 'Kevin'
date: '2026-05-26'
status: 'complete'
completedAt: '2026-05-26'
---

# semvertag - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for **semvertag**, decomposing the requirements from the PRD and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

Source: `prd.md`. Items tagged *(v1.x)* are deferred post-MVP. v1.0 FR count: 40.

**Tag Creation**
- FR1: System creates a semver tag on the default branch's latest commit when invoked.
- FR2: System reads the most recent commit on the default branch to determine bump candidacy.
- FR3: System skips tag creation without error (exit 0, informative log) when the latest commit is not a merge commit or contains no signal conforming to the active bump strategy.
- FR4: System skips tag creation without error when the latest commit is already tagged.
- FR5: System reports the created tag name, the source commit SHA, and the chosen bump strategy in its output.
- FR6: System is idempotent — repeated invocations on the same commit produce no duplicate tag and exit success.
- FR7: System handles repositories with zero pre-existing tags by skipping with an informative message and exit 0.
- FR8: System ignores non-semver-conforming tags (e.g. `release-2024-Q1`) when determining the previous version, finding the latest valid semver tag.
- FR9: System detects the default branch from the active provider's API, with `SEMVERTAG_DEFAULT_BRANCH` as an explicit override. (Local-dev / `--offline` operation deferred to v1.x.)
- FR10: System operates correctly on repositories using shallow CI clones by sourcing tag history from the provider API rather than the local git tree.

**Bump Strategy**
- FR11: User can select the bump strategy (`branch-prefix` or `conventional-commits`) per repository via configuration.
- FR12: System parses GitFlow-style branch prefixes from merge commit messages to determine bump level when the branch-prefix strategy is active.
- FR13: *(v1.x)* User can override the default branch-prefix → bump-level mappings via configuration. Requires v1.x file-based config layer.
- FR14: System parses Conventional Commits headers from merge commit messages to determine bump level when the Conventional Commits strategy is active.
- FR15: System detects major bumps via the `!` suffix or `BREAKING CHANGE:` footer when the Conventional Commits strategy is active.
- FR16: *(v1.x)* User can extend or override the Conventional Commits → bump-level mappings via configuration. Requires v1.x file-based config layer.

**Provider Integration**
- FR17: System creates tags on GitLab projects via the GitLab REST API (v1.0).
- FR18: *(v1.x)* System creates tags on GitHub repositories via the GitHub REST API.
- FR19: *(v1.x)* System creates tags on Bitbucket Cloud repositories via the Bitbucket REST API.
- FR20: System auto-detects the active provider from CI environment variables (`CI_PROJECT_ID`, `GITHUB_REPOSITORY`, etc.) and falls back to the git remote URL.
- FR21: User can override the auto-detected provider via the `--provider` flag or `provider` config key.
- FR22: A contributor can add a new provider by implementing the documented `Provider` protocol in a single file. New providers ship in the standard install — no optional-extras.

**Configuration & Environment**
- FR23: *(v1.x)* User can configure semvertag via a `[tool.semvertag]` block in `pyproject.toml`.
- FR24: *(v1.x)* User can configure semvertag via a standalone `.semvertag.toml` file.
- FR25: User can run semvertag entirely via environment variables and CLI flags — the only supported configuration surface in v1.0.
- FR26: System reads provider-native credential environment variables (`CI_JOB_TOKEN`, `GITLAB_TOKEN`, `GITHUB_TOKEN`, `BITBUCKET_TOKEN`) as fallbacks when `SEMVERTAG_TOKEN` is unset.
- FR27: System resolves effective configuration with the precedence: CLI flags > environment variables > built-in defaults.
- FR28: When file-based configuration arrives in v1.x, the loader rejects templating constructs, env-var interpolation inside TOML values, and remote/URL-loaded config — exiting with configuration error (exit code 2). (Forward-compat policy.)

**Diagnostics & Validation**
- FR29: User can run `semvertag doctor` to validate token presence, token scopes, project access, default-branch detection, and protected-tag rules before first use.
- FR30: System reports each pre-flight check with a named, actionable cause on failure.
- FR31: User can run `semvertag doctor --json` to obtain machine-readable pre-flight status.
- FR32: System reports the resolved configuration source for each value (CLI / env / config / default) as part of doctor output, with secrets redacted.

**CLI Surface & Output**
- FR33: User invokes the primary action with no required positional arguments when running inside a recognized CI environment.
- FR34: User can override the active project via `--project-id` or the equivalent provider-native flag (`--repository`).
- FR35: User can request machine-readable output via `--json`, returning a schema-versioned envelope (top-level `schema_version` key).
- FR36: User can suppress non-error informational output during the run via `--quiet` — the final result is still emitted in the chosen output format.
- FR37: System uses stable, documented exit codes: 0 (success or intentional no-op), 1 (generic failure), 2 (configuration error), 3 (auth or permission error), 4 (provider API error).
- FR38: System writes informational output to stdout and error output to stderr with no interleaving.
- FR39: User can install shell completion for bash, zsh, fish, and PowerShell via `semvertag --install-completion`.

**CI Distribution**
- FR40: User can adopt semvertag in GitLab CI by including the published GitLab CI Catalog component (v1.0).
- FR41: User can adopt semvertag in GitHub Actions via the published Marketplace action wrapper (v1.0).
- FR42: User can invoke semvertag with zero installation footprint via `uvx semvertag` in any CI environment where `uv` is available.

**Documentation & Trust**
- FR43: User can read a published migration guide for switching from `semantic-release`, `go-semrel-gitlab`, or `RightBrain/auto-semver`, each with a config-mapping table.
- FR44: User can rely on the published API stability policy: CLI flags, config keys, exit codes, and JSON output schema are SemVer-stable post-1.0.
- FR45: User can discover semvertag via SEO-tuned README content and via published presence on the GitHub Actions Marketplace and GitLab CI Catalog.
- FR46: A contributor can set up a development environment using documented commands in `CONTRIBUTING.md` (`uv sync`, `uv run pytest`, `uv run ruff check`, `uv run ty check`) and run the full test suite offline using `httpx2.MockTransport` fixtures.

### NonFunctional Requirements

Source: `prd.md`. v1.x-specific NFRs noted; the rest apply to v1.0.

**Performance**
- NFR1: End-to-end CI runtime ≤30s at p95 for repos with <500 existing tags, on warm `uvx` cache + healthy provider API.
- NFR2: Cold-start `uvx semvertag --help` ≤5s on a fresh CI runner.
- NFR3: First-tag time <5 minutes median (new user, copy-pasted snippet).
- NFR4: `semvertag doctor` completes in ≤10s against a single project (all four checks).

**Reliability**
- NFR5: Idempotency — running on same commit twice produces no duplicate and exits 0 both times.
- NFR6: Exit 0 with informative message on every benign no-op (no merge commit, no conforming commit, already-tagged, no existing tags).
- NFR7: Retry transient provider failures (5xx, connection reset, 429) with exponential backoff + jitter — max 3 attempts, ≤30s total wall time — before exiting with code 4.
- NFR8: Fail-closed on auth/scope errors — never attempt tag creation when pre-flight cannot succeed. Exit 3 always paired with a named cause.
- NFR9: Shadow-mode parity with `raif-autosemver` on internal `pypelines` for ≥1 full release cycle (~2 weeks) with byte-identical tag outcomes before public v1.0.

**Security**
- NFR10: Tokens never written to stdout, stderr, log files, or `doctor` output — redacted to `***` or last 4 chars only.
- NFR11: Configuration sources local-only — no remote/URL-loaded config, no templating, no env-var interpolation in TOML (when v1.x ships).
- NFR12: `pip-audit` clean-report attestation per release; deps pinned in `uv.lock`.
- NFR13: PyPI publishing via trusted publishing (no long-lived API tokens in CI secrets).
- NFR14: Documented vulnerability-disclosure path in `SECURITY.md` — private reporting via GitHub Security Advisories, 90-day disclosure.

**Integration**
- NFR15: GitLab CE/EE 15.0+ (`gitlab.com` + self-hosted); tested against current major + previous major.
- NFR16: *(v1.x)* GitHub Enterprise Server 3.10+ supported.
- NFR17: *(v1.x)* Bitbucket Cloud only; Data Center out of scope.
- NFR18: Operates correctly inside documented CI environments: GitLab CI (16.0+), GitHub Actions (active runner), Bitbucket Pipelines (v1.x).
- NFR19: Honors provider-native context detection in canonical scenarios: GitLab + `CI_JOB_TOKEN`, GitLab + PAT, GitHub + `GITHUB_TOKEN`, Bitbucket + `BITBUCKET_TOKEN` (v1.x).
- NFR20: JSON output schema versioned and stable (`schema_version: "1.0"` at v1.0).

**Maintainability**
- NFR21: Core codebase (excluding tests/docs/generated) ≤1,500 lines of Python for v1.0 — soft target visible in CI.
- NFR22: ≥85% line coverage overall; bump-strategy parsing logic at 100% branch coverage; gated in CI.
- NFR23: `ty` clean (no `# ty: ignore` outside documented external boundaries); `ruff check` clean with the `ALL` ruleset.
- NFR24: Mean issue first-response time ≤7 days for the first 12 months post-launch.
- NFR25: Public CLI flag and config-key surface SemVer-stable post-1.0; breaking change requires one-minor-version deprecation + documented migration. Internal `_*.py`, `providers/*`, `strategies/*` NOT covered.
- NFR26: Dependency-update cadence ≥quarterly via `uv lock --upgrade` cron PR.

**Compatibility**
- NFR27: Python 3.10, 3.11, 3.12, 3.13 supported at launch; CI matrix on every PR.
- NFR28: Linux (Ubuntu latest LTS) is canonical; macOS and Windows best-effort (unit tests only).
- NFR29: Compatible with `uv` 0.5+ for `uvx` invocation.
- NFR30: Drops Python minor support no sooner than 12 months after upstream EOL; announced one minor release in advance.

### Additional Requirements

Architecture-level requirements that drive implementation. Source: `architecture.md`.

**Starter template (binding for Epic 1 Story 1):**
- **Scaffold from `modern-di` (structural template)** at `/Users/kevinsmith/src/pypi/modern-di`. Mirror verbatim: `Justfile`, `.readthedocs.yaml`, `docs/requirements.txt`, `LICENSE`. Adapt: `mkdocs.yml`, `.github/workflows/{ci.yml,publish.yml}`. Author fresh: `README.md`, `CLAUDE.md`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `action.yml`, GitLab CI Catalog descriptor, three `docs/migrating-from-*.md`.
- **Port behavior from existing `autosemver/`** (Raiffeisen-internal reference). Port the bump algorithm, DI wiring pattern, settings shape, and test cases — re-authored on the modern-di-shaped scaffolding, NOT moved in place.
- **Strip-before-publish:** Raiffeisen `Dockerfile`, hardcoded `https://gitlabci.raiffeisen.ru` default, internal Artifactory `[[tool.uv.index]]` blocks, `AUTOSEMVER_` → `SEMVERTAG_` env prefix.
- **Broaden Python floor:** current code is 3.13-only; must support 3.10–3.13.

**Technology stack (PRD-binding, Architecture-confirmed):**
- HTTP layer: **`httpx2`** (v2.2.0+ pinned defensively) replacing `python-gitlab`; **`httpx2.MockTransport`** for tests (replaces `requests-mock`). No per-provider SDK.
- DI: `modern-di-typer` (internal-only; not part of public CLI contract). Four Groups: `SettingsGroup`, `ProvidersGroup`, `StrategiesGroup`, `OutputsGroup`.
- Settings: `pydantic-settings` with single `Settings(BaseSettings)` root + nested `BaseModel` per-provider configs; `AliasChoices` for token fallback chain; `settings_customise_sources` for provenance recording (FR32).
- Output: `rich` (human) + stdlib `json.dumps` (machine). Two `rich.Console` instances per output impl for strict stdout/stderr split.
- Build: `uv_build` backend; `[project.scripts]` for `semvertag` console script; no optional-extras packaging (httpx2-for-all-providers removes the need).
- Versioning: `semver` package.

**Cross-cutting concerns (single-owner modules):**
- Retry & rate-limit (NFR7): custom `RetryingTransport(httpx2.BaseTransport)` in `semvertag/_transport.py` — the one place retries live.
- Token redaction (NFR10): `pydantic.SecretStr` + `semvertag/_redact.py` output-boundary scanner (patterns: `glpat-*`, `ghp_*`, `ATBB*`, generic ≥32 hex).
- Exit-code mapping (FR37, NFR25): typed exception hierarchy (`SemvertagError → ConfigError/AuthError/ProviderAPIError`) → `typer.Exit(code=N)` at **one** place in `__main__.py`.
- Config provenance (FR32): recorded in `Settings._provenance` at resolution time; consumed by doctor.
- Stream discipline (FR38): two `rich.Console` instances in `_output.py` only.

**Repository structure (full tree specified in `architecture.md` §Project Structure):**
- Source: `semvertag/` (flat, no `src/`) with `_types.py`, `_errors.py`, `_settings.py`, `_transport.py`, `_redact.py`, `_output.py`, `_use_case.py`, `ioc.py`, `__main__.py`, `providers/`, `strategies/`, `doctor/`.
- Tests: `tests/unit/` + `tests/integration/` mirroring source layout; shared `conftest.py` with `httpx2.MockTransport` fixtures and `compose_handler` helper.
- Trust-surface: `.github/workflows/{ci.yml,publish.yml}`, `.github/ISSUE_TEMPLATE/` (including `new_provider_request.md`), `.gitlab/catalog/component.yml`, `action.yml`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `LICENSE`, `README.md`, `Justfile`, `pyproject.toml`, `uv.lock`, `context7.json`, `CLAUDE.md`, `.readthedocs.yaml`, `mkdocs.yml`.
- Docs: `docs/index.md`, `docs/cli-reference.md`, `docs/strategies/{branch-prefix,conventional-commits}.md`, `docs/providers/{gitlab,github,bitbucket}.md`, `docs/doctor.md`, `docs/api-stability.md`, `docs/contributing/{dev-setup,adding-a-provider}.md`, three `docs/migrating-from-*.md`.

**Implementation sequencing (informs epic/story order):**
1. Bootstrap scaffolding from modern-di + strip Raiffeisen + Python floor broadening.
2. `Settings` class with nested per-provider models + `AliasChoices` chain + provenance recording.
3. Error hierarchy + `RunResult` + `RichOutput` + `JsonOutput`.
4. `RetryingTransport`.
5. `GitLabProvider` against the four GitLab endpoints.
6. `BranchPrefixStrategy` + `ConventionalCommitsStrategy` (100% branch coverage gate).
7. DI wiring (Groups) + Typer entrypoint.
8. `doctor` subcommand.
9. Trust-surface scaffolding (CI, publish, mkdocs, migration guides, `action.yml`, GitLab Catalog descriptor, `pip-audit` job, quarterly `uv lock --upgrade` cron).
10. External shadow-mode in `pypelines` against `raif-autosemver` (NFR9).

**Implementation patterns (binding for all AI-agent PRs; full list in `architecture.md` §Implementation Patterns):**
- Frozen dataclasses with `kw_only=True, slots=True` for all domain types.
- `typing.Final` on module-level constants.
- One file per provider (`providers/<vendor>.py`) and one file per strategy.
- Error template: `<NamedCondition>: <Cause>. <SuggestedAction>.`
- `pydantic.SecretStr` for token fields; output routed through `_redact.py`.
- No `print()` outside `_output.py`; no `from __future__ import annotations`; no bare `Exception` catches.
- Global imports per `CLAUDE.md`; lazy imports only at the `ioc.py` provider-selection boundary.
- `# ty: ignore` (not `# type: ignore`).

### UX Design Requirements

Not applicable — semvertag is a non-interactive CLI tool with no graphical user interface.

### FR Coverage Map

v1.0-scope FRs only. v1.x deferred FRs (FR13, FR16, FR18, FR19, FR23, FR24) and v1.x integration NFRs (NFR16, NFR17) are out of scope for this epic breakdown.

| FR | Epic | Brief |
|---|---|---|
| FR1 | Epic 1 | Create semver tag on default branch's latest commit |
| FR2 | Epic 1 | Read most recent commit to determine bump candidacy |
| FR3 | Epic 1 | Skip without error when no merge / no conforming signal |
| FR4 | Epic 1 | Skip without error when commit already tagged |
| FR5 | Epic 1 | Report tag name, commit SHA, strategy |
| FR6 | Epic 1 | Idempotent reruns |
| FR7 | Epic 1 | Handle zero pre-existing tags |
| FR8 | Epic 1 | Ignore non-semver-conforming tags |
| FR9 | Epic 1 | Detect default branch via provider API + `SEMVERTAG_DEFAULT_BRANCH` override |
| FR10 | Epic 1 | Operate on shallow CI clones via provider API |
| FR11 | Epics 1 + 2 | Strategy selection (wiring in Epic 1; second strategy lands in Epic 2) |
| FR12 | Epic 1 | Parse GitFlow branch prefixes |
| FR14 | Epic 2 | Parse Conventional Commits headers |
| FR15 | Epic 2 | Detect major via `!` suffix / `BREAKING CHANGE:` footer |
| FR17 | Epic 1 | Create tags via GitLab REST API |
| FR20 | Epic 1 | Auto-detect provider from CI env / git remote |
| FR21 | Epic 1 | Override provider via `--provider` |
| FR22 | Epic 1 | Provider protocol seam, single file per provider |
| FR25 | Epic 1 | Env + CLI flags as v1.0 config surface |
| FR26 | Epic 1 | Provider-native credential fallbacks via `AliasChoices` |
| FR27 | Epic 1 | CLI > env > defaults precedence |
| FR28 | Epic 4 | Forward-compat policy for v1.x TOML loader (docs only) |
| FR29 | Epic 3 | `semvertag doctor` validates pre-flight |
| FR30 | Epic 3 | Named, actionable cause on failure |
| FR31 | Epic 3 | `doctor --json` machine-readable form |
| FR32 | Epic 3 | Doctor reports resolved config source, secrets redacted |
| FR33 | Epic 1 | Zero-arg invocation in recognized CI environment |
| FR34 | Epic 1 | `--project-id` / `--repository` override |
| FR35 | Epic 1 | `--json` with `schema_version` envelope |
| FR36 | Epic 1 | `--quiet` composes with `--json`, suppresses non-error narrative |
| FR37 | Epic 1 | Stable exit codes 0–4 |
| FR38 | Epic 1 | stdout / stderr discipline, no interleaving |
| FR39 | Epic 1 | `--install-completion` for bash/zsh/fish/powershell |
| FR40 | Epic 4 | GitLab CI Catalog component |
| FR41 | Epic 4 | GitHub Actions Marketplace action |
| FR42 | Epic 1 | `uvx semvertag` zero-install path |
| FR43 | Epic 4 | Three migration guides (`semantic-release`, `go-semrel-gitlab`, RightBrain) |
| FR44 | Epic 4 | Published API stability policy |
| FR45 | Epic 4 | README SEO + Marketplace + Catalog listings |
| FR46 | Epic 4 | `CONTRIBUTING.md` with 4-command dev setup; offline tests via `httpx2.MockTransport` |

### NFR Coverage (cross-cutting)

| NFR | Epic | Anchor |
|---|---|---|
| NFR1 (≤30s p95) | Epic 1 | Per-request timeout × retry budget math |
| NFR2 (≤5s cold start `--help`) | Epic 1 | `uvx` + import-graph discipline |
| NFR3 (<5min first-tag median) | Epic 4 | README hero + doctor docs |
| NFR4 (≤10s doctor) | Epic 3 | Sequential chain budget |
| NFR5, NFR6 (idempotency, benign no-ops) | Epic 1 | `RunResult.status` enum + Epic 2 (conv-commits no-conforming) |
| NFR7 (retry budget) | Epic 1 | `RetryingTransport` |
| NFR8 (fail-closed auth) | Epic 1 | `AuthError` exit code 3 |
| NFR9 (shadow-mode parity) | Epic 4 | External `pypelines` validation cycle |
| NFR10 (token redaction) | Epic 1 | `SecretStr` + `_redact.py` |
| NFR11 (no remote config) | Epic 4 | Docs + forward-compat policy |
| NFR12 (pip-audit) | Epic 4 | CI job |
| NFR13 (trusted publishing) | Epic 4 | `publish.yml` workflow |
| NFR14 (SECURITY.md) | Epic 4 | Vulnerability disclosure docs |
| NFR15 (GitLab CE/EE 15.0+) | Epic 1 | REST API choice + version tests |
| NFR18 (CI environments) | Epics 1 + 4 | GitLab CI + GitHub Actions runtime |
| NFR19 (provider-native context) | Epic 1 | `AliasChoices` chain |
| NFR20 (JSON schema versioned) | Epic 1 | `schema_version: "1.0"` envelope |
| NFR21 (≤1500 LOC core) | Epics 1 + 4 | Soft target visible; LOC gate in CI |
| NFR22 (≥85% line / 100% branch on bump) | Epics 1 + 2 | Coverage gates on both strategies |
| NFR23 (`ty` + `ruff ALL`) | Epic 1 | Lint config from day 1 |
| NFR24 (≤7d issue first-response) | Epic 4 | Process commitment + docs |
| NFR25 (SemVer stability post-1.0) | Epic 4 | API stability policy doc |
| NFR26 (quarterly dep update) | Epic 4 | Scheduled `uv lock --upgrade` cron |
| NFR27 (Python 3.10–3.13) | Epic 1 | Floor broadened from 3.13-only; matrix in CI |
| NFR28 (Linux primary) | Epic 1 | CI on `ubuntu-latest` |
| NFR29 (uv 0.5+) | Epic 1 | `astral-sh/setup-uv@v3` |
| NFR30 (Python EOL+12mo drop) | Epic 4 | Documented in API stability page |

## Epic List

### Epic 1: Foundation & First Auto-Tag (GitLab + branch-prefix)

A user can run `uvx semvertag` inside a GitLab CI job and get a semver tag created on the default branch via the branch-prefix strategy — with stable exit codes, token redaction, stdout/stderr discipline, `--json` output, and `--quiet` composability. The repo has modern-di-shaped scaffolding (Justfile, pyproject.toml, basic CI, lint config) ready for downstream epics. All Provider-protocol methods (main verb + `check_*` for later doctor use) are implemented on `GitLabProvider`.

**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR7, FR8, FR9, FR10, FR11 (selection mechanism), FR12, FR17, FR20, FR21, FR22, FR25, FR26, FR27, FR33, FR34, FR35, FR36, FR37, FR38, FR39, FR42

### Epic 2: Conventional Commits Strategy & Per-Repo Switching

A mid-migration team lead (Marina, PRD Journey 2) can flip a single GitLab pilot project to conventional-commits via a project-level `SEMVERTAG_STRATEGY` CI variable — no code change, no toolchain swap. Adds the `ConventionalCommitsStrategy` parser including major-bump detection via `!` suffix and `BREAKING CHANGE:` footer (absent from existing internal `autosemver/`), finalizes per-repo selection wiring with the second strategy actually present, and gates 100% branch coverage on the new strategy.

**FRs covered:** FR14, FR15 (finalizes FR11's per-repo switching with the second strategy real)

### Epic 3: Pre-flight Diagnostics (`semvertag doctor`)

A first-time user (Petr, PRD Journey 1) can run `semvertag doctor` before their first real CI invocation and get a named, actionable list of what's missing — token, scopes, project access, protected-tag rules — with config-source provenance and a `--json` variant for CI dashboards. Adds `doctor/_checks.py` chain runner with sequential skip-on-failure semantics, exit-code dominance resolver (3 > 4 > 2 > 1), and the `semvertag doctor` Typer subcommand consuming Provider's `check_*` methods established in Epic 1.

**FRs covered:** FR29, FR30, FR31, FR32

### Epic 4: Public-Launch Readiness — Trust Surface, Distribution & Shadow-Mode

External users (Dani-style tag-only adopters via Marketplace; Sasha-style contributors) can discover, install, and contribute to semvertag. Internal Raiffeisen pipelines continue working with byte-identical tag outcomes (NFR9 shadow-mode validation). v1.0 is announceable. Adds full CI polish (pytest matrix 3.10–3.13, codecov, `pip-audit`, LOC gate), publish workflow via PyPI trusted publishing, mkdocs+Material at ReadTheDocs, three migration guides, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `action.yml`, `.gitlab/catalog/component.yml`, API stability policy doc, README hero with SEO + badges, issue templates including `new_provider_request.md`, quarterly `uv lock --upgrade` cron, and shadow-mode validation in `pypelines` against `raif-autosemver` for ≥1 release cycle.

**FRs covered:** FR28 (docs only), FR40, FR41, FR43, FR44, FR45, FR46

## Epic 1: Foundation & First Auto-Tag (GitLab + branch-prefix)

A user can run `uvx semvertag` inside a GitLab CI job and get a semver tag created on the default branch via the branch-prefix strategy — with stable exit codes, token redaction, stdout/stderr discipline, `--json` output, and `--quiet` composability. The repo has modern-di-shaped scaffolding ready for downstream epics.

### Story 1.1: Bootstrap public semvertag scaffolding from modern-di shape

As a project maintainer,
I want a public-OSS-ready repository skeleton mirrored from `modern-di`'s structure with Raiffeisen artefacts stripped and the Python floor broadened to 3.10,
So that downstream stories can implement semvertag's logic onto clean, conventional scaffolding without dragging company-internal files forward.

**Acceptance Criteria:**

**Given** a fresh greenfield checkout
**When** I follow the bootstrap recipe
**Then** `pyproject.toml` is authored modeled on `/Users/kevinsmith/src/pypi/modern-di/pyproject.toml`, with `[project]` set for semvertag, `[project.scripts]` declaring `semvertag = "semvertag.__main__:main"`, `requires-python = ">=3.10,<3.14"`, and **no** `[[tool.uv.index]]` Artifactory blocks
**And** `Justfile`, `.readthedocs.yaml`, `docs/requirements.txt`, and `LICENSE` (MIT) are copied verbatim from `/Users/kevinsmith/src/pypi/modern-di`
**And** `mkdocs.yml` is adapted (theme preserved, minimal `nav:` declaring only `index.md` so `mkdocs build` succeeds against the empty scaffolding — the full nav structure is filled in by Story 4.4 once the pages exist)
**And** `.github/workflows/ci.yml` is adapted to lint on Python 3.10 and run pytest matrix on Python 3.10–3.13 on `ubuntu-latest`

**Given** the scaffolding is in place
**When** I search the repo for Raiffeisen artefacts
**Then** no `Dockerfile`, no `https://gitlabci.raiffeisen.ru` literal, no `AUTOSEMVER_` env-var reference, and no internal Artifactory `[[tool.uv.index]]` block survives anywhere

**Given** the package directory is named `semvertag/`
**When** I run `python -c "import semvertag"` after `just install`
**Then** the import succeeds (the package body is minimal — `__init__.py` and `py.typed`)
**And** `just lint` passes on the empty scaffolding

### Story 1.2: Settings layer with token AliasChoices chain and source provenance

As a CLI user,
I want semvertag to resolve configuration from `SEMVERTAG_TOKEN`, falling back to provider-native variables (`CI_JOB_TOKEN`, `GITLAB_TOKEN`) automatically, and to track which source supplied each value,
So that I can run `uvx semvertag` in any documented CI environment with zero additional configuration, and so that `semvertag doctor` (downstream) can show me where each effective value came from.

**Acceptance Criteria:**

**Given** `Settings(BaseSettings)` is defined with `env_prefix="SEMVERTAG_"` and `env_nested_delimiter="__"`
**When** I instantiate `Settings()` with no environment variables set
**Then** `settings.provider == "gitlab"`, `settings.strategy == "branch-prefix"`, and `settings.gitlab.token.get_secret_value() == ""`

**Given** only `CI_JOB_TOKEN` is set in the environment
**When** I instantiate `Settings()`
**Then** `settings.gitlab.token.get_secret_value()` equals `CI_JOB_TOKEN`'s value (via `AliasChoices` fallback) and `_provenance["gitlab.token"].detail == "CI_JOB_TOKEN"`

**Given** both `SEMVERTAG_TOKEN` and `GITLAB_TOKEN` are set
**When** I instantiate `Settings()`
**Then** `settings.gitlab.token` resolves from `SEMVERTAG_TOKEN` (higher precedence in `AliasChoices`)

**Given** Settings is instantiated and provenance is recorded
**When** I overlay CLI flags via `.model_copy(update={"strategy": "conventional-commits"})` and re-record provenance
**Then** `_provenance["strategy"]` reflects `ConfigSource(layer="cli", detail="--strategy")`

**Given** both `SEMVERTAG_TOKEN` is set in the environment and a `--token` CLI flag is supplied with a different value
**When** Settings is instantiated and the CLI overlay is applied
**Then** `settings.gitlab.token.get_secret_value()` equals the `--token` flag value (CLI beats env per FR27)
**And** `_provenance["gitlab.token"]` reflects `ConfigSource(layer="cli", detail="--token")`

**Given** a token value is set
**When** the Settings object is printed or logged via standard `repr()`
**Then** the token value never appears in the output (uses `pydantic.SecretStr`)

**Given** unit tests in `tests/unit/test_settings.py` and `tests/unit/test_provenance.py`
**When** the test suite runs
**Then** `AliasChoices` precedence, nested env-var resolution (`SEMVERTAG_GITLAB__ENDPOINT`), default fallbacks, CLI overlay, and every provenance entry are each covered

### Story 1.3: Typed error hierarchy + RunResult + RichOutput + JsonOutput + redaction

As a CI pipeline operator,
I want semvertag's output cleanly split between human-readable Rich output (stdout) and machine-readable JSON envelopes (`--json` on stdout), with errors always on stderr, tokens redacted everywhere, and a stable `schema_version` on JSON output,
So that I can pipe `--json` to `jq` without error chatter contaminating my parser, and so I can build CI dashboards on a stable JSON contract.

**Acceptance Criteria:**

**Given** `_errors.py` defines the exception hierarchy
**When** I import `SemvertagError`, `ConfigError`, `AuthError`, `ProviderAPIError`
**Then** each subclass has its `exit_code` class attribute set to 1, 2, 3, and 4 respectively, with `SemvertagError.exit_code == 1` as the generic default

**Given** `_types.py` defines `RunResult` as a frozen dataclass with `kw_only=True, slots=True`
**When** I serialize `RunResult(strategy="conventional-commits", bump="minor", status="created", tag="2.1.0", commit="a2b4d12", reason=None)` via `json.dumps(dataclasses.asdict(...))`
**Then** the output's first key is `"schema_version": "1.0"`, all keys are snake_case, and unset optional fields are emitted as `null` (not omitted)

**Given** `RichOutput` is constructed with two `rich.Console` instances (one stdout, one stderr)
**When** I call `output.progress("Detected strategy: branch-prefix")` and then `output.emit(result)`
**Then** the progress line and the final lines are written to stdout, never to stderr, with no interleaving from the error console
**And when** `--quiet` is active
**Then** `progress()` becomes a no-op but `emit()` still renders the final result

**Given** `JsonOutput` is constructed
**When** I call `output.progress("anything")`
**Then** nothing is written to stdout (no-op regardless of `--quiet`)
**And when** I call `output.emit(result)`
**Then** exactly one line of `json.dumps(dataclasses.asdict(result))` is written to stdout

**Given** `_redact.py` defines pattern matchers for `glpat-*`, `ghp_*`, `ATBB*`, and generic ≥32-char hex
**When** I call `redact("Token is glpat-AbCdEf1234567890 here")`
**Then** the GitLab token pattern is replaced with `***` or last-4 only
**And when** any of the other patterns appear, they are also redacted

**Given** unit tests in `tests/unit/test_errors.py`, `test_output_rich.py`, `test_output_json.py`, `test_redact.py`
**When** the test suite runs
**Then** exit-code mapping, `RunResult` envelope serialization, stdout/stderr discipline, `--quiet` × `--json` matrix, and token pattern detection are each covered

### Story 1.4: RetryingTransport with NFR7 retry policy

As a CI pipeline operator,
I want semvertag to automatically retry transient provider API failures (5xx, connection reset, 429) with exponential backoff and a bounded wall budget,
So that my CI doesn't fail on a momentary GitLab API hiccup, but also doesn't hang indefinitely.

**Acceptance Criteria:**

**Given** `_transport.py` defines `RetryingTransport(httpx2.BaseTransport)` with `MAX_ATTEMPTS = 3`, `MAX_WALL_SECONDS = 30.0`, and `BACKOFF_BASE_SECONDS = 1.0` as `typing.Final` constants
**When** a wrapped request encounters HTTP 500
**Then** the transport retries up to 3 attempts total with exponential backoff (base 1s × 2^n) plus full jitter

**Given** a wrapped request encounters HTTP 429 with `Retry-After` in seconds form
**When** the transport handles the response
**Then** the next attempt waits at least the `Retry-After` seconds before firing
**And when** `Retry-After` is in HTTP-date form, it is parsed correctly

**Given** the 30-second wall budget
**When** cumulative time including backoffs would exceed the budget
**Then** the transport stops retrying and surfaces the last response or exception to the caller

**Given** an `httpx2.ConnectError`, `ReadTimeout`, `WriteTimeout`, or `RemoteProtocolError` occurs
**When** the transport handles the exception
**Then** it retries per the same policy

**Given** an HTTP 4xx response (excluding 408 and 429) is returned
**When** the transport handles the response
**Then** it does NOT retry — the response is returned for translation into `AuthError` (401/403) or `ConfigError` (404/422) downstream

**Given** unit tests in `tests/unit/test_transport_retry.py` using `httpx2.MockTransport` to simulate sequences (500 → 500 → 200; 429 + Retry-After → 200; 503 × 3 → exhaustion; ConnectError → 200)
**When** the test suite runs
**Then** retry budget arithmetic, backoff timing, `Retry-After` honoring, exhaustion-then-raise behavior, and the non-retry of static 4xx are each covered

### Story 1.5: GitLabProvider against four endpoints via httpx2

As a GitLab CI user,
I want semvertag to fetch the default branch, latest commit on that branch, list of existing tags, and to create a new tag against the GitLab REST API — and to check token / scopes / project access / protected-tag rules on demand,
So that I have a working primary provider before bump-strategy alternatives and the doctor subcommand wire everything together.

**Acceptance Criteria:**

**Given** `providers/_base.py` defines the `Provider` protocol with main-verb methods (`get_default_branch`, `get_latest_commit_on_default_branch`, `list_tags`, `create_tag`) and doctor methods (`check_token`, `check_scopes`, `check_project_access`, `check_protected_tags`)
**When** I implement `providers/gitlab.py:GitLabProvider`
**Then** it is a frozen dataclass with `slots=True, kw_only=True` carrying a `GitLabConfig` and an `httpx2.Client` constructed with `RetryingTransport`, with `name: typing.ClassVar[str] = "gitlab"`, satisfying the `Provider` protocol structurally

**Given** GitLab responds to `GET /api/v4/projects/{id}` with `{"default_branch": "main", ...}`
**When** `provider.get_default_branch()` is called
**Then** it returns `"main"`

**Given** `GET /repository/commits?ref_name=main` returns a list with the latest commit first
**When** `provider.get_latest_commit_on_default_branch()` is called
**Then** it returns a `Commit(sha=..., message=...)` frozen dataclass

**Given** `GET /repository/tags` returns a paginated list including non-semver tags like `release-2024-Q1`
**When** `provider.list_tags()` is called
**Then** it returns all tags as `list[Tag]` — semver filtering happens downstream in the use case (FR8)

**Given** the API returns HTTP 401
**When** any main-verb method is called
**Then** it raises `AuthError("Token rejected: 401. Verify SEMVERTAG_TOKEN is valid and has 'api' scope.")` matching the named-condition template

**Given** the API returns HTTP 403 with body indicating missing scope
**When** the call is made
**Then** it raises `AuthError("Token missing scope: 'write_repository'. Add it to the SEMVERTAG_TOKEN scopes on GitLab.")` per the template

**Given** `POST /repository/tags` succeeds with HTTP 201
**When** `provider.create_tag(name="1.4.3", commit_sha="a2b4d12")` is called
**Then** the request payload contains `{"tag_name": "1.4.3", "ref": "a2b4d12"}` and no exception is raised

**Given** doctor methods are implemented (consumed later in Epic 3)
**When** `provider.check_token()` is called against a valid token
**Then** it returns `CheckResult(name="token", status="passed", cause="Token recognized by GitLab API.")`

**Given** integration tests in `tests/integration/test_gitlab_provider.py` use the shared `httpx2.MockTransport` fixture and `compose_handler` helper from `tests/conftest.py`
**When** the test suite runs
**Then** all four main-verb endpoints, all four doctor endpoints, and the error-translation paths (401/403/404/422/429/5xx) are each covered

### Story 1.6: BranchPrefixStrategy with 100% branch coverage

As a user on a GitFlow-style repo,
I want semvertag to parse merge commit messages for `feature/`, `bugfix/`, `hotfix/` branch prefixes and decide the bump level accordingly,
So that my existing GitFlow workflow keeps producing semver tags without changing my commit conventions.

**Acceptance Criteria:**

**Given** `strategies/_base.py` defines the `BumpStrategy` protocol and `_types.py` defines `Bump` enum (`NONE`, `PATCH`, `MINOR`, `MAJOR`)
**When** I implement `strategies/branch_prefix.py:BranchPrefixStrategy`
**Then** it is a frozen dataclass carrying a `BranchPrefixConfig`, with `name: typing.ClassVar[str] = "branch-prefix"`, satisfying `BumpStrategy` structurally

**Given** the default config (`minor=("feature/",)`, `patch=("bugfix/", "hotfix/")`, `merge_mark_text="Merge branch"`)
**When** `strategy.decide(Commit(sha="...", message="Merge branch 'feature/new-thing' into main"))` is called
**Then** it returns `Bump.MINOR`
**And when** the message contains `'bugfix/'` or `'hotfix/'`, it returns `Bump.PATCH`
**And when** the message contains no recognized prefix or is not a merge commit, it returns `Bump.NONE`

**Given** the strategy has no major mapping (major bumps require conventional-commits per architecture)
**When** any branch prefix is encountered
**Then** `Bump.MAJOR` is never returned

**Given** unit tests in `tests/unit/test_branch_prefix_strategy.py`
**When** `pytest --cov=semvertag.strategies.branch_prefix --cov-branch --cov-fail-under=100` is run in CI
**Then** the test passes — every branch in the parser is exercised
**And** the same gate is wired into `just test-branch` per architecture conventions

### Story 1.7: Wire DI groups + Typer entrypoint to deliver the `uvx semvertag` flow

As a GitLab CI user,
I want to run `uvx semvertag` (or `semvertag --json --quiet`) inside a GitLab CI job and get a semver tag created on the default branch, with stable exit codes and proper stream discipline,
So that I have a working end-to-end product for Journey 1 before bump-strategy alternatives, doctor, and trust-surface land.

**Acceptance Criteria:**

**Given** `ioc.py` defines `SettingsGroup`, `ProvidersGroup`, `StrategiesGroup`, `OutputsGroup` (all `modern_di.Group` subclasses) with lazy `Factory` resolution
**When** `ALL_GROUPS: typing.Final[list[type[modern_di.Group]]]` is exported
**Then** only the active provider and strategy Factory is resolved per CLI run (lazy imports at the provider-selection boundary)

**Given** `_use_case.py:SemvertagUseCase` orchestrates `Provider + BumpStrategy + Output`
**When** `use_case.run()` is invoked against a GitLab project where the latest commit on main is `Merge branch 'feature/foo' into main` and the most recent semver tag is `1.4.2`
**Then** the use case calls `provider.get_default_branch()`, `provider.get_latest_commit_on_default_branch()`, `provider.list_tags()`, `strategy.decide(commit) → Bump.MINOR`, computes `1.5.0`, calls `provider.create_tag(name="1.5.0", commit_sha=...)`, and emits `RunResult(status="created", tag="1.5.0", ...)`

**Given** the latest commit is already tagged
**When** `use_case.run()` is invoked
**Then** it emits `RunResult(status="already_tagged", ...)` and `__main__.py` exits 0

**Given** the latest commit is not a merge commit
**When** `use_case.run()` is invoked
**Then** it emits `RunResult(status="no_merge_commit", ...)` and exits 0

**Given** the repo has zero pre-existing tags
**When** `use_case.run()` is invoked
**Then** it emits `RunResult(status="no_tags", ...)` and exits 0

**Given** `__main__.py` is the Typer entrypoint declared in `[project.scripts]` as `semvertag = "semvertag.__main__:main"`
**When** I invoke `semvertag --help`
**Then** the help lists at minimum `--project-id`, `--strategy`, `--provider`, `--token`, `--default-branch`, `--gitlab-endpoint`, `--request-timeout`, `--json`, `--quiet`, `--install-completion`, `--version`

**Given** any `SemvertagError` subclass is raised during `use_case.run()`
**When** `__main__.py`'s callback catches it
**Then** the redacted error message is printed to stderr and `typer.Exit(code=err.exit_code)` raises — propagating exit codes 1, 2, 3, or 4 per FR37 (single point of exception → exit-code conversion)

**Given** integration tests in `tests/integration/test_cli_main_verb.py` and `test_cli_quiet_json_matrix.py` use `typer.testing.CliRunner` with `httpx2.MockTransport` injected at client construction
**When** the test suite runs
**Then** the four cells of `(--quiet, --json)` × `(presence, absence)` are exercised; the five exit codes (0 created, 0 no-op, 1, 2, 3, 4) are each covered; FR3/FR4/FR6/FR7 edge cases are covered

**Given** `just test` is run from a fresh checkout
**When** the full suite completes
**Then** unit + integration tests pass; `pytest --cov` reports ≥85% line coverage and 100% branch coverage on `strategies/branch_prefix.py`

## Epic 2: Conventional Commits Strategy & Per-Repo Switching

A mid-migration team lead (Marina, PRD Journey 2) can flip a single GitLab pilot project from `branch-prefix` to `conventional-commits` via a project-level `SEMVERTAG_STRATEGY` CI variable — no code change, no toolchain swap. Adds the parser (including the major-bump detection that's absent from the existing internal `autosemver/`) and finalizes the per-repo strategy-selection wiring stubbed in Epic 1.

### Story 2.1: Add ConventionalCommitsStrategy with `!` / `BREAKING CHANGE:` major detection and wire SEMVERTAG_STRATEGY switching end-to-end

As a platform engineer mid-migration from GitFlow to Conventional Commits,
I want to flip a single pilot repo to the `conventional-commits` strategy by setting `SEMVERTAG_STRATEGY=conventional-commits` as a project-level CI variable,
So that I can migrate one repo at a time without changing tools or commit conventions on the legacy repos.

**Acceptance Criteria:**

**Given** `strategies/conventional_commits.py:ConventionalCommitsStrategy` is implemented as a frozen dataclass carrying a `ConventionalCommitsConfig`
**When** I inspect the class
**Then** it has `name: typing.ClassVar[str] = "conventional-commits"`, satisfies the `BumpStrategy` protocol structurally, and matches the one-file-per-strategy pattern established in Epic 1

**Given** the default config (`minor_types=("feat",)`, `patch_types=("fix", "perf")`)
**When** `strategy.decide(Commit(sha="...", message="feat: add new thing"))` is called
**Then** it returns `Bump.MINOR`
**And when** the message starts with `fix:` or `perf:`, it returns `Bump.PATCH`
**And when** the message starts with an unrecognized type (e.g., `chore:`, `docs:`, `Fixed thing`), it returns `Bump.NONE`

**Given** the message contains `!` suffix on the type (e.g., `feat!: drop python 3.9`)
**When** `strategy.decide(...)` is called
**Then** it returns `Bump.MAJOR`

**Given** the message body contains a `BREAKING CHANGE:` footer (e.g., `feat: new thing\n\nBREAKING CHANGE: old thing removed`)
**When** `strategy.decide(...)` is called
**Then** it returns `Bump.MAJOR`

**Given** the message has both `feat:` and a `BREAKING CHANGE:` footer
**When** `strategy.decide(...)` is called
**Then** `Bump.MAJOR` wins over `Bump.MINOR` (precedence documented in `docs/conventional-commits.md` per architecture)

**Given** `ioc.py:StrategiesGroup` currently exposes `branch_prefix_strategy` only (from Epic 1)
**When** Story 2.1 lands
**Then** a `conventional_commits_strategy = modern_di.providers.Factory(...)` factory is added to the same Group, and `__main__.py`'s strategy-selection dispatch resolves the active Factory based on `settings.strategy`

**Given** the integration test scaffolding established in Epic 1
**When** I set `SEMVERTAG_STRATEGY=conventional-commits` and invoke `semvertag` against a GitLab fixture where the latest commit is `feat: add foo`
**Then** the run emits `RunResult(strategy="conventional-commits", bump="minor", status="created", tag=...)` and exits 0
**And when** the same fixture's commit is `feat!: breaking change`
**Then** `bump="major"` and the new tag reflects a major bump

**Given** the latest commit is `Fixed thing` (no conforming Conventional Commits header) and `SEMVERTAG_STRATEGY=conventional-commits`
**When** `semvertag` is invoked
**Then** it emits `RunResult(status="no_conforming_commit", reason="No conforming Conventional Commits type found in commit message.")` and exits 0 — graceful skip per NFR6 / FR3

**Given** unit tests in `tests/unit/test_conventional_commits_strategy.py`
**When** `pytest --cov=semvertag.strategies.conventional_commits --cov-branch --cov-fail-under=100` runs in CI
**Then** every branch of the parser is exercised — including `feat:` / `fix:` / `perf:` happy paths, `!` suffix, `BREAKING CHANGE:` footer, both-set precedence, unrecognized type, malformed header, multi-paragraph body

**Given** new integration test `tests/integration/test_strategy_switching.py`
**When** the test suite runs
**Then** Marina's narrative is exercised: same project, same fixture, two runs with different `SEMVERTAG_STRATEGY` values — different bump outcomes

## Epic 3: Pre-flight Diagnostics (`semvertag doctor`)

A first-time user (Petr, PRD Journey 1) can run `semvertag doctor` before their first real CI invocation and get a named, actionable list of what's missing — token, scopes, project access, protected-tag rules — with config-source provenance and a `--json` variant for CI dashboards. Consumes the `check_*` methods already implemented on `GitLabProvider` in Story 1.5, so this epic does not modify `providers/gitlab.py`.

### Story 3.1: Doctor chain runner with skip-on-failure semantics and exit-code dominance

As a CLI engineer wiring up doctor,
I want a pure-Python chain runner that executes the four Provider `check_*` methods in sequence, marks dependents as `skipped` when their prerequisites fail, and resolves the dominant exit code from the accumulated results,
So that Story 3.2 can wrap a thin Typer subcommand around stable, unit-tested orchestration logic.

**Acceptance Criteria:**

**Given** `doctor/_checks.py` defines `run_checks(provider: Provider) -> list[CheckResult]`
**When** I call it against a provider where `check_token()` returns `status="passed"` and `check_scopes()`, `check_project_access()`, `check_protected_tags()` all return `status="passed"`
**Then** it returns four `CheckResult` items, all with `status="passed"`, in the declared order: token → scopes → project_access → protected_tags

**Given** the same provider where `check_token()` returns `status="failed"` with `cause="Token rejected: 401. Verify SEMVERTAG_TOKEN."`
**When** `run_checks(provider)` is called
**Then** it returns four items: the first is `failed` with the original cause; the remaining three are `status="skipped"` each with `cause="Skipped: blocked by token check."`
**And** none of `check_scopes()`, `check_project_access()`, `check_protected_tags()` are invoked

**Given** `doctor/_checks.py` also defines `resolve_exit_code(results: list[CheckResult]) -> int`
**When** all results are `status="passed"`
**Then** it returns 0

**Given** mixed results where one `failed` carries an `AuthError`-mapped cause, another carries a `ProviderAPIError`-mapped cause, and the rest are `skipped`
**When** `resolve_exit_code(results)` is called
**Then** it returns 3 (the dominant code per architecture's `3 > 4 > 2 > 1` ordering)

**Given** a `failed` result whose cause does not map to any specific `SemvertagError` subclass
**When** `resolve_exit_code(results)` is called
**Then** it returns 1 (generic failure)

**Given** unit tests in `tests/unit/test_doctor_checks.py` use a stub `Provider` implementation whose `check_*` methods return canned `CheckResult` values
**When** the test suite runs
**Then** every chain ordering (all-passed, fail-at-step-1, fail-at-step-2, fail-at-step-3, fail-at-step-4) is exercised
**And** every cell of the exit-code dominance table (0, 1, 2, 3, 4, and multi-fail-dominance) is exercised
**And** no test reaches into `httpx2` or makes real network calls — the stub Provider is sufficient

### Story 3.2: `semvertag doctor` Typer subcommand with config-source renderer and JSON form

As a first-time GitLab CI user,
I want to run `semvertag doctor` (or `semvertag doctor --json`) and see, in one place, which CI variables are wired up, where each effective config value came from, and which pre-flight checks pass or fail with named actionable causes,
So that I can fix problems before my first real `semvertag` invocation and feed the output into CI dashboards.

**Acceptance Criteria:**

**Given** `doctor/_render.py` defines a `DoctorResult` frozen dataclass with `kw_only=True, slots=True` carrying `schema_version: str = "1.0"`, `configuration: dict[str, ConfigSourceView]` (redacted), and `checks: list[CheckResult]`
**When** I serialize a `DoctorResult` via `json.dumps(dataclasses.asdict(...))`
**Then** the output's first key is `"schema_version": "1.0"`, all keys are snake_case, and token values are rendered as `***` or last-4 only

**Given** `__main__.py` registers a `doctor` subcommand on the Typer app
**When** I invoke `semvertag doctor --help`
**Then** the help text describes the four checks and shows `--json` as a flag

**Given** a healthy GitLab project (all four checks pass) and `SEMVERTAG_TOKEN` set
**When** I run `semvertag doctor` with no `--json` flag
**Then** a Rich-rendered output appears on stdout with two sections: a configuration table (showing each resolved value with its `ConfigSource.layer:detail`, tokens redacted) and a checks table (showing all four checks with `status="passed"` and their causes)
**And** the process exits 0

**Given** the same scenario but with `--json`
**When** I run `semvertag doctor --json`
**Then** exactly one line of `json.dumps(dataclasses.asdict(doctor_result))` is written to stdout — no progress chatter
**And** `jq '.checks | length'` returns 4

**Given** `SEMVERTAG_TOKEN` is not set, no provider-native fallback is set, and `semvertag doctor` is invoked
**When** the run executes
**Then** the token check fails with cause `"Token missing: no SEMVERTAG_TOKEN, CI_JOB_TOKEN, or GITLAB_TOKEN found in environment. ..."`
**And** the three subsequent checks are reported as `skipped`
**And** the process exits 3 (auth/permission dominance from Story 3.1's resolver)

**Given** `SEMVERTAG_TOKEN` is set but has insufficient scopes
**When** `semvertag doctor --json` is invoked
**Then** the token check passes, scopes fails with `"Token missing scope: 'write_repository'. ..."`, the remaining two are skipped, the JSON envelope contains all four checks with their `status` and `cause` fields populated, and the process exits 3

**Given** the same `Settings._provenance` consumed throughout the run
**When** the configuration section is rendered
**Then** for each settings field with a recorded `ConfigSource`, the rendered row shows the field name, its (redacted) effective value, the source layer (`cli` / `env` / `default`), and the source detail (e.g., `--strategy`, `SEMVERTAG_TOKEN`, `CI_JOB_TOKEN`, `default`)

**Given** integration tests in `tests/integration/test_cli_doctor.py` use `CliRunner` + `httpx2.MockTransport`
**When** the test suite runs
**Then** the four chain outcomes from Story 3.1 are each end-to-end-tested via the CLI, both human and JSON forms are exercised, and token redaction is verified on every output path (stdout, stderr, JSON envelope)

**Given** a real-world doctor run completes against a single GitLab project
**When** measured under the conditions described in NFR4
**Then** total wall time is ≤10 seconds (single project, all four sequential checks)

## Epic 4: Public-Launch Readiness — Trust Surface, Distribution & Shadow-Mode

External users (Dani-style tag-only adopters via Marketplace; Sasha-style contributors) can discover, install, and contribute to semvertag. Internal Raiffeisen pipelines continue working with byte-identical tag outcomes (NFR9 shadow-mode validation). v1.0 is announceable.

### Story 4.1: CI workflow polish — `pip-audit`, codecov upload, LOC gate, quarterly dependency-update cron

As a maintainer landing v1.0,
I want the `ci.yml` workflow to enforce security, coverage, and size discipline on every PR, plus a scheduled cron that opens dependency-update PRs quarterly,
So that NFR12 (`pip-audit` clean), NFR21 (≤1500 LOC core visible), NFR22 (≥85% line coverage), and NFR26 (quarterly `uv lock --upgrade`) are continuously enforced rather than aspirational.

**Acceptance Criteria:**

**Given** `.github/workflows/ci.yml` (created in Story 1.1) currently runs lint + pytest matrix
**When** Story 4.1 lands
**Then** a `pip-audit` job is added that runs after install and fails the build on any reported vulnerability with severity ≥ medium

**Given** the same workflow
**When** pytest matrix completes
**Then** a codecov upload step posts coverage to codecov.io and the README badge URL becomes meaningful

**Given** an LOC-count step is added
**When** the production source (`semvertag/**/*.py` excluding tests, docs, generated files) exceeds 1500 lines
**Then** the step emits a warning (not a hard failure) per NFR21's "soft target visible in CI" framing
**And** the actual LOC count is printed in the job log for visibility

**Given** a new `.github/workflows/dependency-update.yml`
**When** the cron fires quarterly (declared schedule e.g., `cron: '0 9 1 */3 *'`)
**Then** the workflow runs `uv lock --upgrade`, commits the result to a new branch, and opens a PR with a summary of the diff
**And** the workflow runs once daily as a no-op safety check that drift hasn't already broken the lock — surfacing dependency rot earlier than the quarterly cadence

**Given** the workflow files
**When** I review them against the architecture
**Then** they pin `astral-sh/setup-uv@v3`, `extractions/setup-just@v2`, and use the same lint/test invocations as `Justfile` (no duplication of command lines)

### Story 4.2: Publish workflow via PyPI trusted publishing

As a maintainer releasing v1.0,
I want a `release: published` workflow that builds the wheel + sdist and publishes to PyPI via trusted publishing (OIDC), with no long-lived `PYPI_TOKEN` in CI secrets,
So that NFR13 holds and releases happen by tagging in GitHub, not by hand-running `uv publish` with a token.

**Acceptance Criteria:**

**Given** `.github/workflows/publish.yml`
**When** a GitHub release is published
**Then** the workflow runs `uv build` (producing wheel + sdist in `dist/`) and `uv publish` via trusted publishing (uses `id-token: write` permission and the PyPI Trusted Publisher OIDC flow)
**And** the workflow does not reference any `PYPI_TOKEN` / `PYPI_API_TOKEN` secret

**Given** the PyPI project page has been configured with the `semvertag` repo as a trusted publisher (a manual one-time setup step documented in the release runbook, not in this workflow)
**When** the workflow runs
**Then** the publish succeeds without explicit credentials

**Given** the workflow
**When** it runs against a release whose tag does not match the published `__version__` or `[project.version]`
**Then** the publish step fails with a clear error before `uv publish` is invoked (a pre-publish guard step)

**Given** a release-runbook entry in `docs/contributing/release.md` (or equivalent)
**When** I follow it
**Then** I can cut a release in ≤5 minutes from "merge final PR" to "PyPI artifact live" — version bump, tag, GitHub release, workflow auto-fires
**And** the runbook includes an explicit pre-release gate: "for v1.0 and any subsequent major release, confirm Story 4.8's shadow-mode parity cycle (≥2 weeks, 100% match) has been re-run and signed off per NFR9 — release MUST NOT proceed without this gate"

### Story 4.3a: GitHub Actions Marketplace wrapper (`action.yml`)

As Dani the Terraform module maintainer (PRD Journey 3),
I want to add semvertag to my GitHub Actions workflow with a 7-line YAML block referencing the Marketplace action,
So that "tag-only" adopters on GitHub get a one-liner integration path without writing a custom `run:` block.

**Acceptance Criteria:**

**Given** `action.yml` at the repo root
**When** consumed by `uses: <org>/semvertag@v1` in a GitHub Actions workflow
**Then** the action accepts a single input `strategy` (default `branch-prefix`), reads `GITHUB_TOKEN` automatically, and shells out to `uvx semvertag` with the right flags
**And** the action's metadata (name, description, icon, color) is set per Marketplace conventions
**And** a working example workflow is included in `docs/providers/github.md` (or equivalent) showing the 7-line `uses:` snippet from Journey 3

**Given** the `action.yml` descriptor
**When** I attempt a release that publishes it
**Then** the GitHub release automation surfaces the Marketplace listing within minutes, tied to the release tag

**Given** integration tests cannot run the Marketplace in CI directly
**When** Story 4.3a ships
**Then** `action.yml` validates against its schema (`actionlint` or equivalent) in `ci.yml`

### Story 4.3b: GitLab CI Catalog component (`.gitlab/catalog/component.yml`)

As Petr the GitLab SRE (PRD Journey 1),
I want to include semvertag via the GitLab CI Catalog with a minimal `include:` snippet,
So that GitLab CI adopters get a native one-liner integration path discoverable through the Catalog browser.

**Acceptance Criteria:**

**Given** `.gitlab/catalog/component.yml`
**When** consumed by `include:` in a GitLab CI pipeline using GitLab Catalog v1
**Then** the component declares its inputs (e.g., `strategy`), defaults, and runs `uvx semvertag` with `CI_JOB_TOKEN` auto-detected
**And** a working example pipeline is included in `docs/providers/gitlab.md` showing the include snippet from Journey 1

**Given** the `component.yml` descriptor
**When** I attempt a release that publishes it
**Then** the GitLab Catalog component is discoverable in the Catalog browser tied to the release tag

**Given** integration tests cannot run the Catalog in CI directly
**When** Story 4.3b ships
**Then** `component.yml` validates against GitLab's published schema (if available) in `ci.yml`

### Story 4.4: mkdocs site content — Quick Start, CLI reference, strategies, providers, doctor pages

As a new visitor reading the docs site,
I want a Quick Start that gets me to a successful first tag in ≤5 minutes, a CLI reference page documenting every flag/env/exit-code, a strategies page per strategy, a providers page per provider, and a doctor page with all four checks documented,
So that NFR3 (<5min first-tag median) is supported by real on-ramp content rather than just a README hero.

**Acceptance Criteria:**

**Given** the `docs/` tree (scaffolded by Story 1.1 with `mkdocs.yml`)
**When** Story 4.4 lands
**Then** the following pages exist with full content (not stubs):
- `docs/index.md` — Quick Start: 5-minute path to first tag (GitLab CI + GitHub Actions)
- `docs/cli-reference.md` — every flag, every env var (`SEMVERTAG_*` + provider-native fallbacks), every exit code (0–4), the `--json` envelope schema with field-by-field descriptions
- `docs/strategies/branch-prefix.md` — when to use it, default mappings, examples
- `docs/strategies/conventional-commits.md` — when to use it, default mappings, `!` and `BREAKING CHANGE:` precedence, examples
- `docs/providers/gitlab.md` — token scopes required, `CI_JOB_TOKEN` notes, working CI snippet (from Story 4.3b)
- `docs/providers/github.md` — v1.x notice + planned shape (since GitHub provider is v1.x), working Marketplace snippet (from Story 4.3a)
- `docs/providers/bitbucket.md` — v1.x notice
- `docs/doctor.md` — all four checks documented with example human + JSON output

**Given** `mkdocs.yml` nav
**When** Story 4.4 lands
**Then** the nav reflects the new pages in a logical order (Quick Start → CLI ref → strategies → providers → doctor)

**Given** `mkdocs build --strict` runs in `ci.yml` as a smoke check
**When** any docs page has broken internal links or missing referenced files
**Then** CI fails — broken docs are never merged

**Given** Read the Docs is configured (from Story 1.1's `.readthedocs.yaml`)
**When** `main` is pushed
**Then** the site builds and serves at the configured RTD URL within minutes

### Story 4.5: Three migration guides (`semantic-release`, `go-semrel-gitlab`, `RightBrain/auto-semver`)

As a team currently on `semantic-release` (or `go-semrel-gitlab`, or `RightBrain/auto-semver`),
I want a published migration guide with a side-by-side config-mapping table,
So that I can evaluate whether semvertag fits my use case before committing to switch tools — and execute the switch without trial-and-error.

**Acceptance Criteria:**

**Given** `docs/migrating-from-semantic-release.md`
**When** I read it
**Then** it includes (a) a one-paragraph "why migrate" framing, (b) a side-by-side config-mapping table (semantic-release `package.json` config keys → semvertag equivalents), (c) a worked migration example (a real `.releaserc.json` translated to env vars), (d) notes on features that don't translate (e.g., changelog generation, npm publish — semvertag does only tagging)

**Given** `docs/migrating-from-go-semrel-gitlab.md`
**When** I read it
**Then** it covers the same four sections, calling out the abandonment of `go-semrel-gitlab` as the migration trigger and the GitLab-native parity in semvertag

**Given** `docs/migrating-from-rightbrain-auto-semver.md`
**When** I read it
**Then** it covers the same four sections, including the branch-prefix → branch-prefix continuity story

**Given** `mkdocs.yml` nav
**When** Story 4.5 lands
**Then** the three migration guides are linked under a "Migrating" section in the nav

**Given** all three guides
**When** any link to a config key in `cli-reference.md` (from Story 4.4) is broken
**Then** `mkdocs build --strict` fails — guides stay in sync with the CLI reference

### Story 4.6: Trust-surface markdown — `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, API stability policy

As an external contributor or downstream user,
I want clear documents covering: how to report security issues, how to set up a dev environment in 4 commands, the community code of conduct, the release history, and the API stability promise,
So that I can trust this project enough to adopt it or contribute to it.

**Acceptance Criteria:**

**Given** `SECURITY.md`
**When** I read it
**Then** it documents private vulnerability reporting via GitHub Security Advisories, a 90-day disclosure timeline, and an explicit "no public bug bounty" line — per NFR14

**Given** `CONTRIBUTING.md`
**When** I follow the dev-setup section
**Then** four commands — `uv sync`, `uv run pytest`, `uv run ruff check`, `uv run ty check` — succeed against a fresh clone and the full test suite passes offline (no network calls) via `httpx2.MockTransport` per FR46
**And** the file includes a "Adding a Provider" section pointing at `docs/contributing/adding-a-provider.md` (which names `providers/gitlab.py` as the canonical reference shape per Journey 4 / FR22)

**Given** `CODE_OF_CONDUCT.md`
**When** I read it
**Then** it adopts a standard community CoC text (Contributor Covenant or equivalent) with the maintainer contact email filled in

**Given** `CHANGELOG.md`
**When** v1.0 is cut
**Then** the file follows Keep a Changelog format, with a `[Unreleased]` section at the top and the v1.0 release notes formatted as the first dated entry

**Given** `docs/api-stability.md`
**When** I read it
**Then** it documents (a) the SemVer-stable surface (CLI flags, config keys, exit codes 0–4, `--json` envelope `schema_version`), (b) the explicitly-NOT-stable surface (`semvertag.providers.*`, `semvertag.strategies.*`, `_*.py` modules per NFR25), (c) the deprecation policy (one-minor-version warning + documented migration path), (d) the FR28 forward-compat policy for the future TOML file layer (rejects templating, env-var interpolation in TOML, remote/URL-loaded config; exits 2 on violation), (e) the Python EOL+12mo drop policy from NFR30

**Given** `mkdocs.yml` nav
**When** Story 4.6 lands
**Then** the API stability page is linked in nav, and SECURITY/CONTRIBUTING/CODE_OF_CONDUCT are reachable from the repo root (GitHub renders them inline on the repo page)

### Story 4.7: README hero with copy-pasteable snippets, badges, SEO + issue templates

As a search-engine visitor who types "gitlab ci auto tag semver",
I want to land on a README whose hero shows a working 4-line `.gitlab-ci.yml` snippet within the first viewport, plus badges for CI status / PyPI version / supported Python / coverage / license,
So that I can decide in 10 seconds whether to keep reading — and so first-contact issues funnel to templates that route me to the right place.

**Acceptance Criteria:**

**Given** `README.md`
**When** I view the file on GitHub
**Then** the H1 contains "semvertag" with a one-line tagline including the SEO-tuned terms "GitLab CI", "auto tag", "semver" per FR45
**And** the hero (above any subsections) contains: (a) a row of badges — CI status, PyPI version, supported Python versions, coverage, license, (b) a copy-pasteable 4-line `.gitlab-ci.yml` snippet, (c) a copy-pasteable 7-line GitHub Actions workflow snippet, (d) a one-line "What it does" pitch

**Given** the snippets in the hero
**When** I copy-paste them into a fresh repo with `SEMVERTAG_TOKEN` set
**Then** they work as-is (a CI run produces a tag) — verified by the same fixtures used in Story 1.7's integration tests

**Given** an asciicast or animated GIF of a real semvertag run
**When** Story 4.7 lands
**Then** the README links it from the hero (a `.cast` file plus a pre-rendered GIF stored under `docs/assets/` so the README renders offline as well)

**Given** `.github/ISSUE_TEMPLATE/`
**When** Story 4.7 lands
**Then** three templates exist: `bug_report.md`, `feature_request.md`, `new_provider_request.md`
**And** the `new_provider_request.md` template guides Journey 4 contributors toward the documented acceptance path (links to `docs/contributing/adding-a-provider.md` and the existing `GitLabProvider` as the reference shape)

**Given** `.github/PULL_REQUEST_TEMPLATE.md`
**When** I open a PR
**Then** the template prompts for: summary, what changed, test plan, FR/NFR reference, screenshots-or-output if user-visible

### Story 4.8: Shadow-mode parity validation in `pypelines` against `raif-autosemver` (NFR9 gate)

As the maintainer about to publish v1.0,
I want semvertag to run alongside `raif-autosemver` in the Raiffeisen `pypelines` shared CI for at least one full release cycle (~2 weeks), comparing tag outputs on the same triggers,
So that NFR9 is met (byte-identical tag outcomes on the GitLab + branch-prefix path) and there are zero regressions for the internal pipelines depending on `raif-autosemver`.

**Acceptance Criteria:**

**Given** `pypelines` CI is configured to run both `raif-autosemver` (canonical) and `semvertag` (shadow) on the same triggers (merge events on the canonical set of internal repos)
**When** the shadow run completes
**Then** both tools' decisions are recorded (would-create-tag X / would-skip-with-reason Y) to a comparison artifact — a CSV or JSONL line per trigger with `trigger_id`, `repo`, `raif_decision`, `semvertag_decision`, `match: bool`, `diff_summary`

**Given** the shadow run continues for at least one full release cycle (≈2 weeks of merge activity)
**When** the cycle completes
**Then** the match rate is 100% on the GitLab + branch-prefix path — every shadow decision matches the canonical decision byte-identically (tag name, source commit SHA, no-op reason wording is allowed to differ)

**Given** any mismatch surfaces during the cycle
**When** the mismatch is investigated
**Then** the root cause is traced to either (a) a semvertag bug — fixed by a follow-up PR before public v1.0 — or (b) an intentional behavior difference — documented in the v1.0 release notes as a deliberate departure

**Given** the cycle completes with 100% match
**When** the maintainer cuts v1.0
**Then** the comparison artifact is published as a release asset (or a permanent gist) so external auditors can verify the parity claim

**Given** the shadow run is external to this repo's CI
**When** the cycle is in progress
**Then** the shadow infrastructure is documented in `docs/contributing/shadow-mode.md` (or equivalent) so future maintainers can re-run it before subsequent releases if needed

**Given** the NFR9 gate is the final blocker before public v1.0 announcement
**When** the cycle's 100%-match outcome is verified
**Then** the public v1.0 release can be cut — all other Epic 4 stories must be complete first
