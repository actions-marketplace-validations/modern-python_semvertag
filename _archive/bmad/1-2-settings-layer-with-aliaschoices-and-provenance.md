# Story 1.2: Settings layer with token AliasChoices chain and source provenance

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a CLI user,
I want semvertag to resolve configuration from `SEMVERTAG_TOKEN`, falling back to provider-native variables (`CI_JOB_TOKEN`, `GITLAB_TOKEN`) automatically, and to track which source supplied each value,
so that I can run `uvx semvertag` in any documented CI environment with zero additional configuration, and so that `semvertag doctor` (downstream) can show me where each effective value came from.

## Acceptance Criteria

### AC1 — Defaults with no environment set

**Given** `Settings(BaseSettings)` is defined with `env_prefix="SEMVERTAG_"` and `env_nested_delimiter="__"`
**When** I instantiate `Settings()` with no relevant environment variables set
**Then** `settings.provider == "gitlab"`, `settings.strategy == "branch-prefix"`, and `settings.gitlab.token.get_secret_value() == ""`
**And** `settings.gitlab.endpoint == "https://gitlab.com"`
**And** `settings.default_branch is None`
**And** `settings.request_timeout == 8.0`

### AC2 — Provider-native fallback via AliasChoices

**Given** only `CI_JOB_TOKEN` is set in the environment (no `SEMVERTAG_TOKEN`, no `GITLAB_TOKEN`)
**When** I instantiate `Settings()`
**Then** `settings.gitlab.token.get_secret_value()` equals `CI_JOB_TOKEN`'s value (via `AliasChoices` fallback)
**And** `settings._provenance["gitlab.token"] == ConfigSource(layer="env", detail="CI_JOB_TOKEN")`

### AC3 — SEMVERTAG_TOKEN beats provider-native

**Given** both `SEMVERTAG_TOKEN=tok-A` and `GITLAB_TOKEN=tok-B` are set
**When** I instantiate `Settings()`
**Then** `settings.gitlab.token.get_secret_value() == "tok-A"` (SEMVERTAG_TOKEN wins per AliasChoices order)
**And** `settings._provenance["gitlab.token"] == ConfigSource(layer="env", detail="SEMVERTAG_TOKEN")`

### AC4 — Nested-prefixed form has highest env precedence

**Given** `SEMVERTAG_GITLAB__TOKEN=tok-nested` and `SEMVERTAG_TOKEN=tok-flat` and `CI_JOB_TOKEN=tok-ci` are all set
**When** I instantiate `Settings()`
**Then** `settings.gitlab.token.get_secret_value() == "tok-nested"`
**And** `settings._provenance["gitlab.token"] == ConfigSource(layer="env", detail="SEMVERTAG_GITLAB__TOKEN")`

### AC5 — Nested env-var resolution for non-aliased fields

**Given** `SEMVERTAG_GITLAB__ENDPOINT=https://gitlab.example.com` is set
**When** I instantiate `Settings()`
**Then** `settings.gitlab.endpoint == "https://gitlab.example.com"`
**And** `settings._provenance["gitlab.endpoint"] == ConfigSource(layer="env", detail="SEMVERTAG_GITLAB__ENDPOINT")`

### AC6 — Defaults recorded as `layer="default"`

**Given** no relevant env vars are set
**When** I instantiate `Settings()`
**Then** `settings._provenance["strategy"] == ConfigSource(layer="default", detail="default")`
**And** `settings._provenance["gitlab.token"] == ConfigSource(layer="default", detail="default")`
**And** every documented setting key has an entry in `_provenance`

### AC7 — CLI overlay via `model_copy` records `layer="cli"`

**Given** Settings is instantiated and provenance is recorded
**When** I overlay a CLI flag via `apply_cli_overlay(settings, {"strategy": ("conventional-commits", "--strategy")})`
**Then** the returned Settings has `strategy == "conventional-commits"`
**And** `_provenance["strategy"] == ConfigSource(layer="cli", detail="--strategy")`
**And** every other `_provenance` entry is preserved unchanged from the pre-overlay Settings

### AC8 — CLI beats env (FR27)

**Given** `SEMVERTAG_TOKEN=env-tok` is set and the CLI passes `--token cli-tok`
**When** Settings is instantiated and `apply_cli_overlay(settings, {"gitlab.token": (SecretStr("cli-tok"), "--token")})` is applied
**Then** `settings.gitlab.token.get_secret_value() == "cli-tok"`
**And** `settings._provenance["gitlab.token"] == ConfigSource(layer="cli", detail="--token")`

### AC9 — `repr()` never leaks the token

**Given** `Settings(gitlab=GitLabConfig(token=SecretStr("plaintext-secret")))` is constructed
**When** the object is rendered via `repr(settings)` or `str(settings.gitlab.token)`
**Then** the string `"plaintext-secret"` does NOT appear in the output (Pydantic's `SecretStr` renders as `**********`)

### AC10 — `request_timeout` clamped to ≤10.0

**Given** `SEMVERTAG_REQUEST_TIMEOUT=99` is set
**When** I instantiate `Settings()`
**Then** `settings.request_timeout == 10.0` (clamp applied via field validator)
**And** values ≤10 pass through unchanged

### AC11 — Unit-test coverage

**Given** unit tests in `tests/unit/test_settings.py` and `tests/unit/test_provenance.py`
**When** the test suite runs
**Then** every AC above is covered, including: AliasChoices precedence ordering, nested env-var resolution, default fallbacks, CLI overlay, SecretStr redaction in repr, and the `request_timeout` clamp
**And** `just lint`, `just lint-ci`, and `just test` all pass
**And** `_settings.py` line coverage is ≥85% in the term-missing report

## Tasks / Subtasks

- [x] **Task 1: Add `ConfigSource` to `semvertag/_types.py`** (AC: #2, #3, #4, #5, #6, #7, #8)
  - [x] 1.1 Create `semvertag/_types.py` with a single frozen, slotted, kw-only dataclass `ConfigSource(layer: Literal["cli", "env", "default"], detail: str)`. Use stdlib `dataclasses.dataclass(frozen=True, slots=True, kw_only=True)`.
  - [x] 1.2 Imports: `dataclasses`, `typing`. NO `from __future__ import annotations`. NO docstring on the class (`D1*` is ignored by ruff but architecture comment policy: avoid pure WHAT comments).
  - [x] 1.3 Verify the file's lint cleanliness via `just lint`.

- [x] **Task 2: Create strategy-config dataclass stubs** (AC: #1)
  - [x] 2.1 Create `semvertag/strategies/__init__.py` (empty).
  - [x] 2.2 Create `semvertag/strategies/branch_prefix.py` containing ONLY `BranchPrefixConfig` (frozen, slots, kw_only=True per architecture §Bump Strategy Abstraction). Fields: `minor: tuple[str, ...] = ("feature/",)`, `patch: tuple[str, ...] = ("bugfix/", "hotfix/")`, `merge_mark_text: str = "Merge branch"`. The Strategy class itself lands in Story 1.6 — DO NOT add it here.
  - [x] 2.3 Create `semvertag/strategies/conventional_commits.py` containing ONLY `ConventionalCommitsConfig` (frozen, slots, kw_only=True). Fields: `minor_types: tuple[str, ...] = ("feat",)`, `patch_types: tuple[str, ...] = ("fix", "perf")`. Strategy class lands in Story 2.1 — DO NOT add it here.
  - [x] 2.4 Imports global per `CLAUDE.md`; no lazy imports. Module-level constants (if any) get `typing.Final`.

- [x] **Task 3: Implement `semvertag/_settings.py`** (AC: #1, #2, #3, #4, #5, #10)
  - [x] 3.1 Import block (global, alphabetized per ruff isort): `dataclasses`, `os`, `typing`, `pydantic`, `pydantic_settings`. Then local: `from semvertag._types import ConfigSource`, `from semvertag.strategies.branch_prefix import BranchPrefixConfig`, `from semvertag.strategies.conventional_commits import ConventionalCommitsConfig`.
  - [x] 3.2 Define module-level alias-choice constants with `typing.Final` (improves readability + auto-typing-final compliance):
    ```python
    _GITLAB_TOKEN_ALIASES: typing.Final = pydantic.AliasChoices(
        "SEMVERTAG_GITLAB__TOKEN", "SEMVERTAG_TOKEN", "CI_JOB_TOKEN", "GITLAB_TOKEN",
    )
    _GITHUB_TOKEN_ALIASES: typing.Final = pydantic.AliasChoices(
        "SEMVERTAG_GITHUB__TOKEN", "SEMVERTAG_TOKEN", "GITHUB_TOKEN",
    )
    ```
  - [x] 3.3 Define `class GitLabConfig(pydantic.BaseModel)`:
    - `endpoint: str = "https://gitlab.com"`
    - `token: pydantic.SecretStr = pydantic.Field(default=pydantic.SecretStr(""), validation_alias=_GITLAB_TOKEN_ALIASES)`
  - [x] 3.4 Define `class GitHubConfig(pydantic.BaseModel)`:
    - `token: pydantic.SecretStr = pydantic.Field(default=pydantic.SecretStr(""), validation_alias=_GITHUB_TOKEN_ALIASES)`
  - [x] 3.5 Define `class Settings(pydantic_settings.BaseSettings)`:
    ```python
    model_config = pydantic_settings.SettingsConfigDict(
        env_prefix="SEMVERTAG_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )
    strategy: typing.Literal["branch-prefix", "conventional-commits"] = "branch-prefix"
    provider: typing.Literal["gitlab", "github", "bitbucket"] = "gitlab"
    default_branch: str | None = None
    request_timeout: float = 8.0
    gitlab: GitLabConfig = pydantic.Field(default_factory=GitLabConfig)
    github: GitHubConfig = pydantic.Field(default_factory=GitHubConfig)
    branch_prefix: BranchPrefixConfig = pydantic.Field(default_factory=BranchPrefixConfig)
    conventional_commits: ConventionalCommitsConfig = pydantic.Field(default_factory=ConventionalCommitsConfig)
    _provenance: dict[str, ConfigSource] = pydantic.PrivateAttr(default_factory=dict)
    ```
  - [x] 3.6 Add `@pydantic.field_validator("request_timeout")` that clamps the value to `min(value, 10.0)`. Architecture §Provider Abstraction §Per-request timeout: 8s default, configurable, clamped ≤10s.
  - [x] 3.7 Implement provenance recording as a `@pydantic.model_validator(mode="after")` on `Settings` that calls a helper `_scan_env_provenance(self)` — see Task 4 for the helper.
  - [x] 3.8 Expose a module-level helper `apply_cli_overlay(settings: Settings, overrides: dict[str, tuple[typing.Any, str]]) -> Settings`:
    - `overrides` keys are dotted paths (`"strategy"`, `"gitlab.token"`); values are `(new_value, flag_detail)` tuples.
    - Build an update dict suitable for `model_copy(update=...)`. For dotted keys targeting nested BaseModels, use `<nested>.model_copy(update=...)` on the nested instance and pass the new nested instance in the outer `update`.
    - Return a fresh Settings via `settings.model_copy(update=update_dict, deep=False)`.
    - Copy `settings._provenance` into the new instance, then overwrite each overridden key with `ConfigSource(layer="cli", detail=flag_detail)`.
  - [x] 3.9 Do NOT add a `print()` anywhere. No bare `Exception` catches. No `from __future__ import annotations`. `# ty: ignore` only if pydantic's dynamic types break ty (architecture §Type-Annotation Style).

- [x] **Task 4: Implement provenance scanner** (AC: #2, #3, #4, #5, #6)
  - [x] 4.1 In `_settings.py`, define `_scan_env_provenance(settings: Settings) -> None` (private to the module). Pure function modifying `settings._provenance` in place via `settings._provenance.update(...)`.
  - [x] 4.2 Walk `Settings.model_fields` recursively. For each leaf field (non-BaseModel), build the dotted key path (e.g., `"gitlab.token"`).
  - [x] 4.3 Determine the env source: collect alias candidates by checking `FieldInfo.validation_alias` (`AliasChoices.choices` returns a list); if no `validation_alias`, derive the default env var name as `f"SEMVERTAG_{dotted_path.upper().replace('.', '__')}"`. Iterate aliases in order — first one present in `os.environ` is the source.
  - [x] 4.4 If any alias matched: record `ConfigSource(layer="env", detail=<matched_name>)`. Else: record `ConfigSource(layer="default", detail="default")`.
  - [x] 4.5 Handle nested `BaseModel` fields by recursing with the updated dotted prefix. Use `Settings.model_fields[name]` to discover the field's annotation and decide recursion (`issubclass(annotation, pydantic.BaseModel)`).
  - [x] 4.6 Top-level scalar fields are also walked the same way. Top-level path is just the field name (no dot prefix).
  - [x] 4.7 Edge case: when a token alias matches an empty string in `os.environ`, treat it as a hit (the env var is set, even if empty) — pydantic-settings already resolved it. Detail records the matched var name.

- [x] **Task 5: Wire tests directory layout** (AC: #11)
  - [x] 5.1 Create `tests/unit/__init__.py` (empty). Story 1.1 left `tests/__init__.py` + `tests/test_smoke.py`; this story introduces the `unit/` subdir from architecture §Test Architecture.
  - [x] 5.2 Confirm `[tool.pytest.ini_options] testpaths = ["tests"]` already covers `tests/unit/**` (no pyproject changes expected).
  - [x] 5.3 Do NOT move `tests/test_smoke.py` — leave as-is at `tests/test_smoke.py` (it's a top-level smoke test, not a unit test of a specific module).

- [x] **Task 6: Implement `tests/unit/test_settings.py`** (AC: #1, #2, #3, #4, #5, #9, #10)
  - [x] 6.1 Imports: global, alphabetized. Use `pytest` for fixtures + parametrization, `monkeypatch.setenv`/`monkeypatch.delenv` for env-var isolation (never mutate `os.environ` directly — pytest-randomly will break ordering assumptions).
  - [x] 6.2 Module-level constants get `typing.Final` (auto-typing-final scope includes `tests/`). Example: `EMPTY_ENV_VARS: typing.Final = ("SEMVERTAG_TOKEN", "GITLAB_TOKEN", "CI_JOB_TOKEN", ...)`.
  - [x] 6.3 Add a fixture `clean_settings_env(monkeypatch)` that `delenv`s every `SEMVERTAG_*`, `CI_JOB_TOKEN`, `GITLAB_TOKEN`, `GITHUB_TOKEN`, `BITBUCKET_TOKEN` so tests start from a known-empty baseline. Apply via `pytest.fixture(autouse=False)` and request it explicitly per test.
  - [x] 6.4 Test functions (one assertion-cluster each, `test_<verb>_<outcome>_when_<condition>` per architecture §Test Naming):
    - `test_uses_defaults_when_no_env_set` — AC1
    - `test_resolves_token_from_ci_job_token_when_only_native_var_set` — AC2
    - `test_prefers_semvertag_token_over_provider_native` — AC3
    - `test_prefers_nested_prefix_over_flat_semvertag_token` — AC4
    - `test_reads_nested_env_var_for_endpoint` — AC5
    - `test_secret_str_is_redacted_in_repr` — AC9
    - `test_request_timeout_clamps_to_ten` — AC10
    - `test_request_timeout_passes_through_when_below_ten` — AC10
  - [x] 6.5 For SecretStr assertions, use `.get_secret_value()` to compare actual token contents. For repr assertions, build the string via `repr(settings)` and `repr(settings.gitlab.token)`.
  - [x] 6.6 Use `pytest.mark.parametrize` for the precedence-ordering matrix when it tightens the file (optional — readability > brevity).

- [x] **Task 7: Implement `tests/unit/test_provenance.py`** (AC: #6, #7, #8)
  - [x] 7.1 Same fixture and conventions as `test_settings.py`. Re-use the `clean_settings_env` fixture via `tests/unit/conftest.py` if both files reach for it.
  - [x] 7.2 Test functions:
    - `test_provenance_records_default_when_no_env_set` — AC6
    - `test_provenance_records_env_var_name_when_native_token_set` — AC2 + AC6
    - `test_provenance_records_semvertag_token_when_set` — AC3 + AC6
    - `test_provenance_records_nested_form_when_double_underscore_var_set` — AC4 + AC6
    - `test_provenance_records_endpoint_env_var_when_set` — AC5 + AC6
    - `test_cli_overlay_records_cli_layer_and_flag_detail` — AC7
    - `test_cli_overlay_preserves_unrelated_provenance_entries` — AC7
    - `test_cli_overlay_beats_env_for_overridden_key` — AC8
    - `test_every_documented_field_has_a_provenance_entry` — AC6 (sanity scan: assert `set(settings._provenance.keys()) >= EXPECTED_KEYS`)
  - [x] 7.3 The expected-keys set should be a module-level `typing.Final` tuple containing at minimum: `"strategy"`, `"provider"`, `"default_branch"`, `"request_timeout"`, `"gitlab.endpoint"`, `"gitlab.token"`, `"github.token"`. Do NOT iterate `branch_prefix.*` or `conventional_commits.*` here — those nested dataclasses aren't `BaseModel`s, so the scanner skips them; document that as a Dev Notes constraint.

- [x] **Task 8: Lint + test pass** (AC: #11)
  - [x] 8.1 Run `just install` (regenerates `uv.lock` per template; existing lock should still resolve).
  - [x] 8.2 Run `just lint` — must pass clean. Common gotchas under `select=["ALL"]`:
    - `PLR2004` magic-number rule may flag `8.0`, `10.0` — keep them as constants with `typing.Final` if needed, or accept the per-line ignore where intentional.
    - `D1*` is in the ignore list, so no docstring noise.
    - `S105` (hardcoded password) is in ignore list — token literals in tests are fine.
    - `S101` (assert) is per-file-ignored in `tests/*` — fine.
  - [x] 8.3 Run `just lint-ci` — same plus `--check` modes.
  - [x] 8.4 Run `just test` — all tests pass; coverage report shows `semvertag/_settings.py` at ≥85% line coverage (architecture §Test Architecture: settings is unit-tested in isolation).
  - [x] 8.5 Run `uv build` to confirm packaging is unaffected (CI runs this per Story 1.1's review patch).
  - [x] 8.6 Manually verify `python -c "from semvertag._settings import Settings; s = Settings(); print(s._provenance)"` produces a sensible default-layer mapping (smoke check before declaring done).

- [x] **Task 9: Update `_bmad/` artefacts**
  - [x] 9.1 Update this story's Dev Agent Record + File List as work proceeds (per Story 1.1's pattern).
  - [x] 9.2 Set this story's `Status:` to `review` after lint + tests pass and before requesting code review.

## Dev Notes

### Story framing

This is **Step 2 of the architecture's Implementation Sequence**: "Settings + Provenance — `Settings` class with nested per-provider `BaseModel`s, `AliasChoices` token chain, `settings_customise_sources` provenance recording." [Source: architecture.md#Decision Impact Analysis §Implementation sequence]

Story 1.1 left `semvertag/` containing only `__init__.py` (empty) + `py.typed`. Every file this story creates is NEW. The behavioral reference at `_autosemver_reference/settings.py` is a 15-line flat `BaseSettings` with `AUTOSEMVER_` prefix — it is NOT the target shape. The target shape (nested per-provider `BaseModel`s, `AliasChoices`, provenance) is materially different. Read the reference once to internalize "we are replacing this, not porting it."

### Critical architectural constraints

These come from `architecture.md` and are non-negotiable for this story:

1. **One BaseSettings only.** Architecture §Anti-Patterns: "Multiple BaseSettings classes — there's exactly one (`Settings`); nested config is `BaseModel`." All `*Config` classes are `pydantic.BaseModel`, NOT `pydantic_settings.BaseSettings`.
2. **`pydantic.SecretStr` for every token field.** Defense in depth alongside the (downstream Story 1.3) `_redact.py` boundary scanner. [Source: architecture.md#Error Model & Exit Codes §Redaction (NFR10)]
3. **`AliasChoices` order = precedence.** First alias listed wins when multiple env vars are set. Order for GitLab: `SEMVERTAG_GITLAB__TOKEN` > `SEMVERTAG_TOKEN` > `CI_JOB_TOKEN` > `GITLAB_TOKEN`. [Source: architecture.md#Configuration Resolution §Settings shape]
4. **`env_prefix` does NOT auto-apply to AliasChoices.** Per pydantic-settings 2.x, default `env_prefix_target="variable"` means aliases bypass the prefix. The nested-prefix form (`SEMVERTAG_GITLAB__TOKEN`) must therefore appear LITERALLY in `AliasChoices` to preserve env_nested_delimiter behavior. [Source: pydantic-settings docs (via context7) §Configuring Environment Prefix Targeting]
5. **Provenance keys use dotted paths for nested fields.** `"gitlab.token"`, `"gitlab.endpoint"` — not `"gitlab__token"`. Doctor (Story 3.x) renders these as `Settings.gitlab.token <- $SEMVERTAG_GITLAB__TOKEN`. [Source: architecture.md#Doctor Architecture §Output]
6. **CLI overlay uses `model_copy(update=...)`, not in-place mutation.** Frozen-ish semantics: Settings is conceptually immutable post-construction; CLI overlay returns a new Settings instance. [Source: architecture.md#Configuration Resolution §CLI overlay]
7. **No remote/file config in v1.0.** No dotenv, no TOML, no remote secrets — explicitly out of scope (FR23/FR24 deferred to v1.x). `settings_customise_sources` is NOT required because we have only env+init layers; the post-construct scanner approach is equivalent and simpler. [Source: prd.md#FR25, FR28 + architecture.md#Configuration Resolution §Layers]
8. **Settings is DI-managed as a singleton per CLI run.** Story 1.7 wires `SettingsGroup`; this story only ensures `Settings` is constructible standalone for unit tests. Do NOT add modern-di Group wiring here. [Source: architecture.md#DI & Dependency Boundary §Groups]

### Why post-construct scanner over `settings_customise_sources`

Architecture text suggests `settings_customise_sources` for provenance recording. In practice, pydantic-settings 2.x makes that path significantly more complex than the architecture sketch implies:

- `EnvSettingsSource.get_field_value()` is called per top-level field; nested `BaseModel` fields are walked internally with a different code path that doesn't expose which alias matched at the leaf.
- A custom source needs to either re-implement nested resolution (fragile, couples to pydantic-settings internals) or carry per-instance state across recursive calls (awkward).
- The post-construct scan walks `model_fields` deterministically and inspects `os.environ` directly — no coupling to pydantic-settings internals, easier to unit-test, easier for the doctor command to understand.

The end-to-end behavior is identical: the AC tests pass either way. **Pick the post-construct scanner (Task 4) unless you discover during implementation that pydantic-settings resolves an alias against an env var the scanner misses (e.g., case-insensitive match) — in that case, port the matching logic from `pydantic_settings.sources.EnvSettingsSource._read_env_vars` rather than subclassing the source.**

### File-by-file targets

| Target file | NEW / UPDATE | Purpose |
|---|---|---|
| `semvertag/_types.py` | NEW | `ConfigSource` frozen dataclass (only this — Commit/Tag/RunResult arrive in Stories 1.3/1.5) |
| `semvertag/_settings.py` | NEW | `Settings(BaseSettings)`, `GitLabConfig`, `GitHubConfig`, `apply_cli_overlay`, `_scan_env_provenance` |
| `semvertag/strategies/__init__.py` | NEW | Empty namespace marker |
| `semvertag/strategies/branch_prefix.py` | NEW | `BranchPrefixConfig` only (Strategy class lands in Story 1.6) |
| `semvertag/strategies/conventional_commits.py` | NEW | `ConventionalCommitsConfig` only (Strategy class lands in Story 2.1) |
| `tests/unit/__init__.py` | NEW | Empty |
| `tests/unit/conftest.py` | NEW (optional) | Shared `clean_settings_env` fixture if both test files use it |
| `tests/unit/test_settings.py` | NEW | AC1, AC2, AC3, AC4, AC5, AC9, AC10 |
| `tests/unit/test_provenance.py` | NEW | AC6, AC7, AC8 + sanity-scan over expected keys |

**Files this story does NOT touch:**

| File | Story |
|---|---|
| `semvertag/_errors.py`, `_transport.py`, `_redact.py`, `_output.py`, `_use_case.py`, `ioc.py`, `__main__.py` | Stories 1.3 / 1.4 / 1.7 |
| `semvertag/providers/*` | Stories 1.5+ |
| `semvertag/strategies/*` Strategy classes (the configs are in scope; the Strategy classes are not) | Stories 1.6 / 2.1 |
| `semvertag/doctor/*` | Story 3.x |
| `pyproject.toml`, `Justfile`, `.github/workflows/*`, `mkdocs.yml`, anything else from Story 1.1's scaffolding | (no changes expected; revisit only if a lint rule breaks) |
| `tests/test_smoke.py` | Leave at `tests/`, not `tests/unit/` |

### Settings target shape (verbatim from architecture)

[Source: architecture.md#Configuration Resolution §Settings shape lines 445–490]

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
    default_branch: str | None = None
    request_timeout: float = 8.0
    gitlab: GitLabConfig = pydantic.Field(default_factory=GitLabConfig)
    github: GitHubConfig = pydantic.Field(default_factory=GitHubConfig)
    branch_prefix: BranchPrefixConfig = pydantic.Field(default_factory=BranchPrefixConfig)
    conventional_commits: ConventionalCommitsConfig = pydantic.Field(default_factory=ConventionalCommitsConfig)

    _provenance: dict[str, ConfigSource] = pydantic.PrivateAttr(default_factory=dict)
```

```python
@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class ConfigSource:
    layer: typing.Literal["cli", "env", "default"]
    detail: str  # "--strategy" | "SEMVERTAG_TOKEN" | "CI_JOB_TOKEN" | "default"
```

**Implementation note (deviation):** `kw_only=True` is added to `ConfigSource` even though architecture line 487 shows it without — architecture §Frozen-Dataclass Conventions §All domain types makes `kw_only=True` mandatory for all domain types. Add it.

### `apply_cli_overlay` signature shape (concrete sketch)

```python
def apply_cli_overlay(
    settings: Settings,
    overrides: dict[str, tuple[typing.Any, str]],
) -> Settings:
    """Return a new Settings with CLI overrides applied and provenance updated.

    overrides keys: dotted paths like "strategy" or "gitlab.token".
    overrides values: (new_value, flag_detail) — flag_detail is the human-facing
    flag name, e.g., "--strategy" or "--token".
    """
    ...
```

The Typer entrypoint (Story 1.7) calls this once with all `--flag value` pairs the user passed.

### Pydantic-settings + AliasChoices interaction details

[Source: context7 /pydantic/pydantic-settings §Configuring Environment Prefix Targeting + §Parse Nested Variables with Delimiter]

- Default `env_prefix_target='variable'` → `env_prefix="SEMVERTAG_"` is prepended ONLY to plain field names, never to alias strings. So `validation_alias=AliasChoices("CI_JOB_TOKEN", ...)` reads literally `CI_JOB_TOKEN` — exactly what we want.
- Setting `validation_alias` on a nested field REPLACES the default env-resolution behavior for that field. To preserve nested resolution via `env_nested_delimiter`, the alias chain MUST include `SEMVERTAG_GITLAB__TOKEN` explicitly. **Architecture's chain already does this — do not "simplify" by removing it.**
- `AliasChoices.choices` is the list of strings (used by Task 4's scanner to know which env vars to look up).
- `case_sensitive=False` (in `SettingsConfigDict`) makes env-var lookup case-insensitive on the pydantic side. The scanner SHOULD also use case-insensitive lookup against `os.environ` (or use `os.environ.get(name) is not None` after normalizing keys via a dict copy if running on a case-sensitive OS — Linux/macOS env is case-sensitive; Windows is not). For test reliability, use exact-case lookup in `os.environ` since tests will set the exact-case name via `monkeypatch.setenv`. Architecture §NFR28 makes Linux canonical; case discipline matters there.

### Testing standards

- **Framework**: `pytest` + `pytest-cov` + `pytest-randomly` + `pytest-xdist` (already declared in `[dependency-groups] dev`, no changes needed).
- **HTTP**: This story has no HTTP — defer `httpx2.MockTransport` patterns to Stories 1.5+.
- **Env isolation**: USE `monkeypatch.setenv` / `monkeypatch.delenv` exclusively. NEVER mutate `os.environ` directly (pytest-randomly will randomize test order and leak state).
- **Coverage gate**: ≥85% line on `semvertag/_settings.py` per `pyproject.toml [tool.pytest.ini_options] addopts = "--cov=. --cov-report term-missing"`. No branch-coverage gate yet — that's Story 1.6/2.1 for strategy modules.
- **Test naming**: `test_<verb>_<outcome>_when_<condition>` per architecture §Test Naming.
- **Module-level constants get `typing.Final`** (auto-typing-final scope includes `tests/`).
- **`assert` is OK in tests** (`tests/*.py` has `S101` per-file-ignored).
- **Three pytest layers exist** in architecture: unit / integration / shadow-mode. This story creates only `tests/unit/`. Integration tests under `tests/integration/` arrive with Story 1.7.

### Anti-patterns to avoid (carried from architecture §Anti-Patterns)

- `print()` anywhere — including tests.
- `from __future__ import annotations` — banned project-wide.
- Bare `Exception` catches.
- Mutable defaults: use `pydantic.Field(default_factory=...)` for nested configs, never `gitlab: GitLabConfig = GitLabConfig()`.
- `# type: ignore` — use `# ty: ignore` (global `CLAUDE.md`).
- Module-level singleton of `Settings()` — DO NOT instantiate Settings at module level. The behavioral reference does `settings = Settings()` at module bottom; that pattern is BANNED in semvertag (architecture §Anti-Patterns: "Module-level singletons of stateful clients — these go through DI"). Settings is instantiated by `SettingsGroup` in Story 1.7's `ioc.py`.
- Function-local imports — global imports only (`PLC0415` enforced; per `CLAUDE.md`).
- `str()` or f-string interpolation of `SecretStr` — always `.get_secret_value()` at the HTTP boundary, never in logs/errors.

### Learnings from Story 1.1

[Source: 1-1-bootstrap-public-scaffolding-from-modern-di.md#Dev Agent Record §Debug Log References + §Completion Notes]

- **Ruff `select=["ALL"]` + `target-version="py310"`** flagged `PLC0415 import should be at the top-level` when the smoke test used a function-local import. **All imports in this story must be at module level.**
- **`[tool.ty.src] exclude`** is the canonical ty configuration key; if ty surfaces something in `_settings.py` that needs suppressing, use `# ty: ignore` per global `CLAUDE.md`.
- **`auto-typing-final semvertag tests`** is the lint scope per Story 1.1's patch (`Justfile:9, Justfile:16`). Any module-level constant in `semvertag/` or `tests/` must carry `typing.Final` annotation, or `auto-typing-final --check` will fail in CI.
- **Coverage `omit`** is `["_autosemver_reference/*", "_bmad/*", "tests/*"]` — so coverage IS measured on `semvertag/_settings.py`. Aim for ≥85% line coverage explicitly.
- **`testpaths = ["tests"]`** picks up both `tests/test_smoke.py` and the new `tests/unit/**`. No pyproject changes needed.
- **Story 1.1 deferred** `semvertag/__main__:main` (pyproject's `[project.scripts]` references a missing entrypoint until Story 1.7). This story does NOT touch the entrypoint — Story 1.7's territory.

### Coverage-omit interaction with `tests/*`

`tests/*` is in `[tool.coverage.run] omit`, meaning test files themselves don't count toward coverage. The scanner code in `_settings.py` (Task 4) is what gets measured. Aim for the scanner to be small (~30 lines) and fully exercised by `test_provenance.py`.

### Project Structure Notes

This story adds the first `semvertag/strategies/` directory contents (configs only). Story 1.6 adds `BranchPrefixStrategy` to the existing `branch_prefix.py`; Story 2.1 adds `ConventionalCommitsStrategy` to `conventional_commits.py`. No conflict with architecture's specified structure — both classes co-locate with their Config dataclass in the same file per architecture §Strategy Implementation Pattern.

The architecture's `_settings.py` comment says "Settings + nested *Config models + provenance" — strategy configs being defined in `strategies/<name>.py` rather than `_settings.py` is a small structural choice: strategy-specific config travels with the strategy, which is consistent with the "one file per strategy" rule (FR22-ish for strategies). Architecture's example imports `BranchPrefixConfig` and `ConventionalCommitsConfig` into `_settings.py` — the import direction confirms they live in `strategies/`. Document this in the dev record.

### References

- [Source: architecture.md#Configuration Resolution §Settings shape lines 445–490] — verbatim Settings target shape
- [Source: architecture.md#Configuration Resolution §CLI overlay] — `model_copy(update=...)` mechanism
- [Source: architecture.md#Configuration Resolution §Source tracing (FR32)] — `_provenance` recording requirement
- [Source: architecture.md#Bump Strategy Abstraction lines 360–373] — `BranchPrefixConfig` + `ConventionalCommitsConfig` shapes
- [Source: architecture.md#Naming Patterns §Module naming] — `_settings.py`, `strategies/branch_prefix.py` paths
- [Source: architecture.md#Frozen-Dataclass Conventions] — `kw_only=True, slots=True` mandatory; nested configs use `BaseModel` not `BaseSettings`
- [Source: architecture.md#Type-Annotation Style] — no `from __future__ import annotations`; `typing.Final` for module constants
- [Source: architecture.md#Anti-Patterns to Avoid] — multiple BaseSettings, module-level singletons, `print()`, mutable defaults
- [Source: architecture.md#Implementation Patterns §Strategy Implementation Pattern] — strategy + config co-located, frozen dataclass
- [Source: architecture.md#Test Architecture §Three layers + §Coverage gates] — unit/integration split, 85% line gate
- [Source: architecture.md#Test Naming & File Organization] — `test_<verb>_<outcome>_when_<condition>`, `typing.Final` on test constants
- [Source: architecture.md#Project Structure & Boundaries §Complete Project Directory Structure lines 1087–1138] — full target tree, comments per module
- [Source: prd.md#FR25, FR26, FR27, FR32] — env+CLI surface, provider-native fallback, precedence, source reporting
- [Source: prd.md#NFR10] — token redaction (SecretStr is the in-Settings half of the defense)
- [Source: prd.md#NFR19] — provider-native context honored (CI_JOB_TOKEN, GITHUB_TOKEN, GITLAB_TOKEN)
- [Source: prd.md#NFR23, NFR27] — `ty` clean, `ruff ALL`; Python 3.10–3.14 supported
- [Source: epics.md#Epic 1 §Story 1.2 lines 324–360] — original AC text (this story restates and expands)
- [Source: 1-1-bootstrap-public-scaffolding-from-modern-di.md#Dev Agent Record + Review Findings] — Story 1.1 patches that define the current lint/test surface
- [Source: _autosemver_reference/settings.py] — behavioral reference (read for context; the target shape differs significantly — do not port verbatim)
- [Source: pydantic-settings docs via context7 /pydantic/pydantic-settings §Configuring Environment Prefix Targeting] — `env_prefix_target='variable'` default makes aliases bypass the prefix
- [Source: pydantic-settings docs via context7 /pydantic/pydantic-settings §Parse Nested Variables with Delimiter] — `env_nested_delimiter` behavior
- [Source: ~/.claude/CLAUDE.md] — global rules: `ty: ignore` (not `type: ignore`), global imports, no `from __future__ import annotations`
- [Source: memory: project-semvertag-bootstrap-framing] — autosemver/ is behavioral reference only, not a code starter

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context) via Claude Code, invoked through `bmad-dev-story` skill on 2026-05-26.

### Debug Log References

- **AliasChoices on nested BaseModel does NOT drive env-var lookup.** Initial implementation followed architecture's literal sketch (`validation_alias=AliasChoices(...)` on `GitLabConfig.token`), and 3 tests failed (`gitlab.token` resolved to empty string even when `CI_JOB_TOKEN`, `SEMVERTAG_TOKEN`, or `SEMVERTAG_GITLAB__TOKEN` were set). Root cause: pydantic-settings' `env_nested_delimiter` builds `{"gitlab": {"token": "..."}}` keyed by FIELD NAME, but with `validation_alias` set on the field (without `populate_by_name=True`), the nested model rejects the `"token"` key — only the listed aliases work. Additionally, top-level env vars like `CI_JOB_TOKEN` are never considered by pydantic-settings for nested fields regardless of alias configuration. **Resolution:** dropped `validation_alias` from `GitLabConfig.token` / `GitHubConfig.token`, added a `@model_validator(mode="before")` `_inject_token_aliases` on `Settings` that walks each token's alias chain against `os.environ` and injects the first hit into the nested dict before construction. Architecture's *intent* (FR26 provider-native fallback + FR27 precedence) is preserved; architecture's *literal code sketch* was inaccurate about pydantic-settings 2.x semantics.
- **Provenance scanner needs a path→aliases map.** With `validation_alias` removed from the nested fields, `field_info.validation_alias` is `None` and can't drive the scanner. Replaced with a module-level `_TOKEN_ALIASES_BY_PATH: dict[str, tuple[str, ...]]` keyed by dotted path (`"gitlab.token"`, `"github.token"`). Non-aliased fields still derive `SEMVERTAG_<UPPER>__<...>` automatically.
- **Ruff SLF001 on `_provenance` access.** Tests legitimately read `settings._provenance`; extended `[tool.ruff.lint.extend-per-file-ignores]` from `"tests/*.py" = ["S101"]` to `"tests/**/*.py" = ["S101", "SLF001"]` to (a) cover the new `tests/unit/` subdir and (b) allow private-attribute assertions. Two `# noqa: SLF001` markers remain in `_settings.py` on `apply_cli_overlay` where the function's entire purpose is to manage `_provenance` across a `model_copy` instance.
- **Auto-typing-final rewrote conftest fixture body.** First lint pass auto-rewrote `yield` → `return` (PT022, no-teardown-needed). ty then errored because the annotation was still `Iterator[None]`. Resolved by dropping the trailing `return`, the `collections.abc` import, and updating the annotation to `-> None`. Pytest accepts implicit-None fixtures; PT004 was removed in ruff 0.6+.
- **`just install` regenerated `uv.lock`** (typer 0.26.0 → 0.26.1) as part of the standard `uv lock --upgrade` step. Not a story-scope change but unavoidable under the inherited install recipe.

### Completion Notes List

- All 9 tasks and every subtask executed; ACs 1–11 satisfied by `tests/unit/test_settings.py` (8 tests) + `tests/unit/test_provenance.py` (9 tests).
- `just lint` / `just lint-ci` / `just test` / `uv build` all pass clean.
- Coverage on `semvertag/_settings.py` is **98%** (target ≥85%). Two uncovered lines are defensive branches: the `_inject_token_aliases` early-return when input is not a dict, and the `TypeError` raise when an overlay target isn't a `BaseModel`. Both are unreachable from the documented Settings construction paths.
- **One implementation deviation from architecture's literal sketch:** `validation_alias=AliasChoices(...)` removed from nested `*Config` fields; alias resolution lifted to a Settings `model_validator(mode="before")`. Behavior matches AC1–AC11 exactly; semantics match FR25/FR26/FR27 exactly. Documented above under Debug Log References.
- **One pyproject.toml change:** `[tool.ruff.lint.extend-per-file-ignores]` glob broadened from `"tests/*.py"` → `"tests/**/*.py"` and added `"SLF001"`. Justified above.
- No changes to `_bmad/deferred-work.md` — no new items deferred from this story.

### File List

**New:**
- `semvertag/_types.py` — `ConfigSource` frozen dataclass (only — Commit/Tag/RunResult arrive in Stories 1.3/1.5)
- `semvertag/_settings.py` — `GitLabConfig`, `GitHubConfig`, `Settings`, `_inject_token`, `_scan_model`, `_resolve_source`, `_candidate_env_names`, `apply_cli_overlay`
- `semvertag/strategies/__init__.py` — empty
- `semvertag/strategies/branch_prefix.py` — `BranchPrefixConfig` only (Strategy class deferred to Story 1.6)
- `semvertag/strategies/conventional_commits.py` — `ConventionalCommitsConfig` only (Strategy class deferred to Story 2.1)
- `tests/unit/__init__.py` — empty
- `tests/unit/conftest.py` — `clean_settings_env` fixture
- `tests/unit/test_settings.py` — AC1–AC5, AC9–AC10 (8 tests)
- `tests/unit/test_provenance.py` — AC6–AC8 + every-field sanity scan (9 tests)

**Modified:**
- `pyproject.toml` — `[tool.ruff.lint.extend-per-file-ignores]` glob broadened to `tests/**/*.py`, added `SLF001` to the test-file ignores
- `_bmad/sprint-status.yaml` — Story 1.2 status: backlog → ready-for-dev → in-progress → review

**Auto-regenerated:**
- `uv.lock` — `just install` ran `uv lock --upgrade`; typer 0.26.0 → 0.26.1

### Change Log

| Date | Author | Change |
|---|---|---|
| 2026-05-26 | Claude Opus 4.7 (1M) via Claude Code | Story 1.2 implemented end-to-end. Added `Settings(BaseSettings)` with nested per-provider `BaseModel`s; provider-native credential fallback chains for `gitlab.token` and `github.token` via a top-level `model_validator(mode="before")` (architecture deviation documented under Debug Log References); post-construct provenance scanner records `ConfigSource(layer, detail)` for every documented field; `apply_cli_overlay(settings, overrides)` helper for Typer entrypoint; `request_timeout` clamp validator at 10.0s ceiling. 17 unit tests (`tests/unit/test_settings.py` + `tests/unit/test_provenance.py`), 98% line coverage on `_settings.py`. `pyproject.toml` per-file-ignores glob widened to `tests/**/*.py` and `SLF001` added so tests can assert on `_provenance`. `just lint`/`just lint-ci`/`just test`/`uv build` all green. Status: review. |

### Review Findings

Generated 2026-05-26 by `bmad-code-review` (Blind Hunter + Edge Case Hunter + Acceptance Auditor). Findings ordered by class: decision-needed first, then patch, then defer.

**Decision-needed (resolved on 2026-05-26):**

- [x] [Review][Patch] **Promote `BranchPrefixConfig` and `ConventionalCommitsConfig` to `pydantic.BaseModel(frozen=True)`** [semvertag/strategies/branch_prefix.py, conventional_commits.py] — Resolves former #1 (TypeError on nested CLI overrides) and #2 (provenance gap). Documented architecture deviation: §Bump Strategy Abstraction says frozen dataclass; we are promoting to a frozen BaseModel so the overlay path and provenance scanner work uniformly. Update `_EXPECTED_KEYS` in `test_provenance.py` to include `branch_prefix.*` and `conventional_commits.*`.
- [x] [Review][Patch] **Add `Field(gt=0, le=10.0)` bounds to `request_timeout` + log warning on clamp** [semvertag/_settings.py:51, 68-71] — Floor at >0 prevents httpx footgun; warning surfaces when user input is silently overridden.
- [x] [Review][Patch] **Gate token alias injection by selected `provider`** [semvertag/_settings.py:59-66] — Only inject for the active provider. Stops `CI_JOB_TOKEN` from landing in `gitlab.token` when `provider=github`.
- [x] [Review][Patch] **Add `extra="ignore"` to `SettingsConfigDict`** [semvertag/_settings.py:42-46] — Match spec Task 3.5 explicitly. Pydantic's default is already `ignore` for BaseSettings but the spec lists it.
- Decision-needed items accepted as-documented (no patch): hand-rolled `_inject_token` mechanism (Dev Agent Record justifies); `os.environ`-based provenance re-derivation (architectural, kept simple); `pyproject.toml` glob widening + `SLF001` + `uv.lock` typer bump (accepted).

- [x] [Review][Patch] **CLI overlay bypasses pydantic validation entirely** [semvertag/_settings.py:114-138] — `model_copy(update=...)` skips validators. Confirmed by Edge Case Hunter execution: `apply_cli_overlay(s, {"request_timeout": (9999.0, "--rt")})` produces `request_timeout == 9999.0`; `{"gitlab.token": ("raw-plain", "--token")}` produces a bare `str` (not `SecretStr`) so `repr()` leaks plaintext; `{"strategy": ("garbage", "--strategy")}` accepts a non-Literal value. Fix: after `model_copy`, re-run validation via `Settings.model_validate(new.model_dump())` (or `model_construct` + targeted re-validation), then re-apply `_provenance`. Sources: blind, edge.
- [x] [Review][Patch] **Empty-string env var treated as a valid token, masking later aliases** [semvertag/_settings.py:84-87] — `os.environ.get(env_var)` returns `""` (e.g. `CI_JOB_TOKEN=""` is common on unprotected GitLab branches); the `if value is not None` check passes and short-circuits before `GITLAB_TOKEN` or `SEMVERTAG_TOKEN` is read. Fix: tighten the guard to `if value`. Sources: blind, edge.
- [x] [Review][Patch] **`case_sensitive=False` declared but env lookups in `_inject_token` / `_resolve_source` are case-sensitive** [semvertag/_settings.py:42-46, 84, 102] — pydantic-settings reads case-insensitively, but the alias-injection and provenance paths use `os.environ.get(exact_case)` / `name in os.environ`. On POSIX, lowercase `ci_job_token=...` is partially picked up by pydantic-settings (for known fields) but missed by injection and lies as `default` in provenance. Fix: normalize the env-var lookup either by lowercasing the comparison or by setting `case_sensitive=True` to match the alias paths. Sources: blind, edge.
- [x] [Review][Patch] **Multi-dot CLI keys in `apply_cli_overlay` silently drop the value while still recording `cli` provenance** [semvertag/_settings.py:120-138] — `partition(".")` only splits on the first dot. `{"gitlab.foo.bar": (...)}` produces head=`gitlab`, leaf=`foo.bar`. `nested.model_copy(update={"foo.bar": ...})` neither raises nor stores, yet `_provenance["gitlab.foo.bar"]` is still written as `layer="cli"`. Defeats the provenance contract. Fix: validate that each dotted key resolves to a real field (depth ≤ 2, leaf exists) before recording provenance. Sources: edge.
- [x] [Review][Patch] **`apply_cli_overlay` shares nested instances across new/old Settings (`deep=False`)** [semvertag/_settings.py:133] — `model_copy(deep=False)` means when a top-level field like `gitlab` isn't in `update_top`, the new and old Settings share the same `gitlab` `BaseModel` instance. Future mutation of one leaks into the other. The reassignment `new_settings._provenance = new_provenance` also bypasses the `mode="after"` validator. Fix: use `deep=True` for the outer `model_copy`, or explicitly recopy untouched nested configs. Sources: blind, edge.
- [x] [Review][Patch] **AC9 test asserts only that plaintext is absent, not the canonical `**********` rendering** [tests/unit/test_settings.py:test_secret_str_is_redacted_in_repr] — Spec AC9 names `**********` explicitly. A future change that rendered `""` would slip past the negative-only assertion. Fix: add a positive assertion that `"**********" in repr(settings.gitlab.token)`. Sources: auditor.
- [x] [Review][Patch] **AC10 boundary `value == 10.0` not exercised** [tests/unit/test_settings.py:test_request_timeout_passes_through_when_below_ten] — Pass-through test uses `5.5`. The boundary case where the clamp must pass `10.0` through unchanged is not tested. Fix: parametrize with `5.5` and `10.0`. Sources: auditor.

**Dismissed (1):** `# noqa: ANN401` on `_inject_token_aliases` — canonical pydantic `model_validator(mode="before")` signature; the noqa is correct.

**Failed layers:** none.
