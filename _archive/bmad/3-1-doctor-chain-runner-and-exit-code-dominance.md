# Story 3.1: Doctor chain runner with skip-on-failure semantics and exit-code dominance

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a CLI engineer wiring up `semvertag doctor`,
I want a pure-Python chain runner that executes the four `Provider.check_*` methods in sequence, marks dependents as `status="skipped"` when their prerequisite fails, and resolves the dominant exit code from the accumulated `CheckResult` list,
So that Story 3.2 can wrap a thin Typer subcommand around stable, unit-tested orchestration logic that satisfies FR29, FR30, and NFR4.

## Acceptance Criteria

### AC1 — `doctor/_checks.py:run_checks` returns four `CheckResult` items in declared order when all four checks pass

**Given** `doctor/_checks.py` defines `run_checks(provider: Provider) -> list[CheckResult]`
**And** a `Provider` implementation whose `check_token()`, `check_scopes()`, `check_project_access()`, and `check_protected_tags()` all return `CheckResult(status="passed", ...)`
**When** `run_checks(provider)` is called
**Then** it returns exactly **four** `CheckResult` items, all with `status="passed"`, in this declared order:

1. `name="token"`
2. `name="scopes"`
3. `name="project_access"`
4. `name="protected_tags"`

**And** each `check_*` method is invoked exactly once (verified via a `unittest.mock.Mock` or a call-count counter on the stub).

### AC2 — First failure short-circuits the chain; all subsequent checks return `status="skipped"` with a fixed cause format

**Given** a `Provider` whose `check_token()` returns `CheckResult(name="token", status="failed", cause="Token rejected by GitLab. Verify SEMVERTAG_TOKEN is valid.")`
**And** `check_scopes()`, `check_project_access()`, `check_protected_tags()` would each return `passed` if called
**When** `run_checks(provider)` is called
**Then** the returned list has exactly four items:

1. The first item is the **original** failed `CheckResult` from `check_token()` (verbatim — `cause` not rewritten)
2. The next three items are each `CheckResult(name=<their name>, status="skipped", cause="Skipped: blocked by token check.")`

**And** `check_scopes()`, `check_project_access()`, `check_protected_tags()` are **NOT** invoked (verified via call-count assertions).

### AC3 — The blocking-check name appears in every skipped result's cause regardless of where the failure occurred

**Given** the same provider as AC1 except `check_scopes()` returns `failed` with any cause
**When** `run_checks(provider)` is called
**Then** the returned list is:

1. `CheckResult(name="token", status="passed", ...)` — original
2. `CheckResult(name="scopes", status="failed", ...)` — the original failed result
3. `CheckResult(name="project_access", status="skipped", cause="Skipped: blocked by scopes check.")`
4. `CheckResult(name="protected_tags", status="skipped", cause="Skipped: blocked by scopes check.")`

**And** by symmetry, a failure at `check_project_access()` produces a single `"Skipped: blocked by project_access check."` cause on `protected_tags`. A failure at `check_protected_tags()` produces no skipped results (it is the last in the chain).

### AC4 — `resolve_exit_code(results)` returns `0` when every result is `status="passed"`

**Given** `doctor/_checks.py` also defines `resolve_exit_code(results: list[CheckResult]) -> int`
**When** `results` contains four `passed` items
**Then** `resolve_exit_code(results) == 0`.

### AC5 — `resolve_exit_code` resolves a single `failed` result via cause-fragment translation to its mapped exit code

**Given** a single `CheckResult(status="failed", cause=<token-class cause>)` plus three `skipped` results
**When** `resolve_exit_code(results)` is called
**Then** the returned code matches the `SemvertagError` subclass implied by the cause fragment:

- Causes containing one of `("Token rejected", "Token blocked", "Token missing", "Token cannot read", "Token has no access")` → `AuthError.exit_code` = **3**
- Causes containing one of `("GitLab project not found", "GitLab version too old")` → `ConfigError.exit_code` = **2**
- Causes containing one of `("GitLab unreachable", "Unexpected GitLab response")` → `ProviderAPIError.exit_code` = **4**
- Any other failed cause → `SemvertagError.exit_code` = **1** (generic)

**And** the fragment lists are declared as module-level `typing.Final` tuples in `doctor/_checks.py` (single owner per Dev Notes §Cause→exit-code translation), not duplicated in `_errors.py` or elsewhere.

### AC6 — Multi-fail dominance: `3 > 4 > 2 > 1`

**Given** a results list with two `failed` items — one mapping to `AuthError` (3) and one mapping to `ProviderAPIError` (4), plus any number of `skipped` / `passed`
**When** `resolve_exit_code(results)` is called
**Then** it returns **3** (AuthError wins over ProviderAPIError).

**And** the dominance table holds for every pairing — exhaustively:

| Failed codes present | Returned |
|---|---|
| `{0}` (all passed) | `0` |
| `{1}` | `1` |
| `{2}` | `2` |
| `{3}` | `3` |
| `{4}` | `4` |
| `{1, 2}` | `2` |
| `{1, 3}` | `3` |
| `{1, 4}` | `4` |
| `{2, 3}` | `3` |
| `{2, 4}` | `4` (4 wins over 2) |
| `{3, 4}` | `3` (3 wins over 4) |
| `{1, 2, 3}` | `3` |
| `{1, 2, 4}` | `4` |
| `{1, 3, 4}` | `3` |
| `{2, 3, 4}` | `3` |
| `{1, 2, 3, 4}` | `3` |

(Dominance order: `3 > 4 > 2 > 1`.) Each table row is exercised by a parametrized test in AC10.

### AC7 — `resolve_exit_code` is `0` when no `failed` results are present, even if `skipped` results exist

**Given** a results list with zero `failed` items and at least one `skipped` item (cannot happen via `run_checks` — only via direct construction)
**When** `resolve_exit_code(results)` is called
**Then** it returns **0**.

**And** this case exists for unit-test completeness; `run_checks` never produces `skipped` without a preceding `failed`, but the resolver MUST be total — defined for any `list[CheckResult]`.

### AC8 — `doctor/__init__.py` exports nothing from `_checks.py` (private surface)

**Given** `semvertag/doctor/__init__.py` is a new module
**When** Story 3.1 lands
**Then** `__init__.py` is **empty** or contains only `__all__: typing.Final = ()`. The chain runner and resolver are addressed via `from semvertag.doctor._checks import run_checks, resolve_exit_code` — Story 3.2's Typer subcommand is the consumer.

**And** `doctor/_checks.py` declares `__all__: typing.Final = ("resolve_exit_code", "run_checks")` (alphabetical to satisfy `RUF022`).

### AC9 — No new dependencies; no changes to `_types.py`, `_errors.py`, `providers/_base.py`, `providers/gitlab.py`, or the DI Groups

**Given** Epic 3's framing ("does not modify `providers/gitlab.py`")
**When** Story 3.1 lands
**Then** the diff modifies only the new files listed in §Files this story touches.
**And** `CheckResult` shape (`name`, `status`, `cause`) is preserved — no `exit_code` field is added.
**And** `SemvertagError`-subclass `exit_code` ClassVars (`_errors.py:5,9,13,17`) remain the source of truth for the codes; `_checks.py` imports them rather than re-declaring magic numbers.

### AC10 — Unit tests: every chain ordering and every dominance-table cell exercised

**Given** `tests/unit/test_doctor_checks.py` is a new file
**When** `pytest --cov=semvertag.doctor --cov-branch --cov-fail-under=100 tests/unit/test_doctor_checks.py` runs
**Then**:

- A stub `Provider` implementation in the test module returns canned `CheckResult` values keyed per check.
- The stub records call counts so AC1/AC2/AC3 can assert that skipped checks were **never invoked**.
- Every chain ordering is exercised by a parametrized test:
  - all-passed
  - fail-at-`token` (verifies AC2)
  - fail-at-`scopes` (verifies AC3 — `project_access` and `protected_tags` skipped citing `scopes`)
  - fail-at-`project_access` (verifies AC3 — only `protected_tags` skipped citing `project_access`)
  - fail-at-`protected_tags` (verifies AC3 — no skipped result follows)
- Every cell of the AC6 dominance table is exercised — parametrize across the 16 rows.
- Each fragment in each of the three cause-fragment tuples (AC5) is exercised at least once by a parametrized test asserting the correct exit-code mapping.
- An "unmapped cause" test asserts the fall-through to `1`.
- `resolve_exit_code([])` returns `0` (empty input edge case — total function).

**And** every test reuses a single stub-provider factory; no `httpx2`, no `MockTransport`, no real network access. Suite runs in <0.1s.

### AC11 — `just test-doctor` recipe enforces 100% branch coverage on `semvertag/doctor`

**Given** the existing strict-coverage recipe pattern in `Justfile:25-29` (`test-branch-strategies`, `test-cc-strategies`)
**When** Story 3.1 lands
**Then** a new recipe `test-doctor` is added that runs:

```just
test-doctor:
    uv run --no-sync pytest -o "addopts=" --cov=semvertag.doctor --cov-branch --cov-fail-under=100 --cov-report=term-missing tests/unit/test_doctor_checks.py
```

**And** the recipe is documented in `Dev Notes §Coverage interaction`.

### AC12 — `just test` green; full suite passes; no regressions

**Given** `just test` is run from a fresh checkout post-`uv sync`
**When** the full pytest suite completes
**Then**:

- All 356 tests from Epic 1+2 pass unchanged (regression canary).
- New unit tests from AC10 (chain orderings + dominance table cells + cause-fragment cases + edge case = expected ~30 cases) pass.
- `pytest --cov` global line coverage **≥85%** (`pyproject.toml` gate).
- `just test-branch-strategies` and `just test-cc-strategies` still pass at 100% branch.
- **NEW**: `just test-doctor` runs clean per AC11.
- `just lint-ci`, `uv run ty check`, and `uv build` all complete clean.

## Tasks / Subtasks

- [x] **Task 1: Scaffold `semvertag/doctor/` package (AC8, AC9)**.
  - [x] 1.1 Create `semvertag/doctor/__init__.py` with `__all__: typing.Final = ()` (or empty file — pick one; the `__all__` form is more grep-friendly).
  - [x] 1.2 Create `semvertag/doctor/_checks.py` skeleton with module imports: `import typing; from semvertag._errors import AuthError, ConfigError, ProviderAPIError, SemvertagError; from semvertag._types import CheckResult; from semvertag.providers._base import Provider`. NO `from __future__ import annotations` (architecture line 1045 / CLAUDE.md).

- [x] **Task 2: Implement chain runner `run_checks` (AC1, AC2, AC3)**.
  - [x] 2.1 Define `_CHAIN_METHODS: typing.Final = (("token", "check_token"), ("scopes", "check_scopes"), ("project_access", "check_project_access"), ("protected_tags", "check_protected_tags"))` as a single source of truth for chain order + name↔method pairing. Use a tuple of tuples (NOT a dict — preserve order explicitly per architecture's "no `OrderedDict` smells, just rely on insertion order or `tuple`s" convention).
  - [x] 2.2 Implement `run_checks(provider: Provider) -> list[CheckResult]`:
    1. Initialize `results: list[CheckResult] = []` and `blocking_check: str | None = None`.
    2. For each `(name, method_name)` in `_CHAIN_METHODS`:
       - If `blocking_check is not None`: append `CheckResult(name=name, status="skipped", cause=f"Skipped: blocked by {blocking_check} check.")` and continue.
       - Else: call `getattr(provider, method_name)()`, append the returned `CheckResult` verbatim, and if its `status == "failed"`, set `blocking_check = name`.
    3. Return `results`.
  - [x] 2.3 The skip cause string is `f"Skipped: blocked by {blocking_check} check."` — note the period; matches the AC2/AC3 acceptance text verbatim. Define the prefix as a module-level constant `_SKIPPED_CAUSE_TEMPLATE: typing.Final = "Skipped: blocked by {name} check."` so tests can `.format(name=...)` instead of hardcoding.

- [x] **Task 3: Implement `resolve_exit_code` (AC4, AC5, AC6, AC7)**.
  - [x] 3.1 Declare module-level cause-fragment tuples (AC5):
    ```python
    _AUTH_CAUSE_FRAGMENTS: typing.Final = (
        "Token rejected",
        "Token blocked",
        "Token missing",
        "Token cannot read",
        "Token has no access",
    )
    _CONFIG_CAUSE_FRAGMENTS: typing.Final = (
        "GitLab project not found",
        "GitLab version too old",
    )
    _PROVIDER_API_CAUSE_FRAGMENTS: typing.Final = (
        "GitLab unreachable",
        "Unexpected GitLab response",
    )
    ```
  - [x] 3.2 Implement `_exit_code_for_failed_check(result: CheckResult) -> int`:
    - `if any(f in result.cause for f in _AUTH_CAUSE_FRAGMENTS): return AuthError.exit_code`
    - `if any(f in result.cause for f in _CONFIG_CAUSE_FRAGMENTS): return ConfigError.exit_code`
    - `if any(f in result.cause for f in _PROVIDER_API_CAUSE_FRAGMENTS): return ProviderAPIError.exit_code`
    - `return SemvertagError.exit_code`
  - [x] 3.3 Implement `resolve_exit_code(results: list[CheckResult]) -> int`:
    1. `failed_codes: typing.Final = [_exit_code_for_failed_check(r) for r in results if r.status == "failed"]`
    2. If `not failed_codes`: return `0` (covers AC4 all-passed and AC7 no-failed-only-skipped).
    3. Walk dominance order `_DOMINANCE: typing.Final = (3, 4, 2, 1)` and return the first match.
    4. Fall-through (`return 1`) is unreachable in practice (every `_exit_code_for_failed_check` returns one of `{1, 2, 3, 4}`) but keep it as a defensive default so branch coverage tools don't choke on an unreachable end of function.

- [x] **Task 4: Author unit tests `tests/unit/test_doctor_checks.py` (AC10)**.
  - [x] 4.1 Module preamble: `import dataclasses; import typing; import pytest; from semvertag._types import CheckResult; from semvertag.doctor._checks import resolve_exit_code, run_checks`. Pre-annotate `typing.Final` on every module-level constant (Story 1.2 conftest precedent).
  - [x] 4.2 Define a stub `Provider` shape — a `@dataclasses.dataclass` (NOT a class with mocks) carrying four `CheckResult` fields plus a `call_log: list[str] = dataclasses.field(default_factory=list)`. Each `check_*` method appends its name to `call_log` and returns the corresponding canned `CheckResult`. The stub's `name`, `get_default_branch`, `get_latest_commit_on_default_branch`, `list_tags`, `create_tag` are no-op stubs that `raise AssertionError` if called — the doctor chain MUST NOT touch them.
  - [x] 4.3 Implement chain-ordering tests (parametrize over `(token_result, scopes_result, project_access_result, protected_tags_result, expected_statuses, expected_call_log)` tuples):
    - All-passed: `["passed"]*4`, call log `["token", "scopes", "project_access", "protected_tags"]`.
    - Fail-at-token: `["failed", "skipped", "skipped", "skipped"]`, call log `["token"]`, skipped cause `"Skipped: blocked by token check."`.
    - Fail-at-scopes: `["passed", "failed", "skipped", "skipped"]`, call log `["token", "scopes"]`, skipped cause `"Skipped: blocked by scopes check."`.
    - Fail-at-project_access: `["passed", "passed", "failed", "skipped"]`, call log `["token", "scopes", "project_access"]`, skipped cause `"Skipped: blocked by project_access check."`.
    - Fail-at-protected_tags: `["passed", "passed", "passed", "failed"]`, call log `["token", "scopes", "project_access", "protected_tags"]`, no skipped results.
  - [x] 4.4 Implement cause-fragment translation tests (parametrize over each fragment from each tuple in §3.1):
    - For each `_AUTH_CAUSE_FRAGMENTS` member, assert `_exit_code_for_failed_check(CheckResult(name="token", status="failed", cause=f"…{fragment}…"))` returns `AuthError.exit_code`. Similarly for config and provider-API fragments.
    - **Note:** `_exit_code_for_failed_check` is module-private. Test it via `resolve_exit_code([CheckResult(...)])` to exercise the same path without reaching into private API.
    - Unmapped cause: `cause="Some weird thing not in any list."` → exit `1`.
  - [x] 4.5 Implement dominance-table tests (parametrize over the 16 rows in AC6):
    - Each row constructs the appropriate `list[CheckResult]` using sample causes from §3.1 (e.g., code-3 row → `cause="Token rejected by GitLab."`), then asserts `resolve_exit_code(results) == expected`.
  - [x] 4.6 Edge cases:
    - `resolve_exit_code([])` → `0` (total-function guarantee, AC7).
    - `resolve_exit_code([passed, passed, passed, passed])` → `0`.
    - `resolve_exit_code([skipped, skipped])` → `0` (no failed = pass-through).
  - [x] 4.7 Verify naming follows `test_<verb>_<outcome>_when_<condition>` (architecture line 911). Example names:
    - `test_returns_four_passed_results_when_every_check_passes`
    - `test_skips_subsequent_checks_when_token_fails`
    - `test_skipped_cause_names_the_blocking_check`
    - `test_resolves_exit_code_to_auth_when_cause_matches_token_rejected_fragment`
    - `test_resolves_dominant_exit_code_when_multiple_checks_fail`

- [x] **Task 5: Add `test-doctor` recipe to `Justfile` (AC11)**.
  - [x] 5.1 Append the recipe to `Justfile` matching the style of `test-branch-strategies` / `test-cc-strategies`.
  - [x] 5.2 No changes to `default`, `install`, `lint`, `lint-ci`, or `test` recipes (don't fold the new gate into the global suite per Story 1.6/2.1 precedent).

- [x] **Task 6: Run the full local validation gate (AC12)**.
  - [x] 6.1 `just install` (fresh sync).
  - [x] 6.2 `just lint-ci` — must be clean.
  - [x] 6.3 `just test` — full suite passes; global line coverage ≥85%.
  - [x] 6.4 `just test-branch-strategies` — Story 1.6 gate stays 100%.
  - [x] 6.5 `just test-cc-strategies` — Story 2.1 gate stays 100%.
  - [x] 6.6 `just test-doctor` — NEW 100% branch gate on `semvertag/doctor`.
  - [x] 6.7 `uv run ty check` — clean.
  - [x] 6.8 `uv build` — clean.
  - [x] 6.9 Update `_bmad/sprint-status.yaml`: `epic-3: backlog → in-progress`; `3-1-…: backlog → ready-for-dev → in-progress → review` (code-review step bumps to `done`).
  - [x] 6.10 Update this story file: tick all task/subtask checkboxes; fill in Dev Agent Record sections; bump Status to `review`.

### Review Findings

_Code review 2026-05-29 — Blind Hunter + Edge Case Hunter + Acceptance Auditor. 1 patch, 6 deferred, ~25 dismissed as noise._

- [x] [Review][Patch] Add 1-line module comment to `_checks.py` documenting cause-fragment ownership coupling to `providers/gitlab.py` per Dev Notes §Critical architectural constraints item 10 [`semvertag/doctor/_checks.py:16`] — applied 2026-05-29: `# Cause fragments shadow GitLabProvider's cause vocabulary (providers/gitlab.py); update in lockstep when wording changes there. See story 3-1.`
- [x] [Review][Defer] `resolve_exit_code` raises `StopIteration` if `_exit_code_for_failed_check` ever returns a code not in `_DOMINANCE` [`semvertag/doctor/_checks.py:46`] — deferred, intentional trade-off documented in Debug Log References to satisfy 100% branch gate; future contributors adding a new `SemvertagError` subclass must extend `_DOMINANCE` in lockstep.
- [x] [Review][Defer] Multi-family cause string routes to first matching family (auth → config → provider_api lexical order in `_exit_code_for_failed_check`), bypassing `_DOMINANCE` order for within-cause classification [`semvertag/doctor/_checks.py:43-49`] — deferred, hypothetical; current `GitLabProvider` emits one cause per check, no realistic input mixes config + provider_api fragments. Worth pinning when Story 3.2 lands integration tests against the real provider.
- [x] [Review][Defer] Empty `cause=""` on a failed `CheckResult` silently maps to `SemvertagError.exit_code` (1) with no test pinning behavior [`semvertag/doctor/_checks.py:43-49`] — deferred, provider contract makes this unreachable; reconsider if `CheckResult.cause` ever loosens to `str | None`.
- [x] [Review][Defer] Cause-fragment matching is substring-based and case-sensitive; "Token missing" inside an unrelated phrase mis-classifies; lowercase "token rejected" falls through to generic [`semvertag/doctor/_checks.py:43-49`] — deferred, `providers/gitlab.py` is single owner of cause vocabulary; integration tests in Story 3.2 will catch real drift.
- [x] [Review][Defer] Working tree carries uncommitted Story 2.1 work alongside 3.1 (extra Justfile recipe, `_bmad/deferred-work.md` 2.1 entries, `_bmad/sprint-status.yaml` flips Epic 2 / Story 2.1 to `done`) — deferred, out of 3.1's declared scope but not wrong; resolves when Story 2.1 lands its own commit.
- [x] [Review][Defer] `test_doctor_checks.py` is 294 LOC vs spec budget of ~150-200 [`tests/unit/test_doctor_checks.py`] — deferred, spec uses `~`; case count (33) is within `~30` tolerance and 100% branch gate is satisfied.

**Dismissed (sample):** provider exception handling (spec anti-pattern line 368 explicitly forbids catching `check_*` exceptions); empty `__all__` in `__init__.py` (AC8 mandates it); `_DOMINANCE` uses `.exit_code` refs vs spec literal (improvement honoring Constraint 6); `resolve_exit_code` `next()` vs for-loop (documented Debug Log refactor for 100% branch gate); stub doesn't assert `Protocol` conformance (style); `noqa: ARG002` (documented precedent from Stories 1.5/1.7); skip-message cites first-failed not predecessor (matches AC3 verbatim); `getattr` dynamic dispatch (intentional `_CHAIN_METHODS` table pattern); `_CHAIN_METHODS` string method names; sprint-status workflow state skipping; speculation about future UI miscounting `len(results)`.

**Verdict:** All AC1–AC12 functional requirements satisfied. Implementation tracks spec intent on every load-bearing constraint; the one Constraint 10 miss is a 1-line comment.

## Dev Notes

### Story framing

This is the **first story of Epic 3** — Pre-flight Diagnostics. Story 3.1 ships the pure-Python orchestration (chain runner + exit-code resolver) with full unit-test coverage; Story 3.2 wraps a Typer subcommand around it, adds the config-source renderer, and wires DI. By splitting orchestration from CLI plumbing, Story 3.1 can land a strict 100%-branch gate on `semvertag/doctor` without the integration-test surface (`CliRunner` + `MockTransport`) coupling.

Epic 3's epic statement explicitly says: *"this epic does not modify `providers/gitlab.py`"*. Story 3.1 inherits that constraint. The four `Provider.check_*` methods were implemented in Story 1.5; they return `CheckResult(name, status, cause)` tuples that Story 3.1 orchestrates. The `CheckResult` shape stays untouched (Dev Notes §`CheckResult` shape rationale below).

### Critical architectural constraints

1. **Single-pass sequential chain** (architecture §Doctor Architecture line 527). Token → scopes → project_access → protected_tags. No parallelism, no async (deferred per architecture line 297 — "sequential is comfortably under NFR4's 10s budget"). Implement as a `for` loop, not a recursion.

2. **First failure blocks ALL subsequent checks** (AC2). Each skipped result cites the *first* failing check's name, not the immediately preceding one. This is a "blocking-check name" model: once `blocking_check` is set, every later iteration appends a skipped result citing it.

3. **`CheckResult` shape is stable** (`_types.py:42-46`). Story 3.1 does NOT add an `exit_code` field. Reason: Epic framing forbids touching `providers/gitlab.py`; adding `exit_code` would either require a stale `default=1` for every existing `CheckResult(...)` call site (defeating the dominance logic) or force a `gitlab.py` update (forbidden). Instead, the resolver maps `cause` → exit code via fragment tuples declared in `_checks.py`.

4. **Cause-fragment ownership** (§Cause→exit-code translation below). The fragment tuples live in `doctor/_checks.py`, NOT in `_errors.py` or `providers/gitlab.py`. They are the single canonical mapping between user-visible cause text and `SemvertagError`-subclass exit codes. If `providers/gitlab.py` ever changes the cause wording, `_checks.py` must be updated in lockstep (and the unit tests will catch the drift). Document this coupling in `Dev Agent Record §Debug Log References` so a future provider-author doesn't silently break the gate.

5. **Exit-code dominance order: `3 > 4 > 2 > 1`** (architecture line 529). AuthError trumps ProviderAPIError trumps ConfigError trumps generic. The architecture's rationale (PRD prioritization): a 401 misconfiguration is the user's most actionable signal — fix the token, then re-run, then look at network/provider issues.

6. **`SemvertagError` subclasses are the source of truth for exit codes** (`_errors.py:5,9,13,17`). `_checks.py` MUST import them and reference `.exit_code` rather than hardcoding `1`, `2`, `3`, `4`. This keeps the FR37 stability surface single-owner.

7. **No DI wiring in this story** — `ioc.py` is do-not-touch. Story 3.2 will add a `DoctorGroup` or fold doctor into an existing Group. Story 3.1 ships pure-Python functions consumable from any caller.

8. **No `print()` / `Output` / `typer.Exit` calls in `_checks.py`** (anti-pattern line 1041; architecture line 1216). The chain runner returns data; the resolver returns an int. The Typer entrypoint (Story 3.2) translates `resolve_exit_code(...)` into `typer.Exit(code=...)`. The runner is pure-Python with no IO.

9. **No `from __future__ import annotations`** (architecture line 1045). Use `typing.TYPE_CHECKING` for forward references if needed (Story 3.1 should not need any — `Provider` and `CheckResult` are both safe to import at module scope).

10. **Comment policy** (CLAUDE.md, architecture line 1046). Only WHY when non-obvious. The cause-fragment ownership (constraint 4) is non-obvious and deserves a 1-line module docstring or comment at the top of the fragment-tuple block, referencing this story.

### Cause→exit-code translation

The fragment tuples in `_checks.py` shadow the cause-string vocabulary emitted by `GitLabProvider.check_*` methods (`semvertag/providers/gitlab.py:164-278`). Map sources:

| Fragment (`_AUTH_CAUSE_FRAGMENTS`) | Originating gitlab.py site | HTTP context |
|---|---|---|
| `"Token rejected"` | `check_token` 401, `check_project_access` 401 | 401 Unauthorized |
| `"Token blocked"` | `check_token` 403 | 403 Forbidden, /user endpoint |
| `"Token missing"` | `check_scopes` 401/403, scope eval failures | 401/403 or scope shortfall |
| `"Token cannot read"` | `check_protected_tags` 401/403 | 401/403 on /protected_tags |
| `"Token has no access"` | `check_project_access` 403 | 403 on /projects/{id} |

| Fragment (`_CONFIG_CAUSE_FRAGMENTS`) | Originating gitlab.py site | HTTP context |
|---|---|---|
| `"GitLab project not found"` | `check_project_access` 404, `check_protected_tags` 404 | 404 — wrong `project_id` |
| `"GitLab version too old"` | `check_scopes` 404 | 404 on /personal_access_tokens/self (GitLab <15.0) |

| Fragment (`_PROVIDER_API_CAUSE_FRAGMENTS`) | Originating gitlab.py site | HTTP context |
|---|---|---|
| `"GitLab unreachable"` | every `check_*` `response is None` branch | `httpx2.RequestError` family |
| `"Unexpected GitLab response"` | every `check_*` else-branch | unknown status code |

The fragment matching uses `in`, not `startswith` — `gitlab.py` may add prefixes like `"Token rejected by GitLab"` and the match will still hit. This is intentional: fragment is a substring sentinel, not a strict prefix.

**Future drift risk:** if `gitlab.py` rewords a cause string (e.g., normalization, i18n), the fragment must change in lockstep. The 100% branch gate on `_checks.py` will not catch wording drift — only the *integration* tests in Story 3.2 (CLI → real provider → assert exit code) will. For Story 3.1's unit-test surface, the fragments are tested against synthetic cause strings, so the gate is internally consistent. Flag wording-drift coupling in `Dev Agent Record §Debug Log References`.

### Coverage interaction

| File | Target |
|---|---|
| `semvertag/doctor/_checks.py` | **100% line + 100% branch** (new strict gate via `just test-doctor` — AC11). |
| `semvertag/doctor/__init__.py` | trivially 100% (empty or single `__all__`). |
| `semvertag/strategies/branch_prefix.py` | 100% line + branch (Story 1.6 gate; unchanged). |
| `semvertag/strategies/conventional_commits.py` | 100% line + branch (Story 2.1 gate; unchanged). |
| `semvertag/providers/gitlab.py` | ≥85% line (existing; unchanged — not touched by this story). |
| `tests/**/*.py` | not measured. |

**Coverage gate verification commands:**

- `just test` — global ≥85% line coverage (term-missing report).
- `just test-branch-strategies` — Story 1.6 100% branch on `branch_prefix.py`.
- `just test-cc-strategies` — Story 2.1 100% branch on `conventional_commits.py`.
- `just test-doctor` — NEW per AC11: 100% branch on `semvertag/doctor`.

### Files this story touches

| File | Action | Notes |
|---|---|---|
| `semvertag/doctor/__init__.py` | **NEW** | Empty (or `__all__: typing.Final = ()`). Package marker. |
| `semvertag/doctor/_checks.py` | **NEW** | `run_checks`, `resolve_exit_code`, `_exit_code_for_failed_check`, three `_*_CAUSE_FRAGMENTS` tuples, `_CHAIN_METHODS` tuple, `_DOMINANCE` tuple, `_SKIPPED_CAUSE_TEMPLATE` constant. ~40-60 LOC. |
| `tests/unit/test_doctor_checks.py` | **NEW** | Stub `Provider` dataclass + chain-ordering tests + cause-fragment tests + dominance-table tests + edge cases. ~150-200 LOC, ~30 cases. |
| `Justfile` | **UPDATE** | Add `test-doctor` recipe (AC11). |
| `_bmad/sprint-status.yaml` | **UPDATE** | `epic-3: backlog → in-progress`; `3-1-…: backlog → ready-for-dev → in-progress → review`. Update `last_updated_note`. |
| `_bmad/3-1-doctor-chain-runner-and-exit-code-dominance.md` (this file) | **UPDATE** | Status, all task/subtask checkboxes, Dev Agent Record, File List, Change Log. |
| `_bmad/deferred-work.md` | **UPDATE** (post-review only) | Append `## Deferred from: story 3-1-…` for any non-blocking decisions / discovered edge cases. |
| **Do-not-touch** (regression canaries / Epic 3 scope) | — | `semvertag/__main__.py`, `semvertag/_use_case.py`, `semvertag/_settings.py`, `semvertag/_types.py`, `semvertag/_errors.py`, `semvertag/_output.py`, `semvertag/_transport.py`, `semvertag/_redact.py`, `semvertag/_commit_parse.py`, `semvertag/ioc.py`, `semvertag/providers/_base.py`, `semvertag/providers/gitlab.py`, `semvertag/strategies/*.py`, all existing tests, `pyproject.toml`. |

### Testing standards

(Architecture §Test Architecture lines 548–581; carried forward from Stories 1.5/1.6/1.7/2.1.)

- **Unit-only for Story 3.1.** No integration tests — the chain runner is pure-Python orchestration over a `Provider` Protocol stub. Story 3.2 owns the CLI integration surface (`tests/integration/test_cli_doctor.py`).
- **Stub Provider, NOT `unittest.mock`.** A `@dataclasses.dataclass` stub keeps the test surface concrete and readable; `Mock` would obscure the four `check_*` return types. The stub doubles as a usage example for Story 3.2's DI wiring.
- **`tests/unit/test_use_case.py:55-69` already has a stub-Provider precedent** with `# pragma: no cover` on the `check_*` methods — Story 3.1 mirrors the shape but flips the `pragma: no cover` to assert coverage (the chain runner WILL exercise those methods).
- **Test function naming:** `test_<verb>_<outcome>_when_<condition>` (architecture line 911). Use `parametrize` aggressively for the chain orderings and dominance table.
- **`typing.Final` on every module-level constant** in the test file (Story 1.2 conftest precedent / `auto-typing-final` discipline).
- **No `unittest.mock.patch`, no monkeypatching** — the chain runner has no side effects to patch.

### Anti-patterns to avoid

(Architecture §Anti-Patterns lines 1039–1049; highlighting the relevant ones for this story.)

- **`print()` in `_checks.py`** — strategies don't emit progress, neither does the chain runner. Output flows through `Output` (Story 3.2).
- **Calling `typer.Exit(...)` from `_checks.py`** — exit-code mapping happens in `__main__.py` (architecture line 1216). `resolve_exit_code` returns an int; the Typer callback (Story 3.2) translates.
- **Re-declaring exit-code constants (1/2/3/4) in `_checks.py`** — import `SemvertagError.exit_code` etc. Single-owner per architecture's "every cross-cutting concern has a documented single owner".
- **Walking `_CHAIN_METHODS` by index instead of by name** — keep the chain declarative; the `_CHAIN_METHODS` tuple is the data, the loop is the engine.
- **Async / `concurrent.futures` parallelism** — explicitly out of scope (architecture line 297). NFR4's 10s budget tolerates sequential.
- **Catching exceptions from `provider.check_*()`** — the `Provider` Protocol contract says `check_*` returns `CheckResult` (the provider catches its own httpx2 errors internally — see `gitlab.py:286-295` `_safe_get`). If a provider raises, that's a provider bug; don't paper over it in `_checks.py`.
- **`from __future__ import annotations`** — banned (architecture line 1045).
- **Comments restating WHAT the code does** — only WHY (CLAUDE.md).
- **Mutable default arguments** — N/A here (no kwargs with defaults), but architecture line 1047 applies.

### Learnings from Epic 1 + 2 (carried forward)

[Source: `_bmad/epic-1-retro-2026-05-28.md` + Stories 1.1–1.7, 2.1 Dev Agent Records + Review Findings]

- **Architecture sketches under-specified library semantics in every Epic 1 story past 1.1.** Expect 1–2 seams the spec didn't name. Document them in `Dev Agent Record §Debug Log References`. Likely candidates here: whether the `_CHAIN_METHODS` tuple should also encode the prerequisite (currently implicit — every check's prerequisite is "everything before it"); whether `resolve_exit_code([])` returning `0` is reasonable (it is — an empty input means no failures means pass; the AC pins this).
- **Protocol modules need a structural-conformance unit test to count for coverage** (Epic 1 retro §2). `semvertag/doctor/_checks.py` is NOT a Protocol module — but `__init__.py` IS easy to leave at 0% coverage if no test imports it. Importing `from semvertag.doctor._checks import …` in the test file implicitly imports `semvertag.doctor.__init__` and covers it.
- **`auto-typing-final` will rewrite `yield None` → `return None`** in fixtures (Story 1.2 precedent). Pre-annotate `typing.Final` on every test-level constant.
- **`PLC0415 import-not-at-top-of-file`** — does NOT apply here (no lazy imports needed). All imports at module top.
- **`uv build` is a per-story acceptance bar** (Story 1.1+). Run alongside `just test` and `just lint-ci` before flipping to `review` (Task 6.8).
- **Test fixture drift / Click ≥8.2 / `CliRunner` quirks** — N/A for Story 3.1 (no CliRunner used).
- **Story 2.1 added a pydantic `field_validator` on `ConventionalCommitsConfig`** — no analog needed here. `CheckResult.status` is already `Literal["passed", "failed", "skipped"]`; the `_checks.py` code only ever produces those values.
- **Story 2.1 demonstrated the `current_strategy` Factory pattern** for clean DI dispatch — Story 3.2 may borrow this pattern (e.g., a `DoctorGroup` with a single `chain_runner` Factory), but Story 3.1 does not need DI at all.

### Project Structure Notes

After this story:

- `semvertag/doctor/` exists as a new package — first one outside `providers/` and `strategies/`.
- Module count: previous 15 + `doctor/_checks.py` + `doctor/__init__.py` = **17 code files**. Architecture's ~1,300 LOC at end of Epic 2 grows by ~50 LOC to ~1,350 — comfortably under NFR21's 1,500-line soft target.
- `Justfile` gains one recipe (`test-doctor`). Story 4.1 (CI workflow polish) may consolidate the three strict-coverage recipes into a single CI step.
- Story 3.2 will introduce: `doctor/_render.py` (DoctorResult + ConfigSourceView), `tests/integration/test_cli_doctor.py`, modifications to `__main__.py` (subcommand registration), `ioc.py` (doctor wiring), and `docs/doctor.md` (per architecture line 1159).
- Epic 3 completes with Story 3.2. There is no Story 3.3.

## References

- [Source: architecture.md#Doctor Architecture lines 525–533] — sequential chain, skip-on-failure, exit-code mirroring, dominance order
- [Source: architecture.md#Decision Impact Analysis line 593] — Doctor subcommand sequencing decision (orchestration first, CLI second)
- [Source: architecture.md#Anti-Patterns to Avoid lines 1039–1049] — banned patterns
- [Source: architecture.md#Test Architecture lines 548–581] — three test layers; doctor is unit-only in 3.1
- [Source: architecture.md line 671] — `doctor/_checks.py # the chain runner + CheckResult helpers`
- [Source: architecture.md#Doctor subcommand flow lines 1270–1286] — runtime flow diagram
- [Source: architecture.md#Module-Component Mapping line 1189] — `Doctor ↔ Provider` consumes only the four `check_*` methods
- [Source: architecture.md#Cross-cutting NFR coverage line 1411] — single-owner per cross-cutting concern
- [Source: epics.md#Story 3.1 lines 606–639] — original epic scoping; ACs reflected here with implementation detail
- [Source: prd.md FR29] — `semvertag doctor` validates token, scopes, project access, default-branch detection, protected-tag rules
- [Source: prd.md FR30] — Named, actionable cause on failure
- [Source: prd.md NFR4] — ≤10s for `semvertag doctor` against a single project
- [Source: prd.md NFR10] — Tokens never appear in stdout, stderr, log files, or doctor output (redaction enforced at `_redact.py`; Story 3.1 produces no token output)
- [Source: prd.md FR37 / NFR25] — Stable exit codes (0/1/2/3/4) — dominance order documented under NFR25 stability surface
- [Source: 1-5-gitlabprovider-four-endpoints-via-httpx2.md (Status: done)] — `GitLabProvider.check_*` implementations and exact cause string vocabulary
- [Source: 1-7-wire-di-groups-and-typer-entrypoint.md (Status: done)] — `__main__.py` exception→exit-code translation pattern (Story 3.2 follows the same shape)
- [Source: 2-1-conventional-commits-strategy-and-per-repo-switching.md (Status: done)] — `current_strategy` Factory pattern (informs Story 3.2's potential `doctor_runner` Factory)
- [Source: epic-1-retro-2026-05-28.md (Status: done)] — Recurring themes 1 (architecture under-specifies library semantics), 2 (protocol-coverage test pattern), 3 (lint/typing tool friction)
- [Source: semvertag/_types.py:43-46] — `CheckResult(name: str, status: Literal["passed","failed","skipped"], cause: str)`
- [Source: semvertag/_errors.py:4-17] — `SemvertagError(1)`, `ConfigError(2)`, `AuthError(3)`, `ProviderAPIError(4)`
- [Source: semvertag/providers/_base.py:6-17] — `Provider` Protocol shape (the four `check_*` methods Story 3.1 consumes)
- [Source: semvertag/providers/gitlab.py:164-278] — `check_*` implementations; the cause-string vocabulary the resolver fragments shadow
- [Source: tests/unit/test_use_case.py:55-69] — stub-Provider precedent (Story 3.1 mirrors but flips `# pragma: no cover` to active coverage)
- [Source: Justfile:25-29] — strict-coverage recipe pattern (`test-branch-strategies` / `test-cc-strategies`)
- [Source: pyproject.toml:83] — `addopts = "--cov=. --cov-report term-missing"` (85% global gate)

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context) — bmad-dev-story workflow

### Debug Log References

- **`typing.Final` on loop-local variables tripped Pyright.** `result: typing.Final = getattr(provider, method_name)()` inside `run_checks` was flagged: `"Final" variable cannot be assigned within a loop`. Dropped the annotation — the variable is single-use within the loop body. Runtime semantics unchanged.
- **`resolve_exit_code` defensive fallback was unreachable and tripped the 100%-branch gate.** Initial implementation ended with `return SemvertagError.exit_code` after the dominance loop. Since `_DOMINANCE` enumerates all four exit codes (`1, 2, 3, 4`) and `_exit_code_for_failed_check` returns from the same set, the loop always finds a match. Refactored to `return next(code for code in _DOMINANCE if code in failed_codes)` — concise, no dead branch, generator's `StopIteration` would surface a genuine bug if the invariant broke. Branch coverage now natural at 100%.
- **`ARG002 Unused method argument`** on `_StubProvider.create_tag(name, commit_sha)`. The Protocol shape requires the signature; the stub raises if called. Resolved with `# noqa: ARG002` on the `def` line — same workaround as the pragma-noqa pattern Stories 1.5/1.7 used for `PLC0415` lazy imports.
- **Initial test had a redundant `test_exit_code_constants_match_error_hierarchy` asserting `SemvertagError.exit_code == 1` etc.** Tripped `PLR2004` (magic-value-in-comparison) and overlapped with `tests/unit/test_errors.py` coverage. Deleted; the cause-fragment translation tests already prove the mapping via `AuthError.exit_code` references (no magic numbers).

### Completion Notes List

- All 12 ACs (AC1–AC12) verified by **33 new unit tests** (5 chain-ordering + 3 zero-exit + 5 auth-fragment + 2 config-fragment + 2 provider-api-fragment + 1 generic + 15 dominance-table). Full suite: **389 tests passed** (Epic 1+2 baseline 356, +33 net add), 0 regressions.
- Coverage: `semvertag/doctor/_checks.py` **100% line + 100% branch** (new gate via `just test-doctor`); `semvertag/doctor/__init__.py` **100%** (trivial); strategy gates (1.6, 2.1) preserved at 100% branch; global **94%** line (above 85% NFR22 gate).
- `just lint-ci` clean (`eof-fixer`, `ruff format`, `ruff check`, `ty check`).
- `uv build` produces wheel + sdist.
- **No DI wiring, no `__main__.py` changes, no `providers/gitlab.py` changes** — Epic 3 framing held. Story 3.2 will register `semvertag doctor` as a Typer subcommand and consume `run_checks` / `resolve_exit_code`.
- **Cause-fragment ownership in `_checks.py`** matches the spec design: when `gitlab.py` rewords a cause, `_checks.py` fragments must update in lockstep. Documented in Dev Notes §Cause→exit-code translation as a known drift risk; Story 3.2's integration tests will close it via real-CLI assertions.
- `_StubProvider` in the test file uses `@dataclasses.dataclass` (NOT `unittest.mock`) per Dev Notes §Testing standards. The four non-`check_*` Protocol methods raise `AssertionError` if called — confirms the chain runner never touches them.
- Empty-input `resolve_exit_code([])` returns `0`, satisfying the total-function guarantee (AC7). The skipped-without-failed edge case is also covered.

### File List

- **New:** `semvertag/doctor/__init__.py` (2 stmts — `__all__: typing.Final = ()`).
- **New:** `semvertag/doctor/_checks.py` (36 stmts, 14 branches — `_CHAIN_METHODS`, `_SKIPPED_CAUSE_TEMPLATE`, three `_*_CAUSE_FRAGMENTS` tuples, `_DOMINANCE`, `run_checks`, `_exit_code_for_failed_check`, `resolve_exit_code`).
- **New:** `tests/unit/test_doctor_checks.py` (33 cases covering AC1–AC10).
- **Modified:** `Justfile` (added `test-doctor` recipe — AC11).
- **Modified:** `_bmad/sprint-status.yaml` (`3-1-…: ready-for-dev → in-progress → review`).
- **Modified:** `_bmad/3-1-doctor-chain-runner-and-exit-code-dominance.md` (Status, all task/subtask checkboxes, Dev Agent Record).
- **No-change confirmed:** `semvertag/__main__.py`, `semvertag/_use_case.py`, `semvertag/_settings.py`, `semvertag/_types.py`, `semvertag/_errors.py`, `semvertag/_output.py`, `semvertag/_transport.py`, `semvertag/_redact.py`, `semvertag/_commit_parse.py`, `semvertag/ioc.py`, `semvertag/providers/_base.py`, `semvertag/providers/gitlab.py`, `semvertag/strategies/*.py`, all existing tests, `pyproject.toml`.

### Change Log

- 2026-05-29 — Created `semvertag/doctor/` package: `__init__.py` (empty `__all__`) + `_checks.py` with `run_checks`, `resolve_exit_code`, and three module-level cause-fragment tuples plus `_DOMINANCE` and `_CHAIN_METHODS`.
- 2026-05-29 — `run_checks(provider)` walks `token → scopes → project_access → protected_tags`; first failure short-circuits and emits `CheckResult(status="skipped", cause=f"Skipped: blocked by {first_failed_check} check.")` for every subsequent step. Subsequent `check_*` methods are NOT invoked (verified via `_StubProvider.call_log` assertions in AC2/AC3 tests).
- 2026-05-29 — `resolve_exit_code(results)` returns `0` when no `failed` results are present; otherwise picks the dominant exit code via `next(code for code in _DOMINANCE if code in failed_codes)` where `_DOMINANCE = (AuthError.exit_code, ProviderAPIError.exit_code, ConfigError.exit_code, SemvertagError.exit_code)` — encodes `3 > 4 > 2 > 1`.
- 2026-05-29 — Cause-fragment translation in `_exit_code_for_failed_check` matches against three module-level tuples (`_AUTH_CAUSE_FRAGMENTS`, `_CONFIG_CAUSE_FRAGMENTS`, `_PROVIDER_API_CAUSE_FRAGMENTS`) shadowing `providers/gitlab.py`'s cause-string vocabulary. Unmapped causes fall through to `SemvertagError.exit_code` (1).
- 2026-05-29 — Authored 33 unit tests in `tests/unit/test_doctor_checks.py`: 5 chain-ordering tests (every fail-at-step-N case plus all-passed), 3 zero-exit cases (all-passed, empty, passed+skipped), 9 cause-fragment translation tests (one per fragment + 1 unmapped), 15 dominance-table cases (every cell in the AC6 table). Stub `Provider` is a `@dataclasses.dataclass` with `call_log` for invocation-count assertions.
- 2026-05-29 — Added `test-doctor` recipe to `Justfile` per AC11 (mirrors `test-cc-strategies` shape; isolates strict 100%-branch gate from global `just test` invocation per Story 1.6/2.1 precedent).
- 2026-05-29 — All gates green: `just lint-ci` clean; `just test` 389 passed; `just test-branch-strategies` / `just test-cc-strategies` / `just test-doctor` each at 100% branch; `uv run ty check` clean; `uv build` clean. Status flipped `in-progress → review`.
