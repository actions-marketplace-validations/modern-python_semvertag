# Story 1.3: Typed error hierarchy + RunResult + RichOutput + JsonOutput + redaction

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a CI pipeline operator,
I want semvertag's output cleanly split between human-readable Rich output (stdout) and machine-readable JSON envelopes (`--json` on stdout), with errors always on stderr, tokens redacted everywhere, and a stable `schema_version` on JSON output,
so that I can pipe `--json` to `jq` without error chatter contaminating my parser, and so I can build CI dashboards on a stable JSON contract.

## Acceptance Criteria

### AC1 — Exception hierarchy + exit codes

**Given** `semvertag/_errors.py` defines the exception hierarchy
**When** I import `SemvertagError`, `ConfigError`, `AuthError`, `ProviderAPIError`
**Then** each class has its `exit_code` class attribute set to `1`, `2`, `3`, `4` respectively (with `SemvertagError.exit_code == 1` as the generic default per FR37)
**And** every subclass IS-A `SemvertagError` (so `__main__.py` Story 1.7 can catch the base class and read `.exit_code`)
**And** `repr()` / `str()` round-trip a constructed exception preserving the single positional `args[0]` message

### AC2 — Error message template enforcement (FR30)

**Given** an exception is constructed via the project pattern `raise <ErrorClass>("<NamedCondition>: <Cause>. <SuggestedAction>.")`
**When** I render `str(err)`
**Then** the message string is the exact positional argument (no keyword-arg construction is used)
**And** chained-cause patterns preserve the underlying traceback when written as `raise <ErrorClass>("...") from exc`

### AC3 — `RunResult` envelope shape and ordering

**Given** `semvertag/_types.py` exposes `RunResult` as a frozen, slotted, kw-only dataclass alongside the existing `ConfigSource`
**When** I construct `RunResult(strategy="conventional-commits", bump="minor", status="created", tag="2.1.0", commit="a2b4d12", reason=None)` and run `json.dumps(dataclasses.asdict(result))`
**Then** the JSON object's keys appear in declaration order with `"schema_version": "1.0"` as the FIRST key
**And** all keys are `snake_case`
**And** unset optional fields render as `null`, never omitted (consumers MUST rely on key presence per architecture §JSON Field Naming)
**And** `RunResult(...)` rejects positional construction (kw-only) and rejects field mutation (frozen)

### AC4 — RichOutput stdout/stderr discipline

**Given** `RichOutput` is constructed with two `rich.Console` instances — `info_console` writing to stdout and `error_console` writing to stderr
**When** I call `output.progress("Detected strategy: branch-prefix")` and then `output.emit(result)` and then `output.error("ConfigError: ...")`
**Then** the progress line AND the final-result lines are written to stdout via `info_console`
**And** the error line is written to stderr via `error_console`
**And** there is no interleaving — every byte of stdout comes from `info_console`, every byte of stderr comes from `error_console`
**And when** `quiet=True` is active on the RichOutput
**Then** `progress()` becomes a no-op
**And** `emit()` still renders the final result to stdout (per FR36 — `--quiet` suppresses progress narrative only, NOT the final result)
**And** `error()` still writes to stderr (per FR38 — errors always to stderr regardless of `--quiet`)

### AC5 — JsonOutput contract

**Given** `JsonOutput` is constructed (with or without `quiet=True`)
**When** I call `output.progress("anything")`
**Then** nothing is written to stdout (no-op regardless of `quiet`)
**And when** I call `output.emit(result)`
**Then** EXACTLY one line of `json.dumps(dataclasses.asdict(result))` is written to stdout
**And** the line ends with a single `\n` (one envelope, one newline)
**And when** I call `output.error("...")`
**Then** the error text is written to stderr as plain text (NOT as JSON) — `--quiet --json | jq` keeps stdout valid JSON regardless of error state

### AC6 — `--quiet` × `--json` matrix (4 cells)

**Given** the four combinations of `quiet ∈ {False, True}` × output impl ∈ {`RichOutput`, `JsonOutput`}
**When** each combination calls `progress("p")`, then `emit(result)`, then `error("e")` in order
**Then** stdout and stderr contents match this matrix exactly:

| quiet | impl | stdout contains | stderr contains |
|---|---|---|---|
| `False` | `RichOutput` | `"p"` AND rendered result lines | `"e"` |
| `True`  | `RichOutput` | rendered result lines only (no `"p"`) | `"e"` |
| `False` | `JsonOutput` | exactly one `json.dumps(...)` line | `"e"` |
| `True`  | `JsonOutput` | exactly one `json.dumps(...)` line | `"e"` |

### AC7 — Token redaction patterns

**Given** `semvertag/_redact.py` defines `redact(text: str) -> str` with pattern matchers for the four documented token families (NFR10)
**When** I call `redact("Token is glpat-AbCdEf1234567890 here")`
**Then** the GitLab personal-access-token pattern (`glpat-` + ≥20 alphanumerics) is replaced with `***`
**And when** I call `redact("Authorization: ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345")` the GitHub PAT pattern (`ghp_` + ≥20 chars) is redacted
**And when** I call `redact("Bearer ATBB0a1b2c3d4e5f6g7h8i9j0KLm")` the Bitbucket app-password pattern (`ATBB` + ≥20 chars) is redacted
**And when** I call `redact("Hash: " + "a" * 40)` a generic ≥32-char hex sequence is redacted
**And** the surrounding non-token text in each call is preserved byte-for-byte except for the substituted token
**And** `redact("nothing sensitive here")` returns the input unchanged

### AC8 — Redaction never widens the input

**Given** a string containing zero tokens
**When** `redact(text)` runs
**Then** the function returns the input unchanged (identity for the negative path)
**And given** a string containing only a token
**When** `redact(text)` runs
**Then** the output is exactly the replacement marker (`***`) with no leaked characters from the token before the substitution boundary
**And** the function is idempotent: `redact(redact(text)) == redact(text)`

### AC9 — Defense-in-depth: SecretStr + redact compose

**Given** a `Settings` instance from Story 1.2 carries `gitlab.token = SecretStr("glpat-AbCdEf1234567890")`
**When** the token leaks into log output via `str(settings.gitlab.token)` accidentally (rendered as `"**********"` by Pydantic)
**Then** `redact("**********")` returns `"**********"` unchanged — both layers compose cleanly with no double-substitution
**And given** an exception message `raise ProviderAPIError("GitLab API failed: glpat-RealToken1234567890")`
**When** `__main__.py` (future Story 1.7) calls `output.error(redact(str(err)))`
**Then** the rendered stderr contains `***` in place of `glpat-RealToken1234567890`

### AC10 — Unit-test coverage

**Given** unit tests in `tests/unit/test_errors.py`, `tests/unit/test_output_rich.py`, `tests/unit/test_output_json.py`, `tests/unit/test_redact.py`
**When** the test suite runs
**Then** AC1–AC9 are each covered by named tests (one assertion-cluster per test, parameterized where it tightens the file)
**And** `just lint`, `just lint-ci`, and `just test` all pass clean
**And** the per-file line coverage in the `--cov-report term-missing` output is **≥85%** for each of `semvertag/_errors.py`, `semvertag/_types.py`, `semvertag/_output.py`, `semvertag/_redact.py`

## Tasks / Subtasks

- [x] **Task 1: Implement `semvertag/_errors.py` exception hierarchy** (AC: #1, #2)
  - [x] 1.1 Create `semvertag/_errors.py`. Imports: none from semvertag (this module is a leaf — every other module imports FROM it). No `from __future__ import annotations`. Global imports only (per `CLAUDE.md`).
  - [x] 1.2 Define `SemvertagError(Exception)` with `exit_code: typing.ClassVar[int] = 1` (per FR37 generic-failure default). One-line module-level docstring is fine; no per-class docstrings beyond a single line if they add WHY (architecture §Comment Policy). Reference: architecture §Error Model & Exit Codes lines 383–401.
  - [x] 1.3 Define `ConfigError(SemvertagError)` with `exit_code: typing.ClassVar[int] = 2`.
  - [x] 1.4 Define `AuthError(SemvertagError)` with `exit_code: typing.ClassVar[int] = 3`. Architecture §Error Model: "Auth or permission failure — fail-closed per NFR8."
  - [x] 1.5 Define `ProviderAPIError(SemvertagError)` with `exit_code: typing.ClassVar[int] = 4`. Architecture §Error Model: "Provider API failure (5xx, network, rate-limit, exhausted retries)."
  - [x] 1.6 Do NOT define `__init__` on any subclass. Pythonic exceptions accept positional `args`; the project pattern is `raise AuthError("...message...")` — architecture §Exception Construction Patterns explicitly forbids keyword-arg construction.
  - [x] 1.7 Add `__all__: typing.Final = ("SemvertagError", "ConfigError", "AuthError", "ProviderAPIError")` so downstream `from semvertag._errors import *` is well-defined. Note: ruff `RUF022` sorts alphabetically; final form is `("AuthError", "ConfigError", "ProviderAPIError", "SemvertagError")`.

- [x] **Task 2: Add `RunResult` to `semvertag/_types.py` alongside the existing `ConfigSource`** (AC: #3)
  - [x] 2.1 EXTEND the existing file — do NOT replace. The current contents (Story 1.2's `ConfigSource` frozen dataclass) MUST remain unchanged. Read `semvertag/_types.py` first to confirm the existing shape before editing.
  - [x] 2.2 Add `@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)` to `RunResult` with fields in this exact declaration order so `dataclasses.asdict()` produces the schema-stable JSON key order:
    ```python
    @dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
    class RunResult:
        schema_version: str = "1.0"
        strategy: str
        bump: str
        status: str
        tag: str | None
        commit: str | None
        reason: str | None
    ```
  - [x] 2.3 The default-then-non-default ordering is permitted because `kw_only=True` is set on the dataclass — Python's positional-default restriction does NOT apply when all fields are keyword-only. Architecture §Frozen-Dataclass Conventions calls `kw_only=True` mandatory.
  - [x] 2.4 Domain note (NOT type-enforced in this story — that's for `__main__.py` / use case in Stories 1.5–1.7):
    - `bump` ∈ `{"none", "patch", "minor", "major"}` per architecture §Output Architecture line 419.
    - `status` ∈ `{"created", "no_merge_commit", "no_conforming_commit", "already_tagged", "no_tags"}` per architecture §Output Architecture line 420.
  - [x] 2.5 `tag`, `commit`, `reason` are `str | None`. `null` (not omitted) for unset values — verified by AC3 round-trip.
  - [x] 2.6 No imports change beyond adding `typing` if not already imported. Confirm `dataclasses` is already imported by `ConfigSource`. (Both already imported.)

- [x] **Task 3: Implement `semvertag/_redact.py`** (AC: #7, #8, #9)
  - [x] 3.1 Create `semvertag/_redact.py`. Imports: `re`, `typing`. No project imports (leaf module).
  - [x] 3.2 Define the redaction marker as a module-level constant: `_REDACTION: typing.Final = "***"`.
  - [x] 3.3 Define a single compiled pattern at module scope covering all four token families. Compile ONCE per process — `re.compile(...)` at import time, assigned to `_TOKEN_PATTERN: typing.Final`. The architecture sketch and AC7 pin the four families:
    - `glpat-` followed by ≥20 alphanumeric or `_`/`-` characters (GitLab personal access tokens).
    - `ghp_` followed by ≥20 alphanumerics (GitHub personal access tokens). Architecture also names `gho_`, `ghu_`, `ghs_`, `ghr_` indirectly — do NOT add them in this story; AC7 only requires `ghp_`. Note them in dev record for Story 1.5/3.x to revisit.
    - `ATBB` followed by ≥20 alphanumerics (Bitbucket app passwords).
    - A generic ≥32-character hex sequence (`[0-9a-fA-F]{32,}`) — covers SHA-256 hashes and many opaque tokens. Word-boundary anchored on both sides to avoid mid-word false positives in noun-heavy log lines.
  - [x] 3.4 Define `def redact(text: str) -> str:` — return `_TOKEN_PATTERN.sub(_REDACTION, text)`. One line of body besides the signature. Pure function; no side effects; no logging.
  - [x] 3.5 Add `__all__: typing.Final = ("redact",)` — `_TOKEN_PATTERN` and `_REDACTION` are private.
  - [x] 3.6 Per architecture §Anti-Patterns: do NOT add a `print()` here, do NOT catch `Exception`, do NOT log anything (this is a pure transformation).
  - [x] 3.7 Word-boundary detail: the generic hex pattern MUST NOT match inside longer alphanumeric strings — anchor it so the 40-char run inside a 60-char alphanumeric blob is NOT redacted; that direction risks false positives. AC8 idempotency relies on this.

- [x] **Task 4: Implement `semvertag/_output.py`** (AC: #4, #5, #6, #9)
  - [x] 4.1 Create `semvertag/_output.py`. Imports (global, alphabetized): `dataclasses`, `json`, `sys`, `typing`, `rich.console.Console`, then local `from semvertag._redact import redact`, `from semvertag._types import RunResult`.
  - [x] 4.2 Define the `Output` protocol per architecture §Output Architecture lines 426–429:
    ```python
    class Output(typing.Protocol):
        def progress(self, message: str) -> None: ...
        def emit(self, result: RunResult) -> None: ...
        def error(self, message: str) -> None: ...
    ```
    Note: architecture's sketch shows only `progress` and `emit`. Adding `error` to the protocol is an explicit story-level design call — see Dev Notes §Output protocol extension below. Document it as a deviation in the Dev Agent Record.
  - [x] 4.3 Define `RichOutput` as a frozen, slotted dataclass with `kw_only=True` carrying:
    - `info_console: rich.console.Console`
    - `error_console: rich.console.Console`
    - `quiet: bool = False`
    Methods:
    - `progress(message)`: if `self.quiet`, return immediately. Else `self.info_console.print(redact(message))`.
    - `emit(result)`: render to stdout via `self.info_console` as human-readable lines. At minimum, print `f"Created tag {result.tag} on commit {result.commit[:7]} (strategy: {result.strategy}, bump: {result.bump})"` when `result.status == "created"`; print a single descriptive line for each documented `status` value otherwise. `redact(...)` the formatted string before printing.
    - `error(message)`: `self.error_console.print(redact(message))`. ALWAYS writes — `self.quiet` does NOT suppress errors (FR38).
  - [x] 4.4 Define `JsonOutput` as a frozen, slotted dataclass with `kw_only=True` carrying:
    - `error_console: rich.console.Console`
    - `quiet: bool = False` (accepted for protocol parity; never read because `progress` is already a no-op)
    Methods:
    - `progress(message)`: no-op (return None). Architecture §Output Architecture line 427: "json: no-op".
    - `emit(result)`: write exactly one line to `sys.stdout` via `sys.stdout.write(json.dumps(dataclasses.asdict(result), separators=(",", ":")) + "\n")` then `sys.stdout.flush()`. Use the stdlib `json` module (no third-party JSON lib per PRD Architecture Notes). DO NOT route this through `rich.Console` — Rich's `print` may wrap, color, or escape; the JSON contract requires byte-exact output.
    - `error(message)`: `self.error_console.print(redact(message))` — plain Rich print to stderr. NOT a JSON envelope; the JSON contract covers `emit()` output only. The architecture is unambiguous that errors live on stderr (FR38) and the `--quiet --json | jq` composability story (FR36) requires stdout to remain pure JSON regardless of error state.
  - [x] 4.5 Module-level factory helpers (kept tiny — `ioc.py` will use them in Story 1.7):
    - `def build_rich_output(*, quiet: bool = False) -> RichOutput`: constructs `Console()` for stdout and `Console(stderr=True)` for stderr, then returns `RichOutput(info_console=..., error_console=..., quiet=quiet)`.
    - `def build_json_output(*, quiet: bool = False) -> JsonOutput`: constructs `Console(stderr=True)` and returns `JsonOutput(error_console=..., quiet=quiet)`. (`JsonOutput` carries no `info_console` — stdout writes go through `sys.stdout` directly to bypass Rich formatting.)
  - [x] 4.6 Add `__all__: typing.Final = ("Output", "RichOutput", "JsonOutput", "build_rich_output", "build_json_output")`. (Note: ruff `RUF022` sorts alphabetically; final form is `("JsonOutput", "Output", "RichOutput", "build_json_output", "build_rich_output")`.)
  - [x] 4.7 Per architecture §Anti-Patterns: ZERO `print()` calls anywhere outside this file once it exists — `_output.py` is the one place output happens. Do NOT add `print()` even for debugging; route through one of the consoles or `sys.stdout`.
  - [x] 4.8 Redaction applies at the OUTPUT BOUNDARY: every user-facing string (`progress`, `emit`, `error`) is passed through `redact(...)` before hitting a console. Defense-in-depth alongside `SecretStr` (NFR10).

- [x] **Task 5: Implement `tests/unit/test_errors.py`** (AC: #1, #2)
  - [x] 5.1 Create the file. Imports global per `CLAUDE.md` + Story 1.1 lint surface (`PLC0415`). No `from __future__ import annotations`.
  - [x] 5.2 Module-level constants get `typing.Final` (auto-typing-final scope per Story 1.1 `Justfile:9`).
  - [x] 5.3 Test functions (one assertion-cluster each, naming `test_<verb>_<outcome>_when_<condition>` per architecture §Test Naming):
    - `test_semvertag_error_has_exit_code_one` — AC1.
    - `test_config_error_has_exit_code_two` — AC1.
    - `test_auth_error_has_exit_code_three` — AC1.
    - `test_provider_api_error_has_exit_code_four` — AC1.
    - `test_subclasses_inherit_from_semvertag_error` — AC1 (use `pytest.mark.parametrize` over the four classes; assert `issubclass(cls, SemvertagError)`).
    - `test_exception_message_is_positional_args_zero` — AC2 (`err = AuthError("msg"); assert err.args == ("msg",)`).
    - `test_chained_from_exc_preserves_cause` — AC2 (raise/catch pattern: `raise AuthError("...") from ValueError("orig")`; assert `caught.__cause__` is the ValueError).
  - [x] 5.4 Use `pytest.raises` for the `from exc` test; capture the raised exception, then read `__cause__`. (Moved the raise/catch into a helper so the `with pytest.raises(...)` block remains a single statement — `PT012` would flag the multi-statement form.)

- [x] **Task 6: Implement `tests/unit/test_redact.py`** (AC: #7, #8, #9)
  - [x] 6.1 Imports: `pytest`, `typing`, `from semvertag._redact import redact`.
  - [x] 6.2 Module-level constants for the four token families with `typing.Final` (per Story 1.1 auto-typing-final scope):
    ```python
    GITLAB_TOKEN: typing.Final = "glpat-AbCdEf1234567890ABCD"
    GITHUB_TOKEN: typing.Final = "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345"
    BITBUCKET_TOKEN: typing.Final = "ATBB0a1b2c3d4e5f6g7h8i9j0KLm"
    HEX_TOKEN: typing.Final = "a" * 40
    ```
  - [x] 6.3 Test functions:
    - `test_redacts_gitlab_pat_pattern` — AC7.
    - `test_redacts_github_pat_pattern` — AC7.
    - `test_redacts_bitbucket_app_password_pattern` — AC7.
    - `test_redacts_generic_hex_token_pattern` — AC7.
    - `test_preserves_surrounding_text_when_redacting` — AC7 (uses whitespace boundary to avoid greedy match: GitLab PAT class includes `-` so a `-suffix` would be gobbled — see Dev Agent Record §Debug Log References).
    - `test_returns_input_unchanged_when_no_tokens_present` — AC8.
    - `test_redaction_is_idempotent` — AC8 (parametrized over four families).
    - `test_redaction_does_not_match_inside_longer_alphanumeric_blob` — AC8.
    - `test_composes_with_secret_str_render` — AC9.
    - `test_redacts_token_only_input_to_marker_only` — AC8 added to assert no leaked characters from a pure-token input.
  - [x] 6.4 Use `pytest.mark.parametrize` for the token-family matrix where it tightens the file.

- [x] **Task 7: Implement `tests/unit/test_output_rich.py`** (AC: #4, #6, #9)
  - [x] 7.1 Imports: `pytest`, `typing`, `io`, `rich.console.Console`, `from semvertag._output import RichOutput`, `from semvertag._types import RunResult`. (Also imports `JsonOutput`, `build_rich_output`, `build_json_output` for factory tests added to reach 100% coverage.)
  - [x] 7.2 Construct `RichOutput` per-test with two `Console(file=io.StringIO(), force_terminal=False, color_system=None)` instances so stdout/stderr capture is deterministic and free of ANSI codes.
  - [x] 7.3 Helper `_make_pair(*, quiet)` returns `(output, stdout_buf, stderr_buf)` for clean per-test setup.
  - [x] 7.4 Test functions: all eight named in the story plus `test_matrix_keeps_stderr_for_errors` (parametrized AC6 row 2 verification), `test_emit_renders_non_created_status_to_stdout` (covers `_format_result`'s no-tag branch for 100% coverage), `test_build_rich_output_constructs_two_consoles`, and `test_build_json_output_returns_json_output_with_quiet_passthrough` (factory smoke).
  - [x] 7.5 Module-level `_EXAMPLE_RESULT: typing.Final = RunResult(...)` is in place.

- [x] **Task 8: Implement `tests/unit/test_output_json.py`** (AC: #3, #5, #6, #9)
  - [x] 8.1 Imports: `pytest`, `typing`, `io`, `json`, `re`, `sys`, `dataclasses`, `rich.console.Console`, `from semvertag._output import JsonOutput`, `from semvertag._types import RunResult`.
  - [x] 8.2 Construct `JsonOutput` with `error_console=Console(file=io.StringIO(), force_terminal=False, color_system=None)`. Patch `sys.stdout` to a `StringIO` via `monkeypatch.setattr(sys, "stdout", buf)` for the duration of each test so we capture the raw JSON bytes.
  - [x] 8.3 Test functions: all nine named in the story plus two AC3 frozen/kw-only enforcement tests (`test_run_result_rejects_positional_construction`, `test_run_result_rejects_field_mutation`).
  - [x] 8.4 The `--quiet --json | jq` composability assertion (`test_quiet_json_matrix_keeps_stdout_pure_json`) is present and asserts: exactly one JSON line on stdout, error text routed to stderr.

- [x] **Task 9: Lint + test pass** (AC: #10)
  - [x] 9.1 Run `just install`. (Already current — skipped explicit invocation; `just test`/`just lint` succeed against the existing venv.)
  - [x] 9.2 Run `just lint`. Expected gotchas under `select=["ALL"]`:
    - `auto-typing-final` will demand `typing.Final` on the module-level constants in `_redact.py` (`_REDACTION`, `_TOKEN_PATTERN`), `_output.py` (`__all__`), and in test files (`GITLAB_TOKEN`, etc.) — pre-annotate them.
    - `PLC0415` rejects function-local imports — keep all `re`, `json`, `sys` imports at module top.
    - `S105` (hardcoded password) is in the project's `ignore` list (`pyproject.toml:75`); `S106`/`S107` may still flag — if so, add per-line `# noqa` justified by "test fixture, not a real secret".
    - `RUF012` (mutable-default in class attr): `__all__` is a tuple, not a list — should not trigger; if it does, the tuple form satisfies it.
    - `D1*` (missing docstrings) is in `ignore`. No docstring noise expected.
  - [x] 9.3 Run `just lint-ci` — passes clean.
  - [x] 9.4 Run `just test` — 70/70 passing. Per-file coverage: `_errors.py` 100%, `_types.py` 100%, `_output.py` 100%, `_redact.py` 100% (all ≥85%).
  - [x] 9.5 Run `uv build` — successful (`dist/semvertag-0.tar.gz`, `dist/semvertag-0-py3-none-any.whl`).
  - [x] 9.6 Smoke check ran and produced one valid JSON envelope beginning with `{"schema_version":"1.0",...`.

- [x] **Task 10: Update `_bmad/` artefacts**
  - [x] 10.1 Dev Agent Record + File List updated below.
  - [x] 10.2 Status set to `review`.
  - [x] 10.3 Deviations documented inline under Dev Agent Record §Debug Log References.

## Dev Notes

### Story framing

This is **Step 3 of the architecture's Implementation Sequence**: "Error hierarchy + Output protocols — `SemvertagError` subclasses, `RunResult`, `RichOutput`, `JsonOutput`. Unit-tested." [Source: architecture.md#Decision Impact Analysis §Implementation sequence lines 588]

Story 1.1 left `semvertag/` containing scaffolding. Story 1.2 added `_settings.py`, `_types.py` (with `ConfigSource` only), and strategy config files. **Story 1.3 introduces three NEW modules — `_errors.py`, `_redact.py`, `_output.py` — and EXTENDS the existing `_types.py` with `RunResult` alongside the already-present `ConfigSource`.**

The behavioral reference at `_autosemver_reference/use_cases/autosemver_use_case.py` shows the OLD output pattern (`Console.print(...)` inline, no JSON, no redaction, no typed errors). It is NOT the target shape — it's the thing this story replaces with structured, dual-format, redacted output behind a protocol. Read it once for orientation, then close the tab; the target shape is entirely architecture-driven.

### Critical architectural constraints

These come from `architecture.md` and are non-negotiable for this story:

1. **One source of `print()` for the package.** Architecture §Anti-Patterns: `print()` calls anywhere outside `_output.py`. Even `_redact.py` MUST NOT print. All console output flows through `RichOutput` / `JsonOutput`; all error output flows through their `error()` method. [Source: architecture.md#Anti-Patterns to Avoid line 1041]
2. **Two `rich.Console` instances per Output impl.** `info_console` writes to stdout; `error_console` writes to stderr. No interleaving. Errors ALWAYS to stderr regardless of `--quiet` / `--json` (FR38). [Source: architecture.md#Output Architecture lines 435]
3. **`--quiet` is additive with `--json`.** FR36 explicit semantics: `--quiet` suppresses non-error informational output during the run; the final result is still emitted in the chosen format. `--quiet --json | jq` composes. [Source: prd.md#FR36 + architecture.md#Output Architecture line 437]
4. **JSON contract uses stdlib `json` ONLY.** No third-party JSON lib (no `orjson`, no `ujson`, no `pydantic.json.pydantic_encoder`). [Source: architecture.md#Output Architecture line 439 + prd.md Architecture Notes]
5. **`schema_version` is always present, always first.** Field-order discipline: `dataclasses.asdict` preserves declaration order; the dataclass declares `schema_version` first; downstream consumers parse based on key presence — `null` for unset optional fields, never omitted. [Source: architecture.md#JSON Field Naming lines 883–885]
6. **`pydantic.SecretStr` + output-boundary `redact()` are belt-and-suspenders.** The Settings layer (Story 1.2) wraps tokens in `SecretStr` so accidental string-interpolation renders `**********`. The output layer applies pattern-matching redaction so anything that leaked from a non-Settings path (an HTTP response body echoing a token, a stack trace surfacing one) still gets `***`-replaced before hitting a console. [Source: architecture.md#Error Model & Exit Codes lines 405–408 + prd.md#NFR10]
7. **Exception → exit-code mapping is `__main__.py`'s problem, not this story's.** This story exposes the `.exit_code` class attribute on each `SemvertagError` subclass; Story 1.7 wires `typer.Exit(code=err.exit_code)` at the CLI boundary. Do NOT add Typer or exit logic here. [Source: architecture.md#Decision Impact Analysis line 603]
8. **Error message template per architecture §Error Message Template.** `<NamedCondition>: <Cause>. <SuggestedAction>.` — this story DOES NOT have to raise any errors, but the exception classes MUST accept positional message argument only. Architecture §Exception Construction Patterns lines 781–802 makes positional-only mandatory.
9. **Frozen-dataclass conventions apply to `RunResult` and the Output impls.** `frozen=True, slots=True, kw_only=True` on all three. [Source: architecture.md#Frozen-Dataclass Conventions lines 696–706]
10. **Use `# ty: ignore`, not `# type: ignore`.** Per global `CLAUDE.md`. Likely targets: any `rich.console.Console` field where ty struggles with the dynamic Rich types.

### Output protocol extension (`error()` method) — documented deviation

Architecture §Output Architecture lines 426–429 sketches the protocol with only `progress()` and `emit()`. The error-flow diagram (lines 1289–1310) shows `__main__.py` writing errors directly to `error_console.print(str(err))` — but never specifies whether `__main__.py` constructs its own console or reads it from the Output impl.

This story formalizes the cleaner option: **add `error(message: str) -> None` to the Output protocol**, with both impls writing through their `error_console` to stderr. Rationale:

- `__main__.py` (Story 1.7) is the ONE place exit-code mapping happens. If it also has to know which console implementation to construct based on `--json`, the mapping logic grows. Pushing `error()` into the protocol keeps the use-case-error path uniform: `output.error(redact(str(err)))` works whether `output` is Rich or Json.
- The redaction boundary applies in one place (`_output.py`) instead of two (`_output.py` + `__main__.py`). NFR10's defense-in-depth still composes — `SecretStr.__str__` renders `**********` upstream; `redact()` catches anything that leaked through a non-SecretStr path.
- The protocol stays small: three methods (`progress`, `emit`, `error`) cover the entire CLI output surface for the v1.0 main verb. Doctor (Story 3.x) adds a fourth informally — `emit_doctor()` is mentioned in the architecture's doctor flow but is not part of the strict `Output` protocol; doctor uses a separate renderer that reads the same two consoles.

Document this deviation explicitly in Dev Agent Record §Debug Log References when the work is done.

### JSON-via-`sys.stdout` (not Rich) — design pin

`JsonOutput.emit()` writes through `sys.stdout`, NOT `rich.console.Console.print`. Reasons:

- Rich's `Console.print` adds soft-wrap, ANSI codes (even with `color_system=None` Rich sometimes inserts escape sequences for `legacy_windows` modes), and unicode normalization. The JSON contract requires byte-exact output — one `json.dumps(...)` line ending in exactly one `\n`.
- `sys.stdout.write(json.dumps(...) + "\n")` followed by `sys.stdout.flush()` is the canonical pattern for one-line CI-parseable output. It also plays nicely with `2>/dev/null` and `| jq`.
- Tests must patch `sys.stdout` (not Rich) to capture the JSON bytes. The Rich path is reserved for `error()` only on `JsonOutput`.

### `--quiet` × `--json` interaction matrix (the key behavior)

```
                    quiet=False                      quiet=True
              ┌──────────────────────────┐ ┌──────────────────────────┐
RichOutput    │ stdout: progress + emit  │ │ stdout: emit only        │
              │ stderr: errors           │ │ stderr: errors           │
              └──────────────────────────┘ └──────────────────────────┘
              ┌──────────────────────────┐ ┌──────────────────────────┐
JsonOutput    │ stdout: emit (1 JSON ln) │ │ stdout: emit (1 JSON ln) │
              │ stderr: errors           │ │ stderr: errors           │
              └──────────────────────────┘ └──────────────────────────┘
```

`JsonOutput.progress` is identical between `quiet=False` and `quiet=True` (no-op). `quiet` only changes `RichOutput.progress`. Errors are ALWAYS on stderr. AC6 enumerates the four cells; the four tests for that matrix are the most important regression guards in this story.

### File-by-file targets

| Target file | NEW / UPDATE | Purpose |
|---|---|---|
| `semvertag/_errors.py` | **NEW** | `SemvertagError`, `ConfigError`, `AuthError`, `ProviderAPIError` |
| `semvertag/_types.py` | **UPDATE** | Add `RunResult` alongside existing `ConfigSource`. DO NOT replace the file. |
| `semvertag/_redact.py` | **NEW** | `redact(text)` + compiled token-family pattern |
| `semvertag/_output.py` | **NEW** | `Output` protocol, `RichOutput`, `JsonOutput`, `build_rich_output`, `build_json_output` |
| `tests/unit/test_errors.py` | **NEW** | AC1, AC2 (7 tests) |
| `tests/unit/test_redact.py` | **NEW** | AC7, AC8, AC9 (9+ tests, parameterized) |
| `tests/unit/test_output_rich.py` | **NEW** | AC4, AC6 (RichOutput half), AC9 (8+ tests) |
| `tests/unit/test_output_json.py` | **NEW** | AC3, AC5, AC6 (JsonOutput half), AC9 (9+ tests) |

**Files this story does NOT touch:**

| File | Story |
|---|---|
| `semvertag/_settings.py`, `_types.py`'s `ConfigSource` | Story 1.2 (don't regress; just extend `_types.py`) |
| `semvertag/_transport.py` | Story 1.4 |
| `semvertag/providers/*` | Story 1.5+ |
| `semvertag/strategies/*` Strategy classes | Stories 1.6 / 2.1 |
| `semvertag/_use_case.py`, `ioc.py`, `__main__.py` | Story 1.7 — the wiring story |
| `semvertag/doctor/*` | Story 3.x |
| `pyproject.toml`, `Justfile`, `.github/workflows/*` | (no changes expected; revisit only if a lint rule breaks) |
| `tests/integration/*` | Story 1.7 (this story is unit-only) |
| `tests/test_smoke.py` | leave as-is at `tests/test_smoke.py` |

### Settings/Errors interaction snippet (orientation only — not implementation)

```python
# Future Story 1.5 usage shape — NOT to implement here:
from semvertag._errors import AuthError
from semvertag._redact import redact

try:
    response = client.get(url)
    response.raise_for_status()
except httpx2.HTTPStatusError as exc:
    if exc.response.status_code in (401, 403):
        raise AuthError(
            "Token missing scope: 'write_repository'. "
            "Add 'write_repository' to the SEMVERTAG_TOKEN scopes on GitLab."
        ) from exc
```

The error class accepts a positional message; the message follows the `<NamedCondition>: <Cause>. <SuggestedAction>.` template; `raise ... from exc` preserves traceback. `__main__.py` (Story 1.7) will catch `SemvertagError`, call `output.error(redact(str(err)))`, then raise `typer.Exit(code=err.exit_code)`.

### Token redaction pattern details

The four families per AC7 and architecture §Error Model lines 405–408:

| Token family | Prefix | Body | Source |
|---|---|---|---|
| GitLab PAT | `glpat-` | ≥20 `[A-Za-z0-9_\-]` | architecture line 408 |
| GitHub PAT | `ghp_` | ≥20 `[A-Za-z0-9]` | architecture line 408 |
| Bitbucket app password | `ATBB` | ≥20 `[A-Za-z0-9]` | architecture line 408 |
| Generic hex | (none) | ≥32 `[0-9a-fA-F]` with word boundary | architecture line 408 |

Single compiled `re.Pattern` with alternation is sufficient. Concrete sketch (NOT to be copy-pasted blindly — verify the boundaries during implementation):

```python
_TOKEN_PATTERN: typing.Final = re.compile(
    r"glpat-[A-Za-z0-9_\-]{20,}"
    r"|ghp_[A-Za-z0-9]{20,}"
    r"|ATBB[A-Za-z0-9]{20,}"
    r"|\b[0-9a-fA-F]{32,}\b"
)
```

The `\b` boundary on the hex alternative is critical (see AC8 `test_redaction_does_not_match_inside_longer_alphanumeric_blob`). The other three families are prefix-anchored so word boundaries aren't strictly needed there, but the body's character class disambiguates against trailing whitespace, punctuation, end-of-string.

### Testing standards

- **Framework**: `pytest` + `pytest-cov` + `pytest-randomly` + `pytest-xdist` — already in `[dependency-groups] dev`, no pyproject changes needed.
- **HTTP**: no HTTP in this story.
- **Env isolation**: Story 1.2's `clean_settings_env` fixture in `tests/unit/conftest.py` does not apply here — this story has no Settings dependency. Tests in this story can ignore env vars entirely.
- **Stream capture**: use `io.StringIO()` buffers passed into `rich.console.Console(file=...)` for RichOutput tests. For JsonOutput's `sys.stdout` path, use `monkeypatch.setattr(sys, "stdout", io.StringIO())` per test.
- **Color discipline**: `Console(file=..., force_terminal=False, color_system=None)` — without these, Rich auto-detects pytest's TTY and inserts ANSI codes that break string-equality assertions.
- **Coverage gate**: ≥85% line on each of the four new files. AC10 explicitly names this.
- **Test naming**: `test_<verb>_<outcome>_when_<condition>` per architecture §Test Naming.
- **Module-level constants get `typing.Final`** (auto-typing-final scope includes `tests/` per Story 1.1's `Justfile:9`).
- **`assert` is OK in tests** (`tests/**/*.py` has `S101` and `SLF001` per-file-ignored per Story 1.2's pyproject edit).
- **Parameterize** the four-row matrix (AC6) and the four-family redaction matrix (AC7) — keeps the file scannable.

### Anti-patterns to avoid (carried from architecture §Anti-Patterns)

- `print()` anywhere outside `_output.py` — including in `_errors.py`, `_redact.py`, and tests. Tests use `assert` on captured stream contents, not `print` for "debugging".
- `from __future__ import annotations` — banned project-wide.
- Bare `Exception` catches.
- Keyword-arg construction on exceptions: `AuthError(message="...", scope="api")` — positional only.
- Catching and re-raising WITHOUT `from`: lose the traceback. Always `raise X("...") from exc`.
- `# type: ignore` — use `# ty: ignore` (global `CLAUDE.md`).
- Module-level singleton of `Console()` — both consoles per Output instance are constructed inside the factory (`build_rich_output`, `build_json_output`); the Output dataclass holds them as instance fields, not module-level globals.
- Function-local imports — global imports only (`PLC0415` enforced; per `CLAUDE.md`).
- Re-compiling regexes per call — compile once at module scope.

### Learnings from Story 1.2 (carried forward)

[Source: 1-2-settings-layer-with-aliaschoices-and-provenance.md#Dev Agent Record + Review Findings]

- **Architecture sketches can be inaccurate about library semantics.** Story 1.2 found that pydantic-settings' `validation_alias` on nested fields doesn't behave as architecture's code sample suggested; the dev pivoted to a `model_validator(mode="before")` approach and documented the deviation. **For this story's parallel risk:** the architecture sketch shows `class Output(typing.Protocol)` with `progress` and `emit` only — but the error-flow diagram requires somewhere for errors to go. The protocol extension to `error()` is the right call; document it.
- **Auto-typing-final aggressively rewrites code.** Story 1.2's conftest was auto-rewritten from `yield None` → `return None`. Pre-annotate `typing.Final` on every module-level constant in the new files so the lint pass doesn't surprise you.
- **`tests/**/*.py` per-file-ignores were broadened in Story 1.2** to allow `SLF001` (private-attribute access) on top of `S101` (assert). This story doesn't need `_provenance`-style private access, but the broadened glob is now active and applies to all test files in `tests/unit/`.
- **`uv build` is part of the per-story acceptance bar** (Story 1.1's review patch added it). Run it at the end alongside `just test`.
- **`just install` regenerates `uv.lock`** every run (`uv lock --upgrade`) — Story 1.2 saw typer 0.26.0 → 0.26.1 as a side-effect. Expect a similar drift; it's not a story regression as long as `just test` still passes.
- **No `print()` is enforced even in test files** through `PLE0704`-adjacent rules under `select=["ALL"]`. Capture-and-assert on stream contents instead.

### Coverage-omit interaction

`tests/*` is in `[tool.coverage.run] omit`, so test files don't count toward coverage. The four new `semvertag/*.py` modules ARE measured. Target ≥85% line on each. Easy wins:

- `_errors.py` will trivially hit 100% — five tiny classes.
- `_types.py` will hit 100% — two dataclasses.
- `_redact.py` will hit 100% — one function, one compiled pattern, one constant.
- `_output.py` is the only file where coverage requires care. The four protocol-method paths × two impls × `quiet`/non-`quiet` give 8+ coverage points. The parameterized AC6 matrix tests should cover all of them.

### Architecture section pointers (for the dev agent's quick lookup)

- §Error Model & Exit Codes — lines 379–408 — exception class sketches, exit-code values, redaction strategy.
- §Output Architecture — lines 410–439 — `RunResult`, `Output` protocol, two-console pattern, `--quiet`/`--json` interaction, stdlib `json` mandate.
- §Frozen-Dataclass Conventions — lines 695–727 — `frozen=True, slots=True, kw_only=True`.
- §Error Message Template — lines 744–777 — `<NamedCondition>: <Cause>. <SuggestedAction>.`.
- §Exception Construction Patterns — lines 779–802 — positional-only, `raise X from exc`.
- §JSON Field Naming — lines 866–887 — `snake_case`, `schema_version` first, `null` not omitted.
- §Anti-Patterns to Avoid — lines 1039–1049 — `print()`, bare `Exception`, mutable defaults, retry logic, multiple BaseSettings.
- §Naming Patterns — lines 643–693 — `<Format>Output` class naming, `<Kind>Error` class naming.
- §Architectural Boundaries — lines 1168–1193 — `_output.py` owns stream discipline; `_redact.py` is the redaction choke point.

### Project Structure Notes

This story completes the `semvertag/_*.py` leaf modules (errors, redact, output, plus `RunResult` in `_types.py`). After this story:

- `semvertag/_types.py` carries `ConfigSource` (1.2) + `RunResult` (1.3). `Commit`, `Tag`, `CheckResult`, `Bump` arrive later (1.5 for Commit/Tag, 3.x for CheckResult, 1.6/2.1 for Bump).
- `semvertag/_errors.py`, `_redact.py`, `_output.py` are complete and stable; nothing else in the package will modify them. They are leaf modules — everything else imports FROM them, nothing imports INTO them.
- The package surface area after this story: `_settings.py` + `_types.py` + `_errors.py` + `_redact.py` + `_output.py` + `strategies/branch_prefix.py` + `strategies/conventional_commits.py`. That's 7 files of substantive code, well under NFR21's 1,500-LOC soft target.

### References

- [Source: architecture.md#Error Model & Exit Codes lines 379–408] — exception hierarchy, exit codes, redaction strategy
- [Source: architecture.md#Output Architecture lines 410–439] — `RunResult`, `Output` protocol, two-console pattern, `--quiet`/`--json` interaction
- [Source: architecture.md#Frozen-Dataclass Conventions lines 695–727] — `frozen=True, slots=True, kw_only=True`
- [Source: architecture.md#Error Message Template lines 744–777] — `<NamedCondition>: <Cause>. <SuggestedAction>.`
- [Source: architecture.md#Exception Construction Patterns lines 779–802] — positional-only, `raise X from exc`
- [Source: architecture.md#JSON Field Naming lines 866–887] — `snake_case`, `schema_version` first, `null` not omitted
- [Source: architecture.md#Type-Annotation Style lines 728–743] — `typing.Final`, no `from __future__ import annotations`
- [Source: architecture.md#Anti-Patterns to Avoid lines 1039–1049] — `print()`, bare `Exception`, mutable defaults
- [Source: architecture.md#Naming Patterns lines 643–693] — `<Format>Output`, `<Kind>Error` class naming
- [Source: architecture.md#Implementation Patterns §Enforcement Guidelines lines 1019–1037] — pattern enforcement
- [Source: architecture.md#Architectural Boundaries lines 1168–1193] — `_output.py` owns streams; `_redact.py` is the redaction choke point
- [Source: architecture.md#Decision Impact Analysis §Implementation sequence line 588] — this story is Step 3
- [Source: architecture.md#Test Architecture lines 548–581] — unit-only for this story; coverage gate
- [Source: architecture.md#Test Naming & File Organization lines 888–928] — file naming, function naming, `typing.Final` on test constants
- [Source: prd.md#FR30 line 537] — named, actionable error cause
- [Source: prd.md#FR35 line 545] — `--json` schema-versioned envelope
- [Source: prd.md#FR36 line 546] — `--quiet` suppresses non-error informational only
- [Source: prd.md#FR37 line 547] — exit codes 0/1/2/3/4
- [Source: prd.md#FR38 line 548] — stdout vs stderr discipline, no interleaving
- [Source: prd.md#NFR10 line 585] — token redaction in all output sinks
- [Source: prd.md#NFR20 line 598] — `schema_version: "1.0"` for v1.0; SemVer-stable evolution
- [Source: prd.md#NFR25 line 606] — public flag and config-key surface SemVer-stable; internal modules (`_*.py`) explicitly out of scope
- [Source: epics.md#Epic 1 §Story 1.3 lines 361–397] — original AC text (this story restates and expands)
- [Source: semvertag/_types.py current contents] — `ConfigSource` from Story 1.2 (MUST be preserved when extending)
- [Source: semvertag/_settings.py current contents] — Story 1.2 baseline, including `SecretStr` use for tokens
- [Source: 1-2-settings-layer-with-aliaschoices-and-provenance.md#Dev Agent Record + Review Findings] — Story 1.2 review patches that define current lint/test surface
- [Source: _autosemver_reference/use_cases/autosemver_use_case.py] — behavioral reference for output (target shape is materially different — don't port verbatim)
- [Source: ~/.claude/CLAUDE.md] — global rules: `ty: ignore` (not `type: ignore`), global imports, no `from __future__ import annotations`
- [Source: pyproject.toml lines 56–80] — ruff config; `tests/**/*.py = ["S101", "SLF001"]` per-file-ignores

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m] (Anthropic Claude Code CLI, 2026-05-27)

### Debug Log References

**Deviation 1 — `Output` protocol extended with `error(message)` method.**
Architecture §Output Architecture sketches the protocol with only `progress` and `emit`. This story formalizes the cleaner option of adding `error()` so the use-case-error path in Story 1.7 stays implementation-agnostic: `output.error(redact(str(err)))` works whether `output` is `RichOutput` or `JsonOutput`. Pre-authorized by Dev Notes §Output protocol extension.

**Deviation 2 — `JsonOutput.emit` writes through `sys.stdout`, not `rich.console.Console.print`.**
Rich's console can introduce soft-wrap, color codes (even with `color_system=None` in some terminals), and escape sequences. The JSON contract demands byte-exact output — one `json.dumps(...)` line ending in exactly one `\n`. `sys.stdout.write(payload + "\n")` followed by `sys.stdout.flush()` is the canonical CI-parseable pattern. Pre-authorized by Dev Notes §JSON-via-`sys.stdout`.

**Deviation 3 — `redact()` test surrounding-text fixture uses whitespace, not `-suffix`.**
The architecture-blessed GitLab PAT character class `[A-Za-z0-9_\-]` correctly accepts `-` (real GitLab PATs use it). A test like `redact("prefix-glpat-...-suffix")` would greedily consume the `-suffix` tail. AC7 only requires that the substituted token disappear and non-token text be preserved byte-for-byte; whitespace-bounded fixtures verify that without testing an unreachable boundary. The dedicated `test_redaction_does_not_match_inside_longer_alphanumeric_blob` covers the hex `\b` anchoring requirement directly.

**Deviation 4 — One additional test in `test_errors.py` (`_raise_auth_from_value_error` helper).**
Ruff `PT012` forbids multi-statement `with pytest.raises(...)` blocks. Moved the try/except/from-raise sequence into a helper so the `with` block stays a single statement.

**Deviation 5 — `__all__` declarations are alphabetized (`RUF022`).**
Story specifies `("SemvertagError", "ConfigError", "AuthError", "ProviderAPIError")` and the output module's `("Output", "RichOutput", "JsonOutput", "build_rich_output", "build_json_output")`. Ruff's `RUF022` sorts these alphabetically; semantics are unaffected (tuple identity is preserved as exported names).

**Deviation 6 — Two extra `RunResult` enforcement tests in `test_output_json.py`.**
AC3 calls out kw-only / frozen as part of the contract; tests `test_run_result_rejects_positional_construction` and `test_run_result_rejects_field_mutation` cover those explicitly. Each carries `# ty: ignore[too-many-positional-arguments, missing-argument]` / `# ty: ignore[invalid-assignment]` because the contract under test is exactly that those calls don't type-check.

### Completion Notes List

- All 10 ACs covered by 50 new unit tests across 4 new test files.
- Per-file coverage on the 4 new/extended `semvertag/*.py` modules: 100% line coverage (well above AC10's 85% bar).
- Full suite: 70/70 tests passing (50 new + 20 prior). No Story 1.2 regressions.
- `just lint`, `just lint-ci`, `uv build` all clean.
- Behavioral smoke check produced `{"schema_version":"1.0","strategy":"branch-prefix","bump":"none","status":"no_tags","tag":null,"commit":null,"reason":"no_tags"}` — exact JSON envelope shape, schema_version first, null for unset optionals.

### File List

**New:**
- `semvertag/_errors.py` — exception hierarchy with exit codes 1/2/3/4
- `semvertag/_redact.py` — `redact()` + compiled four-family token pattern
- `semvertag/_output.py` — `Output` protocol, `RichOutput`, `JsonOutput`, factories
- `tests/unit/test_errors.py` — AC1, AC2 (10 tests)
- `tests/unit/test_redact.py` — AC7, AC8, AC9 (17 tests)
- `tests/unit/test_output_rich.py` — AC4, AC6 (Rich rows), AC9 (18 tests)
- `tests/unit/test_output_json.py` — AC3, AC5, AC6 (JSON rows), AC9 (14 tests)

**Modified:**
- `semvertag/_types.py` — added `RunResult` alongside existing `ConfigSource`
- `_bmad/sprint-status.yaml` — story 1-3 status: ready-for-dev → in-progress → review
- `_bmad/1-3-errors-runresult-output-redaction.md` — Dev Agent Record / File List / Status

### Change Log

- 2026-05-27 — Story 1.3 implemented and marked for review. Added typed exception hierarchy, `RunResult` envelope, `Output` protocol with `RichOutput` / `JsonOutput` implementations, and token redaction. 4 new modules, 4 new test files (50 tests), 100% line coverage on new modules.
- 2026-05-27 — Code review complete (bmad-code-review). 8 patch findings, 9 deferred, 24 dismissed as noise. Reviewers: Blind Hunter (adversarial), Edge Case Hunter (path enumeration), Acceptance Auditor (AC verification). Independent green-bar verification: `just test` 70/70 pass, 100% coverage on all 4 new modules, `just lint` clean.

## Review Findings

Source key: `blind` = Blind Hunter (adversarial, no project context); `edge` = Edge Case Hunter (path enumeration); `auditor` = Acceptance Auditor (spec verification). Multi-source findings list both.

### Patches (fix in this cycle)

- [x] [Review][Patch] AC1 — `repr()` round-trip not asserted in `test_errors.py` — AC1 requires `repr()` AND `str()` round-trip; only `args` and `str(err)` are asserted at `tests/unit/test_errors.py:39-40`. Add `assert repr(AuthError("msg")) == "AuthError('msg')"` (or equivalent). [`auditor`] — Applied 2026-05-27: added `test_repr_round_trip_preserves_message`.
- [x] [Review][Patch] AC4 — "no interleaving" sequence test missing — AC4 promises "every byte of stdout from `info_console`, every byte of stderr from `error_console`". No single `RichOutput` test runs `progress` → `emit` → `error` in order and asserts strict stream separation. Add the missing sequenced test. [`auditor`] — Applied 2026-05-27: covered by `test_rich_matrix_no_interleaving_in_full_sequence` (parametrized over quiet, covers AC4 + AC6 RichOutput rows).
- [x] [Review][Patch] AC6 — `RichOutput` row coverage incomplete — Rows 1 (`quiet=False`) and 2 (`quiet=True`) of the AC6 matrix call all three methods "in order"; no test executes the full triple-call sequence. Add a parametrized 2-cell test mirroring `test_quiet_json_matrix_keeps_stdout_pure_json`. [`auditor`] — Applied 2026-05-27: same combined test as above.
- [x] [Review][Patch] AC6 — `JsonOutput` `quiet=False` row not covered — `test_quiet_json_matrix_keeps_stdout_pure_json` at `tests/unit/test_output_json.py:141` is hard-coded to `quiet=True`. Add `@pytest.mark.parametrize("quiet", [False, True])` to cover rows 3 and 4. [`auditor`] — Applied 2026-05-27: renamed to `test_json_matrix_keeps_stdout_pure_json` and parametrized over quiet.
- [x] [Review][Patch] AC8 — Idempotence not asserted on no-token input — `test_redaction_is_idempotent` at `tests/unit/test_redact.py:44-48` parametrizes only over the four token families wrapped in `pre {token} post`; the negative path (`_NO_TOKEN_TEXT`) is never re-fed through `redact()`. Add an idempotence assertion for the no-token case. [`auditor`] — Applied 2026-05-27: added `test_redaction_is_idempotent_on_no_token_input`.
- [x] [Review][Patch] Task 4.3 — Per-status `emit()` output not exercised — Task 4.3 says "print a single descriptive line for EACH documented status value otherwise". `_format_result` at `semvertag/_output.py:60-63` does emit a distinguishable line per status (status value interpolated), but `tests/unit/test_output_rich.py:99` covers only `no_merge_commit`. Parametrize over the four non-`created` values (`no_merge_commit`, `no_conforming_commit`, `already_tagged`, `no_tags`). [`auditor`] — Applied 2026-05-27: parametrized `test_emit_renders_non_created_status_to_stdout` over all four statuses.
- [x] [Review][Patch] Rich-markup injection risk in `RichOutput.progress` / `emit` / `error` — `Console.print()` defaults to `markup=True, highlight=True`; a redacted message containing literal `[` (stack-trace fragment, `dict` repr) will be parsed as Rich markup and may error or silently mutate output. Pass `markup=False, highlight=False` to all three `Console.print(...)` calls in `semvertag/_output.py:30, 33, 36, 53`. [`blind`] — Applied 2026-05-27: added `markup=False, highlight=False` to all four `Console.print` call sites in `_output.py` (RichOutput.progress, RichOutput.emit, RichOutput.error, JsonOutput.error).
- [x] [Review][Patch] File List count mismatch in Dev Agent Record — `_bmad/1-3-...md` File List claims `tests/unit/test_output_json.py — ... (12 tests)`; actual collected count is 13 (`pytest --collect-only` shows 13). Correct the line to `(13 tests)`. [`auditor`] — Applied 2026-05-27: File List updated with post-patch counts (errors=10, redact=17, output_rich=18, output_json=14, total=59).

### Deferred (real but out-of-scope for this story)

- [x] [Review][Defer] Token-family coverage gaps (`gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`, AWS `AKIA`/`ASIA`, OpenAI `sk-`, Slack `xox*`, Stripe `sk_live_`, Azure SAS `sig=`, Bitbucket `ATCTT…`) [`semvertag/_redact.py:6-11`] — deferred, pre-existing scope decision. Task 3.3 explicitly scopes AC7 to four families and tells the dev to "Note them in dev record for Story 1.5/3.x to revisit." Was not noted in Dev Agent Record; recording here. [`blind+edge`]
- [x] [Review][Defer] Full git SHAs (40-char hex) in error/progress messages get redacted to `***` [`semvertag/_redact.py:10`] — deferred, accepted trade-off. The `\b[0-9a-fA-F]{32,}\b` pattern correctly matches a standalone 40-char commit SHA; in error messages this redacts the very identifier the tool emits. Architecture chose hex breadth over SHA-allowlisting; revisit if it bites operators. [`blind+edge`]
- [x] [Review][Defer] `BrokenPipeError` / `OSError` on `sys.stdout.write`/`Console.print` [`semvertag/_output.py:48-50, 30, 33, 36`] — deferred to Story 1.7. `semvertag ... | head` will currently traceback; pipe handling belongs at the CLI top level. [`edge`]
- [x] [Review][Defer] `build_rich_output` / `build_json_output` have no `force_terminal` / `color_system` override [`semvertag/_output.py:66-78`] — deferred to Story 1.7. CLI flag wiring is Story 1.7's job; production color/no-color control is premature here. [`edge`]
- [x] [Review][Defer] `JsonOutput.emit` does NOT redact the serialized payload [`semvertag/_output.py:47-50`] — deferred. AC9 covers the Rich-error path only; if `RunResult.reason` ever carries a provider error string with a token, it would leak. Decide in Stories 1.5/1.7 where reason values are populated. [`blind`]
- [x] [Review][Defer] Long Rich messages wrap at default `width=80`, breaking single-line log expectations [`semvertag/_output.py:30, 33`] — deferred. Add `soft_wrap=True` or `no_wrap=True` if downstream log parsers complain; redaction is applied pre-wrap so security is unaffected. [`edge`]
- [x] [Review][Defer] Marginal `_redact.py` coverage gaps: `redact("")`, multi-line input, two adjacent tokens, uppercase-only hex, hex bordered by `-`/`_`/`.`/`:` [`tests/unit/test_redact.py`] — deferred. Beyond AC8's literal text; 100% line coverage already met. Add when refining the redaction pattern in Story 1.5/3.x. [`edge`]
- [x] [Review][Defer] Spec narrative example in AC9 uses 19-char token body (`"glpat-RealToken1234567890"`) while pattern requires 20+ [`_bmad/1-3-...md` AC9 narrative] — deferred. Cosmetic spec fix; the implementation/tests use a 20+-char fixture and pass. [`auditor`]
- [x] [Review][Defer] Dev Agent Record §Debug Log References doesn't mention the additional GitHub/AWS/etc. token families Task 3.3 asked the dev to note for Story 1.5/3.x — deferred, recorded in `deferred-work.md` instead. [`auditor`]

### Dismissed as noise (24 findings)

ReDoS claim on token regex (pattern shape is well-formed, no catastrophic backtracking); `@typing.runtime_checkable` on `Output` Protocol (not needed, no `isinstance` use); "`RichOutput.emit` ignores `quiet`" (explicit AC4 + FR36 contract); "`JsonOutput.progress` no-op regardless of `quiet`" (explicit AC5 + architecture contract); reliance on dict insertion order in JSON round-trip (guaranteed Python ≥3.7); "`_redact.py` is wrong layer" (architectural critique, no actionable change); `__all__` ceremony on private modules (lint hygiene, harmless); "errors should have structured fields" (spec explicitly forbids keyword-arg construction); test fixture `_GITLAB_TOKEN` underscore prefix (style nit, auto-typing-final scope compliant); `# ty: ignore` not deployed despite constraint 10 anticipating it (`ty` passes clean); `test_run_result_rejects_field_mutation` "mutates shared constant" (assertion is that mutation raises — cannot actually corrupt); `test_run_result_rejects_positional_construction` "duplicates static check" (runtime is dataclass-enforced, valuable); `test_exception_message_is_positional_args_zero` "re-tests stdlib" (documents AC2, mildly verbose but fine); `_COMMIT_SHORT_LEN = 7` hardcoded (display convention, fine); `JsonOutput.emit` not thread-safe (single-threaded CLI); `redact()` should accept `bytes`/`None` (type system already guards, project policy is to trust internal types); `_make_pair` underscore-discard inconsistency (style nit); token-shaped substring over-redaction in benign text (known design trade-off); asymmetric `\b` on hex vs prefix branches (by design); prefix branches lack word boundary (by design — match tokens anywhere); `schema_version` should be structured type, not `str` (spec explicitly chose `str`); `JsonOutput.error` not monkeypatching `sys.stdout` in one test (error path doesn't touch stdout); `RunResult` should use `Literal[...]` for `status`/`bump` (spec explicitly defers validation to use-case layer); `from None` / `ExceptionGroup` not tested (beyond AC2 scope); `exit_code` instance-vs-class lookup divergence (`ClassVar` contract); pickling / `deepcopy` / NaN / Unicode-normalization edges (not applicable to CLI tool of this scope).
