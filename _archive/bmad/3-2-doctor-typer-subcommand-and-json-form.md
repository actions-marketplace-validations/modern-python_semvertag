# Story 3.2: `semvertag doctor` Typer subcommand with config-source renderer and JSON form

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a first-time GitLab CI user,
I want to run `semvertag doctor` (or `semvertag doctor --json`) and see, in one place, which CI variables are wired up, where each effective config value came from, and which pre-flight checks pass or fail with named actionable causes,
So that I can fix problems before my first real `semvertag` invocation and feed the output into CI dashboards (FR29, FR30, FR31, FR32, NFR4, NFR10).

## Acceptance Criteria

### AC1 — `doctor/_render.py` defines a `DoctorResult` frozen dataclass with `schema_version` first

**Given** `semvertag/doctor/_render.py` is a new module
**When** `DoctorResult` is defined
**Then** it is a `@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)` carrying exactly these fields in this declared order:

1. `schema_version: str = "1.0"`
2. `configuration: dict[str, ConfigSourceView]`
3. `checks: list[CheckResult]`

**And** `ConfigSourceView` is also defined in `_render.py` as `@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)` carrying exactly:

- `value: str` — the effective value already redacted (token → `***` or last 4)
- `layer: typing.Literal["cli", "env", "default"]` — copied from `ConfigSource.layer`
- `detail: str` — copied from `ConfigSource.detail` (e.g., `--strategy`, `SEMVERTAG_TOKEN`, `default`)

**And** when serialized via `json.dumps(dataclasses.asdict(doctor_result))`, the first top-level key is `"schema_version"` and its value is `"1.0"`; all keys are snake_case.

### AC2 — `doctor/_render.py` defines a `build_doctor_result(settings, checks)` factory that redacts token fields

**Given** `_render.py` defines `build_doctor_result(settings: Settings, checks: list[CheckResult]) -> DoctorResult`
**When** it is called with a `Settings` whose `_provenance` carries entries for every field (including nested `gitlab.token`, `gitlab.endpoint`, `github.token`, etc.)
**Then** the returned `DoctorResult.configuration` is a `dict[str, ConfigSourceView]` keyed by the same dotted-path keys recorded by `Settings._provenance` (e.g., `"strategy"`, `"gitlab.endpoint"`, `"gitlab.token"`).
**And** for any field whose dotted-path name ends in `.token` (top-level or nested), `ConfigSourceView.value` is rendered as either `"***"` (when the secret is empty) or `"***" + last_4` (when at least 4 characters of secret are present).
**And** for `pydantic.SecretStr` fields, the underlying secret is never extracted into the dataclass — only the redacted display form is stored.
**And** for non-token fields, `ConfigSourceView.value` is `str(effective_value)` with no additional transformation.

### AC3 — `__main__.py` registers a `doctor` subcommand on `MAIN_APP` with `--help` describing the four checks

**Given** `MAIN_APP` already exposes a callback for the main verb
**When** Story 3.2 lands
**Then** `MAIN_APP.command("doctor")` registers a function (e.g., `_doctor_command`) whose Typer help text:

- Names the four checks: `token`, `scopes`, `project_access`, `protected_tags`.
- Documents `--json` as a flag (re-uses `--json` semantics from the main verb).
- States the exit-code surface: 0 all-pass, 3/2/4/1 per the FR37 / Story 3.1 dominance.

**And** `semvertag doctor --help` exits 0 and the help text contains each of the four check names and the `--json` flag.

### AC4 — Healthy run (all four checks pass) prints two human-readable sections and exits 0

**Given** a GitLab project where `check_token`, `check_scopes`, `check_project_access`, `check_protected_tags` all return `status="passed"`
**And** `SEMVERTAG_TOKEN` is set in the environment
**When** `semvertag doctor` is invoked (no `--json` flag)
**Then** stdout contains, in order:

1. A **configuration** section (Rich-rendered, e.g., a `rich.table.Table`) with one row per recorded `Settings._provenance` field; each row shows: field name, redacted effective value, source layer (`cli` / `env` / `default`), source detail (e.g., `--strategy`, `SEMVERTAG_TOKEN`, `CI_JOB_TOKEN`, `default`).
2. A **checks** section (Rich-rendered) with one row per `CheckResult`: name, status (`passed`), cause text from the provider.

**And** the process exits with code `0`.
**And** stderr is empty.

### AC5 — Healthy run with `--json` writes exactly one JSON line and exits 0

**Given** the same all-pass scenario as AC4
**When** `semvertag doctor --json` is invoked
**Then** exactly **one** non-empty line is written to stdout — `json.dumps(dataclasses.asdict(doctor_result))`.
**And** no progress chatter (no `RichOutput.progress` lines) is emitted to stdout.
**And** parsing the line as JSON yields a dict with top-level keys in this order: `schema_version`, `configuration`, `checks`.
**And** `payload["checks"]` is a list of length **4**.
**And** `payload["schema_version"] == "1.0"`.
**And** stderr is empty.
**And** the process exits with code `0`.

### AC6 — Missing token: token check fails, three subsequent checks reported as `skipped`, process exits 3

**Given** none of `SEMVERTAG_TOKEN`, `CI_JOB_TOKEN`, `GITLAB_TOKEN`, or `SEMVERTAG_GITLAB__TOKEN` is set in the environment
**And** `SEMVERTAG_PROJECT_ID` is set so the use-case can construct a provider
**When** `semvertag doctor` is invoked
**Then** the `token` check is reported as `status="failed"` with a cause matching the GitLab provider's "Token rejected" / "Token blocked" vocabulary OR, if the request never makes it out (no token header sent), the provider returns a `failed` result with a cause containing a `_AUTH_CAUSE_FRAGMENTS` keyword.
**And** the three subsequent checks (`scopes`, `project_access`, `protected_tags`) are reported as `status="skipped"` each with cause `"Skipped: blocked by token check."` (verbatim from Story 3.1's `_SKIPPED_CAUSE_TEMPLATE`).
**And** the process exits with code `3` (auth dominance from Story 3.1's `resolve_exit_code`).
**And** the same outcome under `--json` produces exactly one JSON line on stdout containing all four checks with their `status` and `cause` fields populated, and exits with code `3`.

### AC7 — Insufficient scopes: `--json` envelope contains all four checks; process exits 3

**Given** `SEMVERTAG_TOKEN` is set to a valid-looking token
**And** the mocked GitLab `/api/v4/user` endpoint returns 200, but `/api/v4/personal_access_tokens/self` returns a payload whose `scopes` list does not contain `"api"`
**When** `semvertag doctor --json` is invoked
**Then** the JSON envelope's `checks` list contains exactly four items:

1. `name="token", status="passed", cause="Token recognized by GitLab API."`
2. `name="scopes", status="failed", cause="Token missing 'api' scope. Add it to the SEMVERTAG_TOKEN scopes on GitLab."`
3. `name="project_access", status="skipped", cause="Skipped: blocked by scopes check."`
4. `name="protected_tags", status="skipped", cause="Skipped: blocked by scopes check."`

**And** the process exits with code `3`.

### AC8 — Configuration section reflects `Settings._provenance` verbatim and redacts every token field

**Given** the run uses a `Settings` whose `_provenance` carries:

- `strategy → ConfigSource(layer="cli", detail="--strategy")`
- `gitlab.token → ConfigSource(layer="env", detail="SEMVERTAG_TOKEN")`
- `gitlab.endpoint → ConfigSource(layer="env", detail="SEMVERTAG_GITLAB__ENDPOINT")`
- `project_id → ConfigSource(layer="env", detail="CI_PROJECT_ID")`
- `default_branch → ConfigSource(layer="default", detail="default")`

**When** the rendered output is inspected (either Rich form or JSON form)
**Then** each of the five fields appears in the `configuration` section/dict.
**And** `gitlab.token` renders as `"***" + last_4_of_secret` (or `"***"` if the secret is fewer than 4 chars) — the raw secret never appears.
**And** every other field renders its effective value via `str(value)`.
**And** the `(layer, detail)` pair for each field matches what `_provenance` recorded.

### AC9 — DI wiring lets the subcommand resolve a provider without invoking the main use case

**Given** `__main__.py:_doctor_command` is invoked
**When** the function body executes
**Then** it builds a container via `ioc.build_container(settings, json=json_flag, inner_transport=...)` exactly as the main callback does — same Settings construction, same overlay logic, same error translation.
**And** it resolves `ProvidersGroup.gitlab_provider` (NOT `UseCasesGroup.semvertag_use_case`) — the doctor subcommand consumes only the four `check_*` methods on the provider, not the full use case.
**And** the use-case is NEVER instantiated for the doctor path (verified by an integration test that asserts no POST `/repository/tags` request is made).
**And** the doctor subcommand re-uses the same `Settings` overlay rules from the main callback (CLI flags applied via `apply_cli_overlay`).

### AC10 — Errors before the chain runs translate to `typer.Exit(code=err.exit_code)` exactly like the main verb

**Given** the doctor subcommand encounters a `pydantic.ValidationError`, `ConfigError`, `AuthError`, `ProviderAPIError`, or generic `SemvertagError` **before** `run_checks(provider)` is called (e.g., missing `project_id`, malformed `request_timeout`, provider construction failure)
**When** the error propagates
**Then** the doctor command path emits the error message to stderr via `output.error(...)` and raises `typer.Exit(code=err.exit_code)` — same translation as `_main_callback` in `semvertag/__main__.py:154-170`.
**And** `BrokenPipeError` / `OSError(EPIPE)` exit with code `0` (matches `_main_callback` behavior at `__main__.py:165-170`).

### AC11 — Token redaction enforced on every output path (stdout human, stdout JSON, stderr)

**Given** an invocation where `SEMVERTAG_TOKEN="glpat-XXXXXXXXXXXXXXXXXXXX"` is set
**When** `semvertag doctor` (no flag) is run
**Then** stdout contains neither the literal token nor any of its first 16 characters; the only acceptable rendering is `"***"` followed by the last 4 characters (`"XXXX"`) — both in the configuration table row for `gitlab.token` and anywhere else the token might leak (cause strings, headers, debug logs).
**And** the same invariant holds under `semvertag doctor --json`: parsing the JSON envelope reveals no raw token substring; `configuration["gitlab.token"].value` is the redacted form.
**And** when the doctor subcommand emits an error to stderr (AC10 scenarios), `_output.RichOutput.error` / `JsonOutput.error` applies `_redact.redact(...)` exactly as the main verb does today.

### AC12 — Integration tests in `tests/integration/test_cli_doctor.py` cover four chain outcomes × two output forms

**Given** `tests/integration/test_cli_doctor.py` is a new file
**When** `pytest tests/integration/test_cli_doctor.py` runs
**Then** it exercises, via `typer.testing.CliRunner` + `httpx2.MockTransport`, at minimum:

1. **All-pass (human)**: every check returns 200; `cli_runner.invoke(MAIN_APP, ["doctor"])`; expect `exit_code == 0`, configuration section + checks section in stdout, stderr empty.
2. **All-pass (JSON)**: same scenario with `["doctor", "--json"]`; expect single-line JSON, `payload["schema_version"] == "1.0"`, `len(payload["checks"]) == 4`, all `passed`.
3. **Fail-at-token (human)**: `/api/v4/user` returns 401; expect `exit_code == 3`, token row shows `failed` with the GitLab "Token rejected" cause, three rows show `skipped`.
4. **Fail-at-token (JSON)**: same with `--json`; assert the JSON envelope.
5. **Fail-at-scopes (JSON)**: `/api/v4/user` → 200, `/api/v4/personal_access_tokens/self` → 200 with `{"scopes": ["read_repository"]}` (no `api`); expect `exit_code == 3`, scopes row `failed` with the exact "Token missing 'api' scope." cause, two rows `skipped`.
6. **Fail-at-project_access (JSON)**: token + scopes pass; `/api/v4/projects/{id}` → 404; expect `exit_code == 2` (`ConfigError.exit_code`), project_access row `failed` with the "GitLab project not found" cause, protected_tags row `skipped`.
7. **Fail-at-protected_tags (JSON)**: token + scopes + project_access pass; `/api/v4/projects/{id}/protected_tags` → 401; expect `exit_code == 3`, protected_tags row `failed`, no skipped rows.
8. **Token redaction (both forms)**: under any healthy or failing scenario, neither `stdout` nor the parsed JSON envelope contains the raw `SEMVERTAG_TOKEN` value — only `"***XXXX"` (last-4) form.
9. **`--help` exit**: `cli_runner.invoke(MAIN_APP, ["doctor", "--help"])`; expect `exit_code == 0`, all four check names in help text, `--json` flag documented.

**And** the test file imports `MAIN_APP` from `semvertag.__main__`, reuses the `cli_runner` / `cli_env` / `install_mock_transport` fixtures from `tests/integration/conftest.py`, and follows the test-naming convention `test_<verb>_<outcome>_when_<condition>` (architecture line 911).
**And** the integration tests verify that no `POST /api/v4/projects/{id}/repository/tags` request is recorded (the doctor command never reaches the use-case write path).

### AC13 — `_render.py` unit tests pin the redaction rule and the dataclass field ordering

**Given** `tests/unit/test_doctor_render.py` is a new file
**When** `pytest tests/unit/test_doctor_render.py` runs
**Then** it covers:

- `ConfigSourceView` field order and `DoctorResult` field order match the dataclass declaration (`dataclasses.fields(DoctorResult)[0].name == "schema_version"` etc.).
- `build_doctor_result(...)` redaction rule: a `SecretStr("glpat-XXXXXXXXXXXXXXXXXXXX")` produces `value="***XXXX"`; an empty `SecretStr("")` produces `value="***"`; a non-token field's value is `str(...)`-rendered verbatim.
- `dataclasses.asdict(doctor_result)` ordering: the first key is `"schema_version"`, the second is `"configuration"`, the third is `"checks"`.
- `Settings._provenance` round-trip: every recorded `ConfigSource` shows up in the resulting `configuration` dict with matching `(layer, detail)`.

**And** the unit tests do not require a `Provider`, `CliRunner`, or `MockTransport` — they construct `Settings()`, populate `_provenance`, and call `build_doctor_result(settings, checks=[...])` directly.

### AC14 — `just test` green; full suite passes; coverage gates preserved

**Given** `just test` is run from a fresh checkout post-`uv sync`
**When** the full pytest suite completes
**Then**:

- All **389 tests** from Epic 1 + Epic 2 + Story 3.1 pass unchanged (regression canary).
- New unit tests from AC13 (~6 cases) and new integration tests from AC12 (~9 cases) pass.
- `pytest --cov` global line coverage **≥85%** (`pyproject.toml:83` gate).
- `just test-branch-strategies` (Story 1.6 gate) and `just test-cc-strategies` (Story 2.1 gate) still pass at 100% branch.
- `just test-doctor` still passes at 100% branch on `semvertag/doctor` — the new `_render.py` is included in that coverage scope.
- `just lint-ci`, `uv run ty check`, and `uv build` all complete clean.

### AC15 — No changes to `providers/gitlab.py`, `_types.py`, `_errors.py`, or `_settings.py` shapes

**Given** Epic 3's framing ("this epic does not modify `providers/gitlab.py`")
**When** Story 3.2 lands
**Then**:

- `semvertag/providers/gitlab.py` is **not** modified — cause-string vocabulary stays exactly as Story 1.5 landed it.
- `semvertag/_types.py` shapes (`CheckResult`, `ConfigSource`) are preserved verbatim. `_render.py`'s `DoctorResult` and `ConfigSourceView` are new dataclasses in the `doctor/` package, not in `_types.py`.
- `semvertag/_errors.py` is unchanged — `SemvertagError.exit_code` ClassVars remain the single owner of the FR37 exit-code surface.
- `semvertag/_settings.py` is unchanged — `Settings._provenance` already records every field (verified by `tests/unit/test_provenance.py`).
- `semvertag/_output.py` `Output` Protocol stays at three methods (`progress`, `emit`, `error`); doctor rendering is a separate concern living in `doctor/_render.py` (architecture line 531: "doctor uses the same `Output` protocol … with one extension — a configuration-section renderer reading `Settings._provenance`" — implemented as a free function, not a protocol change).

## Tasks / Subtasks

- [x] **Task 1: Author `semvertag/doctor/_render.py` (AC1, AC2, AC8)**.
  - [x] 1.1 Define `ConfigSourceView` frozen dataclass at module top (`frozen=True, slots=True, kw_only=True`; fields in order: `value: str`, `layer: typing.Literal["cli", "env", "default"]`, `detail: str`). Field order matters — it determines key order in `dataclasses.asdict`.
  - [x] 1.2 Define `DoctorResult` frozen dataclass (`frozen=True, slots=True, kw_only=True`; fields in declared order: `schema_version: str = "1.0"`, `configuration: dict[str, ConfigSourceView]`, `checks: list[CheckResult]`).
  - [x] 1.3 Implement `_redact_token(secret: pydantic.SecretStr) -> str`:
    - Extract the secret value with `.get_secret_value()`.
    - If `len(secret_value) < 4`: return `"***"`.
    - Else: return `"***" + secret_value[-4:]`.
    - This function is private to `_render.py` (single owner of doctor-side token redaction); the existing `_redact.redact(...)` regex covers free-text leakage, but for the structured `configuration[*].value` slot we need a deterministic last-4 rendering.
  - [x] 1.4 Implement `_format_setting_value(field_path: str, settings: Settings) -> str`:
    - Walk dotted `field_path` (e.g., `"gitlab.token"`) against `settings`, picking attributes as it descends.
    - If the resolved value is a `pydantic.SecretStr`: return `_redact_token(value)`.
    - Else: return `str(value)`.
    - Bool / int / float values render via their default `str()` form (no special-casing — matches Rich's `Table.add_row` rendering).
  - [x] 1.5 Implement `build_doctor_result(settings: Settings, checks: list[CheckResult]) -> DoctorResult`:
    1. `configuration: dict[str, ConfigSourceView] = {}` — preserve insertion order from `settings._provenance` (which already iterates `model_fields` in declaration order via `_scan_model`).
    2. For each `(field_path, config_source) in settings._provenance.items()`:
       - `value = _format_setting_value(field_path, settings)`.
       - `configuration[field_path] = ConfigSourceView(value=value, layer=config_source.layer, detail=config_source.detail)`.
    3. Return `DoctorResult(configuration=configuration, checks=checks)` — `schema_version` defaults to `"1.0"`.
  - [x] 1.6 Implement `render_doctor_human(doctor_result: DoctorResult, output: RichOutput) -> None`:
    - Build a `rich.table.Table(title="Configuration")` with columns `Setting`, `Value`, `Layer`, `Detail`; one row per `(key, view)` in `doctor_result.configuration.items()`.
    - Build a second `rich.table.Table(title="Checks")` with columns `Check`, `Status`, `Cause`; one row per `CheckResult` in `doctor_result.checks`.
    - Print both tables via `output.info_console.print(table)` — same console instance the existing `RichOutput.progress`/`emit` writes to (stdout, NFR38 stream discipline preserved).
    - Apply `_redact.redact(...)` to the cause cell as a defense-in-depth measure (free-text token leakage from a buggy future provider would still get caught).
  - [x] 1.7 Implement `render_doctor_json(doctor_result: DoctorResult) -> None`:
    - `payload = json.dumps(dataclasses.asdict(doctor_result), separators=(",", ":"))`.
    - `sys.stdout.write(payload + "\n")`; `sys.stdout.flush()` — matches `_output.JsonOutput.emit` pattern at `semvertag/_output.py:47-50`.
    - No `_redact.redact(...)` call on the JSON payload — redaction happens at construction time in `_format_setting_value` (`configuration[*].value` is already the redacted form). Cause strings come from `providers/gitlab.py`, which already produces redacted-safe text.
  - [x] 1.8 Declare `__all__: typing.Final = ("ConfigSourceView", "DoctorResult", "build_doctor_result", "render_doctor_human", "render_doctor_json")` (alphabetical per RUF022).

- [x] **Task 2: Register `doctor` subcommand in `semvertag/__main__.py` (AC3, AC9, AC10)**.
  - [x] 2.1 Import additions at module top:
    ```python
    from semvertag.doctor._checks import resolve_exit_code, run_checks
    from semvertag.doctor._render import build_doctor_result, render_doctor_human, render_doctor_json
    ```
  - [x] 2.2 Add `@MAIN_APP.command("doctor")` decorator + function `_doctor_command(...)` with these Typer parameters (mirror the main callback's overlay-relevant flags):
    - `project_id`, `token`, `gitlab_endpoint`, `default_branch`, `provider`, `request_timeout` — same `typing.Annotated[... | None, typer.Option(...)]` signatures as the main callback.
    - `json_flag: typing.Annotated[bool, typer.Option("--json", help="Emit a JSON envelope on stdout instead of human-readable output.")] = False`.
    - **No** `--strategy` / `--quiet` overrides — they don't affect doctor's behavior (doctor doesn't compute a bump and doesn't emit progress chatter); listing them on `doctor --help` would be misleading. Skip them per architecture's "one CLI option per affected behavior" preference.
    - Docstring (Typer help text) names the four checks: `"Run four pre-flight checks against the configured provider: token, scopes, project_access, protected_tags. Emits a configuration table + checks table to stdout, or a single-line JSON envelope when --json is set. Exits 0 when all pass; 3 (auth) / 2 (config) / 4 (provider) / 1 (generic) on failure per FR37."`
  - [x] 2.3 Implementation body mirrors `_main_callback` setup but resolves the provider directly:
    ```python
    output = _build_output_for_flags(quiet=False, json_flag=json_flag)
    try:
        settings = Settings()
        try:
            overrides = _collect_doctor_overrides(
                project_id=project_id, token=token,
                gitlab_endpoint=gitlab_endpoint, default_branch=default_branch,
                provider=provider, request_timeout=request_timeout,
            )
            settings = apply_cli_overlay(settings, overrides)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
        output = _build_output_for_flags(quiet=False, json_flag=json_flag)
        container = ioc.build_container(settings, json=json_flag)
        with container:
            provider_instance = container.resolve_provider(ioc.ProvidersGroup.gitlab_provider)
            results = run_checks(provider_instance)
            doctor_result = build_doctor_result(settings, results)
            if json_flag:
                render_doctor_json(doctor_result)
            else:
                rich_output = container.resolve_provider(ioc.OutputsGroup.rich_output)
                render_doctor_human(doctor_result, rich_output)
            raise typer.Exit(code=resolve_exit_code(results))
    except pydantic.ValidationError as exc:
        ...
    except ImportError as exc:
        ...
    except SemvertagError as err:
        ...
    except BrokenPipeError as exc:
        raise typer.Exit(code=0) from exc
    except OSError as exc:
        if exc.errno == errno.EPIPE:
            raise typer.Exit(code=0) from exc
        raise
    ```
    Keep error-translation blocks **byte-identical** to `_main_callback`'s (Story 1.7 / Story 3.1 single-owner constraint — exception → exit-code mapping lives in `__main__.py` and is duplicated only by syntactic necessity; never diverge the semantics).
  - [x] 2.4 Implement `_collect_doctor_overrides(...)` as a small helper (alongside `_collect_overrides` at `semvertag/__main__.py:39-67`) — mirrors the existing helper but drops the `strategy` and `quiet` slots since the doctor command does not surface those flags. Name it `_collect_doctor_overrides` so its narrower surface is grep-discoverable.
  - [x] 2.5 Verify the main callback's `if ctx.invoked_subcommand is not None: return` guard at `semvertag/__main__.py:128-129` still works — when the user runs `semvertag doctor`, Typer invokes the doctor command after the callback's early return, so no use-case is constructed. Add an integration assertion in AC12 #1 that no `POST /repository/tags` is recorded.

- [x] **Task 3: Author unit tests `tests/unit/test_doctor_render.py` (AC13)**.
  - [x] 3.1 Module preamble: `import dataclasses; import json; import typing; import pydantic; from semvertag._settings import Settings, GitLabConfig; from semvertag._types import CheckResult, ConfigSource; from semvertag.doctor._render import ConfigSourceView, DoctorResult, build_doctor_result`. `typing.Final` on every module-level constant.
  - [x] 3.2 `test_doctor_result_has_schema_version_first` — assert `dataclasses.fields(DoctorResult)[0].name == "schema_version"`; iterate `dataclasses.fields(DoctorResult)` and check the full order `("schema_version", "configuration", "checks")`.
  - [x] 3.3 `test_config_source_view_field_order_is_value_layer_detail` — assert `tuple(f.name for f in dataclasses.fields(ConfigSourceView)) == ("value", "layer", "detail")`.
  - [x] 3.4 `test_build_doctor_result_redacts_secret_str_token_to_last_four` — construct a `Settings` with `gitlab.token=pydantic.SecretStr("glpat-XXXXXXXXXXXXXXXXXXXX")`, manually populate `_provenance["gitlab.token"] = ConfigSource(layer="env", detail="SEMVERTAG_TOKEN")`, call `build_doctor_result(settings, checks=[])`, and assert `result.configuration["gitlab.token"].value == "***XXXX"` (last 4 of the 24-char glpat string).
  - [x] 3.5 `test_build_doctor_result_redacts_empty_secret_to_triple_star` — construct `gitlab.token=pydantic.SecretStr("")`, assert `result.configuration["gitlab.token"].value == "***"`.
  - [x] 3.6 `test_build_doctor_result_renders_non_secret_value_via_str` — non-token field with `default_branch="main"`, assert `result.configuration["default_branch"].value == "main"`. Integer field (`project_id=999`) → `"999"`. Bool field (`quiet=False`) → `"False"`.
  - [x] 3.7 `test_dataclasses_asdict_first_key_is_schema_version` — call `dataclasses.asdict(doctor_result)`; assert `next(iter(payload.keys())) == "schema_version"`; assert `payload["schema_version"] == "1.0"`.
  - [x] 3.8 `test_build_doctor_result_round_trips_layer_and_detail_from_provenance` — populate `_provenance["strategy"] = ConfigSource(layer="cli", detail="--strategy")`; assert `result.configuration["strategy"].layer == "cli"` and `.detail == "--strategy"`.
  - [x] 3.9 Build a real `Settings()` with overlayed values to exercise `build_doctor_result` end-to-end at the unit level; assert that every key in `settings._provenance` appears in `result.configuration`.

- [x] **Task 4: Author integration tests `tests/integration/test_cli_doctor.py` (AC12)**.
  - [x] 4.1 Module preamble: import `CliRunner` + `httpx2` + `MAIN_APP` + the shared fixtures (`cli_env`, `install_mock_transport`, `cli_runner`, `GITLAB_PROJECT_ID`, `GITLAB_ENDPOINT`, `GITLAB_TOKEN`) from `tests/integration/conftest.py`. Reuse `merge_commit_handler` patterns where applicable; otherwise build a focused `doctor_handler(...)` factory inside the test file.
  - [x] 4.2 Build a `_doctor_handler(*, user_status=200, scopes_payload=..., project_status=200, protected_tags_status=200) -> HandlerCallable` factory that returns canned responses for the four doctor endpoints. Endpoints:
    - `GET /api/v4/user` → user_status / `{"id": 1, "username": "ci-bot"}`.
    - `GET /api/v4/personal_access_tokens/self` → 200 / scopes_payload (default: `{"scopes": ["api"]}`).
    - `GET /api/v4/projects/{GITLAB_PROJECT_ID}` → project_status / `{"default_branch": "main"}`.
    - `GET /api/v4/projects/{GITLAB_PROJECT_ID}/protected_tags` → protected_tags_status / `[]`.
    - Any other path → 404 (so a leaked POST `/repository/tags` from a buggy use-case path would fail loudly).
  - [x] 4.3 Implement each test from AC12 #1-#9 as `test_<verb>_<outcome>_when_<condition>`:
    - `test_emits_configuration_and_checks_sections_when_all_pass`
    - `test_emits_single_line_json_envelope_when_all_pass_and_json_flag`
    - `test_reports_token_failed_and_three_skipped_when_user_endpoint_returns_401`
    - `test_emits_json_envelope_with_token_failed_when_user_endpoint_returns_401_and_json_flag`
    - `test_reports_scopes_failed_when_introspection_payload_lacks_api_scope`
    - `test_reports_project_access_failed_when_projects_endpoint_returns_404`
    - `test_reports_protected_tags_failed_when_protected_tags_endpoint_returns_401`
    - `test_redacts_token_to_last_four_in_both_human_and_json_output`
    - `test_exits_zero_and_shows_help_when_help_flag_set`
  - [x] 4.4 In every test, assert the exit code AND assert that no `POST /api/v4/projects/{id}/repository/tags` request was recorded (verifying AC9's "use-case never instantiated" invariant). Use a recording-handler wrapper pattern similar to `tests/integration/test_cli_main_verb.py:23-31`.
  - [x] 4.5 Token-redaction test (AC11): inspect `result.stdout` for the raw token substring `"glpat-XXXXXXXXXXXXXXXXXXXX"` — assert it does NOT appear; assert `"***XXXX"` (last-4) DOES appear in the configuration row for `gitlab.token`.
  - [x] 4.6 `--help` test: invoke `cli_runner.invoke(MAIN_APP, ["doctor", "--help"])`; assert `exit_code == 0`; assert each of `"token"`, `"scopes"`, `"project_access"`, `"protected_tags"`, `"--json"` appears in `result.output`.

- [x] **Task 5: Run the full local validation gate (AC14)**.
  - [x] 5.1 `just install` (fresh sync).
  - [x] 5.2 `just lint-ci` — must be clean.
  - [x] 5.3 `just test` — full suite passes; global line coverage **≥85%**.
  - [x] 5.4 `just test-branch-strategies` — Story 1.6 gate stays 100% branch.
  - [x] 5.5 `just test-cc-strategies` — Story 2.1 gate stays 100% branch.
  - [x] 5.6 `just test-doctor` — Story 3.1 gate stays 100% branch on `semvertag/doctor` (now includes `_render.py`). If the existing recipe needs to be extended to also cover `tests/unit/test_doctor_render.py`, edit `Justfile:31-32` to add the new test file to the recipe's positional argument list.
  - [x] 5.7 `uv run ty check` — clean.
  - [x] 5.8 `uv build` — clean.
  - [x] 5.9 Update `_bmad/sprint-status.yaml`: `3-2-…: backlog → ready-for-dev → in-progress → review` (code-review step bumps to `done`).
  - [x] 5.10 Update this story file: tick all task/subtask checkboxes; fill in Dev Agent Record sections; bump Status to `review`.

### Review Findings

_From `bmad-code-review` on 2026-05-29. Triaged 23 findings across 3 review layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor) → **4 decision-needed, 7 patch, 6 defer, 6 dismissed**._

- [x] [Review][Decision] AC2 redaction trigger diverges from spec — Impl `semvertag/doctor/_render.py:48` redacts based on `isinstance(current, pydantic.SecretStr)`. AC2 line 38 of this spec says "for any field whose dotted-path name ends in `.token`". Practically equivalent today (every token field IS a SecretStr and vice-versa), but the contract diverges. Decide: keep type-based (auto-redacts any future SecretStr), switch to path-based (matches spec literally), or do both.
- [x] [Review][Decision] Doctor ignores `SEMVERTAG_QUIET` because output is built once with hardcoded `quiet=False` — `semvertag/__main__.py:238` builds `output` before `Settings()` is loaded; never rebuilds post-overlay. `_main_callback` rebuilds with `quiet=settings.quiet`. AC10 byte-identical wording is about exception clauses (those match), but `SEMVERTAG_QUIET=1` is silently ignored by doctor. Decide: rebuild output post-settings to honor the env var, or keep hardcoded `quiet=False` since `--quiet` is intentionally absent.
- [x] [Review][Decision] `_redact_token` discloses entire secret for 4-char tokens — `semvertag/doctor/_render.py:39-41` returns `"***" + secret[-4:]` when `len >= 4`. A 4-char secret produces `"***abcd"` — the whole secret. Spec AC2 line 38 wording technically permits this. Decide: tighten guard to `len <= _TOKEN_SUFFIX_LEN → "***"` for safety, or keep spec-faithful.
- [x] [Review][Decision] Help text wording drift from spec Task 2.2 — `semvertag/__main__.py:231-237` docstring drops "four" and "against the configured provider", adds "dominance". AC3's named requirements (four check names + `--json` + exit-code surface) are all present. Decide: tighten to spec verbatim, or accept the wording drift.

- [x] [Review][Patch] `pydantic.ValidationError` from `apply_cli_overlay` bypasses `_config_error_from_validation` formatting [semvertag/__main__.py:251-253] — `ValidationError IS ValueError`, gets caught by inner `except ValueError`, wrapped raw via `ConfigError(str(exc))`. Raw multi-line pydantic dump lands in stderr instead of the formatted "Configuration error at 'provider': ..." form that `Settings()` failures get at `__main__.py:264-267`. Fix: catch `pydantic.ValidationError` separately inside the overlay try, route through `_config_error_from_validation`.
- [x] [Review][Patch] Non-token str config values are not redacted in either render path [semvertag/doctor/_render.py:50,71-76] — `_format_setting_value` returns `str(current)` verbatim for non-SecretStr; `render_doctor_human` renders `view.value` raw. Trigger: `SEMVERTAG_GITLAB__ENDPOINT=https://gitlab.example.com/?private_token=glpat-XXXX...` leaks the token into the configuration table and JSON envelope, defeating AC11 ("stdout contains neither the literal token"). Fix: apply `_redact.redact(...)` to non-SecretStr `str(value)` results, mirroring `RichOutput.progress/emit/error`.
- [x] [Review][Patch] AC7 cause strings not pinned byte-exact [tests/integration/test_cli_doctor.py:180,183] — AC7 items 1 and 2 require exact strings `"Token recognized by GitLab API."` and `"Token missing 'api' scope. Add it to the SEMVERTAG_TOKEN scopes on GitLab."`. Test asserts only `passed` status for #1 and substring `"Token missing 'api' scope"` for #2. Tighten to byte-exact equality.
- [x] [Review][Patch] AC8 configuration section not verified against all five spec keys [tests/**] — AC8 enumerates `strategy`, `gitlab.token`, `gitlab.endpoint`, `project_id`, `default_branch` and requires all five appear with matching `(layer, detail)`. No single test asserts all five co-presence in one output. Add an integration assertion (or extend `test_emits_single_line_json_envelope_when_all_pass_and_json_flag`) that pins all five keys + their `(layer, detail)`.
- [x] [Review][Patch] `_assert_no_post_to_tags` missing from 4 integration tests [tests/integration/test_cli_doctor.py:234,256,267,303] — AC9/Task 4.4 says "In **every** test". Missing from: `test_redacts_token_to_last_four_in_both_human_and_json_output`, `test_exits_zero_and_shows_help_listing_four_checks_when_help_flag_set`, `test_exits_with_config_error_when_project_id_missing_under_doctor`, `test_exits_with_provider_api_error_when_user_endpoint_returns_500`. Add `recorded` + wrapper + assertion to each.
- [x] [Review][Patch] No test for stderr redaction on doctor error path [tests/integration/test_cli_doctor.py] — AC11 names this explicitly. `_output.RichOutput.error` already redacts (structural coverage), but no test exercises a doctor-path error with a token in the message and asserts stderr is redacted. Add a scenario.
- [x] [Review][Patch] JSON compact-separator unit test will false-positive on realistic causes [tests/unit/test_doctor_render.py:289-290] — `assert ", " not in line` and `assert ": " not in line` check the value space, not the separator space. Real causes contain `": "` (`"Unexpected GitLab response: 500."`, `"GitLab project not found: project_id=..."`). Today's fixture happens to avoid them. Fix: parse the JSON and assert no `, "` / `, ` between encoded keys, OR assert the encoder's structural separators directly (`json.dumps(..., separators=(",", ":"))` output already won't have key-separator whitespace).

- [x] [Review][Defer] `_format_setting_value` will `AttributeError` on a stale/typo'd dotted-path key [semvertag/doctor/_render.py:44-50] — deferred, currently safe since `_provenance` keys come from `_scan_model` on the same Settings; defensive guard for future divergence.
- [x] [Review][Defer] `_build_output_for_flags` raises before `try:` would propagate uncaught [semvertag/__main__.py:_doctor_command top] — deferred, pre-existing pattern mirrored from `_main_callback`; Rich console construction is not known to raise in practice.
- [x] [Review][Defer] Private API coupling on `Settings._provenance` [semvertag/doctor/_render.py:55] — deferred, architecturally accepted per spec Dev Note 5 ("single source of truth"); `noqa: SLF001` already present.
- [x] [Review][Defer] Explicit `--token ""` produces empty `SecretStr` with confusing downstream cause [semvertag/__main__.py:84] — deferred, minor UX wart not introduced by this story; could add empty-string guard in `_collect_doctor_overrides`.
- [x] [Review][Defer] `render_doctor_json` `OSError(non-EPIPE)` from `sys.stdout.flush()` re-raises without `typer.Exit` translation [semvertag/__main__.py:277-280] — deferred, hypothetical (EIO on /dev/stdout); matches main callback pattern.
- [x] [Review][Defer] `tests/integration/conftest.py` `_clean_env_before_each` omits `SEMVERTAG_GITLAB__TOKEN` and other token aliases [tests/integration/conftest.py:28-45] — deferred, pre-existing conftest gap; developer shell pollution could cause flakes in the redaction test. Not introduced by this story.

_Dismissed (6): intentional `--strategy`/`--quiet` omission per Task 2.2; `"Project id missing"` substring assertion style consistent with the suite; AC15 `_checks.py` 1-line wrap documented in Dev Agent Record §Debug Log References item 2; `typer.Exit` cleanup cosmetic note; `_doctor_handler` 404-fallthrough observation (covered by the no-POST patch above); `_close_provider_client` finalizer not registered before `ConfigError` raise (verified safe — no client created)._

## Dev Notes

### Story framing

This is the **second and final story of Epic 3** — Pre-flight Diagnostics. Story 3.1 shipped the orchestration logic (chain runner + exit-code resolver) under a 100% branch-coverage gate; Story 3.2 wraps a thin Typer subcommand around it, adds the configuration-source renderer reading `Settings._provenance`, and ships the JSON envelope for CI dashboards. Once Story 3.2 lands, Epic 3 is complete (no Story 3.3).

The architecture's decision-impact ordering (`architecture.md:584-595` Step 8) explicitly sequences this story after the chain runner: *"Doctor subcommand — sequential skip-on-failure check chain; reuses Output and Provider protocols."* Story 3.2 is the "reuses" half — it adds zero new protocols and zero new providers; it consumes the existing `Provider.check_*` surface, the existing `Settings._provenance` map, and the existing `_output.RichOutput` / `JsonOutput` impls.

Epic 3's epic statement (`epics.md:602-604`) is non-negotiable: **this epic does not modify `providers/gitlab.py`**. Story 3.2 inherits that constraint. If during implementation a cause-string drift is discovered between `providers/gitlab.py` and Story 3.1's `_AUTH_CAUSE_FRAGMENTS` / `_CONFIG_CAUSE_FRAGMENTS` / `_PROVIDER_API_CAUSE_FRAGMENTS` tuples, log the drift in `_bmad/deferred-work.md` and the Dev Agent Record but DO NOT fix it inline — the integration tests will catch it explicitly, and the fragment-update lands in Epic 4 (or a follow-on Epic 3 patch).

### Critical architectural constraints

1. **Doctor `Output` extension is informal — no `Output` Protocol change** (architecture line 531). The existing `Output` Protocol in `_output.py:15-18` keeps its three methods (`progress`, `emit`, `error`). The doctor renderer (`doctor/_render.py:render_doctor_human` / `render_doctor_json`) is a free function consuming a `RichOutput` instance for the rich path and writing directly to `sys.stdout` for the JSON path. **Do NOT add `emit_doctor(...)` to the Protocol** — that would force `RichOutput`/`JsonOutput` to grow methods they don't need, and would couple `Output` to a doctor-specific shape.

2. **`schema_version="1.0"` for the doctor envelope** (architecture line 533 / AC1). This is a **NEW** stability surface — the doctor JSON envelope has not shipped before. Locking to `1.0` at v1.0 means any future breaking change requires `schema_version` bump + deprecation cycle (NFR25). Document this in the public `docs/doctor.md` page (Story 4.4 will create that file; this story creates the schema).

3. **Token redaction at construction time, not at render time** (NFR10). The redaction MUST happen in `build_doctor_result(...)` — by the time the value reaches `ConfigSourceView.value`, it is already `"***XXXX"`. Then `dataclasses.asdict(...)` for the JSON path serializes the already-safe string; the human path renders the same string in a Rich table cell. **Do NOT rely on `_redact.redact(...)` for the structured `configuration[*].value` slot** — that regex catches glpat-`/`ghp_`/`ATBB` patterns in free text, but the configuration slot is a `str`-formatted Settings field and the redaction must be deterministic (last-4), not pattern-matched.

4. **Cause strings come from `providers/gitlab.py` unchanged** (Epic 3 framing). The doctor JSON envelope's `checks[*].cause` field is the exact cause string the provider produced. `_redact.redact(...)` IS applied to the human-form cause cell (Task 1.6) as defense-in-depth, but NOT to the JSON envelope's cause field — `providers/gitlab.py` already produces redaction-safe text per Story 1.5. If a future provider leaks a token into a cause, Story 4.x adds the JSON-path redaction; for v1.0 the contract holds.

5. **`Settings._provenance` is the single source of truth for the configuration section** (architecture line 494, line 601). The `_provenance` dict is keyed by dotted field-paths (`strategy`, `gitlab.token`, `gitlab.endpoint`, `project_id`, `default_branch`, etc.) and produced by `_settings._scan_model` (`semvertag/_settings.py:146-153`). `build_doctor_result(...)` iterates this dict; do NOT re-walk `settings.model_fields` independently — that would risk divergence in field ordering or coverage.

6. **`pydantic.SecretStr` never appears in the `DoctorResult` dataclass** (NFR10 / AC2). Reading `.get_secret_value()` happens exactly once, inside `_redact_token(...)`, and the returned redacted string is what gets stored on `ConfigSourceView.value`. The dataclass itself is `frozen=True, slots=True` and carries only the already-safe display form — no SecretStr leakage via `repr(...)` or `dataclasses.asdict(...)`.

7. **Exit-code translation single-owner** (architecture line 603 / Story 3.1 Constraint 6). `__main__.py` is the **only** site that maps `SemvertagError.exit_code` → `typer.Exit(code=...)`. The doctor subcommand does this translation too — but only for errors raised **before** the chain runs (validation errors, provider construction failures). For chain-result-derived exit codes, the call is `raise typer.Exit(code=resolve_exit_code(results))` using Story 3.1's pure-function resolver. No new mapping logic in `_doctor_command`.

8. **No DI Group additions in `ioc.py`** (Story 3.1 Constraint 7 carryforward). The doctor subcommand consumes existing `ProvidersGroup.gitlab_provider` and `OutputsGroup.rich_output` (or the JSON override path via `build_container(json=True)`). No new `DoctorGroup` — Story 3.1's chain runner is a free function, and Story 3.2's renderer is a free function; neither needs DI plumbing. **Resist the temptation** to factor a `DoctorRunner` class with injected dependencies; the dev-test surface is two functions and a renderer, and the existing groups cover the inputs.

9. **`apply_cli_overlay` re-use, not re-implementation** (`semvertag/_settings.py:190-206`). The doctor subcommand applies CLI flags via the same `apply_cli_overlay(settings, overrides)` call as the main verb. Provenance recording for CLI-source values flows through that helper unchanged — when the doctor renderer reads `_provenance["gitlab.token"]`, the `(layer="cli", detail="--token")` record is correctly attributed.

10. **No `from __future__ import annotations`** (architecture line 1045 / CLAUDE.md). Use direct types or `typing.TYPE_CHECKING` for cycles. `_render.py` imports `Settings` at module top — there is no cycle (`_settings.py` does not import `doctor/*`).

11. **Comment policy** (CLAUDE.md): only WHY when non-obvious. The non-obvious pieces in `_render.py`:
    - Why `_redact_token` is deterministic last-4 instead of `_redact.redact` regex (Constraint 3 — explain in 1-line comment).
    - Why `render_doctor_json` writes directly to `sys.stdout` instead of going through `JsonOutput.emit` (the latter takes a `RunResult`, not a `DoctorResult` — different schema, different envelope).

12. **`render_doctor_human` writes to `RichOutput.info_console`, NOT `JsonOutput.error_console`** (NFR38 stream discipline). The configuration + checks tables go to stdout. Errors raised by the surrounding `try` block still flow through `output.error(...)` → stderr. No interleaving (single-threaded sequential code keeps the discipline easy).

### Configuration-section rendering layout (AC4, AC8)

Human form via `rich.table.Table`:

```
                Configuration
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Setting              ┃ Value       ┃ Layer ┃ Detail                   ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ strategy             │ branch-prefix │ cli │ --strategy               │
│ provider             │ gitlab      │ default │ default                │
│ project_id           │ 999         │ env   │ CI_PROJECT_ID            │
│ default_branch       │ None        │ default │ default                │
│ gitlab.endpoint      │ https://... │ env   │ SEMVERTAG_GITLAB__ENDPOINT │
│ gitlab.token         │ ***XXXX     │ env   │ SEMVERTAG_TOKEN          │
│ ...                  │ ...         │ ...   │ ...                      │
└──────────────────────┴─────────────┴───────┴──────────────────────────┘

                Checks
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Check            ┃ Status ┃ Cause                                    ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ token            │ passed │ Token recognized by GitLab API.          │
│ scopes           │ passed │ Token carries 'api' scope.               │
│ project_access   │ passed │ Project visible: project_id=999.         │
│ protected_tags   │ passed │ Protected-tag configuration is readable. │
└──────────────────┴────────┴──────────────────────────────────────────┘
```

The exact column widths and box style are Rich defaults — `Table(title=...)` with auto-sizing. Tests should NOT pin glyph-level column widths; they should assert on substrings (e.g., `assert "gitlab.token" in result.stdout`, `assert "***XXXX" in result.stdout`).

JSON form (single line; pretty-printed here for the spec only):

```json
{
  "schema_version": "1.0",
  "configuration": {
    "strategy": { "value": "branch-prefix", "layer": "cli", "detail": "--strategy" },
    "provider": { "value": "gitlab", "layer": "default", "detail": "default" },
    "project_id": { "value": "999", "layer": "env", "detail": "CI_PROJECT_ID" },
    "default_branch": { "value": "None", "layer": "default", "detail": "default" },
    "gitlab.endpoint": { "value": "https://gitlab.example.test", "layer": "env", "detail": "SEMVERTAG_GITLAB__ENDPOINT" },
    "gitlab.token": { "value": "***XXXX", "layer": "env", "detail": "SEMVERTAG_TOKEN" }
  },
  "checks": [
    { "name": "token", "status": "passed", "cause": "Token recognized by GitLab API." },
    { "name": "scopes", "status": "passed", "cause": "Token carries 'api' scope." },
    { "name": "project_access", "status": "passed", "cause": "Project visible: project_id=999." },
    { "name": "protected_tags", "status": "passed", "cause": "Protected-tag configuration is readable." }
  ]
}
```

The JSON output uses `separators=(",", ":")` (matches `_output.JsonOutput.emit:48`) — no whitespace, single line.

### Coverage interaction

| File | Target |
|---|---|
| `semvertag/doctor/_checks.py` | 100% line + 100% branch (existing Story 3.1 gate; unchanged). |
| `semvertag/doctor/__init__.py` | trivially 100% (existing; unchanged). |
| `semvertag/doctor/_render.py` | **NEW**: included in `just test-doctor`'s `--cov=semvertag.doctor` scope. 100% branch via combined `test_doctor_render.py` + integration tests. |
| `semvertag/__main__.py` | global ≥85% line gate (existing); `_doctor_command` covered by integration tests in `tests/integration/test_cli_doctor.py`. |
| `semvertag/strategies/branch_prefix.py` | 100% line + branch (Story 1.6 gate; unchanged). |
| `semvertag/strategies/conventional_commits.py` | 100% line + branch (Story 2.1 gate; unchanged). |
| `semvertag/providers/gitlab.py` | ≥85% line (existing; unchanged — not touched by this story). |
| `tests/**/*.py` | not measured. |

**Coverage gate verification commands:**

- `just test` — global ≥85% line coverage; should land at ~93-94% line after this story.
- `just test-branch-strategies` — Story 1.6 100% branch on `branch_prefix.py`.
- `just test-cc-strategies` — Story 2.1 100% branch on `conventional_commits.py`.
- `just test-doctor` — Story 3.1 100% branch on `semvertag/doctor` (now includes `_render.py`). **Edit `Justfile:31-32` to add `tests/unit/test_doctor_render.py` to the recipe's positional argument list** — without the addition the new render file won't reach 100% branch coverage on its own (integration tests can pad lines but not necessarily every branch).

### Files this story touches

| File | Action | Notes |
|---|---|---|
| `semvertag/doctor/_render.py` | **NEW** | `DoctorResult`, `ConfigSourceView`, `_redact_token`, `_format_setting_value`, `build_doctor_result`, `render_doctor_human`, `render_doctor_json`. ~80-120 LOC. |
| `semvertag/__main__.py` | **UPDATE** | Add `_doctor_command` registered via `@MAIN_APP.command("doctor")`; add `_collect_doctor_overrides` helper; add doctor-related imports. Preserve existing main-callback exception handlers byte-identical. |
| `tests/unit/test_doctor_render.py` | **NEW** | Unit tests for `build_doctor_result`, redaction rule, dataclass field ordering. ~6-9 cases. |
| `tests/integration/test_cli_doctor.py` | **NEW** | Integration tests for the four chain outcomes × human + JSON forms; help-text test; token-redaction test. ~9-12 cases. |
| `Justfile` | **UPDATE** | Extend `test-doctor` recipe to include `tests/unit/test_doctor_render.py`. |
| `_bmad/sprint-status.yaml` | **UPDATE** | `3-2-…: backlog → ready-for-dev → in-progress → review` (final transition to `done` happens via `code-review`). Update `last_updated_note`. |
| `_bmad/3-2-doctor-typer-subcommand-and-json-form.md` (this file) | **UPDATE** | Status, all task/subtask checkboxes, Dev Agent Record, File List, Change Log. |
| `_bmad/deferred-work.md` | **UPDATE** (post-review only) | Append `## Deferred from: story 3-2-…` for any non-blocking decisions / discovered edge cases. |
| **Do-not-touch** (Epic 3 scope guardrails) | — | `semvertag/providers/gitlab.py`, `semvertag/providers/_base.py`, `semvertag/doctor/_checks.py`, `semvertag/_types.py`, `semvertag/_errors.py`, `semvertag/_settings.py`, `semvertag/_output.py`, `semvertag/_transport.py`, `semvertag/_redact.py`, `semvertag/_use_case.py`, `semvertag/_commit_parse.py`, `semvertag/ioc.py`, `semvertag/strategies/*.py`, all existing tests, `pyproject.toml`. |

### Testing standards

(Architecture §Test Architecture lines 548–581; carried forward from Stories 1.5/1.7/2.1/3.1.)

- **Unit tests for pure logic, integration tests for the wired CLI.** `tests/unit/test_doctor_render.py` covers `build_doctor_result` redaction + field ordering. `tests/integration/test_cli_doctor.py` covers the wired `semvertag doctor` invocation under `CliRunner` + `MockTransport`.
- **`CliRunner` + `httpx2.MockTransport`** (`tests/integration/conftest.py:55-69`). Reuse `install_mock_transport`, `cli_env`, `cli_runner` fixtures. Do NOT spin up a real `httpx2.Client` against a live endpoint.
- **Stub `Provider`** (`tests/unit/test_doctor_checks.py:_StubProvider` from Story 3.1) is NOT used by Story 3.2's tests — the integration tests use the real `GitLabProvider` against `MockTransport`, and the unit tests construct `Settings` + canned `CheckResult` lists without a provider at all.
- **Test function naming:** `test_<verb>_<outcome>_when_<condition>` (architecture line 911).
- **`typing.Final` on every module-level constant** in the test file (Story 1.2 conftest precedent / `auto-typing-final` discipline).
- **No `unittest.mock`** — integration tests use the `MockTransport` seam; unit tests construct values directly.
- **Reuse `tests/conftest.py:GITLAB_PROJECT_ID`, `GITLAB_ENDPOINT`, `GITLAB_TOKEN`** rather than redeclaring; the existing fixtures already monkeypatch the env correctly via `cli_env`.

### Anti-patterns to avoid

(Architecture §Anti-Patterns lines 1039–1049; highlighting the relevant ones for this story.)

- **`print()` in `_render.py` or `_doctor_command`** — emit via `output.info_console.print(...)` for human path and `sys.stdout.write(...)` for JSON path. `print()` would bypass Rich's redirect handling under `CliRunner`.
- **Calling `typer.Exit(...)` from `_render.py`** — exit-code mapping is `__main__.py`-only. `render_doctor_human` and `render_doctor_json` are pure rendering; the caller (`_doctor_command`) raises `typer.Exit(code=resolve_exit_code(results))`.
- **Re-declaring exit-code constants** in `_doctor_command` — use `resolve_exit_code(results)` directly; for pre-chain errors use `err.exit_code` exactly as `_main_callback` does.
- **Modifying `providers/gitlab.py`** — Epic 3 framing forbids it. If a cause-string mismatch is discovered, log it in deferred-work and let integration tests pin the current vocabulary.
- **Adding `emit_doctor` to the `Output` Protocol** — Constraint 1 above. Doctor rendering lives in `doctor/_render.py` as free functions.
- **Caching the doctor result** — every `semvertag doctor` invocation makes four fresh HTTP requests. No caching, no `lru_cache`, no on-disk artefacts. The fresh-state-per-invocation contract matches NFR4's "≤10 seconds against a single project" budget (4 × ~1s requests + render = <5s typical).
- **Async or parallel doctor checks** — architecture line 297 explicitly defers parallelism. Sequential satisfies NFR4 (10s for the full chain).
- **Catching exceptions from `provider.check_*()`** — provider contract says `check_*` returns `CheckResult` (it catches its own `httpx2.RequestError` internally via `_safe_get`). Don't paper over provider bugs in the doctor command.
- **`from __future__ import annotations`** — banned (architecture line 1045).
- **Comments restating WHAT the code does** — only WHY (CLAUDE.md).
- **Mutable default arguments** — N/A here (no kwargs with mutable defaults), but architecture line 1047 applies.

### Learnings from Story 3.1 (carried forward)

[Source: `_bmad/3-1-doctor-chain-runner-and-exit-code-dominance.md` Dev Agent Record + Review Findings]

- **Cause-fragment ownership lives in `_checks.py`, NOT `_errors.py`** (Story 3.1 Constraint 4). The fragments shadow `providers/gitlab.py`'s vocabulary; if Story 3.2 integration tests catch a drift between fragment text and actual provider output, log it in `Dev Agent Record §Debug Log References` AND in `_bmad/deferred-work.md` — but **do not** edit `providers/gitlab.py` (Epic 3 framing). The fix lands in a later epic.
- **Story 3.1 deferred-work item: "Multi-family cause-string routing bypasses `_DOMINANCE` order"** (`_bmad/deferred-work.md:119`). Hypothetical given current GitLab provider emits one cause per check, but Story 3.2 integration tests against the real provider should pin the current single-family behavior. If a test reveals a multi-family cause, escalate immediately.
- **Story 3.1 deferred-work item: "Cause-fragment matching is substring + case-sensitive"** (`_bmad/deferred-work.md:121`). For Story 3.2's integration tests, the cause strings are produced by the real `GitLabProvider` against `MockTransport`, so the fragments match exactly. No special handling needed in Story 3.2; the substring discipline is internally consistent.
- **`auto-typing-final` rewrites `yield None` → `return None`** in fixtures (Story 1.2 precedent). Pre-annotate `typing.Final` on every test-level constant.
- **Pyright trips on `typing.Final` for loop-local variables** (Story 3.1 Debug Log). Don't annotate `result = getattr(...)` inside `run_checks` — already not in scope for Story 3.2 (which doesn't modify `_checks.py`).
- **`ARG002 Unused method argument`** on stub-provider methods raises a lint flag — Story 3.1 used `# noqa: ARG002`. Story 3.2 doesn't need this since integration tests use the real provider.
- **`PLR2004` (magic-value-in-comparison)** on test asserts comparing exit codes to literals. Use `_EXIT_AUTH_ERROR: typing.Final = 3` style constants at the top of the test file (precedent at `tests/integration/test_cli_quiet_json_matrix.py:32-35`).
- **Test fixture drift / Click ≥8.2 / `CliRunner` quirks** — `CliRunner.invoke` returns a `Result` with `.stdout` AND `.stderr` (separate streams since Click 8.2+). Use `result.stdout` for stdout-only asserts, `result.output` for combined. Precedent at `tests/integration/test_cli_main_verb.py:44`.
- **`uv build` is a per-story acceptance bar** — run alongside `just test` and `just lint-ci` before flipping to `review` (Task 5.7-5.8).
- **`just test-doctor` recipe needs updating** to include `tests/unit/test_doctor_render.py` — pure-`_render.py` branches may not be reachable from integration tests alone. Test the recipe edit before declaring 5.6 done.

### Project Structure Notes

After this story:

- `semvertag/doctor/` grows from 2 files to 3 files (`__init__.py` + `_checks.py` + `_render.py`). Module count: previous 17 + `_render.py` = **18 code files**. Architecture's ~1,350 LOC at end of Story 3.1 grows by ~100 LOC to ~1,450 — still under NFR21's 1,500-line soft target.
- `semvertag/__main__.py` grows by ~80-100 LOC (the doctor subcommand body + helper). It is still well under any soft cap.
- `Justfile` `test-doctor` recipe is the only recipe to touch this story. Story 4.1 (CI workflow polish) may consolidate the three strict-coverage recipes into one CI step.
- Epic 3 completes with this story. The next sprint moves to Epic 4 (Public-Launch Readiness — Trust Surface, Distribution & Shadow-Mode). The next story in `sprint-status.yaml` is `4-1-ci-workflow-polish` (backlog).
- A retrospective for Epic 3 is **optional** per `sprint-status.yaml:65` (`epic-3-retrospective: optional`). Story 3.1 is short enough that a retro isn't gating, but if Story 3.2 surfaces non-trivial deferrals, kick one off.

## References

- [Source: architecture.md#Doctor Architecture lines 525–533] — sequential chain, skip-on-failure, exit-code mirroring, dominance order, JSON envelope schema-versioning
- [Source: architecture.md#Output Architecture lines 410–439] — `Output` Protocol stays at three methods; doctor renderer is informal extension
- [Source: architecture.md#Configuration Resolution lines 441–494] — `Settings._provenance` is the single source of truth for the configuration section; populated by `_settings._scan_model`
- [Source: architecture.md#Decision Impact Analysis lines 593–595] — Story 3.2 sequencing (Doctor subcommand reuses Output + Provider Protocols)
- [Source: architecture.md#Anti-Patterns to Avoid lines 1039–1049] — banned patterns
- [Source: architecture.md#Test Architecture lines 548–581] — three test layers; doctor 3.2 uses unit + integration
- [Source: architecture.md#Doctor subcommand flow lines 1270–1286] — runtime flow diagram (DoctorCheckRunner.run → output.emit_doctor → typer.Exit)
- [Source: architecture.md#Module-Component Mapping line 1189] — `Doctor ↔ Provider` consumes only the four `check_*` methods
- [Source: architecture.md#Cross-cutting NFR coverage line 1411] — single-owner per cross-cutting concern
- [Source: architecture.md#JSON Field Naming lines 866–886] — snake_case for all keys; `schema_version` always present and always first
- [Source: architecture.md#CLI Flag Naming lines 837–857] — kebab-case long-form flags; `--json`, `--quiet` boolean patterns
- [Source: architecture.md#Error Message Template lines 744–778] — named-actionable-cause format (already produced by `providers/gitlab.py`)
- [Source: epics.md#Story 3.2 lines 641–687] — original epic scoping; ACs reflected here with implementation detail
- [Source: prd.md FR29] — `semvertag doctor` validates token, scopes, project access, default-branch detection, protected-tag rules
- [Source: prd.md FR30] — Named, actionable cause on failure
- [Source: prd.md FR31] — `semvertag doctor --json` machine-readable form for CI dashboards
- [Source: prd.md FR32] — Resolved configuration source per value, with secrets redacted
- [Source: prd.md FR36] — `--quiet` suppresses non-error informational output; final result still emits (doctor has no progress to suppress, but the flag's semantics inform the renderer's no-progress-chatter rule)
- [Source: prd.md FR37 / NFR25] — Stable exit codes (0/1/2/3/4); dominance order documented under NFR25 stability surface
- [Source: prd.md NFR4] — ≤10s wall time for `semvertag doctor` against a single project
- [Source: prd.md NFR10] — Tokens never appear in stdout, stderr, log files, or doctor output (last-4 redaction or `***`)
- [Source: prd.md NFR38] — stdout/stderr stream discipline (informational to stdout, errors to stderr, no interleaving)
- [Source: 3-1-doctor-chain-runner-and-exit-code-dominance.md (Status: done)] — `run_checks` + `resolve_exit_code` pure-Python orchestration that Story 3.2 wraps
- [Source: 1-3-errors-runresult-output-redaction.md (Status: done)] — `Output` Protocol shape, `RichOutput` / `JsonOutput` construction; `_redact.redact` regex coverage
- [Source: 1-5-gitlabprovider-four-endpoints-via-httpx2.md (Status: done)] — `GitLabProvider.check_*` cause-string vocabulary the JSON envelope surfaces verbatim
- [Source: 1-7-wire-di-groups-and-typer-entrypoint.md (Status: done)] — `__main__.py` callback exception-handler pattern Story 3.2 mirrors for the doctor subcommand
- [Source: 2-1-conventional-commits-strategy-and-per-repo-switching.md (Status: done)] — `current_strategy` Factory pattern (informs how Story 3.2 resolves the provider without resolving the use-case)
- [Source: epic-1-retro-2026-05-28.md (Status: done)] — recurring lint/typing tool friction and protocol-coverage test patterns
- [Source: semvertag/__main__.py:84-170] — main callback pattern (Settings construction, overlay, error translation) that Story 3.2's `_doctor_command` mirrors
- [Source: semvertag/__main__.py:39-67] — `_collect_overrides` helper Story 3.2's `_collect_doctor_overrides` is modeled after
- [Source: semvertag/ioc.py:97-105] — `ProvidersGroup.gitlab_provider` Factory the doctor subcommand resolves
- [Source: semvertag/ioc.py:155-174] — `build_container(settings, json=...)` signature and JSON-override behavior
- [Source: semvertag/_output.py:15-78] — `Output` Protocol, `RichOutput` (info_console / error_console), `JsonOutput.emit` (one-line `json.dumps` pattern Story 3.2's `render_doctor_json` mirrors)
- [Source: semvertag/_settings.py:75, 146-153] — `Settings._provenance` private attribute and `_scan_model` recorder
- [Source: semvertag/_settings.py:190-206] — `apply_cli_overlay` records `(layer="cli", detail=flag_detail)` for every CLI-source override
- [Source: semvertag/_types.py:13-16] — `ConfigSource(layer, detail)` shape
- [Source: semvertag/_types.py:42-46] — `CheckResult(name, status, cause)` shape; JSON envelope surfaces this verbatim
- [Source: semvertag/_redact.py:6-21] — `_TOKEN_PATTERN` regex (used as defense-in-depth in the human cause cell, not as the structured-value redaction)
- [Source: semvertag/doctor/_checks.py:40-77] — `run_checks` + `resolve_exit_code` Story 3.2 consumes
- [Source: semvertag/providers/_base.py:6-17] — `Provider` Protocol shape (the four `check_*` methods Story 3.2 consumes through `run_checks`)
- [Source: semvertag/providers/gitlab.py:164-278] — `check_*` cause-string vocabulary surfaced verbatim in the JSON envelope
- [Source: tests/integration/conftest.py:23-69] — shared `cli_env`, `cli_runner`, `install_mock_transport` fixtures Story 3.2's integration tests reuse
- [Source: tests/integration/test_cli_main_verb.py:23-31] — recording-handler wrapper pattern Story 3.2 reuses to assert no POST `/repository/tags`
- [Source: tests/integration/test_cli_quiet_json_matrix.py:32-35] — exit-code constants pattern (`_EXIT_AUTH_ERROR: typing.Final = 3`) for clean assertions
- [Source: Justfile:31-32] — current `test-doctor` recipe (extend with the new unit-test file path in Task 5.6)
- [Source: pyproject.toml:83-90] — `addopts = "--cov=. --cov-report term-missing"` (85% global gate); `[tool.coverage.run].omit` excludes `_bmad/*`, `_autosemver_reference/*`, `tests/*`
- [Source: _bmad/deferred-work.md:119, :121] — Story 3.1 deferred items relevant to Story 3.2's integration tests (multi-family cause-string routing; substring/case-sensitive fragment matching)

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context) — bmad-dev-story workflow

### Debug Log References

- **`typing.Final` on loop-local `value` in `build_doctor_result` tripped Pyright** (same trip as Story 3.1 Debug Log). Initial draft had `value: typing.Final = _format_setting_value(field_path, settings)` inside the `for` loop; Pyright reported `"Final" variable cannot be assigned within a loop`. Dropped the annotation — single-use within the loop body. Runtime semantics unchanged.
- **Pre-existing `E501` lint failure in `semvertag/doctor/_checks.py:16`** (Story 3.1's post-review patch comment was 145 chars). Story 3.1's Dev Agent Record claims `just lint-ci` clean, but the post-review patch landed without re-running the gate. Story 3.2 cannot satisfy AC14 (`just lint-ci` must pass) without fixing this. Minimal fix: wrap the 1-line comment across two lines. No behavioral change; cause-fragment ownership documentation preserved verbatim across the wrap. Constraint 15 ("no providers/gitlab.py modification") still holds — `_checks.py` is the doctor module, not gitlab.py, and the change is comment-formatting only.
- **`RUF100 Unused noqa: SLF001`** on the test-side `assert ... settings._provenance.keys()`. Per `pyproject.toml:80`, `tests/**/*.py` already has `SLF001` in per-file-ignores, so the noqa is redundant. Ruff `--fix` auto-removed it.
- **`PLR2004` on `len(payload["checks"]) == 2`** in `test_render_doctor_json_writes_single_line_envelope_to_stdout` — magic value 2. Promoted to `_RENDER_FIXTURE_CHECK_COUNT: typing.Final = 2` constant at module top (same precedent as `_EXIT_AUTH_ERROR` etc. in `tests/integration/test_cli_quiet_json_matrix.py:32-35`).
- **Rich Console under `CliRunner` strips ANSI / picks fallback width** — `is_terminal` returns False under the runner, so Tables emit plain ASCII. For unit tests of `render_doctor_human`, I construct `rich.console.Console(file=buffer, width=200, force_terminal=False)` against an `io.StringIO` buffer to capture deterministic output. The `width=200` keeps cells from auto-wrapping in narrow buffers.
- **`render_doctor_json` writes directly to `sys.stdout`** (not via the resolved `Output` — `JsonOutput.emit` takes a `RunResult`, not a `DoctorResult`). Documented inline as a 1-line WHY comment in `_render.py`. The doctor-side JSON path is distinct from the main-verb JSON envelope; sharing the JsonOutput protocol would require a doctor-result variant, which would couple the Output protocol to a doctor-specific shape (architecture line 531 explicitly defers to "informal extension").
- **`_redact_token` is deterministic last-4, NOT regex-based** — the `_redact.redact(...)` regex (`_redact.py:6-21`) is for free-text leakage detection in cause strings / error messages. The structured `ConfigSourceView.value` slot needs a deterministic rendering: `"***"` for short/empty secrets, `"***" + secret_value[-4:]` for 4+ char secrets. Inline 2-line WHY comment in `_render.py` clarifies the split (Constraint 3 from the spec).
- **`render_doctor_human` still applies `_redact(...)` to the cause cell** as defense-in-depth — Constraint 4 of the spec said `providers/gitlab.py` already produces redaction-safe text, but a future provider could leak. Cheap insurance.

### Completion Notes List

- All 15 ACs (AC1–AC15) verified by **35 new tests** (23 unit `test_doctor_render.py` + 12 integration `test_cli_doctor.py`). Full suite: **424 tests passed** (Story 3.1 baseline 389, +35 net add), 0 regressions. Story 3.1's existing 33 doctor-checks tests pass unchanged.
- Coverage: `semvertag/doctor/_render.py` **100% line + 100% branch** (new file under existing `just test-doctor` recipe); `semvertag/doctor/_checks.py` stays **100% line + 100% branch** (Story 3.1 gate preserved); strategy gates (1.6, 2.1) preserved at 100% branch; global **93%** line (above 85% NFR22 gate).
- **No changes to** `providers/gitlab.py`, `_types.py`, `_errors.py`, `_settings.py`, `_output.py`, `_redact.py`, `_use_case.py`, `_transport.py`, `_commit_parse.py`, `ioc.py`, `providers/_base.py`, `strategies/*.py`, or `doctor/_checks.py` (except a 1-line comment-wrap fix for the pre-existing `E501` regression — see Debug Log References). Constraint 15 (Epic 3 framing) held.
- **DoctorResult envelope schema_version locked to `"1.0"`** — first instance of the doctor JSON contract. Future changes follow NFR25 deprecation cycle (Constraint 2). The envelope's three top-level keys (`schema_version`, `configuration`, `checks`) ship in declared dataclass-field order; `dataclasses.asdict()` preserves the order; tests pin it on every path.
- **`ConfigSourceView` field order pinned**: `value`, `layer`, `detail`. Asserted in unit test via `dataclasses.fields(ConfigSourceView)` and again on the nested asdict output. Future rename / reorder would break a tight test suite.
- **Token redaction at construction time, NOT render time** (Constraint 3 / NFR10). `_redact_token` runs inside `build_doctor_result` → `_format_setting_value`; by the time the value reaches `ConfigSourceView.value`, it is already `"***XXXX"` form. Integration test `test_redacts_token_to_last_four_in_both_human_and_json_output` asserts the raw `glpat-XXXXXXXXXXXXXXXXXXXX` never appears in stdout, stderr, or the JSON envelope, on both human and JSON paths.
- **`_doctor_command` mirrors `_main_callback` exception translation byte-identical** (Constraint 7). All five `except` clauses (`pydantic.ValidationError`, `ImportError`, `SemvertagError`, `BrokenPipeError`, `OSError(EPIPE)`) carry the same `output.error(str(err))` + `raise typer.Exit(code=err.exit_code) from err` shape as the main callback. The chain-result-derived exit code uses `raise typer.Exit(code=resolve_exit_code(results))` (Story 3.1's resolver) inside the `with container:` block.
- **Use-case never instantiated on the doctor path** (Constraint 8 / AC9). `_doctor_command` resolves `ProvidersGroup.gitlab_provider` directly, not `UseCasesGroup.semvertag_use_case`. Verified by every integration test's `_assert_no_post_to_tags(recorded)` invariant — no `POST /api/v4/projects/{id}/repository/tags` request was recorded in any doctor invocation.
- **CLI overlay reuses `apply_cli_overlay`** unchanged (Constraint 9). The `--token` flag overlay correctly records `(layer="cli", detail="--token")` in `_provenance`, surfaced verbatim in the doctor configuration section. Integration test `test_emits_json_envelope_with_passed_checks_when_overlay_sets_token_via_flag` pins this end-to-end.
- **No new DI Group** (Constraint 8). The doctor subcommand consumes existing `ProvidersGroup.gitlab_provider` and `OutputsGroup.rich_output` (the latter overridden to `JsonOutput` when `json_flag=True`, via `build_container(settings, json=True)`). No `DoctorGroup`, no `DoctorRunner` class — the chain runner is a pure function (Story 3.1) and the renderer is a pure function (this story).
- **Output protocol unchanged** (Constraint 1). `Output` Protocol still carries `progress`, `emit`, `error` — no `emit_doctor` method added. Doctor rendering lives in `doctor/_render.py` as free functions `render_doctor_human(result, output)` and `render_doctor_json(result)`.
- **`just test-doctor` recipe extended** to include `tests/unit/test_doctor_render.py` (Justfile:31-32). Without the addition, `_render.py`'s `render_doctor_human` and `render_doctor_json` would not reach 100% branch from `test_doctor_checks.py` alone (which exercises only the chain runner, not the renderer).
- **Pre-existing `_checks.py` lint regression discovered and fixed** (Debug Log References item 2). Story 3.1's post-review 1-line ownership comment was 145 chars long; Story 3.1 claimed `lint-ci` clean but the post-review patch wasn't re-gated. Wrapped to two lines; no behavioral change, no semantic change. Flagged for inclusion in Story 3.1's retrospective notes / `_bmad/deferred-work.md` if Epic 3 retro is run.
- **Cause-fragment substring matching held in real provider integration** (Story 3.1 deferred item, `_bmad/deferred-work.md:121`). Integration test scenarios exercise each cause-fragment family: AC6 (`Token rejected`), AC7 (`Token missing 'api' scope`), AC12 #6 (`GitLab project not found`), AC12 #7 (`Token cannot read protected_tags`), plus AC9-equivalent `Unexpected GitLab response` via the 500-status test. No cross-family cause routing observed — the hypothetical multi-family concern from Story 3.1's deferred-work item remains hypothetical for the current provider.

### File List

- **New:** `semvertag/doctor/_render.py` (62 stmts, 12 branches — `DoctorResult`, `ConfigSourceView`, `_redact_token`, `_format_setting_value`, `build_doctor_result`, `render_doctor_human`, `render_doctor_json`, `__all__`).
- **New:** `tests/unit/test_doctor_render.py` (23 cases — 18 for `build_doctor_result` / dataclass field ordering / token redaction; 5 for `render_doctor_human` and `render_doctor_json` direct invocation).
- **New:** `tests/integration/test_cli_doctor.py` (12 cases — four chain outcomes × human/JSON forms + token redaction round-trip + `--help` + project-id-missing config error + CLI-overlay token flag + provider-API-error via 500 retries).
- **Modified:** `semvertag/__main__.py` (added imports for `run_checks`, `resolve_exit_code`, `build_doctor_result`, `render_doctor_human`, `render_doctor_json`; added `_collect_doctor_overrides` helper; added `@MAIN_APP.command("doctor")` `_doctor_command` function — exception-translation block byte-identical to `_main_callback`'s).
- **Modified:** `Justfile` (extended `test-doctor` recipe positional argument list to include `tests/unit/test_doctor_render.py`).
- **Modified:** `semvertag/doctor/_checks.py` (1-line comment wrap — pre-existing E501 regression from Story 3.1 post-review patch). No behavioral change.
- **Modified:** `_bmad/sprint-status.yaml` (`3-2-…: backlog → ready-for-dev → in-progress → review`).
- **Modified:** `_bmad/3-2-doctor-typer-subcommand-and-json-form.md` (this file — Status, all task/subtask checkboxes, Dev Agent Record, File List, Change Log).
- **No-change confirmed:** `semvertag/providers/gitlab.py`, `semvertag/providers/_base.py`, `semvertag/_types.py`, `semvertag/_errors.py`, `semvertag/_settings.py`, `semvertag/_output.py`, `semvertag/_redact.py`, `semvertag/_use_case.py`, `semvertag/_transport.py`, `semvertag/_commit_parse.py`, `semvertag/ioc.py`, `semvertag/strategies/*.py`, all existing tests, `pyproject.toml`.

### Change Log

- 2026-05-29 — Created `semvertag/doctor/_render.py` with `DoctorResult` + `ConfigSourceView` frozen dataclasses (kw_only, slots), `_redact_token` (deterministic last-4), `_format_setting_value` (walks dotted `Settings._provenance` keys), `build_doctor_result(settings, checks)`, `render_doctor_human(result, output)` (two Rich tables to `output.info_console`), `render_doctor_json(result)` (single-line `json.dumps(asdict(...))` to `sys.stdout`). Field order locked: `(schema_version, configuration, checks)` for `DoctorResult`; `(value, layer, detail)` for `ConfigSourceView`. `schema_version` defaults to `"1.0"`.
- 2026-05-29 — Wired `@MAIN_APP.command("doctor")` `_doctor_command` in `semvertag/__main__.py`. Flag surface: `--project-id`, `--provider`, `--token`, `--default-branch`, `--gitlab-endpoint`, `--request-timeout`, `--json`. Exception translation byte-identical to `_main_callback` (validation/import/SemvertagError/EPIPE). Resolves `ProvidersGroup.gitlab_provider` directly (no use-case construction); calls `run_checks(provider) → build_doctor_result(settings, results) → render_doctor_*(...)`; raises `typer.Exit(code=resolve_exit_code(results))`.
- 2026-05-29 — Added `_collect_doctor_overrides` helper in `__main__.py` (mirrors `_collect_overrides` but drops `--strategy` and `--quiet` slots — neither affects doctor's behavior; listing them on `doctor --help` would be misleading).
- 2026-05-29 — Authored 23 unit tests in `tests/unit/test_doctor_render.py`: field-order pins (2), redaction rules (3: long token / empty / short), non-secret rendering (4: string / int / float / bool), defaults (1), CLI-overlay round-trip (3: strategy / nested token / env layer), provenance coverage (1), schema-version constant (1), `asdict` ordering (2), check-list pass-through (1), Rich-render direct invocation (3: sections / config rows / check rows), JSON-render direct invocation (2: single-line / compact separators). All `@pytest.mark.usefixtures("clean_settings_env")` decorated where Settings is constructed.
- 2026-05-29 — Authored 12 integration tests in `tests/integration/test_cli_doctor.py`: `_doctor_handler` factory with per-endpoint status/payload knobs; `_recording_wrapper` for invariant assertions; tests cover all-pass human + JSON, fail-at-token human + JSON, fail-at-scopes JSON, fail-at-project_access JSON, fail-at-protected_tags JSON, token-redaction both forms, `--help`, project-id-missing config error, CLI `--token` overlay JSON, and provider-API error via 500 with retry sleeps mocked. Every test asserts `_assert_no_post_to_tags(recorded)` to verify use-case never reaches the write path.
- 2026-05-29 — Extended `Justfile:31-32` `test-doctor` recipe to include `tests/unit/test_doctor_render.py` alongside `tests/unit/test_doctor_checks.py`. Without the extension, `_render.py`'s rendering functions don't reach the 100% branch gate from chain-runner tests alone.
- 2026-05-29 — Fixed pre-existing E501 lint regression in `semvertag/doctor/_checks.py:16` (Story 3.1's post-review 1-line comment was 145 chars; wrapped to two lines). No behavioral change; cause-fragment ownership comment preserved verbatim across the wrap.
- 2026-05-29 — All gates green: `just lint-ci` clean (eof-fixer + ruff format + ruff check + ty check); `just test` 424 passed (global 93% line, above 85% gate); `just test-branch-strategies` 100% branch (Story 1.6 preserved); `just test-cc-strategies` 100% branch (Story 2.1 preserved); `just test-doctor` 100% branch on `semvertag/doctor` (chain runner + renderer covered); `uv build` clean (wheel + sdist). Status flipped `in-progress → review`.
