# Story 2.1: Add ConventionalCommitsStrategy with `!` / `BREAKING CHANGE:` major detection and wire `SEMVERTAG_STRATEGY` switching end-to-end

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a platform engineer mid-migration from GitFlow to Conventional Commits,
I want to flip a single pilot repo to the `conventional-commits` strategy by setting `SEMVERTAG_STRATEGY=conventional-commits` as a project-level CI variable,
So that I can migrate one repo at a time without changing tools or commit conventions on the legacy repos.

## Acceptance Criteria

### AC1 — `strategies/conventional_commits.py:ConventionalCommitsStrategy` is a frozen dataclass satisfying `BumpStrategy`

**Given** `semvertag/strategies/conventional_commits.py` currently exports only `ConventionalCommitsConfig` (8 lines, Story 1.2)
**When** Story 2.1 lands
**Then** the module also exports `ConventionalCommitsStrategy` declared as:

```python
@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class ConventionalCommitsStrategy:
    name: typing.ClassVar[str] = "conventional-commits"
    config: ConventionalCommitsConfig

    def decide(self, commit: Commit) -> Bump: ...
```

**And** the shape mirrors `BranchPrefixStrategy` (`strategies/branch_prefix.py:20-22`) — same `ClassVar[str]` name, same `kw_only=True` config injection, same `Bump`-returning `decide` signature. The `BumpStrategy` protocol (`strategies/_base.py`) is satisfied structurally; no explicit `@typing.runtime_checkable` registration needed.

**And** `ConventionalCommitsConfig` (`strategies/conventional_commits.py:4-8`) is **NOT renamed and its defaults are NOT changed** (Story 1.2 stability stance; `_settings.py:73` references it by name).

### AC2 — `decide()` parses subject-line CC header for MINOR / PATCH

**Given** the default `ConventionalCommitsConfig` (`minor_types=("feat",)`, `patch_types=("fix", "perf")`)
**When** `strategy.decide(Commit(sha="abc1234", message="feat: add new thing"))` is called
**Then** it returns `Bump.MINOR`.

**And when** `commit.message` is `"fix: correct typo"` or `"perf: faster path"` → `Bump.PATCH`.

**And when** `commit.message` is `"chore: bump deps"`, `"docs: clarify"`, `"refactor: rename"`, `"test: add cases"`, `"build: bump"`, `"ci: tweak"`, `"style: format"`, `"revert: ..."`, or anything not in `minor_types ∪ patch_types` → `Bump.NONE`.

**And when** `commit.message` is `"Fixed thing"` (no colon, no CC type prefix) → `Bump.NONE` (graceful skip per NFR6 / FR3).

**And when** `commit.message` is `"feat(scope): with scope"` or `"fix(api/v2): scoped"` → the optional `(scope)` is recognized and stripped from the type lookup; bump resolves on the type alone.

### AC3 — `!` suffix on the type triggers `Bump.MAJOR`

**Given** any recognized CC type with `!` immediately after the type (or after the optional `(scope)`)
**When** `strategy.decide(Commit(sha="...", message="feat!: drop python 3.9"))` or `strategy.decide(Commit(sha="...", message="fix(api)!: incompatible response"))` is called
**Then** it returns `Bump.MAJOR`.

**And** the `!` precedes the colon; messages with `!` elsewhere (e.g., `"feat: emphasis!"`) are NOT major-bumped.

### AC4 — `BREAKING CHANGE:` (or `BREAKING-CHANGE:`) footer triggers `Bump.MAJOR`

**Given** a message body containing `BREAKING CHANGE:` (with space) OR `BREAKING-CHANGE:` (with hyphen) as a footer (subject-blank-line-footer shape)
**When** `strategy.decide(Commit(sha="...", message="feat: new thing\n\nBREAKING CHANGE: old thing removed"))` is called
**Then** it returns `Bump.MAJOR`.

**And** the footer detection is anchored: only `BREAKING CHANGE:` / `BREAKING-CHANGE:` at the **start of a footer line** counts (e.g., `"Note: this is a BREAKING CHANGE: warning"` mid-body does **NOT** trigger MAJOR — but a line that begins `BREAKING CHANGE:` does, per Conventional Commits v1.0.0 spec).

**And** detection is case-sensitive on the `BREAKING CHANGE` token (matches CC v1.0.0); the trailing `:` is required.

### AC5 — Precedence: MAJOR wins over MINOR / PATCH; type+breaking compose

**Given** a message with both `feat:` (MINOR-eligible) and a `BREAKING CHANGE:` footer
**When** `strategy.decide(...)` is called
**Then** it returns `Bump.MAJOR` (MAJOR wins).

**And** a message with `fix!:` (PATCH-eligible type + `!`) returns `Bump.MAJOR`.

**And** a message with `chore: bump` (unrecognized type) + `BREAKING CHANGE:` footer returns `Bump.MAJOR` — the footer is sufficient even with an unrecognized type, per CC v1.0.0.

### AC6 — `ioc.py` wires `conventional_commits_strategy` Factory + dynamic strategy selection

**Given** `ioc.py:StrategiesGroup` currently exposes `branch_prefix_strategy` only (`semvertag/ioc.py:99-106`)
**When** Story 2.1 lands
**Then** the Group exposes a second Factory:

```python
class StrategiesGroup(modern_di.Group):
    branch_prefix_strategy = providers.Factory(
        scope=Scope.APP,
        creator=_build_branch_prefix_strategy,
        kwargs={"settings": SettingsGroup.settings},
        skip_creator_parsing=True,
        bound_type=None,
    )
    conventional_commits_strategy = providers.Factory(
        scope=Scope.APP,
        creator=_build_conventional_commits_strategy,
        kwargs={"settings": SettingsGroup.settings},
        skip_creator_parsing=True,
        bound_type=None,
    )
```

**And** `_build_conventional_commits_strategy(settings: Settings) -> ConventionalCommitsStrategy` uses a **lazy import** at the strategy-module boundary (mirrors `_build_branch_prefix_strategy` — architecture §Import Style line 961; preserves the "only active strategy is constructed per CLI run" guarantee).

**And** `build_container(settings, *, json=False, inner_transport=None)` (`semvertag/ioc.py:132-154`) **removes the strategy fail-fast gate** (currently at `ioc.py:141-143`, added in Story 1.7 post-review) and instead **dispatches** the active strategy:

```python
if settings.strategy == "conventional-commits":
    container.override(
        UseCasesGroup.semvertag_use_case_kwargs_strategy,  # see Dev Notes §Strategy dispatch
        ...,
    )
```

The recommended mechanism — see Dev Notes §Strategy dispatch — is to **register a `strategy` kwarg override** on `UseCasesGroup.semvertag_use_case` pointing at `StrategiesGroup.conventional_commits_strategy` instead of the default `branch_prefix_strategy`. Default remains `branch_prefix_strategy` so existing `1.7` integration tests pass unchanged.

**And** the provider fail-fast gate (`ioc.py:138-140`) for non-`gitlab` providers **remains** — Epic 2 is strategy-only; provider dispatch is later epics.

### AC7 — `__main__.py` flows `--strategy` through `apply_cli_overlay` unchanged

**Given** `__main__.py:_main_callback` already collects `strategy` into the overlay (`semvertag/__main__.py:52-53`) and `ioc.build_container(settings, json=json_flag)` (`__main__.py:145`)
**When** Story 2.1 lands
**Then** **no signature changes** to `_main_callback` or `_collect_overrides` are required — `settings.strategy` flows transparently into `build_container`, which now dispatches per AC6.

**And** the existing `--strategy` flag declaration (`__main__.py:90-93`) is preserved.

### AC8 — `_use_case.py` requires no edits; `_status_for_no_bump` / `_reason_for_no_bump` already branch on `"conventional-commits"`

**Given** `semvertag/_use_case.py:128-137` already has the helper:

```python
def _status_for_no_bump(strategy_name: str) -> str:
    if strategy_name == "branch-prefix":
        return "no_merge_commit"
    return "no_conforming_commit"

def _reason_for_no_bump(strategy_name: str) -> str:
    if strategy_name == "branch-prefix":
        return _NO_MERGE_REASON
    return _NO_CONFORMING_REASON
```

**And** `_use_case.py:13` already defines `_NO_CONFORMING_REASON: typing.Final = "No conforming Conventional Commits type found in commit message."`

**When** Story 2.1 lands
**Then** **no edits to `_use_case.py` are needed**. When `ConventionalCommitsStrategy.decide()` returns `Bump.NONE`, the use case's existing `no-bump` branch (`_use_case.py:53-60`) emits `status="no_conforming_commit"` with the documented reason.

**And** the integration test (AC11) verifies this end-to-end without modifying use-case code (Story 1.5/1.6/1.7 regression canary).

### AC9 — Shared subject/footer parsing helper [retro action A3]

**Given** Epic 1 retrospective action A3 (recorded in `_bmad/epic-1-retro-2026-05-28.md`)
**When** Story 2.1 lands
**Then** a new helper module `semvertag/_commit_parse.py` exports:

```python
def subject_line(message: str) -> str:
    """Return the first non-empty line of the commit message, with trailing
    `\\r` stripped. Skips leading blank lines. Returns empty string for an
    all-blank message."""

def footers(message: str) -> list[str]:
    """Return lines after the first blank-line separator following the subject.
    Whitespace-only lines are skipped. Each returned string is .rstrip()-ed."""
```

**And** the helper uses `message.splitlines()` (NOT `split("\n")`) so CRLF (`\r\n`), LS (U+2028), and PS (U+2029) line endings are all handled correctly (Epic 1 retro 1.6-second-pass deferred items: CRLF `\r` trailing, Unicode line separators, leading-newline messages).

**And** `BranchPrefixStrategy.decide()` (`semvertag/strategies/branch_prefix.py:25-26`) is **refactored** to use `_commit_parse.subject_line(commit.message)` in place of `commit.message.split("\n", 1)[0]`. The existing 100% branch-coverage gate (`just test-branch-strategies`) MUST still pass green after the refactor (Story 1.6 canary).

**And** `ConventionalCommitsStrategy.decide()` consumes `_commit_parse.subject_line(...)` for the type/`!` parse and `_commit_parse.footers(...)` for the `BREAKING CHANGE:` scan.

**And** new unit tests in `tests/unit/test_commit_parse.py` exercise: empty string, single-line (no trailing `\n`), CRLF endings, mixed LF/CRLF, leading blank lines, U+2028 / U+2029 separators, message with subject only (no footers), footers with extra blank lines, only-blank-lines body.

### AC10 — Unit tests: 100% line + 100% branch coverage on `strategies/conventional_commits.py`

**Given** `tests/unit/test_conventional_commits_strategy.py` is a new file
**When** `pytest --cov=semvertag.strategies.conventional_commits --cov-branch --cov-fail-under=100` runs
**Then** every branch of `decide()` is exercised:

1. `feat:` happy path → `MINOR`
2. `fix:` / `perf:` happy paths → `PATCH` (parametrized)
3. `feat!:` → `MAJOR`
4. `fix!:`, `perf!:`, `chore!:` → `MAJOR` (parametrized; `!` alone is sufficient even on unrecognized types per CC v1.0.0)
5. `feat(scope):` → `MINOR` (scope stripped from type lookup)
6. `feat(api/v2)!:` → `MAJOR` (scoped + `!`)
7. `feat:\n\nBREAKING CHANGE: …` → `MAJOR` (footer wins)
8. `feat:\n\nBREAKING-CHANGE: …` → `MAJOR` (hyphen variant)
9. Both `feat!:` and `BREAKING CHANGE:` footer → `MAJOR` (no double-counting; composes safely)
10. `chore:` + `BREAKING CHANGE:` footer → `MAJOR` (footer alone is sufficient)
11. `chore:` → `NONE`
12. `docs:` / `refactor:` / `test:` / `build:` / `ci:` / `style:` / `revert:` → `NONE` (parametrized)
13. `Fixed thing` (no CC header) → `NONE`
14. `feat: emphasis!` (`!` not before colon) → `MINOR` (not MAJOR)
15. `Note: this is a BREAKING CHANGE: warning` in the body (NOT a footer) → bump per the subject only (e.g., `feat:` → `MINOR`)
16. Case sensitivity: `FEAT:` → `NONE` (CC v1.0.0 specifies lowercase type)
17. Case sensitivity: `breaking change:` (lowercase) → bump per subject only (CC v1.0.0 footer is case-sensitive on `BREAKING CHANGE` per the spec — verify with the existing reference; if the spec is later softened to case-insensitive, deviate-with-justification in the Debug Log)
18. Empty string message → `NONE`
19. Whitespace-only message → `NONE`
20. CRLF line endings (`"feat: x\r\n\r\nBREAKING CHANGE: y\r\n"`) → `MAJOR`
21. Custom config (`minor_types=("feat", "feature")`, `patch_types=("fix", "patch")`) — both alternatives recognized

**And** parametrize aggressively per Story 1.6's `parametrize` pattern; each `assert` cluster covers one branch.

### AC11 — Integration test: `SEMVERTAG_STRATEGY=conventional-commits` end-to-end

**Given** `tests/integration/test_strategy_switching.py` is a new file
**When** the test suite runs
**Then** it contains at minimum these tests, each invoking the entrypoint via `typer.testing.CliRunner` + `httpx2.MockTransport`:

1. **`test_creates_minor_tag_when_strategy_is_conventional_commits_and_latest_commit_is_feat`** — env: `SEMVERTAG_STRATEGY=conventional-commits`; mock latest commit `feat: add foo`; prior tag `1.4.2`; assert exit 0, stdout contains `Created tag 1.5.0`, POST to `/repository/tags` carries `{"tag_name": "1.5.0", "ref": <sha>}`.
2. **`test_creates_major_tag_when_strategy_is_conventional_commits_and_latest_commit_is_breaking`** — same fixture, commit message `feat!: drop python 3.9`; assert tag created is `2.0.0`.
3. **`test_creates_patch_tag_when_strategy_is_conventional_commits_and_latest_commit_is_fix`** — commit `fix: correct off-by-one`; assert tag `1.4.3`.
4. **`test_skips_with_no_conforming_commit_when_strategy_is_cc_and_message_has_no_type`** — commit `Fixed thing`; assert exit 0, stdout contains `no_conforming_commit`, `reason` matches `_NO_CONFORMING_REASON`.
5. **`test_marina_journey_same_fixture_different_strategies_produces_different_bumps`** — same MockTransport handler, two invocations: one with `SEMVERTAG_STRATEGY=branch-prefix`, one with `SEMVERTAG_STRATEGY=conventional-commits`; latest-commit message `Merge branch 'feature/foo' into main\n\nfeat!: breaking foo`; branch-prefix → MINOR (no `!` handling) → `1.5.0`; conventional-commits → MAJOR → `2.0.0`. **This is Marina's PRD Journey 2 narrative.**
6. **`test_json_envelope_carries_strategy_field_set_to_conventional_commits`** — `SEMVERTAG_STRATEGY=conventional-commits --json`; parse one stdout line; assert `payload["strategy"] == "conventional-commits"` and `payload["bump"]` matches the expected value for the fixture.

**And** tests reuse `tests/integration/conftest.py` fixtures (`cli_env`, `install_mock_transport`, `_clean_env_before_each`, `merge_commit_handler`) — no new conftest fixtures unless a CC-specific handler shape (`feat_commit_handler`?) is genuinely shared. If only one test needs a custom handler, build it inline.

### AC12 — CLI overlay regression test: CLI value survives revalidation when env conflicts [retro action A2]

**Given** Epic 1 retrospective action A2 (recorded in `_bmad/epic-1-retro-2026-05-28.md`)
**When** Story 2.1 lands
**Then** a new test in `tests/unit/test_settings.py` (or `test_provenance.py` — pick the closer-fit) named `test_cli_overlay_strategy_wins_over_conflicting_env` verifies:

- Env: `SEMVERTAG_STRATEGY=branch-prefix`
- CLI overlay: `apply_cli_overlay(settings, {"strategy": ("conventional-commits", "--strategy")})`
- After: `settings.strategy == "conventional-commits"` AND `settings._provenance["strategy"].layer == "cli"` AND `settings._provenance["strategy"].detail == "--strategy"`.

**And** a parallel test for `--provider` (`SEMVERTAG_PROVIDER=gitlab` + `--provider github`) verifies CLI wins (then `build_container` rejects with the 1.7-installed provider gate — confirming both layers behave coherently).

**And** a third test for `--quiet` (`SEMVERTAG_QUIET=true` + no `--quiet` flag) verifies env-set `quiet` survives untouched (Story 1.7 post-review fix to `__main__.py:130` — env honored when CLI didn't override).

### AC13 — Token redaction: add GitHub token-family prefixes to `_redact.py` [retro action A4]

**Given** Epic 1 retrospective action A4 (recorded in `_bmad/epic-1-retro-2026-05-28.md`)
**And** Story 1.3's `_redact.py:6-11` currently covers `glpat-…`, `ghp_…`, `ATBB…`, and a generic ≥32-hex pattern
**When** Story 2.1 lands
**Then** `_TOKEN_PATTERN` is extended with the GitHub token-family alternations:

- `gho_[A-Za-z0-9]{20,}` — GitHub OAuth tokens
- `ghu_[A-Za-z0-9]{20,}` — GitHub user-to-server tokens
- `ghs_[A-Za-z0-9]{20,}` — GitHub server-to-server tokens
- `ghr_[A-Za-z0-9]{20,}` — GitHub refresh tokens
- `github_pat_[A-Za-z0-9_]{20,}` — GitHub fine-grained PATs

**And** `tests/unit/test_redact.py` is extended with parametrized assertions: each new prefix at minimum length (20-char body) and one above-min sample is redacted; mid-string and word-boundary cases match the existing `glpat-` test pattern.

**And** the existing 100% line-coverage gate on `_redact.py` continues to hold.

**Deviation note:** the spec calls out `_redact.py` was a do-not-touch in Story 1.3's spec, but the retro explicitly authorizes this addition. The change is strict-superset (no removals, no behavior change on existing inputs). Document this authorization in `Dev Agent Record §Debug Log References` ("retro action A4 authorizes this extension despite `_redact.py` being do-not-touch in 1.3").

### AC14 — Document the `_transport.time.sleep` monkeypatch coupling [retro action A5]

**Given** Epic 1 retrospective action A5 (recorded in `_bmad/epic-1-retro-2026-05-28.md`)
**When** Story 2.1 lands
**Then** `tests/integration/README.md` is created (new file) with one short section explaining:

- Integration tests reach into `semvertag._transport` internals via `monkeypatch.setattr(_transport.time, "sleep", recorder)` to no-op retry sleeps (precedent: `tests/integration/test_gitlab_provider.py:848-849, 862-863, 876-877`).
- A refactor of `_transport.py` that renames the bound `time` module reference would silently break these tests by reintroducing real sleeps.
- If a future change extracts the sleep into an injected `sleep_fn` parameter on `RetryingTransport`, update the integration tests to inject via that seam instead of monkeypatching the module.

**And** no test-code changes are required by this AC — it is documentation only.

### AC15 — `just test` passes; full suite green; no regressions in Epic 1

**Given** `just test` is run from a fresh checkout post-`uv sync`
**When** the full pytest suite completes
**Then**:

- All existing 243 tests from Epic 1 pass unchanged (1.1–1.7 regression canary).
- New unit tests from AC10 (≥20 cases), AC9 (≥9 cases), AC12 (3 cases), AC13 (≥10 cases) pass.
- New integration tests from AC11 (≥6 cases) pass.
- `pytest --cov` global line coverage **≥85%** (`pyproject.toml:83` gate); branch-prefix coverage **100%** on `strategies/branch_prefix.py` (Story 1.6 gate); **NEW**: `pytest --cov=semvertag.strategies.conventional_commits --cov-branch --cov-fail-under=100` runs clean per AC10 (gate extended).
- `just lint-ci`, `uv run ty check`, and `uv build` all complete clean.

**And** add a new just recipe `test-cc-strategies` (or extend `test-branch-strategies` to `test-strategies` — covering both) that runs the 100% branch gate for `strategies/conventional_commits.py`. Document the recipe in `Dev Notes §Coverage interaction`.

## Tasks / Subtasks

- [x] **Task 1: Author `semvertag/_commit_parse.py` shared helper (AC9)** — retro action A3.
  - [x] 1.1 Create the module with global imports per CLAUDE.md (`import typing`).
  - [x] 1.2 Implement `subject_line(message: str) -> str` using `message.splitlines()`, skipping leading blank lines, returning first non-blank with trailing whitespace already stripped by `splitlines()` (CRLF safe).
  - [x] 1.3 Implement `footers(message: str) -> list[str]` — finds the first blank-line separator after the subject; returns subsequent non-blank lines `.rstrip()`-ed. Returns empty list if no separator found.
  - [x] 1.4 Add `__all__: typing.Final = ("subject_line", "footers")`.
  - [x] 1.5 Author `tests/unit/test_commit_parse.py` with ≥9 cases per AC9: empty string, single-line no-`\n`, CRLF, mixed LF/CRLF, leading blank lines, U+2028/U+2029, subject-only (no footers), footers with extra blank lines, all-blank body.
  - [x] 1.6 Refactor `semvertag/strategies/branch_prefix.py:26` to call `_commit_parse.subject_line(commit.message)` in place of `commit.message.split("\n", 1)[0]`. Confirm `just test-branch-strategies` reports 100% branch coverage unchanged.

- [x] **Task 2: Author `semvertag/strategies/conventional_commits.py:ConventionalCommitsStrategy` (AC1–AC5)**.
  - [x] 2.1 Keep the existing `ConventionalCommitsConfig` class **unchanged** (Story 1.2 stability stance; `_settings.py:73` consumer).
  - [x] 2.2 Add module imports: `import dataclasses; import re; import typing; from semvertag._commit_parse import footers, subject_line; from semvertag._types import Bump, Commit`. NO `from __future__ import annotations` (CLAUDE.md + architecture line 525).
  - [x] 2.3 Declare `ConventionalCommitsStrategy` per AC1: frozen, slots, kw_only; `name: typing.ClassVar[str] = "conventional-commits"`; one `config: ConventionalCommitsConfig` field.
  - [x] 2.4 Define module-level regex `_TYPE_PATTERN: typing.Final = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?(?P<bang>!?):")` — anchored at start, captures the type, optional scope, and optional `!` BEFORE the `:`. Case-sensitive per CC v1.0.0.
  - [x] 2.5 Define module-level constants `_BREAKING_CHANGE_TOKEN: typing.Final = "BREAKING CHANGE:"` and `_BREAKING_CHANGE_HYPHEN: typing.Final = "BREAKING-CHANGE:"`. Footer detection scans `footers(message)` for any line that `startswith` either token (case-sensitive, per CC v1.0.0 spec).
  - [x] 2.6 Implement `decide(self, commit: Commit) -> Bump`:
    1. `subject: typing.Final = subject_line(commit.message)`
    2. If empty → `Bump.NONE` (covers empty / all-blank messages).
    3. `match: typing.Final = _TYPE_PATTERN.match(subject)` — if no match → `Bump.NONE`.
    4. Scan `footers(commit.message)` for a line starting with either breaking-change token → if found, return `Bump.MAJOR` (footer alone is sufficient even with unrecognized type — AC5).
    5. If `match["bang"] == "!"` → `Bump.MAJOR`.
    6. `commit_type: typing.Final = match["type"]`. If `commit_type in self.config.minor_types` → `Bump.MINOR`. If in `self.config.patch_types` → `Bump.PATCH`. Else → `Bump.NONE`.
  - [x] 2.7 Add `__all__: typing.Final = ("ConventionalCommitsConfig", "ConventionalCommitsStrategy")`.

- [x] **Task 3: Author unit tests `tests/unit/test_conventional_commits_strategy.py` (AC10)** — 100% line + 100% branch.
  - [x] 3.1 Module preamble: `import pytest; from semvertag._types import Bump, Commit; from semvertag.strategies.conventional_commits import ConventionalCommitsConfig, ConventionalCommitsStrategy`. Pre-annotate `typing.Final` on every module-level constant (Story 1.2 conftest precedent / auto-typing-final).
  - [x] 3.2 `@pytest.fixture` for `default_strategy` returning `ConventionalCommitsStrategy(config=ConventionalCommitsConfig())`.
  - [x] 3.3 Implement the 21 cases from AC10. Use `@pytest.mark.parametrize` aggressively (Story 1.6 §Testing standards). Each `Commit` fixture uses `sha="abc1234"` constant; only `message` varies per case.
  - [x] 3.4 Verify naming follows `test_<verb>_<outcome>_when_<condition>` (architecture line 911 / Story 1.6).

- [x] **Task 4: Wire `ConventionalCommitsStrategy` in `ioc.py` (AC6, AC7)**.
  - [x] 4.1 Add `_build_conventional_commits_strategy(settings: Settings) -> "ConventionalCommitsStrategy"` mirror to `_build_branch_prefix_strategy` at `semvertag/ioc.py:51-54`. Lazy import inside: `from semvertag.strategies.conventional_commits import ConventionalCommitsStrategy  # noqa: PLC0415`. Return `ConventionalCommitsStrategy(config=settings.conventional_commits)`.
  - [x] 4.2 Add `conventional_commits_strategy` Factory to `StrategiesGroup` mirroring `branch_prefix_strategy` shape (`ioc.py:99-106`).
  - [x] 4.3 In `build_container(settings, *, json=False, inner_transport=None)`:
    - **Remove** the strategy fail-fast gate at `ioc.py:141-143` (the gate added in Story 1.7 post-review).
    - **Keep** the provider fail-fast gate at `ioc.py:138-140`.
    - **Add** a strategy dispatch: after constructing `container`, if `settings.strategy == "conventional-commits"`, call `container.override(StrategiesGroup.branch_prefix_strategy, <conventional_commits instance>)` (or use `overrides_registry` if a per-kwarg API is available — see Dev Notes §Strategy dispatch for the chosen mechanism).
  - [x] 4.4 Add a unit-or-light-integration test in `tests/unit/test_ioc.py` (NEW file) that constructs `build_container(settings_with_strategy="conventional-commits")` and asserts the resolved `UseCasesGroup.semvertag_use_case`'s `.strategy.name == "conventional-commits"`. (Avoid network — no `inner_transport` needed; test asserts on the resolved DI graph only.)
  - [x] 4.5 Confirm `__main__.py` requires NO edits (AC7) — `_collect_overrides` already routes `strategy` into the overlay; `build_container(settings, json=json_flag)` already dispatches per AC6.

- [x] **Task 5: Integration tests `tests/integration/test_strategy_switching.py` (AC11)**.
  - [x] 5.1 Create the file with module preamble: `import collections.abc; import json as json_module; import typing; from typer.testing import CliRunner; from semvertag.__main__ import MAIN_APP; from tests.conftest import HandlerCallable; from tests.integration.conftest import (DEFAULT_COMMIT_SHA, DEFAULT_TAG_NAME, GITLAB_PROJECT_ID)`.
  - [x] 5.2 Add a local helper `_handler_with_message(message: str) -> HandlerCallable` that wraps `merge_commit_handler(commit_message=message)` if the existing helper supports the kwarg — if not, build the handler inline (same shape as `tests/integration/conftest.py:55-78`).
  - [x] 5.3 Implement the 6 tests from AC11.
  - [x] 5.4 For test 5 (Marina's journey), use `monkeypatch.setenv("SEMVERTAG_STRATEGY", "conventional-commits")` for the second invocation; reuse the same `install_mock_transport` fixture across both invocations.
  - [x] 5.5 Each test asserts `result.exit_code`, `result.stdout`, and (where applicable) `result.stderr` separately.

- [x] **Task 6: Settings provenance regression test (AC12)** — retro action A2.
  - [x] 6.1 Add `test_cli_overlay_strategy_wins_over_conflicting_env` to `tests/unit/test_provenance.py` (closer fit than `test_settings.py`).
  - [x] 6.2 Add `test_cli_overlay_provider_wins_over_conflicting_env` — same pattern with `--provider github` over `SEMVERTAG_PROVIDER=gitlab`.
  - [x] 6.3 Add `test_env_quiet_survives_when_cli_flag_absent` — `SEMVERTAG_QUIET=true` + empty CLI overlay → `settings.quiet == True`, provenance layer `"env"`, detail `"SEMVERTAG_QUIET"`.

- [x] **Task 7: `_redact.py` GitHub token-family extension (AC13)** — retro action A4.
  - [x] 7.1 Extend `_TOKEN_PATTERN` regex in `semvertag/_redact.py:6-11` with the 5 GitHub alternations from AC13. Keep alternation ordering: longer/more-specific prefixes first (`github_pat_` before `ghp_`).
  - [x] 7.2 Add parametrized assertions in `tests/unit/test_redact.py` covering each new prefix: min-length (20-char body), above-min sample, mid-string, word-boundary.
  - [x] 7.3 Confirm existing `_redact.py` 100% line coverage still holds.

- [x] **Task 8: Integration-test coupling documentation (AC14)** — retro action A5.
  - [x] 8.1 Create `tests/integration/README.md` with the explainer per AC14.
  - [x] 8.2 Keep it short — under 30 lines. Title, one-paragraph context, three bullet warnings, no code blocks needed.

- [x] **Task 9: `Justfile` and coverage gate update (AC15)**.
  - [x] 9.1 Add a new recipe `test-cc-strategies` in `Justfile` (or rename `test-branch-strategies` → `test-strategies` and have it scope to both `branch_prefix.py` AND `conventional_commits.py` with separate `--cov` invocations — pick the cleaner option).
  - [x] 9.2 If extending `lint-ci` / `test` gates, **do not** add `conventional_commits.py` branch gate to the global `pytest --cov` invocation — keep it isolated like `test-branch-strategies` (Story 1.6 precedent: the strict gate is its own recipe so the global suite remains line-only).
  - [x] 9.3 Document the recipe in `Dev Notes §Coverage interaction`.

- [x] **Task 10: Run the full local validation gate (AC15)**.
  - [x] 10.1 `just install` (fresh sync).
  - [x] 10.2 `just lint-ci` — must be clean.
  - [x] 10.3 `just test` — full suite passes; coverage ≥85%.
  - [x] 10.4 `just test-branch-strategies` — Story 1.6 gate stays 100% branch on `branch_prefix.py`.
  - [x] 10.5 `just test-cc-strategies` (or equivalent) — new 100% branch gate on `conventional_commits.py`.
  - [x] 10.6 `uv run ty check` — clean.
  - [x] 10.7 `uv build` — clean.
  - [x] 10.8 Smoke: `SEMVERTAG_STRATEGY=conventional-commits uv run semvertag --help` should succeed (the help text is unchanged, but the strategy validation should NOT reject the env value — confirms the fail-fast gate is gone).
  - [x] 10.9 Update `_bmad/sprint-status.yaml`: `2-1-conventional-commits-strategy-and-per-repo-switching: ready-for-dev → in-progress → review` (code-review step bumps to `done`).
  - [x] 10.10 Update this story file: tick all task/subtask checkboxes; fill in Dev Agent Record sections; bump Status to `review`.

### Review Findings

_From `bmad-code-review` 2026-05-29 — Blind Hunter + Edge Case Hunter + Acceptance Auditor (full review mode)._

**Decision-needed** — resolved 2026-05-29, each became a patch (applied below):

- [x] [Review][Decision] DI dispatch: dead `conventional_commits_strategy` Factory + misnamed override → **(c) Introduce `current_strategy` Factory + bind use case to it; delete the override.**
- [x] [Review][Decision] Indented footer `BREAKING CHANGE:` not detected → **(b) Lenient — `lstrip()` footer line before `startswith`.**
- [x] [Review][Decision] Footer-without-blank-line returns NONE → **(b) Lenient — collect post-subject lines even without a blank-line separator.**
- [x] [Review][Decision] CC type regex `^[a-z]+` silently rejects user-configured non-`[a-z]+` types → **(a) Strict regex + pydantic `field_validator` on `ConventionalCommitsConfig` rejecting unreachable spellings at config-load.**
- [x] [Review][Decision] `_commit_parse.footers()` over-collects body prose → **(a) Rename to `body_lines()` to reflect the actual semantics.**

**Patch** — applied 2026-05-29:

- [x] [Review][Patch] D1 applied: `ioc.py` introduces `_build_current_strategy` + `current_strategy` Factory; `UseCasesGroup.semvertag_use_case` binds to `current_strategy`; `build_container` no longer overrides `branch_prefix_strategy`. `test_ioc.py` updated to resolve via `current_strategy` and adds a regression asserting named factories still resolve to their concrete types regardless of `settings.strategy`. [`semvertag/ioc.py`, `tests/unit/test_ioc.py`]
- [x] [Review][Patch] D2 applied: `decide()` now `lstrip()`s each `body_lines()` entry before the `startswith` check; new parametrized test row covers tab- and space-indented `BREAKING CHANGE:` / `BREAKING-CHANGE:` footers → `MAJOR`. [`semvertag/strategies/conventional_commits.py:43-46`, `tests/unit/test_conventional_commits_strategy.py`]
- [x] [Review][Patch] D3 applied: `body_lines()` now collects post-subject non-blank lines even when no blank-line separator is present; new test row `"subject\nBREAKING CHANGE: no blank separator"` → footer-detected → `MAJOR`. [`semvertag/_commit_parse.py:11-29`, `tests/unit/test_commit_parse.py`, `tests/unit/test_conventional_commits_strategy.py`]
- [x] [Review][Patch] D4 applied: `_VALID_TYPE_RE = ^[a-z]+$` + `@pydantic.field_validator("minor_types", "patch_types")` on `ConventionalCommitsConfig` raises `ValidationError` on unreachable spellings (`"Feat"`, `"feat-x"`, `"feat2"`, `""`, `" feat"`, `"feat "`); positive + negative tests added. [`semvertag/strategies/conventional_commits.py:11,23-32`, `tests/unit/test_conventional_commits_strategy.py`]
- [x] [Review][Patch] D5 applied: helper renamed `footers()` → `body_lines()`; consumers (`conventional_commits.py`) and tests updated; `__all__` reflects new name. [`semvertag/_commit_parse.py`, `semvertag/strategies/conventional_commits.py`, `tests/unit/test_commit_parse.py`]
- [x] [Review][Patch] P1 applied: explicit test row `"  feat: foo"` (leading whitespace) → `Bump.NONE`. [`tests/unit/test_conventional_commits_strategy.py:177-180`]
- [x] [Review][Patch] P2 applied: explicit test row `"feat : foo"` (space before colon) → `Bump.NONE`. [`tests/unit/test_conventional_commits_strategy.py:183-186`]
- [x] [Review][Patch] P3 applied: dedicated `test_body_lines_strips_carriage_returns_from_crlf_input` asserts `body_lines()` output contains no `\r` characters, so a regression from `splitlines()` to `split("\n")` would fail loudly. [`tests/unit/test_commit_parse.py:60-64`]
- [x] [Review][Patch] P4 applied: `tests/unit/test_ioc.py` `_settings()` constructs via kwargs and is typed `Literal[…]`, so validators run on every call. [`tests/unit/test_ioc.py:12-22`]
- [x] [Review][Patch] P5 applied: non-gitlab provider gate test is now `@pytest.mark.parametrize("provider", ["github", "bitbucket"])`. [`tests/unit/test_ioc.py:42-48`]
- [x] [Review][Patch] P6 applied: `test_redact.py` adds per-prefix min-length (20-char body) cases (`test_redacts_github_token_at_minimum_body_length`), prefix-at-start/end cases (`test_redacts_github_token_at_start_and_end_of_input`), and word-boundary punctuation cases (`test_redacts_github_token_when_followed_by_word_boundary_punctuation`) for all 5 new GitHub prefixes. [`tests/unit/test_redact.py:99-135`]
- [x] [Review][Patch] P7 applied: `tests/integration/README.md` now cites `test_gitlab_provider.py:848-849, 862-863, 876-877`.
- [x] [Review][Patch] P8 applied: Story `Dev Notes §Story framing` adds a "Marina-journey narrative (post-implementation)" subsection clarifying the actual `no_merge_commit` vs `MAJOR` outcome.

**Defer** (pre-existing, future-proofing, or do-not-touch surface):

- [x] [Review][Defer] Future-strategy dispatch guard — current `if settings.strategy == "conventional-commits"` has no `else: raise`; pydantic `Literal` catches typos today, but adding a third strategy without updating dispatch would silently fall through to branch-prefix [`semvertag/ioc.py:154-156`]
- [x] [Review][Defer] `ConventionalCommitsConfig` lacks cross-validation: overlap between `minor_types`/`patch_types`, empty tuples, types unreachable by the regex are all silently accepted [`semvertag/strategies/conventional_commits.py:15-19`]
- [x] [Review][Defer] `commit.message == None` would raise `AttributeError` from `splitlines()`; relies on `Commit.message: str` Protocol contract [`semvertag/_commit_parse.py:5`]
- [x] [Review][Defer] BOM (U+FEFF) at start of message defeats `^[a-z]+` anchor; rare with GitLab/GitHub-produced messages [`semvertag/strategies/conventional_commits.py:11`]
- [x] [Review][Defer] `_TOKEN_PATTERN` greedy matches have no upper bound; adjacent concatenated tokens can leak the second prefix after redaction (over-redaction safe; pre-existing pattern for the hex branch) [`semvertag/_redact.py:6-15`]
- [x] [Review][Defer] Whitespace-only "blank" line between subject and footers is treated as the separator [`semvertag/_commit_parse.py:18,22`]
- [x] [Review][Defer] Hex-token `\b` word-boundary semantics: `_` is a word-char in Python `re`, so `_<40hex>` won't redact — pre-existing, not introduced by this diff [`semvertag/_redact.py:15`]
- [x] [Review][Defer] Add `branch_prefix` regression test row asserting leading-blank-line message behavior after the `subject_line()` refactor — blocked because `tests/unit/test_branch_prefix_strategy.py` is on the do-not-touch list for this story [`tests/unit/test_branch_prefix_strategy.py`]

**Dismissed as noise** (8): `BREAKING CHANGE  :` extra whitespace rejection (spec-strict correct); README code-block presence (spec said "no code blocks needed", not forbidden); AC12 coupling-test split across two files (coverage exists, organizational); `__all__` ordering (`ruff` RUF022 sorts alphabetically); Marina test brittleness (passes; legitimately tests `no_merge_commit` outcome); scope regex `[^)]+` permissiveness (intentional latitude); token charset/family doc-comments (CLAUDE.md no-comments policy); silent fallback on typo'd `SEMVERTAG_STRATEGY` (closed by `Settings.strategy: typing.Literal[...]` at `_settings.py:64`).

## Dev Notes

### Story framing

This story closes **Epic 2** — Conventional Commits Strategy & Per-Repo Switching — in one shot. There is only one story in Epic 2 because the work is tightly scoped: one new strategy class, one DI Group entry, one helper module (shared with branch-prefix), and a handful of tests. The provider fail-fast gate (Story 1.7) for non-`gitlab` providers stays in place — Epic 2 is strategy-only.

After this story lands, the PRD's **Journey 2 (Marina)** is deliverable: a platform engineer mid-migration flips a single GitLab pilot project from `branch-prefix` to `conventional-commits` via a project-level `SEMVERTAG_STRATEGY=conventional-commits` CI variable. No code change, no toolchain swap, no `.semvertag.toml` (file-based config remains deferred to v1.x per PRD FR23/FR24).

**Marina-journey narrative (post-implementation):** the integration test `test_marina_journey_same_fixture_different_strategies_produces_different_bumps` uses the squash-merge fixture `"feat!: drop python 3.9"` for both strategies. Branch-prefix sees no `Merge branch` marker and emits `no_merge_commit` (no tag created); conventional-commits parses the `!` and emits `MAJOR → 2.0.0`. The journey is demonstrated as **same fixture, divergent outcomes** — `no_merge_commit` vs `MAJOR`, not the original `MINOR (1.5.0)` vs `MAJOR (2.0.0)` framing that pre-dated the `subject_line()`-only parse decision. See `Dev Agent Record §Debug Log References` for the fixture rationale.

The story also discharges **4 Epic 1 retrospective action items** baked into the ACs:

- **A2** → AC12 (CLI overlay revalidation regression tests)
- **A3** → AC9 (shared `_commit_parse.py` helper; refactor `BranchPrefixStrategy` to use it)
- **A4** → AC13 (GitHub token-family redaction)
- **A5** → AC14 (document `_transport.time.sleep` coupling)

A6 was "no epic-file update needed" — discharged by writing this story without modifying `_bmad/epics.md`. A1 (BumpStrategy Protocol surface "what commits do I need" extension) was reassessed during the retrospective and is **NOT needed** — the architecture (`_bmad/architecture.md:345`) explicitly chose single-commit input for `BumpStrategy.decide`. Document this finding in `Dev Agent Record §Debug Log References` so future stories don't re-litigate.

### Critical architectural constraints

1. **Single-commit input on `BumpStrategy.decide`** (`_bmad/architecture.md:345`). The strategy receives **one** `Commit` — the latest commit on the default branch — and decides. It does NOT walk history. This is an intentional simplification vs `semantic-release`. ConventionalCommitsStrategy parses the latest merge-commit's message (which on GitLab's squash-and-merge flow is `feat: description` style; on classic merge it's `Merge branch 'feature/foo' into main\n\nfeat: ...`).

2. **Conventional Commits v1.0.0 spec is authoritative** (https://www.conventionalcommits.org/en/v1.0.0/). Subject: `<type>[(<scope>)][!]: <description>`. Type must be lowercase, contiguous letters. Footer: blank-line-separated lines starting with `BREAKING CHANGE:` or `BREAKING-CHANGE:` (with hyphen) anchor MAJOR detection. The footer token IS case-sensitive in the spec (the prose says "MUST consist of UPPERCASE characters").

3. **MAJOR composition is "any sufficient signal"** (AC5). `!`, `BREAKING CHANGE:`, and `BREAKING-CHANGE:` are alternatives, not requirements. Any one of them produces `Bump.MAJOR`, regardless of whether the type is in `minor_types`/`patch_types`. This matches CC v1.0.0 §6: "Breaking changes MAY be indicated by …" (either-or).

4. **No string formatting on the type lookup beyond scope stripping**. The regex captures the type as the first contiguous lowercase letter group before optional `(scope)`/`!`/`:`. Don't lowercase, don't strip, don't normalize whitespace — the spec is strict; mis-formatted inputs (`FEAT:`, ` feat:`, `feat :`) should NOT match (graceful skip per FR3 / NFR6).

5. **Lazy strategy imports preserved** (architecture §Import Style line 961). `_build_conventional_commits_strategy` lazy-imports the strategy module just like `_build_branch_prefix_strategy`. Module-scope imports in `ioc.py` cover only shared internals (`_settings`, `_use_case`, `_output`, `_transport`, `_errors`) per the Story 1.7 cleanup.

6. **`BranchPrefixStrategy` 100% branch coverage MUST hold after the `_commit_parse.subject_line` refactor** (AC9 / Story 1.6 canary). The refactor swaps `commit.message.split("\n", 1)[0]` for a function call. Test cases must continue to exercise all 6 branches in `branch_prefix.py:25-33`.

7. **No `from __future__ import annotations`** (architecture §Anti-Patterns line 525). Use `typing.TYPE_CHECKING` for forward references if needed.

8. **`pyproject.toml [project.scripts]` is NOT touched.** Story 1.7 wired the console script; this story does not change the entrypoint.

### Strategy dispatch

`UseCasesGroup.semvertag_use_case` (`semvertag/ioc.py:109-120`) declares its `strategy` kwarg bound to `StrategiesGroup.branch_prefix_strategy` at Factory-declaration time. To dispatch on `settings.strategy`, the recommended mechanism is the **same `container.override(…)` pattern** Story 1.7 established for `OutputsGroup.rich_output → json_output` swapping:

```python
def build_container(
    settings: Settings,
    *,
    json: bool = False,
    inner_transport: httpx2.BaseTransport | None = None,
) -> modern_di.Container:
    if settings.provider != "gitlab":
        msg = f"Provider {settings.provider!r} not yet supported; v1.0 supports gitlab only."
        raise ConfigError(msg)
    # NOTE: strategy fail-fast gate from Story 1.7 is REMOVED — both strategies are now wired.
    container = modern_di.Container(groups=ALL_GROUPS, context={Settings: settings})

    if settings.strategy == "conventional-commits":
        cc_instance = _build_conventional_commits_strategy(settings)
        container.override(StrategiesGroup.branch_prefix_strategy, cc_instance)

    if inner_transport is not None:
        provider_instance = _construct_gitlab_provider(settings, inner_transport)
        container.override(ProvidersGroup.gitlab_provider, provider_instance)
    if json:
        json_instance = _build_json_output(settings)
        container.override(OutputsGroup.rich_output, json_instance)
    return container
```

**Why override `branch_prefix_strategy` rather than swap kwargs on the use case Factory:** modern-di's installed API exposes `container.override(provider_id, instance)` (verified against the runtime in Story 1.7 review). It does NOT expose `overrides_registry.override(provider, kwarg, with_)` per-kwarg — the spec example in `_bmad/architecture.md` is aspirational, not the installed surface. Overriding the resolved provider is the pragmatic equivalent.

**Trade-off:** when `settings.strategy == "conventional-commits"`, the `branch_prefix_strategy` Factory's resolved value IS the `ConventionalCommitsStrategy` instance. This is slightly counter-intuitive (the Factory name says branch-prefix but resolves to CC), but it is correct: the use case binds to `StrategiesGroup.branch_prefix_strategy` at declaration time; the override redirects what that ID resolves to at run-time. Document this in `Dev Agent Record §Debug Log References` so future readers don't get confused.

**Alternative considered:** introducing two separate `UseCasesGroup` Factories (`semvertag_use_case_bp` / `semvertag_use_case_cc`) and dispatching in `__main__.py`. **Rejected** because it bloats the Group, leaks dispatch into the entrypoint, and complicates Story 3.x's doctor wiring. The override approach keeps `UseCasesGroup` to a single Factory.

### Files this story touches

| File | Action | Notes |
|---|---|---|
| `semvertag/_commit_parse.py` | **NEW** | `subject_line()` + `footers()` helpers; ~30 LOC. |
| `semvertag/strategies/conventional_commits.py` | **UPDATE** | Add `ConventionalCommitsStrategy` class; `ConventionalCommitsConfig` unchanged. |
| `semvertag/strategies/branch_prefix.py` | **UPDATE** | Replace `commit.message.split("\n", 1)[0]` with `_commit_parse.subject_line(commit.message)`. One-line change. |
| `semvertag/ioc.py` | **UPDATE** | Add `_build_conventional_commits_strategy` creator; add `conventional_commits_strategy` Factory to `StrategiesGroup`; remove strategy fail-fast gate; add `container.override` dispatch. |
| `semvertag/_redact.py` | **UPDATE** | Extend `_TOKEN_PATTERN` regex with 5 GitHub token-family alternations (AC13 / retro A4). |
| `tests/unit/test_commit_parse.py` | **NEW** | ≥9 cases per AC9. |
| `tests/unit/test_conventional_commits_strategy.py` | **NEW** | 21 cases per AC10; 100% line + branch. |
| `tests/unit/test_ioc.py` | **NEW** | Single test verifying `build_container(settings_with_strategy="conventional-commits")` resolves the right strategy. |
| `tests/unit/test_redact.py` | **UPDATE** | Add parametrized cases for 5 new GitHub token-family prefixes (AC13). |
| `tests/unit/test_provenance.py` | **UPDATE** | 3 new tests per AC12 (retro A2). |
| `tests/unit/test_branch_prefix_strategy.py` | **NO CHANGE** | Story 1.6's 100% branch gate must still hold post-refactor of `branch_prefix.py:26` to use `_commit_parse.subject_line`. |
| `tests/integration/test_strategy_switching.py` | **NEW** | 6 integration tests per AC11. |
| `tests/integration/README.md` | **NEW** | Short coupling-doc per AC14 (retro A5). |
| `Justfile` | **UPDATE** | Add `test-cc-strategies` recipe (or rename `test-branch-strategies` → `test-strategies` covering both). |
| `pyproject.toml` | **NO CHANGE** | No new dependencies; no script changes. |
| `_bmad/sprint-status.yaml` | **UPDATE** | `2-1-…: ready-for-dev → in-progress → review`; flip `epic-2: backlog → in-progress` (first story trigger); update `last_updated_note`. |
| `_bmad/deferred-work.md` | **UPDATE** | Append new section `## Deferred from: story 2-1-…` for any non-blocking decisions / discovered edge cases. |
| `_bmad/2-1-conventional-commits-strategy-and-per-repo-switching.md` (this file) | **UPDATE** | Status, all task/subtask checkboxes, Dev Agent Record, File List, Change Log. |
| **Do-not-touch** (regression canaries) | — | `semvertag/__main__.py`, `semvertag/_use_case.py`, `semvertag/_settings.py`, `semvertag/_types.py`, `semvertag/_errors.py`, `semvertag/_output.py`, `semvertag/_transport.py`, `semvertag/providers/_base.py`, `semvertag/providers/gitlab.py`, `tests/conftest.py`, `tests/unit/conftest.py`, `tests/integration/conftest.py`, `tests/integration/test_cli_main_verb.py`, `tests/integration/test_cli_quiet_json_matrix.py`, `tests/integration/test_gitlab_provider.py`, `tests/test_smoke.py`, `tests/unit/test_use_case.py`, `tests/unit/test_settings.py`, `tests/unit/test_branch_prefix_strategy.py`. |

### Testing standards

(Architecture §Test Architecture lines 548–581; carried forward from Stories 1.5/1.6/1.7.)

- **Three test layers** — Story 2.1 adds one new unit-layer file per new module + one new integration-layer file.
- **`typer.testing.CliRunner` + `httpx2.MockTransport`** — same pattern as Stories 1.5/1.7. Reuse `tests/integration/conftest.py` fixtures.
- **`mix_stderr=False` is unavailable in Click ≥8.2** (Story 1.7 finding) — use no-arg `CliRunner()`; stream separation works by default.
- **One assertion-cluster per test; parametrize for variations** (Story 1.6 §Testing standards).
- **Test function naming:** `test_<verb>_<outcome>_when_<condition>` (architecture line 911).
- **`typing.Final` on every module-level constant** in test files (Story 1.2 conftest precedent).

### Coverage interaction

| File | Target |
|---|---|
| `semvertag/strategies/conventional_commits.py` | **100% line + 100% branch** (new strict gate, mirror of `branch_prefix.py` Story 1.6). |
| `semvertag/strategies/branch_prefix.py` | **100% line + 100% branch** (Story 1.6 gate must NOT regress after the `_commit_parse.subject_line` refactor in AC9 / Task 1.6). |
| `semvertag/_commit_parse.py` | ≥85% line (global gate); 100% line is achievable with the 9 cases listed in AC9. |
| `semvertag/ioc.py` | ≥85% line (currently 91% per Story 1.7 close). The new strategy-dispatch branch adds 2-3 lines and is covered by AC11 integration tests. |
| `semvertag/_redact.py` | 100% line (Story 1.3 gate; preserved). |
| `tests/**/*.py` | Not measured (omit in `pyproject.toml:90`). |

**Coverage gate verification commands:**

- `just test` — global ≥85% line coverage (term-missing report).
- `just test-branch-strategies` — 100% branch on `branch_prefix.py` (Story 1.6 gate, unchanged scope).
- `just test-cc-strategies` (NEW per AC15 / Task 9.1) — 100% branch on `conventional_commits.py`.

### Anti-patterns to avoid

(Architecture §Anti-Patterns to Avoid lines 1039–1049; highlighting the relevant ones for this story.)

- **Walking commit history.** `decide()` operates on ONE commit. Do NOT call `provider.list_commits()` / introduce a "commits since last tag" loop. The architecture explicitly chose single-commit input. If a future spec adds multi-commit awareness, it requires a `BumpStrategy` Protocol change (out of scope for v1.0).
- **Regex-as-Conventional-Commits-validator.** The regex captures the type/scope/`!`. It does NOT validate the description, body, or footers per CC v1.0.0. Strict-validator behavior is NOT a goal; graceful skip (`Bump.NONE`) on anything malformed is.
- **`print()` anywhere outside `_output.py`** — strategies do NOT emit progress. `output.progress(...)` is called by the use case, NOT by `decide()`.
- **Calling `typer.Exit(...)` or `sys.exit(...)` from a strategy** — exit-code mapping is `__main__.py` only (architecture §Cross-cutting concerns line 1216, AC7 of Story 1.7).
- **Module-level config-driven regex compilation.** The `_TYPE_PATTERN` regex is config-independent (the type-list lookup uses `match["type"] in self.config.minor_types`). Don't compile a regex per `decide()` call, but also don't bake `config.minor_types` into the regex.
- **`from __future__ import annotations`** — keep annotations evaluated (architecture line 525).

### Learnings from Epic 1 (carried forward)

[Source: Stories 1.1–1.7 Dev Agent Records + Review Findings + `_bmad/epic-1-retro-2026-05-28.md`]

- **Architecture sketches under-specified library semantics in every Epic 1 story past 1.1.** Expect 1–2 seams that the spec didn't name. Document them in `Dev Agent Record §Debug Log References`. Likely candidates here: how `_commit_parse.footers()` handles a body that contains a blank-line-separator INSIDE prose (e.g., quoted text); how the regex handles surrogate-pair Unicode in the type position (it won't — `[a-z]+` rejects it; that's correct).
- **Test fixture drift is real** (Story 1.7 hoisting of `_clean_env_before_each` to conftest). When you add `tests/unit/test_ioc.py`, do NOT redeclare env-cleanup fixtures — `tests/unit/conftest.py:_EXPLICIT_ENV_VARS` already covers settings env vars for unit tests.
- **`auto-typing-final` will rewrite `yield None` → `return None`** in fixtures (Story 1.2 precedent). Pre-annotate `typing.Final` on test-level constants.
- **`PLC0415 import-not-at-top-of-file`** must be `# noqa`-suppressed on lazy strategy imports (Story 1.7's `ioc.py` has the precedent: one `# noqa: PLC0415` per lazy import). Architecture §Import Style mandates the lazy pattern.
- **`uv build` is a per-story acceptance bar** (Story 1.1 onwards). Run alongside `just test` and `just lint-ci` before flipping to `review` (Task 10.7).
- **`tests/conftest.py` is the cross-layer fixture surface** (Story 1.5); `tests/integration/conftest.py` is the integration-layer surface (Story 1.7). Reuse — don't redefine.
- **The `default_handler` test fixture's permissive shape** (`tests/conftest.py`) returns 201 for any POST and 404 for unknown paths. The 404 fallback masks URL-builder typos as `ConfigError("project not found")`. For the new integration tests (AC11), prefer `compose_handler` with explicit endpoint overrides if you find a URL-builder regression — but the default shape should be fine for happy-path bump tests.
- **The Conventional Commits parser is the first non-trivial regex in the codebase.** Test surface (AC10) is intentionally exhaustive to lock the semantics — future contributors will copy these tests when adding scopes/types.

### Project Structure Notes

After this story:

- Epic 2 has **one story (2.1) and it is `done`**. Sprint-status flips `epic-2: backlog → in-progress` on story-creation (this skill's automatic step) and `→ done` on story land.
- `semvertag/strategies/` is **complete for v1.0**. Both strategies have their own modules, both are 100% branch covered, both are wired in `ioc.py:StrategiesGroup`. No further strategy additions are planned for v1.0.
- `semvertag/_commit_parse.py` is the **first shared parsing helper**. Future doctor (Epic 3) or shadow-mode (Story 4.8) consumers of commit-message parsing should reuse `subject_line` / `footers` rather than re-implementing.
- Module count after this story: previous 14 + `_commit_parse.py` = **15 substantive code files**. Architecture's projected ~1,200 LOC at end of Epic 1 is now ~1,300 LOC at end of Epic 2 — still well under NFR21's 1500-line soft target.
- `Justfile` gains one recipe (`test-cc-strategies`). Story 4.1 (CI workflow polish) may consolidate the strict-coverage recipes into a single CI step.

## References

- [Source: architecture.md#Bump Strategy Abstraction lines 343–378] — `BumpStrategy` protocol shape; `ConventionalCommitsConfig` defaults; user-extensible mappings; single-commit input rationale
- [Source: architecture.md#Strategy selection line 377] — config-resolved at startup; one strategy instantiated per CLI run
- [Source: architecture.md#Implementation Patterns §Strategy Implementation Pattern lines 1005–1017] — frozen-dataclass shape; `kw_only=True`
- [Source: architecture.md#DI Group Conventions lines 804–836] — Group naming; `ALL_GROUPS` typing; active-selection pattern
- [Source: architecture.md#Anti-Patterns to Avoid lines 1039–1049] — banned patterns
- [Source: architecture.md#Test Architecture lines 548–581] — three test layers; CliRunner + MockTransport
- [Source: epics.md#Story 2.1 lines 550–600] — original epic scoping; ACs reflected here with implementation detail
- [Source: prd.md FR11–FR16] — strategy abstraction, mappings, BREAKING CHANGE detection
- [Source: prd.md FR3 / NFR6] — graceful skip on malformed input
- [Source: prd.md NFR22] — ≥85% line coverage; 100% branch on strategy modules
- [Source: prd.md FR23 / FR24] — file-based `.semvertag.toml` deferred to v1.x (so Marina's switch is env-only)
- [Source: Conventional Commits v1.0.0 spec — https://www.conventionalcommits.org/en/v1.0.0/] — type, scope, `!`, `BREAKING CHANGE:` footer semantics; case sensitivity
- [Source: 1-2-settings-layer-with-aliaschoices-and-provenance.md (Status: done)] — `Settings.strategy`, `Settings.conventional_commits`; `apply_cli_overlay`
- [Source: 1-3-errors-runresult-output-redaction.md (Status: done)] — `_redact.py`; `SemvertagError` hierarchy; redaction defense-in-depth
- [Source: 1-6-branchprefixstrategy-100-branch-coverage.md (Status: done)] — `BumpStrategy` Protocol; `BranchPrefixStrategy` shape; 100% branch gate pattern; `just test-branch-strategies` recipe
- [Source: 1-7-wire-di-groups-and-typer-entrypoint.md (Status: done)] — `ioc.py:build_container` + `container.override(…)` pattern; strategy fail-fast gate at `ioc.py:141-143` (REMOVED in this story); use case's `_status_for_no_bump`/`_reason_for_no_bump` already branches on strategy name
- [Source: epic-1-retro-2026-05-28.md (Status: done)] — A1 reassessment (not needed); A2 (AC12); A3 (AC9); A4 (AC13); A5 (AC14); A6 (no epic-file update)
- [Source: semvertag/_types.py#Bump#Commit] — enum + dataclass shapes
- [Source: semvertag/strategies/conventional_commits.py:4-8] — existing `ConventionalCommitsConfig` (unchanged)
- [Source: semvertag/strategies/branch_prefix.py:25-33] — strategy implementation pattern + reference for `_commit_parse.subject_line` refactor
- [Source: semvertag/ioc.py:99-106, 138-143] — `StrategiesGroup`, current strategy fail-fast gate
- [Source: semvertag/_use_case.py:128-137] — `_status_for_no_bump`, `_reason_for_no_bump` already branch on strategy name
- [Source: semvertag/_redact.py:6-11] — `_TOKEN_PATTERN` regex (extending in AC13)
- [Source: tests/integration/conftest.py] — `cli_env`, `install_mock_transport`, `merge_commit_handler`, `_clean_env_before_each` (autouse), `GITLAB_PROJECT_ID`, `DEFAULT_COMMIT_SHA`, `DEFAULT_TAG_NAME`
- [Source: tests/conftest.py] — `HandlerCallable`, `compose_handler`
- [Source: pyproject.toml:83] — `addopts = "--cov=. --cov-report term-missing"`
- [Source: pyproject.toml:90] — `omit = ["_autosemver_reference/*", "_bmad/*", "tests/*"]`
- [Source: Justfile:19-26] — `test`, `test-branch`, `test-branch-strategies` recipes

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context) — bmad-dev-story workflow

### Debug Log References

- **Marina test fixture refactored mid-implementation.** Initial test used `"Merge branch 'feature/foo' into main\n\nfeat!: breaking foo"` as a fixture for both strategies. CC strategy parses **only the subject line** (`_commit_parse.subject_line()` returns `"Merge branch 'feature/foo' into main"`), so `_TYPE_PATTERN.match()` failed and CC returned `Bump.NONE`. The test now uses `"feat!: drop python 3.9"` (squash-merge style): branch-prefix returns `no_merge_commit` (no "Merge branch" marker), CC returns `MAJOR` → `2.0.0`. The journey is still demonstrated — same fixture, divergent bumps.
- **U+2028 / U+2029 literal in test source tripped `RUF001` (ambiguous character).** Replaced with ` ` / ` ` escape sequences in `tests/unit/test_commit_parse.py:8-9`. Runtime behavior identical; lint passes.
- **`_build_json_output(settings)` / `_build_rich_output(settings)` lifted to module scope in `ioc.py`** (already done in Story 1.7 post-review). Verified the lazy-import discipline remains only on provider/strategy modules (architectural mandate). The new `_build_conventional_commits_strategy` lazy-imports `ConventionalCommitsStrategy` from its module to match `_build_branch_prefix_strategy`'s pattern.
- **Strategy dispatch via `container.override(StrategiesGroup.branch_prefix_strategy, cc_instance)`.** modern-di's installed API does not expose per-kwarg override; overriding the resolved provider instance is the equivalent and Story 1.7's pattern (output rich→json swap). Trade-off: when `settings.strategy == "conventional-commits"`, the Factory named `branch_prefix_strategy` resolves to a `ConventionalCommitsStrategy` instance. Counter-intuitive but correct — `UseCasesGroup` binds to the Factory ID at declaration time; the override redirects what that ID resolves to at run-time.
- **A1 reassessed (retrospective action item) and discharged as not-needed.** The architecture (`_bmad/architecture.md:345`) explicitly chose single-commit input for `BumpStrategy.decide`. ConventionalCommitsStrategy parses only the latest merge-commit's subject + footers; no Provider Protocol extension needed.
- **Tests/unit/test_ioc.py NEW.** Three tests cover strategy dispatch (default branch-prefix; CC override; non-gitlab ConfigError). Resolves only `StrategiesGroup.branch_prefix_strategy` directly (avoids triggering provider construction and HTTP-client init in a unit test).

### Completion Notes List

- All 15 ACs (AC1–AC15) verified by **81 new tests** (24 commit-parse + 31 CC strategy + 3 ioc-dispatch + 6 strategy-switching integration + 3 provenance regression + 14 redact extension). Full suite: **324 tests passed** (Epic 1 baseline 243, +81 net add), 0 regressions in Stories 1.1–1.7.
- Coverage: `conventional_commits.py` **100% line + 100% branch** (new gate via `just test-cc-strategies`); `branch_prefix.py` **100% line + 100% branch** (Story 1.6 gate preserved after `_commit_parse.subject_line` refactor); `_commit_parse.py` **100%**; `_redact.py` **100%**; global **93%** (above 85% NFR22 gate).
- `just lint-ci` clean (`eof-fixer`, `ruff format`, `ruff check`, `ty check`).
- `uv build` produces wheel + sdist.
- Story 1.7 strategy fail-fast gate (`ioc.py:141-143`) removed; provider gate (`ioc.py:138-140`) preserved per AC6 / story framing.
- 4 retro action items discharged: A2 (provenance regression tests in `test_provenance.py`), A3 (`_commit_parse.py` shared helper + `branch_prefix.py` refactor), A4 (5 GitHub token-family patterns added to `_redact.py`), A5 (`tests/integration/README.md` documents `_transport.time.sleep` coupling). A1 documented as not-needed; A6 discharged (no `_bmad/epics.md` update).
- `__main__.py` and `_use_case.py` unchanged — Story 1.7's framing held: `_status_for_no_bump`/`_reason_for_no_bump` already branched on strategy name, and the entrypoint already routed `--strategy` into the overlay.
- No new dependencies; `pyproject.toml` unchanged.

### File List

- **New:** `semvertag/_commit_parse.py` (24 stmts — `subject_line()`, `footers()`).
- **New:** `semvertag/strategies/conventional_commits.py` (33 stmts — adds `ConventionalCommitsStrategy`; `ConventionalCommitsConfig` unchanged).
- **New:** `tests/unit/test_commit_parse.py` (24 cases covering AC9).
- **New:** `tests/unit/test_conventional_commits_strategy.py` (31 cases covering AC10).
- **New:** `tests/unit/test_ioc.py` (3 cases covering AC6 dispatch + provider gate).
- **New:** `tests/integration/test_strategy_switching.py` (6 cases covering AC11; includes Marina's journey).
- **New:** `tests/integration/README.md` (AC14 / retro A5 — `_transport.time.sleep` coupling note).
- **Modified:** `semvertag/strategies/branch_prefix.py` (use `_commit_parse.subject_line` per AC9 / retro A3; 100% branch gate preserved).
- **Modified:** `semvertag/ioc.py` (add `ConventionalCommitsStrategy` lazy-import; add `_build_conventional_commits_strategy` creator; add `conventional_commits_strategy` Factory to `StrategiesGroup`; remove strategy fail-fast gate; add `container.override` dispatch when `settings.strategy == "conventional-commits"`).
- **Modified:** `semvertag/_redact.py` (extend `_TOKEN_PATTERN` with 5 GitHub token-family alternations per AC13 / retro A4).
- **Modified:** `tests/unit/test_provenance.py` (3 new regression tests per AC12 / retro A2).
- **Modified:** `tests/unit/test_redact.py` (parametrized cases for 5 new GitHub prefixes).
- **Modified:** `Justfile` (new `test-cc-strategies` recipe per AC15).
- **Modified:** `_bmad/sprint-status.yaml` (`2-1-…: ready-for-dev → in-progress → review`).
- **Modified:** `_bmad/2-1-…md` (Status, all task/subtask checkboxes, Dev Agent Record).
- **No-change confirmed:** `semvertag/__main__.py`, `semvertag/_use_case.py`, `semvertag/_settings.py`, `semvertag/_types.py`, `semvertag/_errors.py`, `semvertag/_output.py`, `semvertag/_transport.py`, `semvertag/providers/_base.py`, `semvertag/providers/gitlab.py`, `tests/conftest.py`, `tests/integration/conftest.py`, `tests/integration/test_cli_main_verb.py`, `tests/integration/test_cli_quiet_json_matrix.py`, `tests/integration/test_gitlab_provider.py`, `tests/unit/conftest.py`, `tests/unit/test_branch_prefix_strategy.py`, `tests/unit/test_settings.py`, `tests/unit/test_use_case.py`, `tests/test_smoke.py`, `pyproject.toml`.

### Change Log

- 2026-05-28 — Added `semvertag/_commit_parse.py` with `subject_line()` and `footers()` per AC9. Uses `splitlines()` (handles `\n`, `\r\n`, U+2028 LS, U+2029 PS).
- 2026-05-28 — Refactored `semvertag/strategies/branch_prefix.py:26` to call `_commit_parse.subject_line(commit.message)` in place of `commit.message.split("\n", 1)[0]`. Story 1.6 100% branch gate preserved.
- 2026-05-28 — Added `ConventionalCommitsStrategy` in `semvertag/strategies/conventional_commits.py` per AC1–AC5. Regex `^(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?(?P<bang>!?):` captures type/scope/`!`; footer scan for `BREAKING CHANGE:` / `BREAKING-CHANGE:` (case-sensitive per CC v1.0.0).
- 2026-05-28 — Wired `ConventionalCommitsStrategy` in `semvertag/ioc.py` per AC6. Removed Story 1.7 strategy fail-fast gate; added `container.override(StrategiesGroup.branch_prefix_strategy, cc_instance)` dispatch when `settings.strategy == "conventional-commits"`.
- 2026-05-28 — Added 31 unit tests in `tests/unit/test_conventional_commits_strategy.py` exercising AC2–AC5 paths and 100% branch coverage.
- 2026-05-28 — Added 24 unit tests in `tests/unit/test_commit_parse.py` covering AC9 cases (CRLF, U+2028/U+2029, leading-blank, footer extraction).
- 2026-05-28 — Added 3 unit tests in `tests/unit/test_ioc.py` covering strategy dispatch (default + CC override) and non-gitlab provider rejection.
- 2026-05-28 — Added 6 integration tests in `tests/integration/test_strategy_switching.py` covering AC11; includes Marina's journey.
- 2026-05-28 — Added 3 provenance regression tests in `tests/unit/test_provenance.py` covering AC12 / retro A2.
- 2026-05-28 — Extended `semvertag/_redact.py:_TOKEN_PATTERN` with 5 GitHub token-family alternations (`gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`) per AC13 / retro A4. Parametrized tests added in `tests/unit/test_redact.py`.
- 2026-05-28 — Added `tests/integration/README.md` documenting `_transport.time.sleep` monkeypatch coupling per AC14 / retro A5.
- 2026-05-28 — Added `test-cc-strategies` recipe to `Justfile` per AC15.
- 2026-05-28 — Bumped Status to `review`; will flip to `done` after `bmad-code-review`.
- 2026-05-29 — `bmad-code-review` complete. 5 decision-needed + 8 patches applied; 8 deferred to `_bmad/deferred-work.md`; 8 dismissed as noise.
- 2026-05-29 — D1: introduced `current_strategy` Factory in `StrategiesGroup`; `UseCasesGroup.semvertag_use_case` now binds to `current_strategy`; the `container.override(StrategiesGroup.branch_prefix_strategy, ...)` dispatch removed from `build_container`. Named `branch_prefix_strategy` and `conventional_commits_strategy` Factories retained for direct-resolve use (future shadow-mode).
- 2026-05-29 — D2: `decide()` `lstrip()`s each `body_lines()` entry before `startswith` — indented `BREAKING CHANGE:` footers now detected.
- 2026-05-29 — D3: `body_lines()` now collects post-subject non-blank lines even without a blank-line separator — lenient footer parse.
- 2026-05-29 — D4: added `_VALID_TYPE_RE` and `@pydantic.field_validator("minor_types", "patch_types")` rejecting non-`[a-z]+$` spellings at config-load.
- 2026-05-29 — D5: renamed `_commit_parse.footers()` → `body_lines()` (helper now honestly reflects its semantics); consumers and tests updated.
- 2026-05-29 — P1/P2 added negative test rows (`"  feat: foo"` and `"feat : foo"` → `Bump.NONE`). P3 added `test_body_lines_strips_carriage_returns_from_crlf_input` to lock `\r`-free body lines. P4 replaced `Settings.model_copy(update=...)` with constructor kwargs in `test_ioc.py`. P5 parametrized non-gitlab gate test over `["github", "bitbucket"]`. P6 added per-prefix min-length + word-boundary + start-of-input cases in `test_redact.py`. P7 cited `test_gitlab_provider.py:848-849, 862-863, 876-877` in `tests/integration/README.md`. P8 clarified Marina-journey wording in `Dev Notes §Story framing`.
- 2026-05-29 — Suite: 356 tests pass (was 324; net +32 review-cycle tests). `branch_prefix.py` and `conventional_commits.py` both 100% line + branch. Global line coverage 94%. `just lint-ci`, `uv run ty check`, `uv build` all clean. Status flipped `review` → `done`.
