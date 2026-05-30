---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - "prd.md"
  - "prd-validation-report.md"
  - "product-brief-semvertag.md"
  - "product-brief-semvertag-distillate.md"
  - "autosemver/__main__.py"
  - "autosemver/ioc.py"
  - "autosemver/settings.py"
  - "autosemver/use_cases/autosemver_use_case.py"
  - "pyproject.toml"
workflowType: 'architecture'
project_name: 'semvertag'
user_name: 'Kevin'
date: '2026-05-26'
lastStep: 8
status: 'complete'
completedAt: '2026-05-26'
---

# Architecture Decision Document — semvertag

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements (46 total, 8 categories):**

- Tag Creation (FR1–FR10): core domain — bump inference, idempotency, edge
  cases (zero tags, non-semver tags, squash-merge, shallow clones, non-`main`
  default, empty default). Source of truth for both commits and tags is the
  provider REST API, not the local git tree (FR10, NFR15).
- Bump Strategy (FR11–FR16): two strategies (`branch-prefix`,
  `conventional-commits`) selectable per-repo; user-extensible mappings.
  Major bumps via `!` suffix or `BREAKING CHANGE:` footer in
  Conventional Commits only.
- Provider Integration (FR17–FR22): GitLab REST API in v1.0; GitHub + Bitbucket
  REST in v1.x behind optional extras. New provider = one file implementing
  the documented `Provider` protocol.
- Configuration & Environment (FR23–FR28): TOML (`[tool.semvertag]` in
  `pyproject.toml` OR `.semvertag.toml`), env vars (`SEMVERTAG_*` plus
  provider-native fallbacks `CI_JOB_TOKEN`, `GITLAB_TOKEN`, `GITHUB_TOKEN`,
  `BITBUCKET_TOKEN`), and CLI flags. Resolution precedence:
  CLI > env > file > defaults. No remote config loading,
  no env-var interpolation in TOML (supply-chain).
- Diagnostics & Validation (FR29–FR32): `semvertag doctor` is a separate
  diagnostic surface with its own JSON output and config-source tracing,
  not a dry-run of the primary verb.
- CLI Surface & Output (FR33–FR39): Typer-based; stable exit codes 0–4;
  stdout/stderr discipline; `--json` envelope with `schema_version: "1.0"`;
  `--install-completion` for bash/zsh/fish/powershell.
- CI Distribution (FR40–FR42): GitLab CI Catalog component + GitHub Actions
  Marketplace wrapper + `uvx semvertag` zero-install.
- Documentation & Trust (FR43–FR46): three migration guides, API stability
  policy, SEO-tuned README, marketplace listings, executable
  `CONTRIBUTING.md` recipe.

**Non-Functional Requirements (30 total, 6 categories):**

- Performance (NFR1–NFR4): ≤30s p95 CI runtime, ≤5s cold-start `--help`
  on a fresh runner, ≤10s `doctor`, <5min first-tag-time median.
- Reliability (NFR5–NFR9): idempotent reruns, exit 0 on documented no-ops,
  bounded retry (3 attempts / 30s wall / exponential backoff) on provider
  5xx/429/timeout, fail-closed on auth, shadow-mode parity with
  `raif-autosemver` on the GitLab+branch-prefix path before public v1.0.
- Security (NFR10–NFR14): token redaction to `***` or last-4 in ALL
  output surfaces including `doctor`; local-only config; `pip-audit` clean
  on release; trusted-publishing for PyPI; `SECURITY.md` private-report path.
- Integration (NFR15–NFR20): GitLab CE/EE 15.0+ (cloud + self-hosted),
  GitHub Enterprise Server 3.10+ (v1.x), Bitbucket Cloud only (v1.x),
  versioned JSON schema.
- Maintainability (NFR21–NFR26): ≤1500 LOC core (soft, CI-visible target),
  ≥85% line coverage / 100% branch coverage on bump-strategy parsing,
  `ty` + `ruff ALL` clean, ≤7d issue first-response, SemVer-stable
  CLI flags / config keys / exit codes / JSON schema post-1.0,
  internal modules NOT stability-covered.
- Compatibility (NFR27–NFR30): Python 3.10–3.13 (existing code is 3.13-only,
  must broaden), Linux primary / macOS+Windows best-effort, `uv` 0.5+,
  Python EOL+12mo drop policy.

### Scale & Complexity

- Technical complexity: **Low–Medium**. Single-verb CLI, batch invocation,
  network-bound (provider API latency dominates).
- Strategic/positioning complexity is high but resolved in the PRD —
  it does not drive architecture decisions.
- Primary domain: developer tooling / CLI / network-bound batch process.
- Estimated architectural components: ~6 — CLI entrypoint, config resolver,
  provider abstraction, strategy abstraction, output layer (human + JSON),
  doctor subsystem.

### Technical Constraints & Dependencies

**Already-fixed stack choices (PRD-binding, not open for re-decision):**

- Runtime: Typer-based CLI; current `modern-di-typer` for DI wiring
  (internal-only — not part of public CLI contract per PRD Architecture Notes).
- HTTP / provider clients: `python-gitlab` (v1.0); GitHub + Bitbucket clients
  TBD and gated behind optional extras.
- Config: `pydantic-settings` for env vars; TOML config via Typer conventions.
- Output: `rich` for human; `json.dumps` for machine (no third-party JSON lib).
- Versioning: `semver` package.
- Build: `uv_build`; distribution via PyPI + `uvx`-runnable headline path.

**Hard constraints:**

- ≤1500 LOC core (NFR21) — pushes against speculative abstraction.
- Module rename `autosemver/` → `semvertag/`; env prefix `AUTOSEMVER_` → `SEMVERTAG_`.
- Remove-before-publish: Raiffeisen Dockerfile, hardcoded
  `https://gitlabci.raiffeisen.ru` default, internal Artifactory
  `[[tool.uv.index]]` blocks in `pyproject.toml`.
- Python 3.10+ floor (current code is 3.13-only — must broaden).
- Shadow-mode parity with `raif-autosemver` on GitLab + branch-prefix
  before public v1.0 (NFR9) — byte-identical tag outcomes.

**Asymmetric stability surface:**

- SemVer-stable post-1.0: CLI flags, config keys, exit codes, JSON envelope schema.
- Not stability-covered: `semvertag.providers.*`, `semvertag.strategies.*`,
  any embed-as-library API. Internal refactors are free.

### Cross-Cutting Concerns Identified

1. **Output discipline.** Two output channels (stdout informational, stderr
   errors) and two formats (rich human, versioned JSON). Cannot interleave;
   `--quiet` suppresses non-error stdout; doctor has its own JSON form.
2. **Error → exit-code mapping.** Five stable codes (0/1/2/3/4). Implementation
   must map every failure path to one of these — suggests typed exception
   hierarchy or sentinel-result pattern, not ad-hoc raises.
3. **Token redaction.** Tokens must never appear in stdout, stderr, log files,
   or doctor output — `***` or last-4 only (NFR10). Cuts across logging,
   error messages, and doctor's "resolved config source" reporting.
4. **Retry / backoff.** 3 retries, 30s wall budget, exponential backoff on
   provider 5xx/429/timeout (NFR7). Lives in one place — provider-call
   middleware — not duplicated per provider.
5. **Config resolution with source tracing.** Four levels with provider-native
   credential fallbacks layered in. Doctor must trace and report which layer
   won for each value (FR32). Pure-function ideal; testable in isolation.
6. **Optional-extras dependency isolation.** Core install must not transitively
   pull PyGithub, Bitbucket client, or similar. Provider modules are imported
   lazily on selection; provider clients are declared in
   `[project.optional-dependencies]` extras only.

## Starter Template Evaluation

### Framing

Two reference roles, kept distinct:

- **Structural template:** `modern-di` (public OSS, same author). Provides
  repo shape, CI/publish workflows, lint stack, Justfile, mkdocs+Material+RTD
  config, packaging conventions, `py.typed`+`context7.json` patterns.
  Mirrored verbatim where applicable; CLI-specific deltas applied.
- **Behavioral reference:** existing `autosemver/` directory (Raiffeisen-
  internal). Provides bump algorithm semantics, DI wiring pattern, settings
  shape, requests-mock test idioms. Logic is **ported** onto the modern-di-
  shaped scaffolding; files are NOT preserved or transformed in place.
  Company artefacts (internal Artifactory indexes, hardcoded internal URLs,
  Raiffeisen Dockerfile, AUTOSEMVER_ env prefix) stay out of the public
  layout entirely.

NFR9 (shadow-mode parity with raif-autosemver) is satisfied by reproducing
outcomes on the GitLab+branch-prefix path, not by file-level preservation.

### Primary Technology Domain

CLI tool (Python, network-bound, batch invocation). Secondary classification:
developer-tool library (pip-installable, optional extras for provider clients).

### Starter Options Considered

1. **Mirror modern-di structurally; port autosemver/ logic.** Recommended.
2. **In-place transform of autosemver/ (rename + strip).** Rejected: drags
   company-internal scaffolding forward; ongoing strip-Raiffeisen work;
   leak risk in public commits.
3. **Greenfield from a generic Python-CLI cookiecutter.** Rejected: doesn't
   match PRD-named conventions (`ty`, `eof-fixer`, `auto-typing-final`,
   mkdocs-material exact theme, `context7.json`); immediate divergence.

### Selected Starter: modern-di (structural) + autosemver/ (behavioral)

**Rationale:**

- PRD explicitly names modern-di as the reference structural model.
- modern-di is actively maintained, public-OSS-shaped, and uses the exact
  toolchain the PRD pins.
- Keeps Raiffeisen artefacts out of the public layout from the first commit.
- Behavioral parity (NFR9) preserved by porting logic and test cases.

**Initialization Sequence (first implementation story):**

```bash
# Phase A — Scaffold from modern-di's shape:
#   1. Author pyproject.toml modeled on modern-di's, with semvertag-specific
#      [project], [project.scripts], [project.optional-dependencies].
#      NO [[tool.uv.index]] Artifactory blocks. requires-python = ">=3.10".
#   2. Copy verbatim from /Users/kevinsmith/src/pypi/modern-di:
#        Justfile, .readthedocs.yaml, docs/requirements.txt, LICENSE
#      Copy with adapt: mkdocs.yml (rewrite nav, keep theme),
#                       .github/workflows/{ci.yml,publish.yml}.
#   3. Author fresh: README.md, CLAUDE.md, SECURITY.md, CONTRIBUTING.md,
#      CODE_OF_CONDUCT.md, action.yml, GitLab CI Catalog descriptor,
#      docs/migrating-from-*.md.
#
# Phase B — Port logic from autosemver/:
#   4. Re-author semvertag/settings.py with SEMVERTAG_ env prefix; no
#      Raiffeisen defaults (gitlab_endpoint becomes a required-on-self-hosted
#      explicit value, not a default).
#   5. Re-author semvertag/ioc.py provider-agnostic; GitLabGroup is one
#      provider group among future GitHubGroup/BitbucketGroup.
#   6. Port AutosemverUseCase's bump algorithm into Provider + BumpStrategy
#      protocols. Behavioral target: existing autosemver/tests/ pass against
#      the new shape (ported, not preserved).
#   7. Port + extend the test suite using requests-mock idioms; add cases for
#      Conventional Commits, BREAKING CHANGE/!, no-tags, non-semver tags,
#      shallow clones, non-main defaults.
#
# Phase C — Shadow-mode validation (NFR9):
#   8. Run semvertag against the same Raiffeisen pypelines triggers as
#      raif-autosemver for one full release cycle; compare tag outputs.
```

**Architectural Decisions Inherited from Structural Template:**

**Language & Runtime:** Python 3.10–3.13; `uv`-managed; `uv_build` backend;
`py.typed` ships with the package.

**Build & Packaging:** `pyproject.toml` with `uv_build`; `[project.scripts]`
for the `semvertag` console script; `[project.optional-dependencies]` for
`github` and `bitbucket` extras; MIT; `context7.json`.

**Testing:** `pytest` + `pytest-cov` + `pytest-xdist` + `pytest-randomly` +
`requests-mock`. Coverage via `[tool.pytest.ini_options]` and
`[tool.coverage.report]`. Branch coverage opt-in via `just test-branch`.

**Lint & Type:** `ruff` (`ALL` minus PRD ignores) + `ty` + `eof-fixer` +
`auto-typing-final`. Driven by `just lint` / `just lint-ci`.

**Code Organization:** Flat top-level package (`semvertag/`); no `src/`
layout; `tests/`, `docs/`, workflows at repo root.

**DI:** `modern-di-typer` (internal-only per PRD; not part of public
CLI contract).

**CI & Release:** GitHub Actions; lint on 3.10; pytest matrix 3.10–3.13;
`astral-sh/setup-uv@v3`; `extractions/setup-just@v2`; codecov. Publish on
`release: published` via PyPI **trusted publishing** (NFR13).

**Documentation:** mkdocs + Material with content.code.copy, edit/view,
instant nav, light/dark palette; Read the Docs hosting; semvertag-specific
nav.

**Deltas vs. modern-di (CLI-specific):**

- `[project.scripts]` entrypoint (modern-di is library-only).
- Optional extras for provider clients.
- `action.yml` (GitHub Actions Marketplace).
- GitLab CI Catalog component descriptor.
- `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (modern-di skips
  these; PRD MVP adds them).
- Three migration guides under `docs/migrating-from-*.md`.
- PyPI trusted publishing replaces token publishing (NFR13).
- Python floor narrowed to 3.10–3.13 (vs. modern-di's 3.10–3.14, per NFR27).

**Note:** Project initialization is the first implementation story
("Bootstrap public semvertag scaffolding from modern-di shape; port
bump algorithm from autosemver/"). Concrete dependency version pins
land in the Technology Stack & Dependencies section (step-07).

## Core Architectural Decisions

### Decision Priority Analysis

**Critical (block implementation):**

1. `Provider` and `BumpStrategy` protocol shapes (§Provider Abstraction, §Bump Strategy Abstraction) — every other layer wires through these.
2. HTTP layer choice — **httpx2** + **httpx2.MockTransport** for tests, replacing `python-gitlab` and `requests-mock` (§Provider Abstraction).
3. Error model — typed exception hierarchy + `typer.Exit(code=N)` at the CLI boundary (§Error Model).
4. Configuration shape — env vars + CLI flags only in v1.0; **no TOML file layer**; nested per-provider `BaseModel` composition under one `Settings(BaseSettings)`; provenance recording via `settings_customise_sources` (§Configuration Resolution).
5. Custom httpx2 transport implementing NFR7 retry policy (§Retry & Rate-Limit Handling).

**Important (shape architecture):**

6. Output protocol — hybrid `progress(msg)` + `emit(RunResult)`; two implementations (`RichOutput`, `JsonOutput`); two `rich.Console` instances for strict stdout/stderr split (§Output Architecture).
7. Doctor — sequential checks, skip-on-failure chain, main-verb exit-code mirroring (§Doctor Architecture).
8. DI — keep `modern-di-typer` with flattened Groups; provider/strategy/output all DI-managed singletons per CLI run (§DI & Dependency Boundary).
9. Test layering — three layers: unit / CLI integration via `CliRunner` + `httpx2.MockTransport` / external shadow-mode in `pypelines` (§Test Architecture).

**Deferred to v1.x (post-MVP):**

- TOML configuration support (`[tool.semvertag]` in `pyproject.toml` and standalone `.semvertag.toml`) — Marina's Journey 2 narrative rewires to use CI variables for v1.0.
- Optional packaging extras `[github]` / `[bitbucket]` — dropped from v1.0 because the httpx2-for-all-providers decision removes any per-provider SDK dep to gate.
- Recorded-fixture parity corpus in-repo (NFR9 belt-and-braces) — v1.0 ships with external shadow-mode in pypelines only.
- Parallel doctor checks (async or threadpool) — sequential is comfortably under NFR4's 10s budget.

### Provider Abstraction

**Protocol surface (single protocol; doctor methods included):**

```python
class Provider(typing.Protocol):
    name: str  # "gitlab" | "github" | "bitbucket"

    def get_default_branch(self) -> str: ...
    def get_latest_commit_on_default_branch(self) -> Commit: ...
    def list_tags(self) -> list[Tag]: ...                      # most-recent-first
    def create_tag(self, name: str, commit_sha: str) -> None: ...

    def check_token(self) -> CheckResult: ...
    def check_scopes(self) -> CheckResult: ...
    def check_project_access(self) -> CheckResult: ...
    def check_protected_tags(self) -> CheckResult: ...


@dataclasses.dataclass(frozen=True, slots=True)
class Commit:
    sha: str
    message: str


@dataclasses.dataclass(frozen=True, slots=True)
class Tag:
    name: str
    commit_sha: str


@dataclasses.dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    status: typing.Literal["passed", "failed", "skipped"]
    cause: str  # named, actionable per FR30; populated even on `passed`
```

**HTTP layer:** httpx2 (Pydantic-stewarded continuation of encode/httpx; v2.2.0+ pinned defensively in `uv.lock`). All four GitLab endpoints accessed via raw `httpx2.Client` calls in `semvertag/providers/gitlab.py` — no `python-gitlab` SDK. Each provider owns its URL paths, auth header format, and response parsing. Per-provider exception translation maps HTTP status → semvertag exception with provider-named, actionable cause (e.g., GitLab "Token missing 'api' scope" vs GitHub "Token missing 'contents: write' permission").

**Per-request timeout:** 8s; configurable via `SEMVERTAG_REQUEST_TIMEOUT`, clamped ≤10s to preserve NFR1/NFR7 budget math.

**Provider lifecycle:** single instance per CLI run, DI-managed via `modern-di-typer` `Factory` (lazy resolution — only the active provider is constructed).

### Bump Strategy Abstraction

**Protocol surface (single-commit input, intentionally less expressive than `semantic-release`):**

```python
class Bump(enum.Enum):
    NONE = "none"
    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"


class BumpStrategy(typing.Protocol):
    name: str  # "branch-prefix" | "conventional-commits"
    def decide(self, commit: Commit) -> Bump: ...


@dataclasses.dataclass(frozen=True, slots=True)
class BranchPrefixConfig:
    minor: tuple[str, ...] = ("feature/",)
    patch: tuple[str, ...] = ("bugfix/", "hotfix/")
    merge_mark_text: str = "Merge branch"
    # No major mapping — major bumps require conventional-commits.


@dataclasses.dataclass(frozen=True, slots=True)
class ConventionalCommitsConfig:
    minor_types: tuple[str, ...] = ("feat",)
    patch_types: tuple[str, ...] = ("fix", "perf")
    # Major detected via `!` suffix or `BREAKING CHANGE:` footer (FR15).
```

**User-extensible mappings:** frozen-dataclass config injected at construction. Defaults live in code; env vars override via `SEMVERTAG_BRANCH_PREFIX__MINOR` (nested env delimiter `__`) and similar.

**Strategy selection:** config-resolved at startup; one strategy instantiated per CLI run, DI-managed (mirrors provider lifecycle).

### Error Model & Exit Codes

**Typed exception hierarchy + `typer.Exit(code=N)` at the CLI boundary:**

```python
class SemvertagError(Exception):
    """Base. Carries a named, actionable cause and an exit code."""
    exit_code: int = 1  # FR37 generic failure default


class ConfigError(SemvertagError):
    exit_code = 2


class AuthError(SemvertagError):
    """Auth or permission failure — fail-closed per NFR8."""
    exit_code = 3


class ProviderAPIError(SemvertagError):
    """Provider API failure (5xx, network, rate-limit, exhausted retries)."""
    exit_code = 4
```

**Translation point:** per-provider in `gitlab.py` / `github.py` / `bitbucket.py`. Each provider catches its own httpx2 exception types and re-raises as a `SemvertagError` subclass with a provider-specific actionable message.

**Redaction (NFR10):** defense in depth.

- `pydantic.SecretStr` for all token fields (catches accidental string interpolation).
- Output-boundary `redact(text: str) -> str` function in the Output layer, scanning for known token patterns (`glpat-...`, `ghp_...`, `ATBB...`, generic ≥32 hex).

### Output Architecture

**Protocol (hybrid progress events + final result):**

```python
@dataclasses.dataclass(frozen=True, slots=True)
class RunResult:
    schema_version: str = "1.0"
    strategy: str
    bump: str           # "none" | "patch" | "minor" | "major"
    status: str         # "created" | "no_merge_commit" | "no_conforming_commit" | "already_tagged" | "no_tags"
    tag: str | None
    commit: str | None
    reason: str | None  # populated when bump == "none"


class Output(typing.Protocol):
    def progress(self, message: str) -> None: ...   # rich: print; json: no-op
    def emit(self, result: RunResult) -> None: ...  # rich: human lines; json: envelope


class RichOutput: ...   # streams progress to stdout; renders final result as human lines
class JsonOutput: ...   # progress() is a no-op; emit() prints one `json.dumps(asdict(result))` to stdout
```

**Stream discipline:** two `rich.Console` instances per Output impl (`info_console` → stdout, `error_console` → stderr). No interleaving. Errors always to stderr regardless of `--quiet` / `--json` (FR38).

**`--quiet` + `--json` interaction:** additive. `--quiet` suppresses progress narrative only; final result still emits in the chosen format. `--quiet --json | jq` composes correctly. **PRD touch-up flagged for FR36.**

**JSON envelope:** frozen dataclass `RunResult` + stdlib `json.dumps(dataclasses.asdict(result))`. No third-party JSON lib (PRD Architecture Notes). Breaking schema changes require `schema_version` bump + deprecation cycle (NFR25).

### Configuration Resolution

**Layers (3, not 4 — TOML deferred to v1.x):** CLI flags > env vars > defaults.

**Settings shape — nested per-provider via `BaseModel` composition under one `Settings(BaseSettings)`:**

```python
class GitLabConfig(pydantic.BaseModel):
    endpoint: str = "https://gitlab.com"
    token: pydantic.SecretStr = pydantic.Field(
        default=pydantic.SecretStr(""),
        validation_alias=pydantic.AliasChoices(
            "SEMVERTAG_GITLAB__TOKEN", "SEMVERTAG_TOKEN",
            "CI_JOB_TOKEN", "GITLAB_TOKEN",
        ),
    )


class GitHubConfig(pydantic.BaseModel):
    token: pydantic.SecretStr = pydantic.Field(
        default=pydantic.SecretStr(""),
        validation_alias=pydantic.AliasChoices(
            "SEMVERTAG_GITHUB__TOKEN", "SEMVERTAG_TOKEN", "GITHUB_TOKEN",
        ),
    )


class Settings(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(
        env_prefix="SEMVERTAG_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )
    strategy: typing.Literal["branch-prefix", "conventional-commits"] = "branch-prefix"
    provider: typing.Literal["gitlab", "github", "bitbucket"] = "gitlab"
    default_branch: str | None = None  # None → auto-detect via provider API; fallback to `git symbolic-ref refs/remotes/origin/HEAD`
    request_timeout: float = 8.0       # clamped ≤10.0 on construction
    gitlab: GitLabConfig = pydantic.Field(default_factory=GitLabConfig)
    github: GitHubConfig = pydantic.Field(default_factory=GitHubConfig)
    branch_prefix: BranchPrefixConfig = pydantic.Field(default_factory=BranchPrefixConfig)
    conventional_commits: ConventionalCommitsConfig = pydantic.Field(default_factory=ConventionalCommitsConfig)

    _provenance: dict[str, ConfigSource] = pydantic.PrivateAttr(default_factory=dict)


@dataclasses.dataclass(frozen=True, slots=True)
class ConfigSource:
    layer: typing.Literal["cli", "env", "default"]
    detail: str  # "--strategy" | "SEMVERTAG_TOKEN" | "CI_JOB_TOKEN" | "default"
```

**CLI overlay:** Typer entrypoint constructs env-resolved Settings, then applies CLI flag overrides via `.model_copy(update=...)`. The overlay step records `cli:--<flag>` provenance for any field it sets.

**Source tracing (FR32):** `settings_customise_sources()` extended to record `_provenance[key] = ConfigSource(layer, detail)` as each pydantic source resolves a value. Doctor reads `_provenance` to render the configuration section with redacted token values.

### Retry & Rate-Limit Handling

**Custom `httpx2.BaseTransport` subclass** wraps the default transport. All client calls flow through it. ~50–70 LOC including jitter and budget tracking. No external dep (no `tenacity`).

```python
RETRYABLE_STATUSES: typing.Final = frozenset({408, 429, 500, 502, 503, 504})
RETRYABLE_EXCEPTIONS: typing.Final = (
    httpx2.ConnectError,
    httpx2.ReadTimeout,
    httpx2.WriteTimeout,
    httpx2.RemoteProtocolError,
)
MAX_ATTEMPTS: typing.Final = 3        # NFR7
MAX_WALL_SECONDS: typing.Final = 30.0  # NFR7
BACKOFF_BASE_SECONDS: typing.Final = 1.0


class RetryingTransport(httpx2.BaseTransport):
    """Wraps the default transport with NFR7 retry semantics:
    3 attempts, 30s wall budget, exponential backoff with jitter, honoring Retry-After on 429.
    """
```

**Per-request timeout:** 8s (configurable, clamped ≤10s). Worst case: 3 attempts × 8s + ~3s cumulative backoff = ~27s — fits inside NFR1 (≤30s p95) and NFR7 (30s wall budget).

**Backoff:** honor `Retry-After` header when present (429 most often); otherwise base 1s × 2^n with full jitter. `Retry-After` parsed for both seconds and HTTP-date forms.

**Non-retryable failures:** 4xx (except 408/429) exit immediately via `AuthError` (401/403) or `ConfigError` (404/422); fail-closed per NFR8.

### Doctor Architecture

**Sequential, skip-on-failure dependency chain:** token → scopes → project access → protected tags. Each check declares its prerequisites; the runner walks the chain. Failed prerequisites mark dependents as `status="skipped"` with `cause="Skipped: blocked by {prereq} check."`

**Exit codes mirror main-verb semantics (FR37):** 0 all passed; 3 auth/permission; 2 config; 4 provider API; 1 generic. When multiple checks fail, severity ordering picks the dominant code: `3 > 4 > 2 > 1`. Documented under NFR25 stability surface.

**Output:** doctor uses the same `Output` protocol from §Output Architecture, with one extension — a configuration-section renderer reading `Settings._provenance`. Token values rendered with last-4 only (NFR10).

**JSON form (FR31):** parallels the human form; same `schema_version: "1.0"` envelope.

### DI & Dependency Boundary

**DI framework:** `modern-di-typer` retained (existing autosemver pattern; PRD Architecture Notes mark DI as internal-only — refactor is free if needed in v1.x).

**Groups (flattened for v1.0 scope):**

- `ProviderGroup` — one `Factory` per provider; only the active one resolves (lazy).
- `StrategyGroup` — one `Factory` per strategy; only the active one resolves.
- `OutputGroup` — `Factory` selects `RichOutput` or `JsonOutput` based on settings.
- `SettingsGroup` — `Settings` resolved once at app startup, including provenance recording.

**Optional extras `[github]` / `[bitbucket]`:** **dropped from v1.0** as a consequence of choosing httpx2-for-all-providers — no per-provider SDK dep exists to gate. Provider implementations ship in core. Code-level lazy import (`import semvertag.providers.github` only when `provider == "github"`) preserves provider-implementation isolation as an internal concern, not a packaging one. **PRD touch-ups flagged.**

### Test Architecture

**Three layers:**

1. **Unit** (`tests/unit/`) — pure functions: `BumpStrategy.decide()`, settings resolution + source-tracing, JSON envelope serialization, error→exit-code mapping, retry-budget arithmetic, redaction. No HTTP. Suite runs in <1s.
2. **Integration / CLI-level** (`tests/integration/`) — full `semvertag` and `semvertag doctor` invocations via `typer.testing.CliRunner` with `httpx2.MockTransport` injected at the client construction seam. Covers the wired-up CLI. Suite runs in <5s.
3. **External shadow-mode parity** — runs in `pypelines` CI alongside `raif-autosemver` for one full release cycle per NFR9. Compares byte-identical tag outcomes. Not part of this repo's test suite.

**Shared MockTransport fixture pattern (`tests/conftest.py`):**

```python
GITLAB_PROJECT_ID: typing.Final = 999


def _default_handler(request: httpx2.Request) -> httpx2.Response:
    """Default GitLab mock — 4 endpoints. Tests compose overrides on top."""
    ...


@pytest.fixture
def gitlab_transport() -> httpx2.MockTransport:
    return httpx2.MockTransport(_default_handler)


def compose_handler(
    base: typing.Callable[[httpx2.Request], httpx2.Response],
    overrides: dict[tuple[str, str], httpx2.Response],
) -> typing.Callable[[httpx2.Request], httpx2.Response]:
    """Per-test endpoint override helper."""
    ...
```

**Coverage gates (NFR22):** `pytest --cov=. --cov-report term-missing --cov-fail-under=85` for line coverage. Bump-strategy modules get a separate `--cov-fail-under=100 --cov-branch` job in CI to enforce 100% branch coverage where it matters most.

### Decision Impact Analysis

**Implementation sequence (informs the first epic's story ordering):**

1. **Foundation** — bootstrap public scaffolding from modern-di shape (per Step 3); broaden Python floor to 3.10; strip Raiffeisen artefacts.
2. **Settings + Provenance** — `Settings` class with nested per-provider `BaseModel`s, `AliasChoices` token chain, `settings_customise_sources` provenance recording. Unit-tested in isolation.
3. **Error hierarchy + Output protocols** — `SemvertagError` subclasses, `RunResult`, `RichOutput`, `JsonOutput`. Unit-tested.
4. **RetryingTransport** — httpx2 BaseTransport subclass with NFR7 retry policy. Unit-tested with `httpx2.MockTransport` simulating 5xx/429/timeout sequences.
5. **GitLabProvider** — implements `Provider` against the four GitLab endpoints using the RetryingTransport. Existing autosemver tests ported.
6. **BranchPrefixStrategy + ConventionalCommitsStrategy** — `BumpStrategy` implementations. 100% branch coverage gate.
7. **DI wiring** — `modern-di-typer` Groups composing the layers. `__main__.py` Typer entrypoint with `typer.Exit(code=N)` handler.
8. **Doctor subcommand** — sequential skip-on-failure check chain; reuses Output and Provider protocols.
9. **Trust-surface scaffolding** — CI workflows, publish workflow (PyPI trusted publishing), mkdocs site, migration guides, action.yml, GitLab CI Catalog descriptor.
10. **External shadow-mode** — staged in `pypelines` against `raif-autosemver` for one release cycle before public v1.0.

**Cross-component dependencies:**

- `RetryingTransport` is consumed by every `Provider` implementation; one bug surfaces everywhere — invest in its test matrix early.
- `RunResult` schema is the public JSON contract (NFR25-stable); any field addition is non-breaking, any rename or type change is breaking.
- `Settings._provenance` is consumed only by doctor; its absence in non-doctor paths is fine.
- The `Output` protocol is consumed by both the use case and doctor; doctor extends it informally with a config-source renderer (no protocol change).
- Exception → exit-code mapping happens at exactly one place (`__main__.py` Typer entrypoint); every other layer just `raise`s.

### PRD Touch-Ups Required (For `/bmad-edit-prd` Pass)

**Status:** ✅ Applied 2026-05-26 via `/bmad-edit-prd` pass. All 8 items resolved in `prd.md`. Item 8 (FR9 fallback) was added during gap analysis; see the "Important Gaps" subsection below for its origin.

The following PRD edits surfaced during architecture decisions. They did not block implementation and were applied as a single edit pass.

1. **FR46** — wording swap: `requests-mock` → `httpx2.MockTransport` (Provider Abstraction §HTTP layer). **Applied** — also cascaded to Project Context L54, Journey 4 narrative + capabilities, Risk-Mitigation row, and Journey Requirements Summary.
2. **FR23, FR24** — remove from v1.0 FR list; relocate to v1.x Growth Features (Configuration Resolution §Layers). **Applied** — FRs tagged *(v1.x)*; Growth Features list updated; Config Schema section rewritten as env+flags only with v1.x-deferral notes.
3. **FR27** — simplify to 3-layer precedence: CLI > env > defaults. **Applied** — both FR27 and the CLI Tool section's flag-precedence list updated; v1.x file-config slot noted parenthetically.
4. **Journey 2 narrative** — rewrite Marina's `.semvertag.toml` change to a GitLab CI variable change on her pilot project. **Applied** — Marina now adds `SEMVERTAG_STRATEGY=conventional-commits` as a project-level CI variable; capabilities list updated; v1.x file-config footnote added.
5. **FR28** — "rejects remote/templated config" partly moot with no file layer in v1.0. Keep as forward-compat policy *or* trim from v1.0 scope. **Applied — kept as forward-compat policy (trimmed)** so the design constraint exists at design-time for the v1.x file layer; NFR11 cross-reference synced.
6. **FR36** — clarify "suppress all output" → "suppress non-error informational output during the run; final result still emitted in the chosen format" so `--quiet --json` composes. **Applied** — FR36 and the Output Formats `--quiet` description both updated.
7. **FR22, Brief, Architecture Notes, Journey 3/4 narratives, NFR15–17** — remove references to `pip install semvertag[github]` / `[bitbucket]` optional extras. The architectural reason: httpx2-for-all-providers removes any per-provider SDK to gate. **Applied** — extras removed from FR18, FR19, FR22, Growth Features, Architecture Notes (httpx2-shared-HTTP rationale added), and Journey 4 narrative + capabilities. NFR15-17 needed no text change (they describe support windows, not packaging). Brief was not edited — separate skill if needed.
8. **FR9 fallback semantics** — `git symbolic-ref refs/remotes/origin/HEAD` never fires in normal CI flow. Trim from FR9 wording *or* scope to a future `--offline` mode. **Applied — trimmed** with v1.x `--offline` deferral noted parenthetically; Risk-Mitigation row + Arch-Notes default-branch-detection bullet synced.

**Judgment-call follow-ups noted by the edit pass (not part of the 8-item backlog):**
- **FR13, FR16** ("override … mappings via configuration") still read as v1.0-capable, but collection-shaped mapping overrides aren't expressible as flat env vars. The PRD now documents this explicitly in the Config Schema's "Strategy-internal collection overrides (deferred)" subsection and in the v1.x Growth Features bullet for FR23/FR24 — but the FR13/FR16 text itself was not retagged. Decide whether to tag *(v1.x)* on those FRs or leave the deferral implicit.

## Implementation Patterns & Consistency Rules

### Conflict Points Identified

For a single-verb CLI like semvertag, the relevant patterns differ from a web app. The 13 below are areas where AI agents implementing different epics could otherwise diverge:

1. Module & class naming for `Provider` / `BumpStrategy` implementations
2. Frozen-dataclass conventions
3. Type-annotation style (existing autosemver / `ty`-compatible)
4. Error message template — the "named, actionable cause" format (FR30)
5. Exception construction call patterns
6. DI Group naming and structure
7. CLI flag naming
8. Environment variable naming (formalizes nested conventions)
9. JSON field naming (RunResult + doctor envelope)
10. Test naming and file organization
11. Module-level constants with `typing.Final`
12. Comment policy
13. Import style (global per CLAUDE.md)

### Naming Patterns

**Module naming (snake_case files, one Provider per file, one Strategy per file):**

```
semvertag/
├── __init__.py
├── __main__.py
├── _types.py            # Commit, Tag, CheckResult, RunResult, Bump, ConfigSource
├── _errors.py           # SemvertagError hierarchy
├── _transport.py        # RetryingTransport
├── _redact.py           # Token redaction
├── _output.py           # Output protocol, RichOutput, JsonOutput
├── _settings.py         # Settings + nested *Config models + provenance
├── ioc.py               # modern-di Groups
├── providers/
│   ├── __init__.py
│   ├── _base.py         # Provider protocol
│   └── gitlab.py        # GitLabProvider (single file per FR22)
│   └── github.py        # v1.x — present-but-skipped in v1.0 imports
│   └── bitbucket.py     # v1.x
├── strategies/
│   ├── __init__.py
│   ├── _base.py         # BumpStrategy protocol
│   ├── branch_prefix.py
│   └── conventional_commits.py
├── doctor/
│   ├── __init__.py
│   └── _checks.py       # the chain runner + CheckResult helpers
└── py.typed
```

**Rules:**

- Files with leading underscore (`_types.py`, `_errors.py`) signal internal modules NOT covered by NFR25 stability surface.
- One implementation per file in `providers/` and `strategies/` (FR22: "single file").
- Snake_case file names; PascalCase class names; snake_case function names; SCREAMING_SNAKE_CASE module-level constants.

**Class naming:**

| Concept | Pattern | Examples |
|---|---|---|
| Provider impl | `<Vendor>Provider` | `GitLabProvider`, `GitHubProvider`, `BitbucketProvider` |
| Strategy impl | `<Kind>Strategy` | `BranchPrefixStrategy`, `ConventionalCommitsStrategy` |
| Strategy config | `<Kind>Config` | `BranchPrefixConfig`, `ConventionalCommitsConfig` |
| Provider config | `<Vendor>Config` | `GitLabConfig`, `GitHubConfig` |
| Exception | `<Kind>Error` | `ConfigError`, `AuthError`, `ProviderAPIError` |
| DI Group | `<Plural>Group` | `ProvidersGroup`, `StrategiesGroup`, `OutputsGroup`, `SettingsGroup` |
| Output impl | `<Format>Output` | `RichOutput`, `JsonOutput` |

**Note:** Use `GitLab` (proper-noun capitalization), not `Gitlab`. Use `GitHub`, not `Github`. Matches GitLab/GitHub brand guidelines and existing autosemver `python-gitlab` ecosystem.

### Frozen-Dataclass Conventions

**All domain types are frozen dataclasses with slots and kw-only args:**

```python
@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Commit:
    sha: str
    message: str
```

Matches existing `AutosemverUseCase` pattern. `kw_only=True` is mandatory for protocols-as-dataclasses to allow subclass field reordering without breaking callers.

**Pydantic models (config layer only) use `BaseModel` (not BaseSettings) when nested:**

```python
class GitLabConfig(pydantic.BaseModel):
    endpoint: str = "https://gitlab.com"
    token: pydantic.SecretStr = pydantic.Field(...)
```

`BaseSettings` is used **once**, on the top-level `Settings` class. Nested configs are plain `BaseModel`.

**Default factories for mutable defaults:**

```python
# YES
gitlab: GitLabConfig = pydantic.Field(default_factory=GitLabConfig)

# NO — same instance shared across runs
gitlab: GitLabConfig = GitLabConfig()
```

### Type-Annotation Style

**Existing autosemver conventions (preserved):**

- `typing.Final` on module-level constants: `MAIN_APP: typing.Final = typer.Typer()`
- `typing.cast` with quoted string for forward refs: `typing.cast("list[ProjectCommit]", ...)`
- `typing.TYPE_CHECKING` guard for type-only imports
- `typing.Annotated[..., modern_di_typer.FromDI(...)]` for Typer-DI parameter injection
- `ALL_GROUPS: typing.Final[list[type[Group]]]` style for module-level collection constants
- Suppression comment: `# ty: ignore` (per global CLAUDE.md)

**Avoid:**

- `from __future__ import annotations` — keep annotations evaluated; rely on `typing.TYPE_CHECKING` instead. `ty` handles forward refs fine.
- Bare `List`, `Dict`, etc. — use built-in generics: `list[str]`, `dict[str, int]`.

### Error Message Template — Named, Actionable Cause (FR30)

Every `SemvertagError` message follows a strict template so users see consistent, actionable diagnostics:

```
<NamedCondition>: <Cause>. <SuggestedAction>.
```

**Examples:**

```python
raise AuthError(
    "Token missing scope: 'write_repository'. "
    "Add 'write_repository' to the SEMVERTAG_TOKEN scopes on GitLab."
)

raise ConfigError(
    "Strategy not recognized: 'conventional'. "
    "Use one of: 'branch-prefix', 'conventional-commits'."
)

raise ProviderAPIError(
    "GitLab API unreachable after 3 attempts. "
    "Check SEMVERTAG_GITLAB__ENDPOINT and network connectivity."
)
```

**Rules:**

- Message starts with the **named condition** (matches the doctor check name when applicable).
- Includes the **specific value** that triggered the error (scope name, strategy string, endpoint).
- Ends with a **suggested action** the user can take.
- No HTTP status codes in user-facing messages (generic). Translate to the named condition.
- Single sentence per clause; period-separated; no trailing whitespace.

### Exception Construction Patterns

**Positional message argument only:**

```python
raise AuthError("Token missing scope: 'api'. ...")
```

**Avoid:**

- Keyword arguments on exception construction (`AuthError(message=..., scope=...)`) — pythonic exceptions accept positional `args`.
- Catching and re-raising without `from`:

```python
# YES — preserves traceback
try:
    response = client.get(url)
except httpx2.HTTPStatusError as exc:
    raise AuthError("Token missing scope: 'api'. ...") from exc

# NO — loses traceback
except httpx2.HTTPStatusError:
    raise AuthError("...")
```

### DI Group Conventions

**Module:** `semvertag/ioc.py` (matches existing autosemver pattern).

**Group naming:** plural, suffixed `Group`. Four groups in v1.0:

```python
class ProvidersGroup(modern_di.Group):
    gitlab_provider = modern_di.providers.Factory(...)
    # github_provider, bitbucket_provider — v1.x


class StrategiesGroup(modern_di.Group):
    branch_prefix_strategy = modern_di.providers.Factory(...)
    conventional_commits_strategy = modern_di.providers.Factory(...)


class OutputsGroup(modern_di.Group):
    rich_output = modern_di.providers.Factory(...)
    json_output = modern_di.providers.Factory(...)


class SettingsGroup(modern_di.Group):
    settings = modern_di.providers.Factory(scope=modern_di.Scope.APP, ...)


ALL_GROUPS: typing.Final[list[type[modern_di.Group]]] = [
    SettingsGroup, ProvidersGroup, StrategiesGroup, OutputsGroup,
]
```

**Active selection happens at use-case construction**, not via DI cleverness. The use case takes a `Provider` and a `BumpStrategy`; the entrypoint picks which Factory to resolve based on `settings.provider` / `settings.strategy`.

### CLI Flag Naming

**Hyphen-separated, lowercase, kebab-case:**

```
--project-id          # NOT --project_id
--strategy            # values: branch-prefix | conventional-commits
--provider            # values: gitlab | github | bitbucket
--gitlab-endpoint     # nested-config flags flatten to top-level kebab-case
--json                # boolean flag
--quiet               # boolean flag
--token               # convenience for SEMVERTAG_TOKEN
--default-branch
--request-timeout
```

**Rules:**

- Long form only at v1.0 (`--strategy`, not `-s`) — short forms are SemVer-locked once added.
- Nested settings flatten with hyphen: `settings.gitlab.endpoint` → `--gitlab-endpoint`.
- Boolean flags are positive (`--json`, not `--no-text`). Negation is the absence.

### Environment Variable Naming

- Top-level: `SEMVERTAG_<KEY>` (case-insensitive but documented uppercase).
- Nested: `SEMVERTAG_<GROUP>__<KEY>` with **double underscore** delimiter (matches `env_nested_delimiter="__"` in Settings).
- Provider-native fallbacks **do not** carry the `SEMVERTAG_` prefix (`CI_JOB_TOKEN`, `GITHUB_TOKEN` — set by the CI provider, not by us).
- Documented under FR25 stability surface; removal or rename follows the deprecation cycle (NFR25).

### JSON Field Naming

**snake_case** for all keys in `RunResult` and doctor envelope. Matches Python conventions and Conventional Commits / SemVer ecosystem norms.

```json
{
  "schema_version": "1.0",
  "strategy": "conventional-commits",
  "bump": "minor",
  "status": "created",
  "tag": "2.1.0",
  "commit": "a2b4d12",
  "reason": null
}
```

**Rules:**

- `schema_version` is always present, always first (by dataclass field ordering).
- Field additions are backward-compatible; renames or removals require `schema_version` bump + deprecation cycle (NFR25).
- `null` for unset optional fields, not omitted — consumers must rely on key presence.

### Test Naming & File Organization

**Test files** mirror source modules with `test_` prefix:

```
tests/
├── conftest.py                        # shared httpx2.MockTransport fixtures
├── unit/
│   ├── test_branch_prefix_strategy.py
│   ├── test_conventional_commits_strategy.py
│   ├── test_settings.py
│   ├── test_provenance.py
│   ├── test_output_rich.py
│   ├── test_output_json.py
│   ├── test_errors.py
│   ├── test_redact.py
│   └── test_transport_retry.py
└── integration/
    ├── test_cli_main_verb.py
    ├── test_cli_doctor.py
    └── test_cli_quiet_json_matrix.py
```

**Test function naming:**

```python
def test_bumps_minor_when_feature_prefix() -> None: ...
def test_skips_with_no_op_when_no_merge_commit() -> None: ...
def test_doctor_skips_dependent_checks_when_token_fails() -> None: ...
```

- Imperative, describes behavior, no `test_test_` prefixes.
- Format: `test_<verb>_<outcome>_when_<condition>`.
- One assertion-cluster per test (parameterize for variations).

**Use `typing.Final` on test-level constants** (existing autosemver pattern):

```python
TEST_RUNNER: typing.Final = CliRunner()
MOCK_PROJECT_ID: typing.Final = 999
```

### Module-Level Constants

All module-level immutable values get `typing.Final`:

```python
RETRYABLE_STATUSES: typing.Final = frozenset({408, 429, 500, 502, 503, 504})
MAX_ATTEMPTS: typing.Final = 3
DEFAULT_GITLAB_ENDPOINT: typing.Final = "https://gitlab.com"
```

Matches existing autosemver style (`MAIN_APP: typing.Final = typer.Typer()`).

### Comment Policy

Per global `CLAUDE.md`: no comments unless the **why** is non-obvious. Specifically:

- **Don't** comment what the code does — well-named identifiers do that.
- **Don't** reference tasks/issues ("Added for FR15 BREAKING CHANGE support") — that belongs in the commit message and PR.
- **Don't** add removed-code markers ("// removed callback").
- **Do** comment hidden constraints (workarounds, subtle invariants):

```python
# httpx2 strict-timeout default differs from requests; explicit per-request
# timeout here keeps us under NFR1's 30s p95 budget when retries fire.
client = httpx2.Client(transport=transport, timeout=settings.request_timeout)
```

Suppression comments use `# ty: ignore` (not `# type: ignore`).

### Import Style

Global imports per CLAUDE.md. Lazy imports **only** at the provider-selection boundary in `ioc.py`:

```python
# semvertag/ioc.py
def _gitlab_provider_factory(settings: Settings) -> Provider:
    from semvertag.providers.gitlab import GitLabProvider  # lazy
    return GitLabProvider(settings=settings.gitlab, ...)
```

Provider modules themselves use **only global imports**. The lazy boundary lives at the IoC layer so provider modules stay easy to read.

### Provider Implementation Pattern (FR22)

**One file per provider; ~150–200 LOC; documented `Provider` protocol shape:**

```python
# semvertag/providers/gitlab.py
import typing
import dataclasses
import httpx2
from semvertag._types import Commit, Tag, CheckResult
from semvertag._errors import AuthError, ConfigError, ProviderAPIError
from semvertag._settings import GitLabConfig


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class GitLabProvider:
    name: typing.ClassVar[str] = "gitlab"
    config: GitLabConfig
    client: httpx2.Client

    def get_default_branch(self) -> str: ...
    def get_latest_commit_on_default_branch(self) -> Commit: ...
    def list_tags(self) -> list[Tag]: ...
    def create_tag(self, name: str, commit_sha: str) -> None: ...

    def check_token(self) -> CheckResult: ...
    def check_scopes(self) -> CheckResult: ...
    def check_project_access(self) -> CheckResult: ...
    def check_protected_tags(self) -> CheckResult: ...
```

**Contributor reference docs** (`docs/contributing/adding-a-provider.md`) name this file as the canonical reference for new provider PRs (Journey 4 / FR22).

### Strategy Implementation Pattern

Same shape — one file per strategy, frozen-dataclass, takes a config object:

```python
# semvertag/strategies/branch_prefix.py
@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class BranchPrefixStrategy:
    name: typing.ClassVar[str] = "branch-prefix"
    config: BranchPrefixConfig

    def decide(self, commit: Commit) -> Bump: ...
```

### Enforcement Guidelines

**All AI Agents MUST:**

- Use the naming conventions above (Provider/Strategy/Group suffixes; snake_case files; PascalCase classes).
- Follow the error-message template exactly: `<NamedCondition>: <Cause>. <SuggestedAction>.`
- Use frozen dataclasses with `kw_only=True, slots=True` for all domain types.
- Annotate module-level constants with `typing.Final`.
- Apply `pydantic.SecretStr` for any token field; route all user-facing output through the redaction filter.
- Place new providers and strategies in single files under `semvertag/providers/` and `semvertag/strategies/` respectively.
- Map every error path to one of the documented `SemvertagError` subclasses (no bare `Exception` raises, no `print()` for errors).
- Cover bump-strategy parsing with 100% branch coverage (NFR22).

**Pattern Enforcement:**

- `ruff check` enforces the lint-level conventions (line length 120, double-quote strings, isort sections, etc.).
- `ty check` enforces type-annotation conventions.
- Code-review checklist in `CONTRIBUTING.md` includes: naming, error template, frozen dataclasses, SecretStr usage, exit-code mapping.
- Violations to existing patterns require explicit `# ty: ignore` or `# noqa: <rule>` with a one-line justification.

### Anti-Patterns to Avoid

- **`print()` calls anywhere outside `_output.py`** — all output flows through the Output protocol.
- **Bare `Exception` catches** that swallow context — always catch a specific httpx2/std exception class and re-raise as `SemvertagError`.
- **Module-level singletons of stateful clients** (httpx2.Client, modern-di Container) — these go through DI, scoped per CLI run.
- **String concatenation of token values** anywhere — use `SecretStr.get_secret_value()` only at the HTTP-call boundary and never in error messages or logs.
- **`from __future__ import annotations`** — keep evaluated annotations; rely on `typing.TYPE_CHECKING` for forward refs.
- **Comments restating WHAT the code does** — only the WHY when non-obvious.
- **Mutable default arguments** in functions or dataclasses — use `default_factory` for collections; `pydantic.Field(default_factory=...)` for nested configs.
- **HTTP retry logic outside `_transport.py`** — the RetryingTransport is the one place retries live.
- **Multiple BaseSettings classes** — there's exactly one (`Settings`); nested config is `BaseModel`.

## Project Structure & Boundaries

### Complete Project Directory Structure

```
semvertag/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                              # lint + pytest matrix (3.10–3.13) + codecov
│   │   └── publish.yml                         # PyPI trusted publishing on release: published
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   ├── feature_request.md
│   │   └── new_provider_request.md             # funnel for Journey 4 contributors (FR22)
│   └── PULL_REQUEST_TEMPLATE.md
│
├── templates/                                  # GitLab CI Catalog component descriptor (canonical Catalog-discoverable path)
│   └── semvertag.yml                           # FR40 — Catalog discovery. NOTE: this line corrects an earlier draft that placed the descriptor at `.gitlab/catalog/component.yml` (also the path in `epics.md:779`). GitLab Catalog ingestion strictly scans `templates/` for component `.yml` files — the `.gitlab/catalog/` path is NOT discoverable. Corrected during Story 4.3b code review (2026-05-30); resolves OQ1.
│
├── action.yml                                  # GitHub Actions Marketplace wrapper (FR41)
│
├── .gitignore
├── .readthedocs.yaml                           # mirrors modern-di
├── context7.json                               # AI-doc indexing (handle reservation post-launch)
├── CLAUDE.md                                   # semvertag-specific conventions
├── LICENSE                                     # MIT
├── README.md                                   # hero with copy-pasteable CI snippets + badges
├── SECURITY.md                                 # NFR14 — private vulnerability reporting
├── CONTRIBUTING.md                             # 4-command dev setup; provider PR funnel
├── CODE_OF_CONDUCT.md
├── CHANGELOG.md                                # release-note source (manual, not generated)
├── Justfile                                    # install / lint / lint-ci / test / test-branch / publish
├── pyproject.toml                              # uv_build backend; [project.scripts] semvertag
├── uv.lock                                     # pinned deps; reviewed before any minor bump
│
├── semvertag/                                  # source package (renamed from autosemver/)
│   ├── __init__.py
│   ├── __main__.py                             # Typer entrypoint; typer.Exit(code=N) handler
│   ├── py.typed                                # PEP 561 typed-package marker
│   │
│   ├── _types.py                               # Commit, Tag, CheckResult, RunResult, Bump,
│   │                                           #   ConfigSource — internal, not NFR25-stable
│   ├── _errors.py                              # SemvertagError, ConfigError, AuthError,
│   │                                           #   ProviderAPIError
│   ├── _settings.py                            # Settings(BaseSettings) + nested *Config
│   │                                           #   BaseModels + settings_customise_sources
│   │                                           #   provenance recorder
│   ├── _transport.py                           # RetryingTransport(httpx2.BaseTransport)
│   ├── _redact.py                              # Token redaction (NFR10) — pattern matchers
│   ├── _output.py                              # Output protocol; RichOutput; JsonOutput
│   ├── _use_case.py                            # SemvertagUseCase — orchestrates Provider +
│   │                                           #   BumpStrategy + Output
│   ├── ioc.py                                  # modern-di Groups (Settings/Providers/
│   │                                           #   Strategies/Outputs); ALL_GROUPS export
│   │
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── _base.py                            # Provider protocol (FR22 canonical reference)
│   │   ├── gitlab.py                           # GitLabProvider — v1.0 ships
│   │   ├── github.py                           # v1.x — file present, lazy-imported via ioc
│   │   └── bitbucket.py                        # v1.x — file present, lazy-imported via ioc
│   │
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── _base.py                            # BumpStrategy protocol
│   │   ├── branch_prefix.py                    # BranchPrefixStrategy
│   │   └── conventional_commits.py             # ConventionalCommitsStrategy
│   │
│   └── doctor/
│       ├── __init__.py
│       └── _checks.py                          # Chain runner; skip-on-failure ordering;
│                                               #   exit-code dominance resolver
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                             # shared httpx2.MockTransport fixtures;
│   │                                           #   compose_handler helper
│   │
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_branch_prefix_strategy.py      # 100% branch coverage gate (NFR22)
│   │   ├── test_conventional_commits_strategy.py  # 100% branch coverage gate (NFR22)
│   │   ├── test_settings.py                    # AliasChoices resolution, defaults, types
│   │   ├── test_provenance.py                  # settings_customise_sources tracking
│   │   ├── test_output_rich.py                 # progress + emit; stdout/stderr discipline
│   │   ├── test_output_json.py                 # schema_version envelope; null vs omitted
│   │   ├── test_errors.py                      # exit_code mapping; error template
│   │   ├── test_redact.py                      # token-pattern detection (glpat-, ghp_, ATBB)
│   │   └── test_transport_retry.py             # retry budget; backoff math; Retry-After
│   │
│   └── integration/
│       ├── __init__.py
│       ├── test_cli_main_verb.py               # CliRunner + MockTransport — full flows
│       ├── test_cli_doctor.py                  # doctor subcommand; chain skip semantics
│       └── test_cli_quiet_json_matrix.py       # --quiet × --json interaction (4-cell)
│
└── docs/                                       # mkdocs + Material; deployed via Read the Docs
    ├── requirements.txt                        # mkdocs-material + plugins
    ├── index.md                                # Quick Start (5-min path to first tag)
    ├── cli-reference.md                        # all flags + exit codes + JSON schema
    ├── strategies/
    │   ├── branch-prefix.md
    │   └── conventional-commits.md
    ├── providers/
    │   ├── gitlab.md
    │   ├── github.md                           # v1.x — present with "coming in v1.x" notice
    │   └── bitbucket.md                        # v1.x — present with "coming in v1.x" notice
    ├── doctor.md                               # all four checks; output examples
    ├── api-stability.md                        # FR44 — what is/isn't SemVer-stable
    ├── contributing/
    │   ├── dev-setup.md                        # 4-command recipe
    │   └── adding-a-provider.md                # Journey 4 reference — points at gitlab.py
    ├── migrating-from-semantic-release.md      # FR43
    ├── migrating-from-go-semrel-gitlab.md      # FR43
    └── migrating-from-rightbrain-auto-semver.md # FR43
```

### Architectural Boundaries

**External boundaries (semvertag → outside world):**

| Boundary | Direction | Mechanism | Where it lives |
|---|---|---|---|
| Provider REST API (GitLab/GitHub/Bitbucket) | semvertag → external | httpx2 over HTTPS via `RetryingTransport` | `_transport.py` + each `providers/<vendor>.py` |
| CI environment variables | external → semvertag | `os.environ` via pydantic-settings + `AliasChoices` fallback chain | `_settings.py` |
| Process exit code | semvertag → CI runner | `typer.Exit(code=N)` raised at the CLI boundary | `__main__.py` |
| stdout / stderr | semvertag → CI logs | two `rich.Console` instances; strict no-interleaving | `_output.py` |
| PyPI (publish) | CI → external | trusted publishing via OIDC | `.github/workflows/publish.yml` |

**Internal boundaries (within the package):**

| Boundary | Mechanism |
|---|---|
| CLI entrypoint ↔ Use case | Typer command receives DI-resolved use case; passes through |
| Use case ↔ Provider | `Provider` protocol; one method per logical action |
| Use case ↔ BumpStrategy | `BumpStrategy.decide(commit) -> Bump` — pure function on the latest commit |
| Use case ↔ Output | `Output` protocol; `progress(msg)` for narrative, `emit(RunResult)` for final |
| Doctor ↔ Provider | Same `Provider` protocol; uses only the four `check_*` methods |
| Settings ↔ everything | DI-injected; never imported as a module global |
| Errors ↔ exit codes | Mapped at one place — `__main__.py` Typer callback |

**No internal modules import `httpx2` directly** except `_transport.py`, `providers/*.py`, and `_settings.py` (for AliasChoices type hints). The retry transport is the one HTTP-policy choke point.

### Requirements → Structure Mapping

**FR Categories → Modules:**

| FR Category (PRD) | Primary location | Supporting locations |
|---|---|---|
| Tag Creation (FR1–FR10) | `_use_case.py` | `providers/gitlab.py`, `_transport.py` |
| Bump Strategy (FR11–FR16) | `strategies/branch_prefix.py`, `strategies/conventional_commits.py` | `_settings.py` (config models) |
| Provider Integration (FR17–FR22) | `providers/_base.py` (protocol), `providers/gitlab.py` (v1.0 impl) | `_transport.py` (retry middleware), `ioc.py` (selection) |
| Configuration & Environment (FR23–FR28) | `_settings.py` | `__main__.py` (CLI overlay), `_redact.py` (token redaction) |
| Diagnostics & Validation (FR29–FR32) | `doctor/_checks.py` | `_output.py` (config-source renderer), `providers/gitlab.py` (`check_*` methods) |
| CLI Surface & Output (FR33–FR39) | `__main__.py` | `_output.py`, `_errors.py` |
| CI Distribution (FR40–FR42) | `.gitlab/catalog/component.yml`, `action.yml` | `README.md` (snippets) |
| Documentation & Trust (FR43–FR46) | `docs/`, `CONTRIBUTING.md`, `SECURITY.md`, `README.md` | `pyproject.toml` (badges metadata) |

**Cross-cutting concerns:**

| Concern | Lives in | Reason |
|---|---|---|
| Token redaction (NFR10) | `_redact.py` + `pydantic.SecretStr` in `_settings.py` | One pattern-matcher; output-boundary filter; SecretStr defense-in-depth |
| Retry & rate-limit (NFR7) | `_transport.py` only | One choke point; every provider call passes through |
| Exit-code mapping (FR37, NFR25) | `__main__.py` only | One place exception → exit code conversion happens |
| Config provenance (FR32) | `_settings.py` (`settings_customise_sources`) | Recorded once at resolution; consumed by doctor |
| Stream discipline (FR38) | `_output.py` only | Two consoles; no interleaving |

### Integration Points & Data Flow

**Startup data flow:**

```
os.environ + sys.argv
        │
        ▼
  Settings(BaseSettings) ──[env+default resolution]──► env_resolved Settings
        │
        ▼
  Typer callback ──[CLI overlay via .model_copy(update=...)]──► final Settings (+ _provenance)
        │
        ▼
  modern-di Container ──[lazy Factory resolution]──► Provider, BumpStrategy, Output
        │
        ▼
  SemvertagUseCase(provider, strategy, output)
```

**Main verb run-time flow:**

```
SemvertagUseCase.run()
  │
  ├─► output.progress("Detected strategy: branch-prefix")
  │
  ├─► provider.get_default_branch()
  │     └─► RetryingTransport ──HTTPS──► GitLab GET /api/v4/projects/{id}
  │
  ├─► provider.get_latest_commit_on_default_branch()
  │     └─► RetryingTransport ──HTTPS──► GET /repository/commits?ref_name=...
  │
  ├─► provider.list_tags()
  │     └─► RetryingTransport ──HTTPS──► GET /repository/tags
  │     └─► filter to semver-conforming (FR8)
  │
  ├─► strategy.decide(latest_commit) ──► Bump.MINOR
  │
  ├─► (compute new_version from last_tag + bump)
  │
  ├─► provider.create_tag(name=new_version, commit_sha=...)
  │     └─► RetryingTransport ──HTTPS──► POST /repository/tags
  │
  └─► output.emit(RunResult(status="created", tag=new_version, ...))
                          │
                          ▼
                  stdout (rich lines or JSON envelope)
```

**Doctor subcommand flow:**

```
DoctorCheckRunner.run()
  │
  └─► for check in (token, scopes, project_access, protected_tags):
        if any prerequisite failed → CheckResult(status="skipped", ...)
        else → provider.check_<name>()  ──HTTPS──► provider API
        accumulate into list[CheckResult]
  │
  ├─► output.emit_doctor(config=settings._provenance, checks=results)
  │     │
  │     ▼
  │   stdout (config section + checks section)
  │
  └─► typer.Exit(code=dominant_failure_code)
```

**Error flow:**

```
provider.<method>()
  │
  ├─► httpx2.ConnectError | ReadTimeout | RemoteProtocolError | HTTPStatusError
  │     │
  │     ▼
  │   per-provider translation in gitlab.py / github.py / bitbucket.py
  │     │
  │     ▼
  │   raise AuthError | ConfigError | ProviderAPIError ("from exc")
  │     │
  │     ▼ propagates up to ...
  │
  ├─► __main__.py Typer callback catches SemvertagError
  │     │
  │     ├─► error_console.print(str(err))                       # to stderr (NFR10 redacted)
  │     └─► raise typer.Exit(code=err.exit_code) from err
  │           │
  │           ▼
  │         process exits with code 1 / 2 / 3 / 4 (FR37)
```

### File Organization Patterns

**Configuration files at repo root** (not in a `config/` subdirectory):

- `pyproject.toml` — single source of truth for tool configuration (build, lint, type-check, pytest, coverage).
- `Justfile` — task runner (install, lint, test, publish).
- `.readthedocs.yaml`, `mkdocs.yml`, `context7.json`, `CLAUDE.md` — docs/AI metadata.

**Source code is flat** (no `src/` layout). Matches both modern-di and existing autosemver/. `[tool.uv.build-backend]` configured for `module-root = ""`.

**Tests mirror source layout** within `unit/` and `integration/` subdirectories. Shared fixtures in `tests/conftest.py`.

**Documentation under `docs/`** with mkdocs-material; flat naming for top-level concepts; subdirectories only for groupings with >2 pages (`providers/`, `strategies/`, `contributing/`).

### Development Workflow Integration

**Development server:** none — semvertag is a batch CLI, not a server. Local dev loop:

```bash
just install      # uv lock --upgrade; uv sync --all-extras --frozen --group lint
just lint         # eof-fixer + ruff format + ruff check --fix + ty check
just test         # pytest --cov=. --cov-report term-missing
just              # default: install + lint + test
```

**Build process:**

```bash
uv build          # produces dist/*.whl + dist/*.tar.gz via uv_build backend
```

Driven by `just publish` (which runs in `publish.yml` on `release: published`).

**Deployment:**

- PyPI via `uv publish` with **PyPI trusted publishing** (no long-lived `PYPI_TOKEN`; NFR13).
- Read the Docs deploys on push to `main` via `.readthedocs.yaml`.
- GitHub Actions Marketplace: published from `action.yml` automatically by tagging a release.
- GitLab CI Catalog: published from `.gitlab/catalog/component.yml` on release tag.

**Documentation:**

- mkdocs site builds in CI as a smoke check (`mkdocs build --strict` in `ci.yml`).
- Read the Docs builds on `main` branch push; serves at `semvertag.readthedocs.io` (or chosen domain).

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**

All chosen technologies compose cleanly. The httpx2 + modern-di-typer + pydantic-settings + Typer + rich stack has no internal conflicts. httpx2's `MockTransport` covers test mocking without requiring a third-party library. modern-di's `Factory` lazy resolution naturally supports v1.x optional provider extras (now collapsed to lazy imports since extras were dropped).

The only friction point identified during decisions — `requests-mock`-compatibility — was resolved by adopting `httpx2.MockTransport` (PRD edit flagged).

**Pattern Consistency:**

- Frozen-dataclass discipline is uniform (domain types, configs, RunResult).
- pydantic `BaseModel` (nested) vs. `BaseSettings` (root once) boundary is consistent.
- `typing.Final` usage matches existing autosemver/ idiom.
- Provider/Strategy/Group naming follows the `<Concept><Suffix>` rule throughout.
- Error-message template enforced by code-review checklist; uniform across all `SemvertagError` subclasses.

**Structure Alignment:**

- `_transport.py` is the single retry choke point — every provider call passes through it (cross-cutting concern boundary respected).
- `_redact.py` + `SecretStr` is the single redaction boundary (NFR10 defense-in-depth).
- `__main__.py` is the single exception → exit-code conversion point (FR37 single source of truth).
- `_settings.py` is the single config provenance source (FR32).
- `_output.py` is the single stream-discipline boundary (FR38).

No architectural decisions contradict each other. The constraint set is internally consistent.

### Requirements Coverage Validation ✅

**Functional Requirements (46 total — all covered):**

| FR Range | Topic | Architectural Support |
|---|---|---|
| FR1–FR10 | Tag creation, edge cases | `_use_case.py` orchestrates; `RunResult.status` enum encodes all no-op paths (FR3/FR4/FR6/FR7); provider API as source of truth for tags/commits (FR10/NFR15) |
| FR11–FR16 | Bump strategies | `strategies/branch_prefix.py`, `strategies/conventional_commits.py`; user-extensible mappings via frozen-dataclass configs (FR13/FR16) |
| FR17–FR22 | Provider integration | `providers/` directory with protocol + one file per implementation; httpx2 transport common; lazy import preserves contributor onramp (FR22) |
| FR23–FR28 | Config & env | env + CLI only in v1.0 (FR23/FR24 deferred); `AliasChoices` chain for provider-native fallbacks (FR26); FR27 simplified to 3 layers (PRD edit) |
| FR29–FR32 | Doctor & diagnostics | `doctor/_checks.py` chain runner; `Settings._provenance` for FR32 |
| FR33–FR39 | CLI surface | Typer + RunResult + typed exception hierarchy; FR36 wording edit flagged |
| FR40–FR42 | CI distribution | `.gitlab/catalog/component.yml`, `action.yml`, `[project.scripts]` for uvx |
| FR43–FR46 | Docs & trust | `docs/migrating-from-*.md`, `docs/api-stability.md`, `CONTRIBUTING.md`, README hero (FR46 wording edit flagged) |

**Non-Functional Requirements (30 total — all covered):**

| NFR Range | Topic | Architectural Support |
|---|---|---|
| NFR1–NFR4 | Performance | per-request 8s × 3 attempts + ~3s backoff = ~27s worst-case < NFR1 30s; sequential doctor < NFR4 10s; `uvx` cold-start naturally satisfies NFR2 |
| NFR5–NFR9 | Reliability | Bump.NONE + RunResult.status enum for benign no-ops (NFR5/NFR6); `RetryingTransport` enforces NFR7; `AuthError` fail-closed for NFR8; external shadow-mode in pypelines for NFR9 |
| NFR10–NFR14 | Security | `SecretStr` + `_redact.py` for NFR10; no file layer + URL/templating bans for NFR11; pip-audit job in CI (added to implementation step 9) for NFR12; trusted publishing in publish.yml for NFR13; SECURITY.md for NFR14 |
| NFR15–NFR20 | Integration | GitLab CE/EE 15.0+ supported via REST stability; GitHub/Bitbucket v1.x stubs in place; `RunResult.schema_version` for NFR20 |
| NFR21–NFR26 | Maintainability | tight component count + ~6 modules sits comfortably under 1500 LOC (NFR21); coverage gates in `pyproject.toml`+CI (NFR22); ruff ALL + ty (NFR23); internal modules explicitly marked (NFR25) |
| NFR27–NFR30 | Compatibility | pytest matrix 3.10–3.13 (NFR27); ubuntu-latest in CI (NFR28); `astral-sh/setup-uv@v3` (NFR29); Python EOL+12mo doc'd (NFR30) |

**Cross-cutting NFR coverage:** every cross-cutting concern (redaction, retry, exit-code mapping, stream discipline, provenance) has a documented single owner — no concern is spread across multiple modules.

### Implementation Readiness Validation ✅

**Decision Completeness:**

All 9 step-04 categories closed with sub-decisions recorded. Code sketches included for protocols, exception hierarchy, RunResult envelope, RetryingTransport, Settings, doctor checks, output protocol. No "TBD" placeholders in the architecture document.

**Structure Completeness:**

Full repo tree enumerated in step-06 with FR-category mapping. Every module has a stated responsibility; every cross-cutting concern has a stated home. No "more directories TBD" gaps.

**Pattern Completeness:**

13 conflict-point categories defined in step-05, each with concrete rules and examples. Enforcement mechanisms named (ruff, ty, code-review checklist, # ty: ignore policy). Anti-patterns listed.

### Gap Analysis Results

**Critical Gaps:** none.

**Important Gaps:**

1. **FR9 fallback semantics** — PRD specifies "git symbolic-ref refs/remotes/origin/HEAD" as the default-branch fallback "when no provider context is available," but the current architecture always constructs a Provider. This fallback path doesn't fire in normal CI flow. Two possible resolutions: (a) scope to a future `--offline` / `--explain` mode (v1.x); (b) trim from FR9 wording. Either way, it's a **PRD touch-up**, not an architectural gap. Tracked in PRD-edit backlog item #8.

**Minor Gaps (tooling, fits in implementation sequence):**

These are implementation details that belong in CI workflow files, not architectural decisions. The architecture already specifies the *what*; these are *how* details for the trust-surface scaffolding story:

- `pip-audit` job in `ci.yml` (NFR12) — add as a workflow step alongside lint and pytest.
- LOC counting CI gate for NFR21's "soft target visible in CI" — simple `wc -l` check on `semvertag/**/*.py` with a warning threshold.
- Quarterly `uv lock --upgrade` cron in `.github/workflows/` (NFR26) — separate workflow file.

These three are part of step 9 of the implementation sequence (Trust-surface scaffolding) and don't block implementation start.

### Validation Issues Addressed

The PRD edits surfaced during architecture work are tracked in the **PRD Touch-Ups Required** section earlier in this document (8 items as of this validation). None block implementation; all should resolve before public v1.0 announcement.

### Architecture Completeness Checklist

**Requirements Analysis**

- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed
- [x] Technical constraints identified
- [x] Cross-cutting concerns mapped

**Architectural Decisions**

- [x] Critical decisions documented with versions (httpx2 v2.2.0+ pinned, Python 3.10–3.13, others via uv.lock)
- [x] Technology stack fully specified
- [x] Integration patterns defined
- [x] Performance considerations addressed (request timeout × retry × backoff budget math)

**Implementation Patterns**

- [x] Naming conventions established
- [x] Structure patterns defined
- [x] Communication patterns specified (Provider/BumpStrategy/Output protocols)
- [x] Process patterns documented (error template, retry policy, doctor chain)

**Project Structure**

- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

All 16 checklist items confirmed. No Critical Gaps remain. The Important Gap (FR9 fallback) is a PRD wording question, not an architectural blocker — the architecture's behavior in normal CI flow is fully specified.

**Confidence Level:** High.

**Key Strengths:**

- **Single-source-of-truth discipline.** Every cross-cutting concern (retry, redaction, exit-codes, provenance, stream discipline) has exactly one home. Bugs are local; changes are local.
- **httpx2.MockTransport eliminates an external test dep.** The decision to use httpx2 + built-in MockTransport removed dependency on respx/pytest-httpx (neither shipping httpx2 support yet), keeping bleeding edge in production code only.
- **TOML scope-cut frees implementation budget.** Dropping TOML config from v1.0 (per real deployment shape) buys headroom under NFR21's 1500 LOC ceiling. v1.x can add it without breaking changes — TOML is a new precedence layer, not a removed one.
- **Optional-extras drop honest with the stack.** Choosing httpx2 for all providers removed the need for `[github]`/`[bitbucket]` extras; dropping them avoids vestigial structure.
- **Existing autosemver/ idioms preserved where they made sense.** Frozen-dataclass use case, `typing.Final` constants, modern-di Groups, `requests-mock` URL-level mocking (now httpx2.MockTransport URL-level handlers) — continuity reduces refactor risk for NFR9 shadow-mode parity.
- **PRD-edit backlog is explicit.** 8 PRD touch-ups recorded with line-level context; can be applied in one `/bmad-edit-prd` pass before public announcement.

**Areas for Future Enhancement (v1.x and beyond):**

- TOML config support (`pyproject.toml` `[tool.semvertag]` first; `.semvertag.toml` second).
- Per-branch strategy switching (v1.0 supports per-repo only).
- `--explain` / `--dry-run` flags with a structured decision-trace output.
- Pre-release / RC tag support (`-rc.1`, `-beta.2`).
- In-repo recorded-fixture parity corpus (belt-and-braces with external shadow-mode).
- Parallel doctor checks (only worth the async sprawl if NFR4's 10s budget tightens).
- `mise` / `asdf` plugin (polyglot DevOps reach).
- Family-of-repos packaging (`semvertag-gitlab`, etc.) if provider count grows beyond ~4 (v2.x escape hatch from PRD vision).

### Implementation Handoff

**AI Agent Guidelines:**

- Follow all architectural decisions in §Core Architectural Decisions exactly. Internal modules (`semvertag.providers.*`, `semvertag.strategies.*`, `_*.py` prefix) are explicitly NOT NFR25-stable — refactor within them is free; external surfaces (CLI flags, env keys, exit codes, JSON envelope) are SemVer-stable post-1.0.
- Use the naming and pattern rules in §Implementation Patterns consistently across every PR.
- Respect the structure boundaries in §Project Structure. Cross-cutting concerns each have one owner module; do not duplicate logic across modules.
- Refer to this document for all architectural questions before opening PRs that introduce new modules or break protocols.
- When in doubt, lean toward removing rather than adding (NFR21's 1500-LOC soft ceiling).

**First Implementation Priority:**

The first implementation story is the bootstrap defined in §Starter Template Evaluation:

```bash
# Phase A — Scaffold from modern-di's shape (Justfile, pyproject.toml,
#   .github/workflows/{ci.yml, publish.yml}, mkdocs.yml, .readthedocs.yaml,
#   LICENSE, context7.json, docs/requirements.txt).
# Phase B — Port logic from autosemver/ (Settings with SEMVERTAG_ prefix and
#   nested *Config models; provider-agnostic ioc.py; bump algorithm refactored
#   into Provider + BumpStrategy protocols; existing tests ported to
#   httpx2.MockTransport fixtures).
# Phase C — Shadow-mode validation in pypelines for one release cycle (NFR9).
```

**Implementation sequence is documented in §Core Architectural Decisions → Decision Impact Analysis.** Stories should be sequenced in that order to minimize rework risk.

**PRD touch-ups (in §PRD Touch-Ups Required) should be applied via `/bmad-edit-prd` before public v1.0 announcement** — they don't block implementation start.
