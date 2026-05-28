# Story 1.6: BranchPrefixStrategy with 100% branch coverage

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user on a GitFlow-style repo,
I want semvertag to parse merge commit messages for `feature/`, `bugfix/`, `hotfix/` branch prefixes and decide the bump level accordingly,
so that my existing GitFlow workflow keeps producing semver tags without changing my commit conventions.

## Acceptance Criteria

### AC1 — `Bump` enum + `BumpStrategy` protocol

**Given** `semvertag/_types.py` is updated
**When** I import it
**Then** it exposes a stdlib `enum.Enum` named `Bump` with exactly these four members (in this declaration order):

```python
class Bump(enum.Enum):
    NONE = "none"
    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"
```

**And** every existing type in `_types.py` (`ConfigSource`, `RunResult`, `Commit`, `Tag`, `CheckResult`) is unchanged — fields, decorators, declaration order all preserved. The dev MAY add `Bump` either before or after the existing types; either position is acceptable. Do NOT split `_types.py` into multiple files.

**Given** `semvertag/strategies/_base.py` is created
**When** I import it
**Then** it exposes a `BumpStrategy` `typing.Protocol` with **exactly** this shape (signatures matching `architecture.md` lines 355–357):

```python
class BumpStrategy(typing.Protocol):
    name: str  # "branch-prefix" | "conventional-commits"

    def decide(self, commit: Commit) -> Bump: ...
```

The Protocol declares `name: str` (plain annotation, per architecture line 356). The impl satisfies it with `name: typing.ClassVar[str] = "branch-prefix"` (a class attribute is structurally accessible as an instance attribute — same idiom as Story 1.5's `GitLabProvider`).

**And** the Protocol is NOT `@typing.runtime_checkable` — structural typing at static-check time only (mirrors `providers/_base.py:Provider`).

**And** the file imports only stdlib (`typing`) plus `semvertag._types` (`Commit`, `Bump`). No external deps.

### AC2 — `BranchPrefixStrategy` shape and construction surface

**Given** `semvertag/strategies/branch_prefix.py` already declares `BranchPrefixConfig` (Story 1.2)
**When** I open `semvertag/strategies/branch_prefix.py`
**Then** `BranchPrefixConfig` is unchanged — same `pydantic.BaseModel`, same `model_config = pydantic.ConfigDict(frozen=True)`, same field defaults:

```python
class BranchPrefixConfig(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True)

    minor: tuple[str, ...] = ("feature/",)
    patch: tuple[str, ...] = ("bugfix/", "hotfix/")
    merge_mark_text: str = "Merge branch"
```

**And** the file is extended (NOT replaced) with `BranchPrefixStrategy` declared as a frozen dataclass with `frozen=True, slots=True, kw_only=True` in this exact field order:

```python
@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class BranchPrefixStrategy:
    name: typing.ClassVar[str] = "branch-prefix"
    config: BranchPrefixConfig

    def decide(self, commit: Commit) -> Bump:
        ...
```

**And** `BranchPrefixStrategy` structurally satisfies the `BumpStrategy` protocol — verifiable at static-check time (`ty check`).

**And** the dataclass holds NO mutable state — `config` is injected (DI in Story 1.7; explicit construction in tests). `name` is a `ClassVar` and therefore is NOT subject to frozen-instance immutability (it's class-level).

**Note on dataclass + pydantic mix:** `BranchPrefixStrategy` is a frozen `dataclass`; `BranchPrefixConfig` (its only field) is a `pydantic.BaseModel`. This is intentional per architecture §Frozen-Dataclass Conventions lines 695–727 — domain types are frozen dataclasses, config types are pydantic models. Don't convert `BranchPrefixConfig` to a dataclass (Story 1.2 already settled the Settings shape and `_settings.py:Settings.branch_prefix` uses the BaseModel via `default_factory`).

### AC3 — `decide` returns `Bump.NONE` for non-merge commits

**Given** a `Commit` whose `message` does NOT contain `config.merge_mark_text` as a substring (case-sensitive)
**When** `strategy.decide(commit)` is called
**Then** the method returns `Bump.NONE`
**And** the method makes no side effects — no I/O, no logging, no mutation of `commit` or `self.config`

Examples (using default config; `merge_mark_text="Merge branch"`):

| `commit.message` | result |
|---|---|
| `"feat: ship the new login"` | `Bump.NONE` |
| `"docs: update README"` | `Bump.NONE` |
| `""` (empty string) | `Bump.NONE` |
| `"merge branch 'feature/x' into main"` (lowercase `merge`) | `Bump.NONE` — `merge_mark_text` is case-sensitive |

### AC4 — `decide` returns `Bump.MINOR` when a minor prefix appears in a merge commit

**Given** a `Commit` whose `message` contains `config.merge_mark_text` AND at least one prefix from `config.minor` (default `("feature/",)`)
**When** `strategy.decide(commit)` is called
**Then** the method returns `Bump.MINOR`

Examples (default config):

| `commit.message` | result |
|---|---|
| `"Merge branch 'feature/new-thing' into main"` | `Bump.MINOR` |
| `"Merge branch 'feature/x-123' into develop"` | `Bump.MINOR` |
| `"Merge branch 'feature/' into main"` (bare prefix) | `Bump.MINOR` |

**And** the prefix match is a plain `substring-in-message` check (`"feature/" in commit.message`) — NOT regex, NOT anchored to a word boundary, NOT case-insensitive. This is intentional: GitFlow merge messages reliably surround the branch name with quote characters (`'feature/x'`) so loose substring matching is robust and cheap. The implementation must use Python `in` / `str.__contains__`, not `re`.

### AC5 — `decide` returns `Bump.PATCH` when only a patch prefix appears in a merge commit

**Given** a `Commit` whose `message` contains `config.merge_mark_text` AND does NOT contain any prefix from `config.minor` AND contains at least one prefix from `config.patch` (default `("bugfix/", "hotfix/")`)
**When** `strategy.decide(commit)` is called
**Then** the method returns `Bump.PATCH`

Examples (default config):

| `commit.message` | result |
|---|---|
| `"Merge branch 'bugfix/x' into main"` | `Bump.PATCH` |
| `"Merge branch 'hotfix/cve-2025' into main"` | `Bump.PATCH` |
| `"Merge branch 'bugfix/x' and 'hotfix/y' into main"` (both patch prefixes) | `Bump.PATCH` |

**Precedence rule:** minor wins over patch when both appear in the same merge message. Example: `"Merge branch 'feature/x' into release; cherry-picked from bugfix/y"` returns `Bump.MINOR` (minor checked first; short-circuits).

### AC6 — `decide` returns `Bump.NONE` for unrecognized merge commits

**Given** a `Commit` whose `message` contains `config.merge_mark_text` but contains NO prefix from `config.minor` AND NO prefix from `config.patch`
**When** `strategy.decide(commit)` is called
**Then** the method returns `Bump.NONE`

Examples (default config):

| `commit.message` | result |
|---|---|
| `"Merge branch 'release/2.0' into main"` (release/ is not in default mappings) | `Bump.NONE` |
| `"Merge branch 'chore/cleanup' into main"` | `Bump.NONE` |
| `"Merge branch 'develop' into main"` (no slash prefix at all) | `Bump.NONE` |

### AC7 — `Bump.MAJOR` is never returned

**Given** the strategy is implemented per AC2
**When** any `Commit.message` is passed to `decide(...)`
**Then** the method NEVER returns `Bump.MAJOR` — major bumps belong to `ConventionalCommitsStrategy` (Story 2.1) which detects `!` suffix and `BREAKING CHANGE:` footer per FR15

**And** there is no `config.major` field (the default `BranchPrefixConfig` has no `major` attribute per architecture line 365 "No major mapping — major bumps require conventional-commits")

**Test invariant:** at least one parametrized test asserts that no input (across the AC3/4/5/6 fixture matrix) produces `Bump.MAJOR`. The test scans `set(strategy.decide(c) for c in cases)` and asserts `Bump.MAJOR not in observed`.

### AC8 — Custom config mappings are honored

**Given** a `BranchPrefixConfig` constructed with overridden tuples — e.g. `BranchPrefixConfig(minor=("feat/",), patch=("fix/", "patch/"), merge_mark_text="Auto-merge:")`
**When** `BranchPrefixStrategy(config=<overridden>).decide(commit)` is called
**Then** the strategy honors the override values, not the defaults

Examples (with `BranchPrefixConfig(minor=("feat/",), patch=("fix/",), merge_mark_text="Auto-merge:")`):

| `commit.message` | result |
|---|---|
| `"Auto-merge: feat/new-thing"` | `Bump.MINOR` |
| `"Auto-merge: fix/bug-123"` | `Bump.PATCH` |
| `"Auto-merge: feature/x"` (default `feature/` not in custom minor) | `Bump.NONE` |
| `"Merge branch 'feat/x' into main"` (default mark text not in custom) | `Bump.NONE` |

**Why this AC exists:** the strategy MUST read `self.config.minor`, `self.config.patch`, and `self.config.merge_mark_text` — NOT hard-code the default tuples inside `decide()`. The test in `tests/unit/test_branch_prefix_strategy.py` constructs a non-default config to enforce this (catches "fast" implementations that grab defaults from `BranchPrefixConfig.model_fields[...]` defaults instead of `self.config`).

### AC9 — Unit tests live in `tests/unit/test_branch_prefix_strategy.py` and achieve 100% line + 100% branch coverage on `semvertag/strategies/branch_prefix.py`

**Given** `tests/unit/test_branch_prefix_strategy.py` is created (NEW file)
**When** the test suite is run
**Then** all tests are unit tests — no `httpx2`, no `MockTransport`, no `tmp_path`, no `monkeypatch`, no I/O. Pure function tests over `BranchPrefixStrategy.decide(Commit(...))`.

**And** the test file uses pytest's `parametrize` to cover at minimum these scenarios:

| Scenario | Expected `Bump` |
|---|---|
| non-merge commit (no `merge_mark_text`) | `NONE` |
| empty-string message | `NONE` |
| case-mismatched `merge_mark_text` (`"merge branch ..."` lowercase) | `NONE` |
| merge with `feature/` prefix | `MINOR` |
| merge with `bugfix/` prefix | `PATCH` |
| merge with `hotfix/` prefix | `PATCH` |
| merge with no recognized prefix (`release/`, `chore/`) | `NONE` |
| merge with both `feature/` and `bugfix/` — minor wins | `MINOR` |
| custom config with custom minor + patch + merge_mark_text | mix of `MINOR` / `PATCH` / `NONE` |
| no input produces `MAJOR` (AC7 invariant test) | invariant assertion |

**And** running this exact command exits 0 — both line AND branch coverage on `semvertag/strategies/branch_prefix.py` reach 100% (no `# pragma: no cover` markers; the parser is small enough that every branch can be hit naturally by the parametrized matrix above):

```bash
uv run --no-sync pytest -o "addopts=" --cov=semvertag.strategies.branch_prefix --cov-branch --cov-fail-under=100 --cov-report=term-missing tests/unit/test_branch_prefix_strategy.py
```

**Why `-o "addopts="` is required:** `pyproject.toml:83` declares `addopts = "--cov=. --cov-report term-missing"` globally. Without overriding, the 100% gate would apply to the union of `--cov=.` AND `--cov=semvertag.strategies.branch_prefix` — i.e., the whole codebase — which sits below 100% on purpose (Story 1.5 lands `providers/gitlab.py` at 94%). `-o "addopts="` clears the inherited `addopts` for this one invocation so the gate scopes to `branch_prefix.py` only.

**Coverage scope:** the 100% gate measures only `semvertag/strategies/branch_prefix.py`. `_base.py` is a Protocol-only module (the `...` body of each method is treated as a no-cover line by `coverage.py`'s default reporting). `_types.py` line coverage is preserved (the new `Bump` enum's class body is exercised by simply importing the module, since `enum.Enum` evaluates its members at class-construction time).

**Test naming:** `test_<verb>_<outcome>_when_<condition>` per architecture §Test Function Naming lines 911–921. Examples:

- `test_returns_minor_when_message_contains_feature_prefix`
- `test_returns_patch_when_message_contains_bugfix_prefix`
- `test_returns_none_when_message_is_not_a_merge_commit`
- `test_returns_minor_when_message_contains_both_feature_and_bugfix_prefixes`
- `test_honors_custom_minor_prefix_when_config_overrides_default`
- `test_never_returns_major_across_all_default_inputs`

### AC10 — `just test-branch-strategies` runs the 100% gate locally

**Given** the existing `Justfile`
**When** the dev opens `Justfile`
**Then** a new recipe is appended after the existing `test-branch` recipe:

```justfile
test-branch-strategies:
    uv run --no-sync pytest -o "addopts=" --cov=semvertag.strategies.branch_prefix --cov-branch --cov-fail-under=100 --cov-report=term-missing tests/unit/test_branch_prefix_strategy.py
```

**And** running `just test-branch-strategies` from a clean checkout exits 0 with `branch_prefix.py` at 100% line + 100% branch coverage.

**Why the recipe calls `pytest` directly instead of delegating to `just test`:** `just test *args` chains the project-default `addopts = "--cov=. --cov-report term-missing"` from `pyproject.toml:83`, which would broaden the coverage measurement to the whole codebase and cause `--cov-fail-under=100` to evaluate against the union (sub-100% by design). Calling `pytest` with `-o "addopts="` clears the inherited config for this one invocation.

**And** the existing `test` and `test-branch` recipes are unchanged — they continue to run the full suite at the existing 85% line gate (no `--cov-fail-under=100` global change). The 100% gate is scoped to the bump-strategy modules only, per architecture §Coverage Gates line 580.

**Note on CI wiring:** the architecture (line 580) and AC9 hint that CI runs the 100% gate as a separate job. Story 4.1 (CI workflow polish) is responsible for the workflow YAML edit. This story only adds the Justfile target — the CI job step is intentionally out of scope. Add the deferred-work entry per Task 6.4 below.

### AC11 — Full test suite still passes; no regressions in Stories 1.1–1.5

**Given** all changes from this story are applied
**When** `just test` is run (full suite)
**Then** all existing tests pass (`tests/unit/test_errors.py`, `test_output_json.py`, `test_output_rich.py`, `test_provenance.py`, `test_redact.py`, `test_settings.py`, `test_transport_retry.py`, `tests/integration/test_gitlab_provider.py`) — exactly the same count as before, plus the new `test_branch_prefix_strategy.py` tests

**And** `just lint`, `just lint-ci`, `ty check`, `uv build` all exit 0 — no new ruff violations, no new `ty` errors, no packaging breakage

**And** `_settings.py:Settings.branch_prefix: BranchPrefixConfig` continues to resolve via `pydantic.Field(default_factory=BranchPrefixConfig)` — the existing settings tests must not require any update (this is the regression canary that `BranchPrefixConfig` was not mutated by this story)

## Tasks / Subtasks

- [x] 1. Add `Bump` enum to `semvertag/_types.py` (AC: 1)
  - [x] 1.1 Add `import enum` at the top of `_types.py` (stdlib import; alphabetically grouped with existing `import dataclasses` / `import typing`)
  - [x] 1.2 Append a `class Bump(enum.Enum):` declaration with the four members in this order: `NONE = "none"`, `PATCH = "patch"`, `MINOR = "minor"`, `MAJOR = "major"`
  - [x] 1.3 Preserve all existing types in `_types.py` byte-for-byte — `ConfigSource`, `RunResult`, `Commit`, `Tag`, `CheckResult` and their decorators must remain unchanged. Diff-review before commit.
  - [x] 1.4 Run `ty check` to verify the enum compiles and is importable.

- [x] 2. Add `BumpStrategy` Protocol to `semvertag/strategies/_base.py` (AC: 1)
  - [x] 2.1 Create the file `semvertag/strategies/_base.py` (NEW). Imports: `import typing` (stdlib) and `from semvertag._types import Bump, Commit` (project) — global imports only.
  - [x] 2.2 Declare `class BumpStrategy(typing.Protocol):` with `name: str` annotation (plain class annotation, no default) and `def decide(self, commit: Commit) -> Bump: ...` method stub.
  - [x] 2.3 Optional: add `__all__: typing.Final = ("BumpStrategy",)` if it improves IDE discoverability — match `providers/_base.py` style if it has one.
  - [x] 2.4 Do NOT add `@typing.runtime_checkable`. Do NOT add `typing.TYPE_CHECKING` guards (the `Commit`/`Bump` imports are needed at evaluation time per architecture §Type-Annotation Style line 741 "no `from __future__ import annotations`").

- [x] 3. Implement `BranchPrefixStrategy` in `semvertag/strategies/branch_prefix.py` (AC: 2–8)
  - [x] 3.1 Open `semvertag/strategies/branch_prefix.py`. Leave `BranchPrefixConfig` (lines 1–9) untouched — only append new code below it.
  - [x] 3.2 Add stdlib imports at the top of the file (alphabetical, grouped before the existing `import pydantic`): `import dataclasses`, `import typing`. Also add `from semvertag._types import Bump, Commit` after the existing pydantic import (isort: standard-library → third-party → local-folder, per `pyproject.toml:78`).
  - [x] 3.3 Below `BranchPrefixConfig`, declare the frozen dataclass:
    ```python
    @dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
    class BranchPrefixStrategy:
        name: typing.ClassVar[str] = "branch-prefix"
        config: BranchPrefixConfig

        def decide(self, commit: Commit) -> Bump:
            if self.config.merge_mark_text not in commit.message:
                return Bump.NONE
            if any(prefix in commit.message for prefix in self.config.minor):
                return Bump.MINOR
            if any(prefix in commit.message for prefix in self.config.patch):
                return Bump.PATCH
            return Bump.NONE
    ```
  - [x] 3.4 Verify no other return paths exist and `Bump.MAJOR` is never referenced inside `decide` (AC7 invariant).
  - [x] 3.5 Run `ty check` — `BranchPrefixStrategy` must structurally satisfy `BumpStrategy` (no explicit `BumpStrategy` subclass declaration). If `ty` complains about the `ClassVar` field vs Protocol's plain `name: str`, see §Protocol structural conformance in Dev Notes — accept the static-check pattern Story 1.5 established (`name: typing.ClassVar[str]` satisfies `name: str` Protocol member structurally).
  - [x] 3.6 Verify no comments are introduced (per architecture §Comment Policy lines 942–957 + global CLAUDE.md). `decide`'s logic is small enough that named identifiers describe the intent.

- [x] 4. Write unit tests in `tests/unit/test_branch_prefix_strategy.py` (AC: 3–9)
  - [x] 4.1 Create the file `tests/unit/test_branch_prefix_strategy.py` (NEW). Imports: stdlib `typing` + project `from semvertag._types import Bump, Commit` + `from semvertag.strategies.branch_prefix import BranchPrefixConfig, BranchPrefixStrategy` + `pytest`. Global imports only.
  - [x] 4.2 Add a module-level constant per architecture §Module-Level Constants lines 930–940: `DEFAULT_STRATEGY: typing.Final = BranchPrefixStrategy(config=BranchPrefixConfig())`. Construct fresh `Commit(sha="0"*40, message=...)` instances inside each test (the sha value is arbitrary — the strategy never reads it; pin it as a 40-hex literal for realism).
  - [x] 4.3 Write parametrized tests covering AC3 (non-merge → NONE):
    - `("feat: ship the new login", Bump.NONE)`
    - `("docs: update README", Bump.NONE)`
    - `("", Bump.NONE)`
    - `("merge branch 'feature/x' into main", Bump.NONE)` — case-sensitive `Merge` vs `merge`
  - [x] 4.4 Write parametrized tests covering AC4 (minor → MINOR):
    - `("Merge branch 'feature/new-thing' into main", Bump.MINOR)`
    - `("Merge branch 'feature/' into main", Bump.MINOR)` (bare prefix)
    - `("Merge branch 'feature/x-123' into develop", Bump.MINOR)`
  - [x] 4.5 Write parametrized tests covering AC5 (patch → PATCH):
    - `("Merge branch 'bugfix/x' into main", Bump.PATCH)`
    - `("Merge branch 'hotfix/cve-2025' into main", Bump.PATCH)`
    - `("Merge branch 'bugfix/x' and 'hotfix/y' into main", Bump.PATCH)`
  - [x] 4.6 Write parametrized tests covering AC5 precedence (minor + patch both present → MINOR wins):
    - `("Merge branch 'feature/x' into release; cherry-picked from bugfix/y", Bump.MINOR)`
  - [x] 4.7 Write parametrized tests covering AC6 (merge with unrecognized prefix → NONE):
    - `("Merge branch 'release/2.0' into main", Bump.NONE)`
    - `("Merge branch 'chore/cleanup' into main", Bump.NONE)`
    - `("Merge branch 'develop' into main", Bump.NONE)`
  - [x] 4.8 Write the AC7 invariant test: gather every parametrized message, run them all through `DEFAULT_STRATEGY.decide(...)`, assert `Bump.MAJOR not in {result for _, result in cases for ...}` (one explicit test function with a single assertion line — not a parametrized case).
  - [x] 4.9 Write the AC8 custom-config test:
    ```python
    def test_honors_custom_minor_prefix_when_config_overrides_default() -> None:
        custom: typing.Final = BranchPrefixStrategy(
            config=BranchPrefixConfig(
                minor=("feat/",),
                patch=("fix/",),
                merge_mark_text="Auto-merge:",
            ),
        )
        assert custom.decide(Commit(sha="0" * 40, message="Auto-merge: feat/new-thing")) is Bump.MINOR
        assert custom.decide(Commit(sha="0" * 40, message="Auto-merge: fix/bug-123")) is Bump.PATCH
        assert custom.decide(Commit(sha="0" * 40, message="Auto-merge: feature/x")) is Bump.NONE
        assert custom.decide(Commit(sha="0" * 40, message="Merge branch 'feat/x' into main")) is Bump.NONE
    ```
  - [x] 4.10 Run `just test tests/unit/test_branch_prefix_strategy.py` — all tests must pass.
  - [x] 4.11 Run `uv run --no-sync pytest -o "addopts=" --cov=semvertag.strategies.branch_prefix --cov-branch --cov-fail-under=100 --cov-report=term-missing tests/unit/test_branch_prefix_strategy.py` — must exit 0 with 100% line AND 100% branch coverage on `branch_prefix.py`. The `-o "addopts="` flag clears the project-default `--cov=. --cov-report term-missing` so the 100% gate scopes to `branch_prefix.py` only. If branch coverage falls short, inspect the `--cov-report term-missing` output for the uncovered branch (likely an `any()` generator iterating without ever reaching the terminating iteration) and add the missing parametrized case.

- [x] 5. Add the `just test-branch-strategies` recipe (AC: 10)
  - [x] 5.1 Open `Justfile`. After the existing `test-branch` recipe (lines 22–23), append a blank line and the new recipe:
    ```justfile
    test-branch-strategies:
        uv run --no-sync pytest -o "addopts=" --cov=semvertag.strategies.branch_prefix --cov-branch --cov-fail-under=100 --cov-report=term-missing tests/unit/test_branch_prefix_strategy.py
    ```
    The recipe calls `pytest` directly (not via `just test`) so it can override the inherited `addopts` — see AC10's "Why the recipe calls pytest directly" note for the rationale.
  - [x] 5.2 Run `just test-branch-strategies` from the repo root — must exit 0.
  - [x] 5.3 Run `just test` and `just test-branch` to confirm the existing recipes are unchanged.

- [x] 6. Full regression + lint pass (AC: 11)
  - [x] 6.1 Run `just test` (full suite) — confirm tests count = previous count + new branch-prefix tests, all green.
  - [x] 6.2 Run `just lint-ci` — confirm zero new violations: `eof-fixer . --check`, `ruff format --check`, `ruff check --no-fix`, `ty check` all clean.
  - [x] 6.3 Run `uv build` — confirm wheel + sdist build cleanly. (Per Story 1.1 review patch, `uv build` is a per-story acceptance bar.)
  - [x] 6.4 Append a single bullet to `_bmad/deferred-work.md` under a new section `## Deferred from: story 1-6-branchprefixstrategy-100-branch-coverage` recording: "CI workflow does not yet enforce 100% branch coverage on `semvertag/strategies/branch_prefix.py`. `Justfile::test-branch-strategies` is the developer-local gate; the equivalent CI job step is Story 4.1 (CI workflow polish) scope." — exactly one entry; do NOT add other deferred items in this story.

- [x] 7. Update Dev Agent Record + File List + Status (AC: 1–11)
  - [x] 7.1 Append entries to **Dev Agent Record** below: Agent Model Used, Debug Log References (any deviations from this story's prescribed shape), Completion Notes List, File List, Change Log.
  - [x] 7.2 Confirm Status (top of file) is `review` before code-review.
  - [x] 7.3 Update `_bmad/sprint-status.yaml` — flip `1-6-branchprefixstrategy-100-branch-coverage` from `ready-for-dev` → `in-progress` (at task start) → `review` (at task completion). Bump `last_updated` and `last_updated_note`.

## Dev Notes

### Story framing

This is **Step 6 of the architecture's Implementation Sequence**: "BranchPrefixStrategy + ConventionalCommitsStrategy — `BumpStrategy` implementations. 100% branch coverage gate." [Source: architecture.md lines 590–591]

Stories 1.1–1.5 built scaffolding, `_settings.py` (with `BranchPrefixConfig` pre-existing as a `pydantic.BaseModel` so the `Settings.branch_prefix` field could wire up — see `_settings.py:63`), `_types.py` (`ConfigSource`, `RunResult`, `Commit`, `Tag`, `CheckResult`), `_errors.py`, `_redact.py`, `_output.py`, `_transport.py`, and `providers/{_base,gitlab}.py`. **Story 1.6 introduces ONE new file (`strategies/_base.py`), extends TWO existing files (`_types.py`, `strategies/branch_prefix.py`), adds ONE new test file (`tests/unit/test_branch_prefix_strategy.py`), and amends `Justfile`.**

Story 2.1 implements `ConventionalCommitsStrategy` against the same `BumpStrategy` Protocol declared here — that's why this story's `_base.py` carries the Protocol (not `branch_prefix.py`). When 2.1 lands, the `test-branch-strategies` recipe expands to also cover `semvertag.strategies.conventional_commits`.

The reference repo `_autosemver_reference/` contains an older branch-prefix parser (`_autosemver_reference/use_cases/autosemver_use_case.py` and adjacent strategy modules) — useful for cross-checking PRD intent, but the v1.0 implementation does NOT port that code. The new parser is intentionally smaller and tighter (architecture §Implementation Sequence line 591 frames this as a rewrite, not a port).

### Critical architectural constraints

These come from `architecture.md` and are non-negotiable:

1. **One strategy per file.** `strategies/branch_prefix.py` holds `BranchPrefixStrategy` (and its existing `BranchPrefixConfig`). `strategies/conventional_commits.py` is Story 2.1's territory — do NOT add anything to it from this story. [Source: architecture.md lines 666–668, 1114–1118]
2. **Frozen dataclass with slots, kw-only.** `@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)` per architecture §Frozen-Dataclass Conventions lines 695–727. `ClassVar` fields are not subject to frozen-instance immutability (they're class-level). [Source: architecture.md lines 695–706, 1011]
3. **`name: typing.ClassVar[str] = "branch-prefix"`.** The string value matches `settings.strategy: typing.Literal["branch-prefix", ...]` (architecture line 474; existing `_settings.py:57`). Hyphen-separated, lowercase, matches CLI flag value.
4. **Frozen-dataclass vs pydantic mix.** `BranchPrefixStrategy` is a frozen `dataclass`; `BranchPrefixConfig` is a frozen `pydantic.BaseModel`. Don't unify them. Story 1.2 settled the `Settings`-shape decision (BaseModel for nested configs so they integrate with `pydantic_settings`'s env-var resolution); this story preserves that boundary.
5. **No `print()`, no `from __future__ import annotations`, no bare `Exception` catches, no function-local imports, `# ty: ignore` (not `# type: ignore`).** All carried from architecture §Anti-Patterns lines 1039–1049 and global `CLAUDE.md`.
6. **Comment policy: no comments unless WHY is non-obvious.** The `decide` method is small and clearly named — no inline explanations. [Source: architecture.md §Comment Policy lines 942–957]
7. **Imports are global.** No function-local imports (`PLC0415` is in `select=["ALL"]`). All imports at module top, isort-grouped per `pyproject.toml:76–77` (`isort.lines-after-imports = 2`, `isort.no-lines-before = ["standard-library", "local-folder"]`).
8. **Tests in `tests/unit/`, not `tests/integration/`.** This story's tests are pure-function tests on `BranchPrefixStrategy.decide()` — no HTTP, no DI, no `CliRunner`. [Source: architecture.md §Test Architecture line 552 "Unit (tests/unit/) — pure functions: BumpStrategy.decide() …"]
9. **No new `pyproject.toml` deps.** `pydantic` is already pulled in transitively via `pydantic-settings` (already in `dependencies`). No new entries needed.
10. **No edits to `_settings.py`.** Story 1.2 settled `Settings.branch_prefix: BranchPrefixConfig = pydantic.Field(default_factory=BranchPrefixConfig)` and provenance scanning. Any change here breaks Story 1.2's invariants.
11. **No edits to `tests/conftest.py`.** That file is Story 1.5's shared-integration-fixture surface (`gitlab_transport`, `gitlab_client`, `gitlab_provider`, `compose_handler`, `default_handler`). It is NOT consumed by `tests/unit/test_branch_prefix_strategy.py`. The unit tests do not need any conftest fixtures. [Source: Story 1.5 file list line 814]
12. **No edits to `tests/unit/conftest.py`.** Story 1.2's `clean_settings_env` fixture is unrelated to strategy unit tests. Don't add a new fixture there either — keep tests self-contained.
13. **No `# pragma: no cover` markers.** The parser is small enough (4 branches + 2 `any()` generators) that 100% branch coverage is achievable by parametrized test data alone. Pragmas hide latent bugs; the AC9 100% gate flushes them out at write time.

### Parser semantics — the four branches `decide` exposes

The `decide(commit)` body has exactly four control-flow paths that must each be exercised by tests for 100% branch coverage:

| Path | Trigger | Returns |
|---|---|---|
| 1. `merge_mark_text not in commit.message` is `True` | non-merge commit | `Bump.NONE` |
| 2. `any(prefix in commit.message for prefix in self.config.minor)` is `True` | merge with minor prefix | `Bump.MINOR` |
| 3. `any(prefix in commit.message for prefix in self.config.patch)` is `True` | merge with patch prefix (no minor) | `Bump.PATCH` |
| 4. fallthrough to terminal `return Bump.NONE` | merge with neither minor nor patch | `Bump.NONE` |

**`any()` generator branch coverage:** `pytest --cov-branch` treats the `any()` generator's loop boundary as a branch — the iteration must "exit on True" AND "exit on exhaustion" to be 100% covered. For the default `config.minor = ("feature/",)` (single element), True requires `"feature/" in message`; False requires it not appearing. For `config.patch = ("bugfix/", "hotfix/")` (two elements), the loop must:
- iterate once and exit True (first element matches: `"bugfix/" in message`),
- iterate once, not match, iterate again, exit True (second element matches: `"hotfix/" in message` but not `"bugfix/"`),
- iterate twice, neither matches, exit False (no patch prefix in message).

The parametrized fixture matrix in Task 4 covers all three patch-loop traversals plus both minor-loop traversals.

### `Bump` enum placement and value strings

The enum lives in `_types.py` (architecture line 651 lists `Bump` in that file's responsibilities). Value strings are lowercase ASCII, hyphen-free: `"none"`, `"patch"`, `"minor"`, `"major"`. These strings are also used in `RunResult.bump` (architecture lines 419, 432 — `"none" | "patch" | "minor" | "major"`). When Story 1.7 wires the use case, it'll serialize `result.bump = decided_bump.value` — so the string values are part of the v1.0 JSON contract. **Do not change them.**

`enum.Enum` (NOT `enum.IntEnum`, NOT `enum.StrEnum`) — see architecture line 348 sketch. `StrEnum` would make `Bump.MINOR == "minor"` evaluate True (string equality), which is convenient but fragile — equality should be enum-to-enum. Tests assert `bump_result is Bump.MINOR` (identity check), not `bump_result == "minor"`.

### Protocol structural conformance (`ClassVar` vs plain annotation)

The `BumpStrategy` Protocol declares `name: str` (architecture line 356). The implementation declares `name: typing.ClassVar[str] = "branch-prefix"`. Per architecture line 336 (also documented in Story 1.5 Debug Log References) this is a deliberate idiom: a class-level constant is structurally accessible as an instance attribute, so the structural-typing check passes. `ty check` accepts it in Story 1.5 (`GitLabProvider`); same pattern applies here.

**Do not** declare `BranchPrefixStrategy(BumpStrategy)` explicitly — Protocols are intentionally non-nominal; structural typing only.

### `is` vs `==` for enum comparison in tests

Tests should assert enum identity using `is`, not value equality:

```python
# YES
assert result is Bump.MINOR

# NO
assert result == Bump.MINOR  # works but masks accidental return of "minor" string
```

This catches a class of bugs where a fast implementation accidentally returns `"minor"` (the string) instead of `Bump.MINOR` (the enum member). `is` enforces both identity and type.

### Files this story touches

| Target file | NEW / UPDATE | Purpose |
|---|---|---|
| `semvertag/_types.py` | **UPDATE** | Append `Bump(enum.Enum)`; `enum` import added |
| `semvertag/strategies/_base.py` | **NEW** | `BumpStrategy` `typing.Protocol` |
| `semvertag/strategies/branch_prefix.py` | **UPDATE** | Append `BranchPrefixStrategy` frozen dataclass; `dataclasses` + `typing` imports + `from semvertag._types import Bump, Commit` |
| `tests/unit/test_branch_prefix_strategy.py` | **NEW** | Parametrized unit tests covering AC3–AC9 |
| `Justfile` | **UPDATE** | Append `test-branch-strategies` recipe |
| `_bmad/deferred-work.md` | **UPDATE** | One bullet recording CI workflow gap (per Task 6.4) |

**Files this story does NOT touch:**

| File | Story |
|---|---|
| `semvertag/_settings.py` | Story 1.2. `BranchPrefixConfig` is consumed via `Settings.branch_prefix`; no shape change. |
| `semvertag/_errors.py` | Story 1.3. The parser raises nothing — invalid configs raise pydantic ValidationError upstream at `Settings` construction time, not from `decide()`. |
| `semvertag/_redact.py`, `_output.py`, `_transport.py` | Stories 1.3 / 1.4. Strategy has no console output, no HTTP, no token handling. |
| `semvertag/providers/*` | Stories 1.5 / 2.x. Strategies operate on `Commit` (already in `_types.py`); they don't call providers. |
| `semvertag/strategies/conventional_commits.py` | Story 2.1. Don't touch — it contains `ConventionalCommitsConfig` only; the strategy impl is 2.1's scope. |
| `semvertag/strategies/_base.py` after this story | Frozen for v1.0. Story 2.1's `ConventionalCommitsStrategy` consumes this same `BumpStrategy` Protocol with no changes. |
| `semvertag/__main__.py`, `_use_case.py`, `ioc.py` | Story 1.7. DI wiring + Typer entrypoint construct the strategy via Factory; this story does NOT wire it. |
| `tests/conftest.py`, `tests/unit/conftest.py` | No changes. Unit tests are self-contained. |
| `pyproject.toml` | No changes. No new deps. No coverage-config changes — the `--cov-fail-under=100` is per-invocation via `Justfile`, not a global default. |
| `.github/workflows/ci.yml` | Story 4.1. CI workflow polish adds the 100% gate job; deferred in this story per Task 6.4. |

### Testing standards

- **Framework:** `pytest`, `pytest-cov`, `pytest-randomly`, `pytest-xdist` — already in `[dependency-groups] dev` (pyproject.toml:44–49). No pyproject changes.
- **No HTTP, no async, no DI, no `CliRunner`.** Pure unit tests over the `decide()` function. Pytest's `parametrize` is the primary structural pattern.
- **No fixtures from `tests/conftest.py` or `tests/unit/conftest.py`.** Construct `BranchPrefixStrategy` and `Commit` inline per test.
- **Module-level test constants get `typing.Final`** (architecture §Module-Level Constants lines 930–940). Example: `DEFAULT_STRATEGY: typing.Final = BranchPrefixStrategy(config=BranchPrefixConfig())`.
- **`assert` is OK in tests** (`S101` per-file-ignored — pyproject.toml:80).
- **Test naming:** `test_<verb>_<outcome>_when_<condition>` per architecture §Test Function Naming lines 911–921.
- **Parametrize over `(message, expected_bump)` tuples** where natural. One test per AC scenario cluster; parametrize within the cluster.
- **AC7 invariant test is one function, one assertion.** Don't parametrize it — it's a single existence proof.
- **`is` not `==`** for enum comparisons (see Dev Notes above).

### Anti-patterns to avoid

- **`print()` anywhere** — including dev-aid `print(f"got {result}")`. Use a debugger if needed.
- **`from __future__ import annotations`** — banned project-wide. `Bump` and `Commit` are imported at evaluation time.
- **Bare `Exception` catches** — `decide()` shouldn't `try`/`except` at all. Invalid configs are caught by pydantic at `Settings` construction (Story 1.2's responsibility).
- **Function-local imports** — `PLC0415` enforced; global imports only.
- **`# type: ignore`** — use `# ty: ignore` (global `CLAUDE.md`).
- **Comments restating WHAT the code does** — `decide()` is small enough that the body reads as prose.
- **Mutable default arguments** in functions or dataclasses — `BranchPrefixStrategy` has no mutable defaults (frozen dataclass + immutable config tuple). Don't introduce any.
- **`re` module** — pure substring matching via `in` is faster and sufficient. Don't reach for regex.
- **Hard-coded default tuples** in `decide()` — read everything from `self.config`. AC8 enforces this.
- **`# pragma: no cover` markers** — every branch must be hit by a real test.
- **Comparing enum to string** (`result == "minor"`) — use `result is Bump.MINOR`.
- **Returning the enum's `.value`** from `decide()` — return the enum member itself; serialization happens at the JSON-output boundary (Story 1.7).
- **Adding `Bump.MAJOR` handling** to `decide()` — major is conventional-commits territory (Story 2.1).
- **Touching `BranchPrefixConfig`** — Story 1.2 settled its shape; the `Settings` regression test depends on it.

### Learnings from Stories 1.1–1.5 (carried forward)

[Source: 1-1-bootstrap-public-scaffolding-from-modern-di.md, 1-2-settings-layer-with-aliaschoices-and-provenance.md, 1-3-errors-runresult-output-redaction.md, 1-4-retryingtransport-with-retry-policy.md, 1-5-gitlabprovider-four-endpoints-via-httpx2.md — all Dev Agent Records]

- **Architecture sketches leave seams unspecified.** Story 1.2 needed a `model_validator(mode="before")` for `AliasChoices` over nested fields. Story 1.3 added an `error()` method to the Output protocol absent from the sketch. Story 1.4 needed an `inner` injection seam on `RetryingTransport`. Story 1.5 added a `_request_failed_message` helper. **For this story:** the architecture sketch (line 348) shows `class Bump(enum.Enum)`. No additional seams expected — the `decide()` body is small. If the dev finds themselves adding helper methods, pause and review whether the four-branch shape in §Parser semantics still holds.
- **Auto-typing-final aggressively rewrites code.** Pre-annotate `typing.Final` on every module-level constant (including in tests). Story 1.2's conftest got auto-rewritten unexpectedly when constants were missing the annotation.
- **`tests/**/*.py` per-file-ignores include `S101` + `SLF001`** (pyproject.toml:80). This story's tests don't touch private attrs, but `assert` is the workhorse — `S101` ignore is what permits it.
- **`uv build` is a per-story acceptance bar** (Story 1.1 review patch). Run alongside `just test` before marking review.
- **Code-review cycle produces Patches / Deferred / Dismissed buckets.** Story 1.3 took 8 patches; Story 1.4 fewer; Story 1.5 took 17 patches plus 8 deferred items. The more rigorous the ACs and Dev Notes, the smaller the patch set. **This story's parser is small** — patch count should be modest.
- **Story 1.4 added `_RETRY_AFTER_STATUS` as a private module constant** to dodge `PLR2004` magic-number lint. Story 1.6's parser has no magic numbers (no HTTP statuses, no retry counts) — no private constants needed inside the strategy.
- **Story 1.4's review noted empty-body branches in defensive parsing trip coverage gates.** This story's `decide()` has no defensive branches — the parser trusts its inputs (pydantic validation upstream ensures `config.minor` / `config.patch` are tuples of strings; the protocol contract ensures `commit.message` is a string). No defensive coverage holes expected.
- **Story 1.5 documented that `# pragma: no cover` is a smell — get to coverage by writing real tests.** This story's 100% gate codifies that lesson; the parser is small enough that no pragma is needed.
- **`tests/conftest.py` (top-level) is integration-fixture surface** (Story 1.5 introduced it). Unit tests do NOT depend on it. Don't import from it.

### Coverage interaction

`tests/*` is in `[tool.coverage.run] omit` (pyproject.toml:90), so test files don't count toward coverage. Measured files for this story:

| File | Target coverage |
|---|---|
| `semvertag/_types.py` | Maintains current 100% line coverage (the new `Bump` enum's class body is exercised by import; each enum member is realized at class-construction time, counted as covered when the module is imported by any test) |
| `semvertag/strategies/__init__.py` | Empty file; 0/0 — not measured |
| `semvertag/strategies/_base.py` | Protocol-only; coverage.py treats the `...` ellipsis bodies as no-cover; effectively 100% by definition (matches `providers/_base.py` pattern from Story 1.5) |
| `semvertag/strategies/branch_prefix.py` | **100% line + 100% branch** — the AC9 gate. This is the only module under the 100% bar; the rest of the codebase remains at the global ≥85% line gate (`pyproject.toml:83`) |

`pyproject.toml:83`'s `addopts = "--cov=. --cov-report term-missing"` runs coverage globally on every pytest invocation. The `just test-branch-strategies` recipe overrides this with `-o "addopts="` so the 100% gate scopes ONLY to `semvertag.strategies.branch_prefix` — otherwise `--cov-fail-under=100` would evaluate the union of `--cov=.` AND `--cov=semvertag.strategies.branch_prefix` (the whole codebase) and fail (since Story 1.5 deliberately lands `providers/gitlab.py` at 94%, not 100%).

### Architecture section pointers (for the dev agent's quick lookup)

- §Bump Strategy Abstraction — lines 343–377 — the Bump enum, BumpStrategy Protocol, config-class layout, strategy selection lifecycle
- §Strategy Implementation Pattern — lines 1005–1017 — the canonical `BranchPrefixStrategy` frozen-dataclass shape (use this verbatim)
- §Frozen-Dataclass Conventions — lines 695–727 — `frozen=True, slots=True, kw_only=True`; pydantic-vs-dataclass separation
- §Implementation Patterns §Class Naming — lines 681–693 — `BranchPrefixStrategy` (not `BranchprefixStrategy`); `BranchPrefixConfig`
- §Test Architecture — lines 548–581 — three layers; this story is Layer 1 (Unit)
- §Test Function Naming — lines 911–921 — `test_<verb>_<outcome>_when_<condition>`
- §Module-Level Constants — lines 930–940 — `typing.Final` discipline (applies to test constants too)
- §Coverage Gates — line 580 — "Bump-strategy modules get a separate `--cov-fail-under=100 --cov-branch` job in CI to enforce 100% branch coverage where it matters most" — this story implements the local Justfile half; Story 4.1 wires the CI workflow half
- §Comment Policy — lines 942–957 — no comments unless WHY is non-obvious
- §Anti-Patterns to Avoid — lines 1039–1049 — every banned pattern
- §Decision Impact Analysis §Implementation sequence — lines 590–591 — this story is Step 6
- §Type-Annotation Style — lines 728–743 — `typing.Final`, no `from __future__ import annotations`, built-in generics
- §Project Structure §Complete Project Directory Structure — lines 1055–1167 — `strategies/` package layout

### Project Structure Notes

After this story:

- `semvertag/strategies/_base.py` is complete and stable for v1.0 — Story 2.1's `ConventionalCommitsStrategy` consumes the same Protocol without changes.
- `semvertag/strategies/branch_prefix.py` is complete and stable for v1.0 — Story 1.7 imports `BranchPrefixStrategy` and constructs it via `StrategiesGroup.branch_prefix_strategy` Factory.
- `semvertag/_types.py` now carries the five "v1.0 in-scope" domain types plus `Bump`: `ConfigSource`, `RunResult`, `Commit`, `Tag`, `CheckResult`, `Bump`. All six types listed in architecture line 651's `_types.py` responsibilities are present.
- Module count after this story: `_settings.py` + `_types.py` + `_errors.py` + `_redact.py` + `_output.py` + `_transport.py` + `providers/_base.py` + `providers/gitlab.py` + `strategies/_base.py` + `strategies/branch_prefix.py` + (existing) `strategies/conventional_commits.py` (config-only stub from Story 1.2) = 11 substantive code files. Architecture's projected ~1,200 LOC at end of Epic 1 remains on-track — the strategy parser is small (~15 LOC including the dataclass declaration).
- `tests/unit/test_branch_prefix_strategy.py` is the new unit-test surface; Story 2.1 will mirror it as `test_conventional_commits_strategy.py`.
- Story 1.7 (`DI wiring + Typer entrypoint`) consumes this strategy:
  - `ioc.py:StrategiesGroup.branch_prefix_strategy = modern_di.providers.Factory(BranchPrefixStrategy, config=...)` — constructed lazily based on `settings.strategy == "branch-prefix"`.
  - `_use_case.py:SemvertagUseCase.run()` calls `strategy.decide(latest_commit)` to produce a `Bump` member; serializes to `RunResult.bump = bump.value`.

### References

- [Source: architecture.md#Bump Strategy Abstraction lines 343–377] — Bump enum, BumpStrategy Protocol, BranchPrefixConfig shape
- [Source: architecture.md#Implementation Patterns §Strategy Implementation Pattern lines 1005–1017] — the canonical BranchPrefixStrategy frozen-dataclass shape
- [Source: architecture.md#Test Architecture lines 548–581] — three test layers; coverage gates
- [Source: architecture.md#Coverage Gates line 580] — the 100% branch coverage rationale for bump-strategy modules
- [Source: architecture.md#Frozen-Dataclass Conventions lines 695–727] — dataclass-vs-pydantic separation
- [Source: architecture.md#Class Naming lines 681–693] — `BranchPrefixStrategy` capitalization
- [Source: architecture.md#Decision Impact Analysis §Implementation sequence line 591] — this story is Step 6
- [Source: epics.md#Story 1.6 lines 475–500] — original epic scoping; same ACs reflected here with implementation detail
- [Source: prd.md FR11, FR12] — bump strategy selection; GitFlow merge-message parsing
- [Source: prd.md NFR22] — coverage targets including 100% branch on bump-strategy modules
- [Source: 1-2-settings-layer-with-aliaschoices-and-provenance.md] — `BranchPrefixConfig` shape decision (pydantic.BaseModel with frozen=True); `Settings.branch_prefix` wiring
- [Source: 1-5-gitlabprovider-four-endpoints-via-httpx2.md#Debug Log References line 791] — ClassVar-vs-Protocol structural conformance pattern (precedent for `name: typing.ClassVar[str]` satisfying `name: str` Protocol member)
- [Source: semvertag/strategies/branch_prefix.py current state] — pre-existing `BranchPrefixConfig` declaration (lines 1–9); the strategy implementation appends below it
- [Source: semvertag/_types.py current state] — pre-existing `ConfigSource`, `RunResult`, `Commit`, `Tag`, `CheckResult`; `Bump` to be appended
- [Source: pyproject.toml lines 56–93] — ruff config (`select=["ALL"]`, ignores), coverage config (`omit=["..._bmad/*", "tests/*"]`), ty config
- [Source: Justfile lines 19–23] — existing `test` and `test-branch` recipes; `test-branch-strategies` appends after them

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context) — bmad-dev-story workflow

### Debug Log References

- **`strategies/_base.py` would have sat at 0% line coverage without an explicit test-side import.** No production module imports the Protocol; Story 1.7's `ioc.py` will construct `BranchPrefixStrategy` directly, bypassing the Protocol seam. Same condition as Story 1.5 hit for `providers/_base.py`. Resolution: imported `BumpStrategy` at module scope in `tests/unit/test_branch_prefix_strategy.py` and added a single structural-conformance test (`test_branch_prefix_strategy_exposes_every_member_required_by_bump_strategy_protocol`) that asserts `hasattr(BranchPrefixStrategy, member)` for `("name", "decide")`. With the import, coverage on `strategies/_base.py` lifts to 100% (5/5 statements; the `...` ellipsis bodies are treated as no-cover by coverage.py defaults). Not a deviation from the spec — same idiom Story 1.5 established and the story Dev Notes anticipated.
- **`-o "addopts="` is mandatory in the `test-branch-strategies` recipe** because `pyproject.toml:83`'s `addopts = "--cov=. --cov-report term-missing"` would otherwise broaden coverage measurement to the whole codebase, causing `--cov-fail-under=100` to evaluate the union (sub-100% by design). Verified the gate now scopes correctly: `branch_prefix.py` 21 stmts / 6 branches, all 100%; full suite remains at 95% line coverage as expected.
- **Test naming kept the AC-prescribed `test_<verb>_<outcome>_when_<condition>` shape.** One small departure: AC9's recommended `test_returns_minor_when_message_contains_feature_prefix` (singular) became `test_returns_minor_when_message_contains_feature_prefix` after parametrize bundled the three feature-prefix variants under one function — function name still reads correctly. Same approach for patch (`test_returns_patch_when_message_contains_bugfix_or_hotfix_prefix`) bundling bugfix + hotfix. No behavioral deviation; AC9 says "at minimum these scenarios" so bundling under one parametrized function is faithful to the spec.

### Completion Notes List

- All 11 ACs (AC1–AC11) verified by `tests/unit/test_branch_prefix_strategy.py` — 17 tests, all green.
- `semvertag/strategies/branch_prefix.py` line coverage: **100%** (21/21 stmts) — branch coverage: **100%** (6/6 branches). Gate verified via `just test-branch-strategies`.
- `semvertag/strategies/_base.py` line coverage: **100%** (5/5 stmts) — Protocol imported by the unit test for the structural-conformance check.
- `semvertag/_types.py` line coverage: **100%** — `Bump` enum class body executed at import time.
- Full suite: **198 tests passed** (197 from prior stories + new `test_branch_prefix_strategy.py`), no regressions.
- `just lint-ci`, `ty check`, `uv build` all clean. One unrelated pre-existing warning surfaces during `uv build` (`uv_build` version unpinned in `build-system.requires`) — already tracked in `deferred-work.md` under Story 1.1.
- No new project dependencies — `pydantic` was already pulled in transitively via `pydantic-settings`; `enum`/`dataclasses`/`typing` are stdlib.
- No edits to `pyproject.toml`, `_settings.py`, `_errors.py`, `_transport.py`, `_redact.py`, `_output.py`, `tests/conftest.py`, `tests/unit/conftest.py`, `providers/*`, or `strategies/conventional_commits.py` — every "do not touch" file in the story's file matrix preserved.
- `BranchPrefixConfig` (Story 1.2) preserved byte-for-byte; `Settings.branch_prefix` regression canary holds (all 10 settings tests green).
- Single deferred-work entry added per Task 6.4: CI workflow's 100% branch-coverage gate is Story 4.1's scope.

### File List

- **New:** `semvertag/strategies/_base.py` (BumpStrategy Protocol — 5 stmts)
- **New:** `tests/unit/test_branch_prefix_strategy.py` (17 tests across AC3–AC9 + the AC1 structural conformance check)
- **Modified:** `semvertag/_types.py` (added `import enum`; appended `Bump(enum.Enum)` with `NONE`/`PATCH`/`MINOR`/`MAJOR` members; existing types untouched)
- **Modified:** `semvertag/strategies/branch_prefix.py` (added `dataclasses`/`typing` imports and `Bump`/`Commit` imports; appended `BranchPrefixStrategy` frozen dataclass with `decide()` method; existing `BranchPrefixConfig` untouched)
- **Modified:** `Justfile` (appended `test-branch-strategies` recipe after `test-branch`)
- **Modified:** `_bmad/deferred-work.md` (added Story 1.6 deferred-work section with one bullet)
- **Modified:** `_bmad/sprint-status.yaml` (`1-6-…: ready-for-dev` → `in-progress` → `review`; `last_updated_note` bumped)
- **Modified:** `_bmad/1-6-branchprefixstrategy-100-branch-coverage.md` (Status, all task/subtask checkboxes, Dev Agent Record, File List, Change Log)

### Change Log

- 2026-05-28 — Added `semvertag/_types.py::Bump(enum.Enum)` with four members (`NONE="none"`, `PATCH="patch"`, `MINOR="minor"`, `MAJOR="major"`) per AC1.
- 2026-05-28 — Added `semvertag/strategies/_base.py::BumpStrategy` Protocol (`name: str` + `decide(self, commit: Commit) -> Bump`) per AC1.
- 2026-05-28 — Added `semvertag/strategies/branch_prefix.py::BranchPrefixStrategy` frozen dataclass (`frozen=True, slots=True, kw_only=True`; `name: typing.ClassVar[str] = "branch-prefix"`; `config: BranchPrefixConfig` field; `decide()` method) per AC2–AC8. Parser logic: non-merge → `NONE`; merge with minor prefix → `MINOR`; merge with patch prefix (no minor) → `PATCH`; merge with neither → `NONE`. `Bump.MAJOR` never returned.
- 2026-05-28 — Added `tests/unit/test_branch_prefix_strategy.py` with 17 tests covering AC3–AC9 plus the AC1 structural-conformance check. Parametrized fixtures over non-merge, minor-prefix, patch-prefix, mixed-prefix-precedence, and unrecognized-prefix scenarios; AC7 invariant test asserts `Bump.MAJOR` never appears in default outputs; AC8 custom-config test verifies the parser reads from `self.config` (not hard-coded defaults).
- 2026-05-28 — Added `Justfile::test-branch-strategies` recipe invoking `pytest -o "addopts=" --cov=semvertag.strategies.branch_prefix --cov-branch --cov-fail-under=100`. The `-o "addopts="` flag clears the project-default `--cov=.` so the 100% gate scopes to `branch_prefix.py` only.
- 2026-05-28 — Appended Story 1.6 section to `_bmad/deferred-work.md` recording that the equivalent 100%-branch-coverage CI job step is Story 4.1's scope.
- 2026-05-28 — Bumped sprint-status to `review` for `1-6-branchprefixstrategy-100-branch-coverage`.

### Review Findings

Code review on 2026-05-28 (bmad-code-review skill, three parallel layers: Blind Hunter, Edge Case Hunter, Acceptance Auditor). Acceptance Auditor verdict: zero spec violations, zero missing implementation, all 11 ACs pass, all "do not touch" files preserved. Adversarial layers raised real-world edge cases — none block this story; all deferred to future spec revision or out-of-scope strategies. Initial summary: **0 decision-needed, 0 patch, 9 defer, ~38 dismissed as noise or spec-intended**.

**Post-review patches (2026-05-28):** user opted to promote two deferred findings to patches before re-running review:

1. **`BranchPrefixConfig` field validation** — added `pydantic.Field(min_length=1)` on `minor` / `patch` tuples and `typing.Annotated[str, pydantic.Field(min_length=1)]` on the element type and on `merge_mark_text`. Empty tuples, empty strings, and empty elements now raise `pydantic.ValidationError` at construction. Pydantic default factory still works (defaults unchanged). _Deviates from AC2's "field defaults preserved" interpretation — defaults are byte-identical but validators tightened. AC2's intent (no shape change to break Story 1.2's `Settings.branch_prefix` field) is preserved._
2. **First-line-only prefix matching in `decide`** — `subject = commit.message.split("\n", 1)[0]` is computed once, and all three substring checks (`merge_mark_text not in subject`, `prefix in subject for prefix in minor`, `prefix in subject for prefix in patch`) now run against the subject line only. _Deviates from AC3-AC8's "contains `merge_mark_text`" / "contains [prefix] in message" wording — strictly tightens behavior. All 11 original AC scenarios still pass (single-line messages). Three new tests pin the multi-line behavior._

After patches: 26 tests in `test_branch_prefix_strategy.py` (17 original + 6 validation + 3 multi-line), full suite **207 passed**, lint/ty/build clean, `branch_prefix.py` line + branch coverage still **100%**.

- [x] [Review][Defer] Back-merge into a feature branch is misclassified as MINOR [`semvertag/strategies/branch_prefix.py:23-26`] — deferred, requires spec revision. `"Merge branch 'main' into feature/x"` returns `MINOR` because `"feature/"` appears in the target branch name; the substring approach (spec-mandated by AC4) cannot distinguish source from target. Real GitFlow misclassification.
- [x] [Review][Defer] Revert of a merge commit double-bumps [`semvertag/strategies/branch_prefix.py:23-26`] — deferred, requires spec revision. `'Revert "Merge branch \'feature/x\'..."'` still returns `MINOR`; after a revert this bumps again instead of holding/rolling back.
- [x] [Review][Patch] Added `Field(min_length=1)` and per-element `Annotated[str, Field(min_length=1)]` on `BranchPrefixConfig.minor` / `.patch` / `.merge_mark_text` [`semvertag/strategies/branch_prefix.py:9-19`] — applied; deviates from AC2's "field defaults preserved" but defaults are unchanged (only validators tightened). Verified via 6 new parametrized tests covering empty tuples, empty strings, and empty elements.
- [x] [Review][Patch] `BranchPrefixStrategy.decide` now restricts matching to the first line of the commit message [`semvertag/strategies/branch_prefix.py:25-32`] — applied; deviates from AC3-AC8 (matching previously specified against the full message). Subject extracted via `commit.message.split("\n", 1)[0]`. All 11 original AC scenarios still pass because they're single-line. Three new tests pin the new multi-line behavior.
- [x] [Review][Defer] Common real-world merge formats unhandled by the default `merge_mark_text="Merge branch"` [`semvertag/strategies/branch_prefix.py:23`] — deferred, out-of-scope for GitFlow strategy. GitHub squash format (`"Add feature (#123)"`), GitHub merge-PR format (`"Merge pull request #N from user/feature/x"`), `"Merge remote-tracking branch 'origin/feature/x'"`, octopus merges (`"Merge branches 'feature/a' and 'bugfix/b'"`) all silently classify as `NONE` with defaults. Users on those workflows must override `merge_mark_text` per-repo; consider documenting common overrides.
- [x] [Review][Defer] Test fixture matrix omits prefix case-sensitivity, whitespace-only, non-ASCII, and very-long messages [`tests/unit/test_branch_prefix_strategy.py:18-69`] — deferred, test-surface expansion. The current fixtures hit 100% line + branch coverage but don't pin down behavior for `"Feature/x"`, `"   "`, `"合并分支 feature/中文"`, or `"A" * 10000`. Add when the parser semantics around case-sensitivity are explicitly decided (currently implicit-by-substring).
- [x] [Review][Patch] Added 6 validation tests covering empty tuples and empty-element configs [`tests/unit/test_branch_prefix_strategy.py:104-118`] — applied alongside the `Field(min_length=1)` patch. Pins the pydantic rejection behavior so future refactors can't silently weaken it.
- [x] [Review][Defer] `uv run --no-sync` in `test-branch-strategies` recipe may run against a stale environment [`Justfile:26`] — deferred, template-inherited. Same condition applies to existing `test` / `test-branch` recipes; revisit when install/lock policy is reconsidered (already tracked elsewhere in deferred-work).
- [x] [Review][Defer] `pytest -o "addopts="` does not override `PYTEST_ADDOPTS` env var [`Justfile:26`] — deferred, Story 4.1 (CI workflow polish) concern. In CI environments that export `PYTEST_ADDOPTS=...`, the 100% gate could be skewed; the local recipe is unaffected. Story 4.1's CI job step should set `PYTEST_ADDOPTS=` explicitly when running the gate.

Dismissed (not written individually): adversarial findings about substring matching looseness, `MAJOR` unreachability, `ClassVar` vs `Protocol name: str`, `enum.Enum` vs `StrEnum`, `is`-vs-`==`, missing `@runtime_checkable`, `--cov-fail-under=100` brittleness, and recipe scoping — all spec-mandated patterns explicitly documented in AC1, AC4, AC5, AC7, AC9, AC10, or the story's Dev Notes (§Protocol structural conformance, §`is` vs `==`, §Coverage interaction). Auditor's two cosmetic AC9 test-naming bundling notes already acknowledged in §Debug Log References.

#### Second review pass (2026-05-28, post-patch)

Three layers re-run against the post-patch diff. **Acceptance Auditor verdict: clean — every AC still passes, both post-review deviations match the Review Findings narrative byte-for-byte, no "do not touch" file modified, 26 tests / 207 suite-wide / 100% branch coverage / lint/ty/build all green.** Adversarial layers raised real-but-out-of-scope edge cases — none block the story. Summary: **0 decision-needed, 0 patch, 9 new defer, ~20 dismissed (mostly v1 themes already settled)**.

- [x] [Review][Defer] `min_length=1` accepts whitespace-only / control-char strings [`semvertag/strategies/branch_prefix.py:9`] — deferred, semantic gap not behavioral bug. `BranchPrefixConfig(minor=(" ",))`, `merge_mark_text="\t"`, `merge_mark_text="\n"` all pass validation. Tightening requires `pattern=r"\S"` plus a per-field validator and impacts user ergonomics — defer to a config-validation hardening story.
- [x] [Review][Defer] CRLF line endings leave `\r` trailing in `subject` [`semvertag/strategies/branch_prefix.py:26`] — deferred, Windows/CRLF-tooling concern. `commit.message = "Merge branch 'feature/x' into main\r\n…"` → `subject = "Merge branch 'feature/x' into main\r"`. Substring match still works because `'feature/'` doesn't end in `\r`, but custom prefixes ending in newline/CR are silently broken. Use `splitlines()[0]` (with empty-list guard) to normalise.
- [x] [Review][Defer] Unicode line separators (U+2028 LINE SEPARATOR, U+2029 PARAGRAPH SEPARATOR) not split by `split("\n", 1)` [`semvertag/strategies/branch_prefix.py:26`] — deferred, exotic input. `commit.message = "Merge branch 'release/2.0' into main feature/foo in body"` → subject contains both. `splitlines()` would handle these; `split("\n", 1)` does not.
- [x] [Review][Defer] Message starting with `\n` yields empty subject [`semvertag/strategies/branch_prefix.py:26`] — deferred, edge of edge cases. `commit.message = "\nMerge branch 'feature/x' into main"` → `subject = ""` and the strategy returns `NONE`. Plausible after some hook normalisation. `next((line for line in commit.message.splitlines() if line), "")` fixes it.
- [x] [Review][Defer] CLI overlay surfaces raw `pydantic.ValidationError` when `--branch-prefix.minor=()` or similar is passed [`semvertag/_settings.py:225`] — deferred, Story 1.7 CLI-ergonomics concern. The new validators raise mid-overlay inside `_revalidate_nested`, producing a Python traceback rather than a user-friendly CLI error. Catch and wrap in `apply_cli_overlay`.
- [x] [Review][Defer] `auto-typing-final` interaction with `typing.TypeAlias` annotation [`semvertag/strategies/branch_prefix.py:9`] — deferred, tooling risk. The project's auto-typing-final tool aggressively adds `typing.Final` to module-level constants. `_NonEmptyStr: typing.TypeAlias = ...` should be exempt, but if the tool rewrites it to `typing.Final`, pydantic stops recognising the annotation and validators silently misfire. `lint-ci` currently passes, so this is latent; verify if the tool runs in pre-commit or CI before the next refactor pass.
- [x] [Review][Defer] `typing.TypeAlias` deprecated in Python 3.12+ in favour of the `type` keyword [`semvertag/strategies/branch_prefix.py:9`] — deferred, future-compatibility. Project targets py310, so `UP040` does not currently flag it. When the target version moves to 3.12+, switch to `type _NonEmptyStr = typing.Annotated[str, pydantic.Field(min_length=1)]`.
- [x] [Review][Defer] `merge_mark_text` or prefix containing `\n` silently never matches subject [`semvertag/strategies/branch_prefix.py:27-32`] — deferred, dead-config risk. Validation allows it (`min_length=1` is satisfied); subject-line scoping makes such strings unreachable. Add `pattern=r"^[^\n]+$"` to `_NonEmptyStr` or a `field_validator` that rejects newline-containing inputs.
- [x] [Review][Defer] No tests for whitespace-only / non-ASCII / very-long-message inputs [`tests/unit/test_branch_prefix_strategy.py`] — deferred, test-surface expansion (carried from first pass; still applies). 100% coverage is satisfied by the existing matrix.

Dismissed (second pass): all v1 themes repeated by Blind Hunter (substring looseness, MAJOR unreachability, ClassVar vs Protocol, `is` vs `==`, no `@runtime_checkable`, single-module coverage gate), `__all__` typed as `typing.Final` tuple, dataclass-slots-with-pydantic interop FUD, `typing.Final` on local variable inside `decide()` (architectural rule per `auto-typing-final`), Commit-contract unverified (frozen dataclass; protocol-trust), strategy-rejects-non-config-input (Python dataclass, not needed for v1.0), and one false-positive from Blind Hunter who received an abbreviated test-file summary in its prompt.
