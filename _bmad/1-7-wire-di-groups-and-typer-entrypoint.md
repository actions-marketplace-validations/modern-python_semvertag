# Story 1.7: Wire DI groups + Typer entrypoint to deliver the `uvx semvertag` flow

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a GitLab CI user,
I want to run `uvx semvertag` (or `semvertag --json --quiet`) inside a GitLab CI job and get a semver tag created on the default branch, with stable exit codes and proper stream discipline,
So that I have a working end-to-end product for Journey 1 before bump-strategy alternatives, doctor, and trust-surface land.

## Acceptance Criteria

### AC1 — `semvertag/ioc.py` defines four `modern_di.Group` subclasses with lazy `Factory` resolution

**Given** `semvertag/ioc.py` is a new module
**When** I import it
**Then** it exposes exactly four `Group` subclasses with these factory members:

- `SettingsGroup.settings: providers.Factory[Settings]` — `scope=Scope.APP`, constructs `Settings` from env (the entrypoint replaces this with a post-CLI-overlay instance via the container's `context` parameter at run time; see Dev Notes §Container construction for the injection pattern).
- `OutputsGroup.rich_output: providers.Factory[RichOutput]` — creator `_build_rich_output(settings)`; reads `settings.quiet` (or equivalent run-time flag; see Dev Notes §Output selection).
- `OutputsGroup.json_output: providers.Factory[JsonOutput]` — creator `_build_json_output(settings)`.
- `ProvidersGroup.gitlab_provider: providers.Factory[GitLabProvider]` — creator `_build_gitlab_provider(settings)`; lazy-imports `semvertag.providers.gitlab.GitLabProvider` and `semvertag._transport.RetryingTransport`; constructs an `httpx2.Client(transport=RetryingTransport(...), base_url=settings.gitlab.endpoint, timeout=settings.request_timeout)`.
- `StrategiesGroup.branch_prefix_strategy: providers.Factory[BranchPrefixStrategy]` — creator `_build_branch_prefix_strategy(settings)`; returns `BranchPrefixStrategy(config=settings.branch_prefix)`.

**And** `ALL_GROUPS: typing.Final[list[type[modern_di.Group]]] = [SettingsGroup, OutputsGroup, ProvidersGroup, StrategiesGroup]` is exported at module scope.

**And** only the active provider Factory and the active strategy Factory are resolved per CLI run — `_build_gitlab_provider` and `_build_branch_prefix_strategy` use **lazy imports** at the provider/strategy module boundary so importing `ioc.py` does not import `gitlab.py` or `branch_prefix.py` until resolution.

### AC2 — `semvertag/_use_case.py:SemvertagUseCase` orchestrates the happy path

**Given** `_use_case.py` is a new module
**When** I import it
**Then** it exposes a frozen dataclass:

```python
@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class SemvertagUseCase:
    provider: Provider
    strategy: BumpStrategy
    output: Output

    def run(self) -> RunResult: ...
```

**And** `run()` implements this sequence against a GitLab project where the latest commit on `main` is `Merge branch 'feature/foo' into main` and the most recent semver tag is `1.4.2`:

1. `provider.get_latest_commit_on_default_branch()` → `Commit(sha="abc1234", message="Merge branch 'feature/foo' into main")`
2. `provider.list_tags()` → `[Tag(name="1.4.2", commit_sha="...prev..."), ...]`
3. Filter `list_tags()` result to semver-conforming tags (per FR8); pick the highest semver-valued tag (not the first by API order — order is not guaranteed across providers).
4. `strategy.decide(latest_commit)` → `Bump.MINOR`
5. Compute new version from `last_tag` + `bump`: `1.4.2` + minor → `1.5.0` (use `semver.Version.parse(last_tag.name).bump_minor()`).
6. `provider.create_tag(name="1.5.0", commit_sha="abc1234")`
7. `output.emit(RunResult(strategy="branch-prefix", bump="minor", status="created", tag="1.5.0", commit="abc1234", reason=None))`
8. Return the same `RunResult` from `run()` (returning enables unit-tests of `run()` without parsing output streams).

**And** `output.progress(...)` is called at least once before each provider call (e.g., `"Detected strategy: branch-prefix"`, `"Fetching latest commit on main..."`, `"Computing bump..."`) — these are no-ops for `JsonOutput` per the Output protocol.

### AC3 — `already_tagged` short-circuit emits `status="already_tagged"` and the entrypoint exits 0

**Given** `provider.list_tags()` returns a tag whose `commit_sha` equals `provider.get_latest_commit_on_default_branch().sha`
**When** `use_case.run()` is invoked
**Then** the use case **skips** the `strategy.decide(...)` and `create_tag(...)` calls
**And** emits `RunResult(strategy=<active>, bump="none", status="already_tagged", tag=<existing-tag-name>, commit=<sha>, reason="Latest commit already tagged.")`
**And** `__main__.py` translates the absence of any raised exception into exit 0.

### AC4 — `no_merge_commit` short-circuit (branch-prefix v1.0)

**Given** the latest commit message does not contain `settings.branch_prefix.merge_mark_text` (e.g., a direct push), so `strategy.decide(commit)` returns `Bump.NONE`
**When** `use_case.run()` is invoked
**Then** the use case **skips** the `create_tag(...)` call
**And** emits `RunResult(strategy="branch-prefix", bump="none", status="no_merge_commit", tag=None, commit=<sha>, reason="Latest commit on default branch is not a merge commit.")`
**And** the entrypoint exits 0.

> **v1.0 mapping note:** branch-prefix is the only wired strategy. `Bump.NONE` under `branch-prefix` always maps to `status="no_merge_commit"`. Story 2.1 introduces `status="no_conforming_commit"` as the `Bump.NONE` mapping under `conventional-commits`; the use case dispatch on `self.strategy.name` is the recommended extension point. Do NOT inspect `commit.message` in the use case — that duplicates the strategy logic and is the anti-pattern Story 1.6's review explicitly flagged.

### AC5 — `no_tags` short-circuit when the repo has zero pre-existing tags

**Given** `provider.list_tags()` returns `[]` (no tags at all) **or** all returned tags are non-semver-conforming and the filtered list is empty (FR8)
**When** `use_case.run()` is invoked
**Then** the use case **skips** the `create_tag(...)` call
**And** emits `RunResult(strategy=<active>, bump="none", status="no_tags", tag=None, commit=<sha>, reason="No prior semver-conforming tags found; not seeding an initial tag in v1.0.")`
**And** the entrypoint exits 0.

> **v1.0 scope:** seeding `0.1.0` on a tagless repo is out of scope; document this in the help text or migration docs in Story 4.4/4.5.

### AC6 — `__main__.py` is the Typer entrypoint declared in `[project.scripts]`

**Given** `pyproject.toml` `[project.scripts]` already declares `semvertag = "semvertag.__main__:main"` (set in Story 1.1)
**When** I invoke `semvertag --help` (post-`uv sync`)
**Then** the help text lists **at minimum** the following flags (long form only; FR33–FR39):

- `--project-id <int>` — overrides `settings.project_id` / `CI_PROJECT_ID`
- `--strategy <branch-prefix|conventional-commits>` — overrides `settings.strategy`
- `--provider <gitlab|github|bitbucket>` — overrides `settings.provider`
- `--token <STRING>` — overrides `settings.gitlab.token` (when active provider is `gitlab`); routed through `pydantic.SecretStr` at overlay time
- `--default-branch <name>` — overrides `settings.default_branch`
- `--gitlab-endpoint <url>` — overrides `settings.gitlab.endpoint`
- `--request-timeout <float>` — overrides `settings.request_timeout`
- `--json` — selects `JsonOutput`
- `--quiet` — suppresses progress narrative (final result still emits)
- `--install-completion [shell]` — typer-built-in
- `--version` — prints `importlib.metadata.version("semvertag")` then exits 0

**And** `__main__.py` declares `MAIN_APP: typing.Final = typer.Typer(...)` (note `typing.Final` annotation per architecture §Module-Level Constants).
**And** the entrypoint is invokable via `python -m semvertag` (the `if __name__ == "__main__":` block is required so `python -m semvertag` works locally for debugging).

### AC7 — Single exception→exit-code conversion point in `__main__.py`

**Given** any `SemvertagError` subclass is raised at any depth during `use_case.run()`
**When** the `__main__.py` callback catches it
**Then** the redacted error message (via `_output.py:redact()` already applied by `output.error()`) is printed to **stderr** through `output.error(str(err))`
**And** `raise typer.Exit(code=err.exit_code) from err` propagates the documented exit code:

- `SemvertagError` (base) → 1 (generic failure)
- `ConfigError` → 2
- `AuthError` → 3
- `ProviderAPIError` → 4

**And** **no other module** in `semvertag/` calls `typer.Exit(...)` or `sys.exit(...)` — exit-code mapping happens at exactly one place (architecture §Cross-cutting concerns line 1216).

**And** `BrokenPipeError` / `OSError` on stdout writes (e.g., `semvertag ... | head -1`) are caught at the entrypoint boundary and produce exit 0 (POSIX convention; resolves deferred-work entry from Story 1.3 about `BrokenPipeError`).

### AC8 — Integration tests in `tests/integration/test_cli_main_verb.py` exercise the four use-case outcomes via `CliRunner` + injected `MockTransport`

**Given** `tests/integration/test_cli_main_verb.py` is a new file
**When** the test suite runs
**Then** it contains at minimum these tests, each invoking the entrypoint via `typer.testing.CliRunner` with a `httpx2.MockTransport` composed via `tests/conftest.py::compose_handler`:

1. `test_creates_tag_when_latest_commit_is_feature_merge_and_prior_tag_exists` — happy path; latest commit message `Merge branch 'feature/foo' into main`; prior tag `1.4.2`; assert exit 0, stdout contains `Created tag 1.5.0`, the POST to `/repository/tags` includes `{"tag_name": "1.5.0", "ref": <sha>}`.
2. `test_skips_with_already_tagged_when_latest_commit_sha_matches_latest_tag` — AC3 path; assert exit 0, stdout contains `already_tagged`.
3. `test_skips_with_no_merge_commit_when_latest_commit_is_not_a_merge` — AC4 path; latest commit message is `Fix typo in README` (no `Merge branch` marker); assert exit 0, stdout contains `no_merge_commit`.
4. `test_skips_with_no_tags_when_repo_has_zero_semver_conforming_tags` — AC5 path; `list_tags` returns `[]`; assert exit 0, stdout contains `no_tags`.
5. `test_emits_json_envelope_with_schema_version_first_when_json_flag_set` — `--json` form of test 1; assert exactly one line on stdout, parse as JSON, first key `schema_version: "1.0"`, all five top-level fields present.

**And** the tests inject the MockTransport by **overriding the http client factory** in the container — see Dev Notes §Test integration seam for the exact pattern (a `build_container(settings, *, inner_transport=None) -> Container` helper).

### AC9 — Integration tests in `tests/integration/test_cli_quiet_json_matrix.py` exercise the `(--quiet, --json)` 2×2 cells and the five exit-code paths

**Given** `tests/integration/test_cli_quiet_json_matrix.py` is a new file
**When** the test suite runs
**Then** the four cells of `(--quiet absent/present)` × `(--json absent/present)` are exercised against the same fixture (latest commit is a feature merge, prior tag `1.4.2`, expected result `1.5.0`):

| Test | Flags | stdout assertion | stderr assertion |
|---|---|---|---|
| `test_emits_progress_and_human_result_when_no_flags` | `[]` | contains progress lines + `Created tag 1.5.0` | empty |
| `test_emits_only_human_result_when_quiet` | `--quiet` | does NOT contain any `Detected strategy:` / `Fetching` progress lines; DOES contain `Created tag 1.5.0` | empty |
| `test_emits_progress_text_to_stdout_and_one_json_line_when_json_only` | `--json` | one parsable JSON line; no progress text (progress is a no-op on JsonOutput per architecture §Output Architecture) | empty |
| `test_emits_only_json_envelope_when_quiet_and_json` | `--quiet --json` | exactly one line, JSON-parsable, first key `schema_version` | empty |

**And** the five FR37 exit codes are each covered by at least one test in this file:

| Exit | Scenario | How to trigger |
|---|---|---|
| 0 (created) | Happy path (`test_emits_progress_and_human_result_when_no_flags`) | Default handler |
| 0 (no-op) | `already_tagged` / `no_merge_commit` / `no_tags` (any one of AC8 tests 2–4 is sufficient) | Override handler |
| 1 | Generic `SemvertagError` raised anywhere (e.g., a deliberate stub provider that raises bare `SemvertagError("oops")`) | Monkeypatch one provider method |
| 2 | `ConfigError` (e.g., GitLab 404 → `ConfigError` per `gitlab.py:_translate_status`) | Override handler to return 404 for `GET /api/v4/projects/{id}` |
| 3 | `AuthError` (GitLab 401) | Override handler to return 401 |
| 4 | `ProviderAPIError` (GitLab 5xx after retry exhaustion; or 429 after retries) | Override handler to return 503 on every call; tests already use `_transport.time.sleep` no-op monkeypatch — see `test_gitlab_provider.py:848-849` precedent |

### AC10 — `pyproject.toml [project.scripts] semvertag = "semvertag.__main__:main"` produces a working console script and `uvx semvertag` is the documented invocation

**Given** `pyproject.toml [project.scripts]` already declares the console script (Story 1.1; pre-existing line 29)
**When** I run `uv sync && uv run semvertag --help` (or `uv build && uvx --from ./dist/semvertag-*.whl semvertag --help`)
**Then** the help text from AC6 appears with exit 0.
**And** `python -m semvertag --help` produces the same help (alternate invocation path for local dev).

> Resolves the Story 1.1 deferred-work entry: "`semvertag` console script references missing `semvertag.__main__:main` [pyproject.toml:34] — Story 1.7 lands the typer entrypoint; bootstrap intentionally ships package skeleton only." After this story, the console-script reference resolves to a real callable.

### AC11 — `just test` passes; full suite green; no regressions in Stories 1.1–1.6

**Given** `just test` is run from a fresh checkout post-`uv sync`
**When** the full pytest suite completes
**Then**:

- All existing unit tests pass unchanged (stories 1.1–1.6: settings, errors, output, redact, transport-retry, branch-prefix-strategy, gitlab-provider, smoke).
- New integration tests from AC8 and AC9 pass.
- `pytest --cov` reports **≥85% line coverage** overall (`pyproject.toml:83` global gate).
- `just test-branch-strategies` continues to report **100% branch coverage** on `semvertag/strategies/branch_prefix.py` (the Story 1.6 gate must not regress).
- `just lint-ci`, `uv run ty check`, and `uv build` all complete clean.

**And** the Story 1.5 regression canary (full `tests/integration/test_gitlab_provider.py` suite) passes unchanged — no edits to `_transport.py`, `providers/gitlab.py`, `_errors.py`, `_output.py`, `_redact.py`, `_types.py`, `strategies/branch_prefix.py`, `strategies/conventional_commits.py`, `strategies/_base.py`, or `providers/_base.py` are made in this story.

## Tasks / Subtasks

- [ ] **Task 1: Add `project_id` to `Settings` with `CI_PROJECT_ID` env alias (AC6, AC8 cells 2-4)** — minimal edit to `semvertag/_settings.py`; preserves Story 1.2's regression canary.
  - [ ] 1.1 Add field `project_id: int | None = pydantic.Field(default=None)` to top-level `Settings` (NOT to `GitLabConfig`; keeps provider configs symmetric — GitHub/Bitbucket would have their own repo-identifier fields in v1.x).
  - [ ] 1.2 Extend the token-alias machinery in `_settings.py` to also alias `SEMVERTAG_PROJECT_ID` with fallback `CI_PROJECT_ID` (add to a new `_PROJECT_ID_ALIASES` constant; route through the existing `_TOKEN_ALIASES_BY_PATH` pattern OR via `validation_alias=pydantic.AliasChoices(...)` on the field — both are spec-compliant; pick whichever surfaces in `_provenance` correctly).
  - [ ] 1.3 Update `tests/unit/test_settings.py` and `tests/unit/test_provenance.py` to confirm: (a) `project_id` defaults to `None`, (b) `SEMVERTAG_PROJECT_ID=42` resolves to `42` with provenance `("env", "SEMVERTAG_PROJECT_ID")`, (c) `CI_PROJECT_ID=42` resolves to `42` with provenance `("env", "CI_PROJECT_ID")` only when `SEMVERTAG_PROJECT_ID` is absent.
  - [ ] 1.4 Confirm Story 1.2's 10 settings tests still pass byte-for-byte (no field renames, no default changes to existing fields).

- [ ] **Task 2: Author `semvertag/_use_case.py:SemvertagUseCase` (AC2, AC3, AC4, AC5)**
  - [ ] 2.1 Create the module with global imports per CLAUDE.md (`import dataclasses; import typing; import semver`).
  - [ ] 2.2 Declare the frozen dataclass shape per AC2 (frozen=True, slots=True, kw_only=True; fields typed against the protocols `Provider`, `BumpStrategy`, `Output`).
  - [ ] 2.3 Implement `run() -> RunResult` orchestrating the happy path per AC2 step list.
  - [ ] 2.4 Add the `_pick_latest_semver_tag(tags: list[Tag]) -> Tag | None` helper that filters to semver-conforming names (use `semver.Version.parse` in a try/except; `semver.VersionInfo.is_valid` is also acceptable) and returns the highest by semver ordering, NOT by list position (FR8).
  - [ ] 2.5 Add the `_compute_new_version(last_tag: Tag, bump: Bump) -> str` helper using `semver.Version.parse(last_tag.name).bump_minor()` / `.bump_patch()` / `.bump_major()`.
  - [ ] 2.6 Add the `_status_for_no_bump(strategy_name: str) -> str` helper returning `"no_merge_commit"` for `strategy_name == "branch-prefix"` (Story 2.1 will extend to `"no_conforming_commit"` for `"conventional-commits"`).
  - [ ] 2.7 Wire the short-circuits: `already_tagged` (AC3) before `strategy.decide`; `no_tags` (AC5) when `_pick_latest_semver_tag` returns `None`; `no_merge_commit` (AC4) when `bump is Bump.NONE`.
  - [ ] 2.8 Emit progress lines via `output.progress(...)` between steps (no progress emission inside no-op short-circuits except the entrypoint status line, to keep `--json` runs fully quiet).
  - [ ] 2.9 Call `output.emit(result)` exactly once at the end and `return result` so unit tests can assert on the return value without parsing streams.

- [ ] **Task 3: Author `semvertag/ioc.py` Groups (AC1)**
  - [ ] 3.1 Module-level imports: `import typing; import modern_di; from modern_di import providers, Scope; from semvertag._settings import Settings`. NO imports from `semvertag.providers.*` or `semvertag.strategies.*` at module scope — those are lazy inside creator functions (architecture §Import Style line 961).
  - [ ] 3.2 Declare `SettingsGroup(modern_di.Group)` with `settings = providers.Factory(scope=Scope.APP, creator=Settings)`. The entrypoint will supersede this via the container's `context={Settings: post_overlay_settings}` parameter — see Dev Notes §Container construction.
  - [ ] 3.3 Declare `OutputsGroup(modern_di.Group)` with `rich_output` and `json_output` factories; creators take `settings: Settings` and call `_output.build_rich_output(quiet=...)` / `_output.build_json_output(quiet=...)`. The `quiet` flag flows from `settings` — see Dev Notes §Output selection.
  - [ ] 3.4 Declare `ProvidersGroup(modern_di.Group)` with `gitlab_provider = providers.Factory(scope=Scope.APP, creator=_build_gitlab_provider)`. The `_build_gitlab_provider(settings: Settings) -> Provider` creator: lazy-imports `RetryingTransport` and `GitLabProvider`; constructs the `httpx2.Client`; raises `ConfigError("Project id missing. Set CI_PROJECT_ID or pass --project-id.")` if `settings.project_id is None`.
  - [ ] 3.5 Declare `StrategiesGroup(modern_di.Group)` with `branch_prefix_strategy = providers.Factory(scope=Scope.APP, creator=_build_branch_prefix_strategy)`. Creator returns `BranchPrefixStrategy(config=settings.branch_prefix)` after lazy-importing.
  - [ ] 3.6 Optional but recommended: add `UseCasesGroup` with `semvertag_use_case = providers.Factory(scope=Scope.APP, creator=SemvertagUseCase)` so the entrypoint resolves a single `SemvertagUseCase` instance — modern-di will wire `provider`, `strategy`, `output` automatically from the Protocol-typed parameter signatures. (Verify by reading `modern-di-typer/tests/test_commands.py` for the dependency-resolution pattern.)
  - [ ] 3.7 Export `ALL_GROUPS: typing.Final[list[type[modern_di.Group]]] = [SettingsGroup, OutputsGroup, ProvidersGroup, StrategiesGroup, UseCasesGroup]` (omit `UseCasesGroup` if Task 3.6 skipped — explain why in dev notes).
  - [ ] 3.8 Add `build_container(settings: Settings, *, inner_transport: httpx2.BaseTransport | None = None) -> modern_di.Container` factory function that constructs the container with `context={Settings: settings}` and (when `inner_transport` is provided) registers an override for the http client factory. This is the **test integration seam** — see Dev Notes.

- [ ] **Task 4: Author `semvertag/__main__.py` Typer entrypoint (AC6, AC7, AC10)**
  - [ ] 4.1 Module preamble per architecture §Module-Level Constants: `MAIN_APP: typing.Final = typer.Typer(name="semvertag", help="...", no_args_is_help=False, add_completion=True)`.
  - [ ] 4.2 Define the single `main` callback (Typer "command" or "callback" — callback works for a single-verb CLI; subcommand pattern arrives in Story 3.2 for `doctor`). Signature: takes all flags from AC6 as `typer.Option` defaults; takes no positional args (FR33).
  - [ ] 4.3 Inside `main()`: env-resolve `Settings()`; collect non-None CLI flag values into a `dict[str, tuple[Any, str]]` matching `apply_cli_overlay` signature (`{"project_id": (value, "--project-id"), "strategy": (value, "--strategy"), ..., "gitlab.endpoint": (value, "--gitlab-endpoint"), "gitlab.token": (pydantic.SecretStr(value), "--token")}`); call `apply_cli_overlay(settings, overrides)`.
  - [ ] 4.4 Construct the container via `ioc.build_container(settings)`; resolve `SemvertagUseCase` (or compose it manually from resolved Provider/Strategy/Output if Task 3.6 was skipped); call `use_case.run()` inside the container's `with` block (modern_di Container is a context manager — see `_autosemver_reference/__main__.py:35-36` for the precedent).
  - [ ] 4.5 Wrap the resolve+run in a try/except: catch `SemvertagError`, route message through `output.error(str(err))`, then `raise typer.Exit(code=err.exit_code) from err`. (See Dev Notes §Exception → exit-code mapping for why the `from err` chaining matters per architecture §Exception Construction Patterns.)
  - [ ] 4.6 Catch `BrokenPipeError` / `OSError` (e.g., `OSError` with `errno.EPIPE`) at the same boundary and silently exit 0 — resolves Story 1.3 deferred-work item.
  - [ ] 4.7 Add the `--version` option (uses `typer.Option(..., callback=version_callback, is_eager=True)`); callback reads `importlib.metadata.version("semvertag")` and `typer.echo(version)` then `raise typer.Exit()`.
  - [ ] 4.8 Add the `if __name__ == "__main__":` block invoking `MAIN_APP()` (allows `python -m semvertag` to work locally for debugging; matches `_autosemver_reference/__main__.py:34-36` pattern). Use `# pragma: no cover` on that block to match the reference precedent — it's exercised by the integration tests via CliRunner, not by import.

- [ ] **Task 5: Integration tests — main verb (AC8)**
  - [ ] 5.1 Create `tests/integration/test_cli_main_verb.py` with module preamble `_RUNNER: typing.Final = CliRunner(mix_stderr=False)` (separate stdout/stderr — required for FR38 assertions).
  - [ ] 5.2 Add a `@pytest.fixture` for `cli_env(monkeypatch)` that sets `SEMVERTAG_TOKEN`, `SEMVERTAG_PROJECT_ID`, `SEMVERTAG_GITLAB__ENDPOINT` to the values from `tests/conftest.py` so the CLI can resolve settings without explicit flags. (Use `monkeypatch.setenv` per pytest convention.)
  - [ ] 5.3 Add a `@pytest.fixture` for `cli_container(monkeypatch)` that monkeypatches `ioc.build_container` (or directly patches the http client construction inside `_build_gitlab_provider`) so tests can inject `MockTransport` per AC8. **Alternative pattern (recommended):** add a `SEMVERTAG_INNER_TRANSPORT` sentinel attribute on a test-only module that `_build_gitlab_provider` consults — but this leaks test plumbing into production code. The clean pattern is `monkeypatch.setattr(ioc, "build_container", lambda s: real_build_container(s, inner_transport=transport))` — keeps production code unaware of tests. **See Dev Notes §Test integration seam for the recommended choice.**
  - [ ] 5.4 Implement the five tests listed in AC8 using `compose_handler` from `tests/conftest.py` to override individual endpoints.
  - [ ] 5.5 Each test asserts `result.exit_code`, `result.stdout`, and (where applicable) `result.stderr` separately; use `result.stdout.strip().splitlines()` to assert line counts for `--json` tests.

- [ ] **Task 6: Integration tests — quiet/json matrix and exit codes (AC9)**
  - [ ] 6.1 Create `tests/integration/test_cli_quiet_json_matrix.py` with the same `_RUNNER` and fixtures from Task 5 (extract them to `tests/integration/conftest.py` if both files use them).
  - [ ] 6.2 Implement the four quiet/json cells per AC9's table.
  - [ ] 6.3 Implement the five exit-code tests:
    - `test_exits_with_one_on_generic_semvertag_error` — `monkeypatch` `SemvertagUseCase.run` to raise `SemvertagError("synthetic generic failure for AC9.")`.
    - `test_exits_with_two_on_config_error_via_404` — override `GET /api/v4/projects/{id}` to 404; assert exit 2 and the redacted error message ends with `Verify CI_PROJECT_ID or --project-id.` (matches `gitlab.py:306`).
    - `test_exits_with_three_on_auth_error_via_401` — override to 401; assert exit 3 and the error message starts with `Token rejected: 401.`.
    - `test_exits_with_four_on_provider_api_error_via_503_after_retry_exhaustion` — override every GET to 503; monkeypatch `_transport.time.sleep` and `_transport.random.uniform` to no-ops (see `tests/integration/test_gitlab_provider.py:848-849, 862-863, 876-877` for the precedent); assert exit 4.

- [ ] **Task 7: `Justfile`, `pyproject.toml`, and `_bmad/deferred-work.md` updates (AC10, AC11)**
  - [ ] 7.1 No changes expected to `pyproject.toml` `[project.scripts]` — line 29 already declares it correctly.
  - [ ] 7.2 Confirm `Justfile::test` recipe (`uv run --no-sync pytest {{ args }}`) does not need adjustment — `addopts = "--cov=. --cov-report term-missing"` from `pyproject.toml:83` already exercises the new integration tests under coverage.
  - [ ] 7.3 If you find `setup-uv` cache issues in CI (Story 1.1 deferred-work line 17), do NOT fix here — it is Story 4.1's scope.
  - [ ] 7.4 Append a new section `## Deferred from: story 1-7-wire-di-groups-and-typer-entrypoint (<DATE>)` to `_bmad/deferred-work.md` and record:
    - Any non-blocking decisions you took (e.g., "did NOT add a `--no-color` flag; deferred to v1.x per architecture §Configuration Resolution v1.x layer").
    - The `output_format` selection mechanism trade-off you picked (see Dev Notes §Output selection).
    - The container's http client lifecycle approach you chose (Dev Notes §Client lifecycle).

- [ ] **Task 8: Run the full local validation gate (AC11)**
  - [ ] 8.1 `just install` (fresh sync).
  - [ ] 8.2 `just lint-ci` — must be clean.
  - [ ] 8.3 `just test` — full suite must pass; coverage ≥85%.
  - [ ] 8.4 `just test-branch-strategies` — Story 1.6 gate must report 100% branch on `branch_prefix.py`.
  - [ ] 8.5 `uv run ty check` — clean.
  - [ ] 8.6 `uv build` — clean.
  - [ ] 8.7 `uv run semvertag --help` — confirm AC6's flag list appears.
  - [ ] 8.8 `uv run python -m semvertag --help` — same output.
  - [ ] 8.9 Update `_bmad/sprint-status.yaml`: `1-7-wire-di-groups-and-typer-entrypoint: ready-for-dev` → `in-progress` → `review` (the bmad-code-review step bumps to `done`).
  - [ ] 8.10 Update this story file: tick all task/subtask checkboxes; fill in Dev Agent Record sections; bump Status to `review`.

## Dev Notes

### Story framing

This story is **Step 7 of the architecture's Implementation Sequence** (architecture.md line 592). It closes Epic 1 — Foundation & First Auto-Tag (GitLab + branch-prefix) — by composing every primitive Stories 1.1–1.6 built into a single end-to-end `uvx semvertag` invocation. There is no new domain logic in this story; it is wiring, error-handling routing, and integration testing.

The deliverable: a user in a GitLab CI job can run `uvx semvertag` (or `semvertag --json --quiet`) and get a semver tag created on the default branch, with FR37-stable exit codes and FR38-clean stream discipline. After this story, Journey 1 of the PRD is **deliverable in isolation** — Stories 2.1, 3.x, 4.x add capabilities (conventional-commits, doctor, trust surface) on top of an already-working product.

### Architecture section pointers (for the dev agent's quick lookup)

- §DI & Dependency Boundary — architecture.md lines 535–547 — Groups (`SettingsGroup`, `ProvidersGroup`, `StrategiesGroup`, `OutputsGroup`); lazy resolution; `[github]`/`[bitbucket]` packaging extras dropped from v1.0.
- §Implementation Patterns §DI Group Conventions — lines 804–836 — Group naming (plural + `Group` suffix); `ALL_GROUPS` typing; active-selection-at-use-case-construction pattern (not via DI cleverness).
- §Decision Impact Analysis §Implementation sequence — lines 584–595 — Step 7 wiring sits between Step 6 (strategies — Story 1.6) and Step 8 (doctor — Story 3.x).
- §Integration Points & Data Flow §Startup data flow — lines 1222–1238 — the env+CLI→Settings→Container→Use Case chain (the exact path `__main__.py` implements).
- §Integration Points & Data Flow §Main verb run-time flow — lines 1240–1268 — the `provider.get_default_branch` / `get_latest_commit_on_default_branch` / `list_tags` / `strategy.decide` / `create_tag` sequence the use case must implement.
- §Integration Points & Data Flow §Error flow — lines 1288–1310 — the `httpx2.* → SemvertagError → typer.Exit(code=N)` chain; **`__main__.py` is the one place exit codes are mapped** (FR37, architecture §Cross-cutting concerns line 1216).
- §Error Model & Exit Codes — lines 379–408 — exit-code-to-exception-subclass mapping (`SemvertagError`→1, `ConfigError`→2, `AuthError`→3, `ProviderAPIError`→4); redaction defense-in-depth (NFR10).
- §Output Architecture — lines 410–439 — Output protocol; two `rich.Console` instances per impl; `--quiet` + `--json` additive composition (final result always emits); stream discipline (no interleaving).
- §Configuration Resolution — lines 441–494 — Settings shape; CLI overlay via `.model_copy(update=...)`; `apply_cli_overlay` helper already implemented in `_settings.py:164-180`.
- §CLI Flag Naming — lines 837–851 — `--project-id` (not `--project_id`); nested-config flags flatten to top-level kebab-case (`--gitlab-endpoint`, not `--gitlab.endpoint`); long-form only at v1.0.
- §Provider Implementation Pattern — lines 972–1003 — GitLabProvider's `Provider` protocol surface; methods the use case calls: `get_default_branch`, `get_latest_commit_on_default_branch`, `list_tags`, `create_tag`.
- §Strategy Implementation Pattern — lines 1005–1017 — BranchPrefixStrategy's frozen-dataclass shape; the `decide(commit) -> Bump` signature.
- §Frozen-Dataclass Conventions — lines 695–727 — `frozen=True, slots=True, kw_only=True` for the new `SemvertagUseCase`.
- §Project Structure §Complete Project Directory Structure — lines 1055–1167 — `__main__.py`, `_use_case.py`, `ioc.py` projected locations.
- §Anti-Patterns to Avoid — lines 1039–1049 — every banned pattern, especially: `print()` outside `_output.py`; bare `Exception` catches; module-level singletons of stateful clients (the http client MUST be per-CLI-run-scoped — DI is correct here, module global is wrong); exit-code mapping outside `__main__.py`.

### Critical architectural constraints

1. **One exception → exit code mapping point** (architecture §Cross-cutting concerns line 1216 + §Error flow line 1303). `__main__.py` is the only module that calls `typer.Exit(...)`. Use cases, providers, strategies, and outputs `raise SemvertagError(...)` and never touch exit codes.

2. **Lazy provider/strategy imports** (architecture §Import Style line 961). `ioc.py` must NOT import `semvertag.providers.gitlab` or `semvertag.strategies.branch_prefix` at module scope — those imports live inside the creator functions. This preserves the "only active provider/strategy is constructed per CLI run" guarantee from AC1 and the epic, and supports the "non-active provider files can be missing/stubbed in v1.0" architecture (architecture lines 539–541, 661–663).

3. **One HTTP retry choke point** (architecture §Cross-cutting concerns line 1215). All http2 client construction routes through `RetryingTransport`. The `_build_gitlab_provider` creator constructs `RetryingTransport()` and wraps it in `httpx2.Client(transport=...)`. No other module instantiates `httpx2.Client` directly except tests.

4. **CLI overlay records `("cli", "--<flag>")` provenance** (architecture §Configuration Resolution line 492 + `_settings.py:apply_cli_overlay:164-180`). The entrypoint MUST pass `(value, "--strategy")` (the flag form, with leading double-dash) as the second tuple element — this is the format doctor (Story 3.2) renders. Inconsistent provenance detail strings break Story 3.2 down the line.

5. **`pydantic.SecretStr` for `--token` overlay** (architecture §Anti-Patterns line 1044). The `--token` flag value must be wrapped in `pydantic.SecretStr(...)` at overlay time (before `apply_cli_overlay`) so the SecretStr defense-in-depth holds throughout the run.

6. **`--quiet --json` composes additively** (architecture §Output Architecture line 437; PRD FR36). `--quiet` suppresses progress; `--json` selects format; both together emit exactly one JSON line on stdout with no progress chatter. **Test this matrix explicitly in AC9.**

7. **`mix_stderr=False` on CliRunner** (architecture §Test Architecture line 553). The default `CliRunner()` merges stderr into stdout. FR38 mandates separation, and AC9 cells assert separately — so every integration test in this story MUST construct `CliRunner(mix_stderr=False)`.

8. **`semver.Version` for bump arithmetic** — the `semver` package is already a dependency (`pyproject.toml:22`). Use `semver.Version.parse(name).bump_minor()`. Do NOT hand-roll the parsing (the existing `_autosemver_reference/use_cases/autosemver_use_case.py:52` precedent uses `semver.Version.parse(name)`).

### Container construction

The entrypoint constructs the container with the post-CLI-overlay Settings injected via the `context` parameter. modern-di's `Container.__init__(context={Settings: my_instance})` registers the instance such that any Factory creator with a `settings: Settings` parameter receives it (see `modern_di/container.py:46`'s `context_registry`). The shape:

```python
def build_container(
    settings: Settings,
    *,
    inner_transport: httpx2.BaseTransport | None = None,
) -> modern_di.Container:
    context: dict[type, typing.Any] = {Settings: settings}
    if inner_transport is not None:
        context[httpx2.BaseTransport] = inner_transport
    return modern_di.Container(groups=ALL_GROUPS, context=context)
```

The `_build_gitlab_provider` creator then optionally pulls the inner transport from the context (or constructs a real `RetryingTransport()` if absent). This is the test integration seam — integration tests pass `inner_transport=httpx2.MockTransport(handler)` and production runs pass nothing.

> **Verify** the `context={httpx2.BaseTransport: inner}` injection path actually resolves through modern-di's type-based lookup. If it doesn't (because modern-di only looks up by registered Factory bound_type, not arbitrary types), fall back to: have `_build_gitlab_provider` accept an optional `transport` parameter that defaults to `None`, and have `build_container` register an `httpx2.BaseTransport` Factory via `Container.overrides_registry` when a test transport is provided. The `modern_di/registries/overrides_registry.py` API is the production-side seam for this. **Pick whichever pattern actually works** — both are spec-compliant and Story 4.x's polishing scope.

### Output selection

The Output factory dispatch (RichOutput vs JsonOutput) has two viable shapes:

**Option A — single Factory with conditional creator:**

```python
class OutputsGroup(modern_di.Group):
    output = providers.Factory(creator=_build_output)

def _build_output(settings: Settings) -> Output:
    if settings.output_format == "json":
        return build_json_output(quiet=settings.quiet)
    return build_rich_output(quiet=settings.quiet)
```

This requires `output_format` and `quiet` fields on `Settings`. Both can be set via CLI overlay only (no env-friendly representation — keep them as transient Settings fields with no env alias OR keep them outside Settings entirely and pass to `_build_output` via the container's context).

**Option B — two Factories, entrypoint picks:**

```python
class OutputsGroup(modern_di.Group):
    rich_output = providers.Factory(creator=_build_rich_output)
    json_output = providers.Factory(creator=_build_json_output)
```

The entrypoint resolves the right one based on the `--json` flag.

**Recommendation: Option B.** It mirrors the ProvidersGroup pattern (one Factory per implementation; entrypoint picks based on the CLI flag), keeps Settings free of presentation-layer concerns, and works without polluting Settings with transient fields. Pass `quiet` from the CLI to the creator via the container's context (`context={Settings: settings, "quiet": flag_value}`) **or** add `quiet: bool = False` to Settings — both work, but adding to Settings means it's recorded in provenance, which is useful for doctor.

> Whichever you pick: document the choice in `_bmad/deferred-work.md` (Task 7.4) so Story 3.2 (`semvertag doctor`) knows how to re-use the same Output construction.

### Test integration seam

The MockTransport seam is the single most important pattern this story establishes — every future integration test will use it. **Get it right.**

Recommended pattern (drop-in for both `test_cli_main_verb.py` and `test_cli_quiet_json_matrix.py`):

```python
# tests/integration/conftest.py (NEW)
import collections.abc
import typing

import httpx2
import pytest
from typer.testing import CliRunner

from semvertag import ioc
from semvertag._settings import Settings
from tests.conftest import HandlerCallable, default_handler


_RUNNER: typing.Final = CliRunner(mix_stderr=False)


@pytest.fixture
def cli_runner() -> CliRunner:
    return _RUNNER


@pytest.fixture
def cli_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEMVERTAG_TOKEN", "glpat-XXXXXXXXXXXXXXXXXXXX")
    monkeypatch.setenv("SEMVERTAG_PROJECT_ID", "999")
    monkeypatch.setenv("SEMVERTAG_GITLAB__ENDPOINT", "https://gitlab.example.test")


@pytest.fixture
def patched_container(monkeypatch: pytest.MonkeyPatch) -> collections.abc.Callable[[HandlerCallable], None]:
    """Returns a function that, given a MockTransport handler, monkeypatches ioc.build_container
    so the produced container wires up the GitLabProvider against the handler."""
    real_build_container = ioc.build_container

    def install(handler: HandlerCallable) -> None:
        transport = httpx2.MockTransport(handler)
        monkeypatch.setattr(
            ioc,
            "build_container",
            lambda settings: real_build_container(settings, inner_transport=transport),
        )

    return install
```

Then in tests:

```python
def test_creates_tag_when_latest_commit_is_feature_merge(
    cli_env: None,
    patched_container: collections.abc.Callable[[HandlerCallable], None],
    cli_runner: CliRunner,
) -> None:
    patched_container(_handler_for_happy_path())
    from semvertag.__main__ import MAIN_APP
    result = cli_runner.invoke(MAIN_APP, [])
    assert result.exit_code == 0
    assert "Created tag 1.5.0" in result.stdout
    assert result.stderr == ""
```

**The handler shape** is composed from `tests.conftest.default_handler` via `compose_handler` from `tests/conftest.py` — Story 1.5 already established the pattern; reuse it.

### Exception → exit-code mapping

The flow at the entrypoint:

```python
try:
    with container:  # container is a context manager (autosemver_reference precedent)
        use_case = container.resolve(SemvertagUseCase)
        use_case.run()
except SemvertagError as err:
    output.error(str(err))                     # redacted via _output.redact() inside output.error
    raise typer.Exit(code=err.exit_code) from err
except (BrokenPipeError, OSError) as err:
    if isinstance(err, OSError) and err.errno != errno.EPIPE:
        raise  # not a pipe error; bubble to Typer's default handler
    raise typer.Exit(code=0) from None
```

**Why `from err` matters** (architecture §Exception Construction Patterns line 791): preserves the original exception's traceback chain through `__cause__` for debugging. **Why `from None` for pipe errors:** the OS-level pipe-closure is not interesting; suppressing the `__context__` keeps tracebacks clean for downstream consumers (e.g., `semvertag | head -1`).

**The `output` instance is needed inside the except clause.** Build it before the try-block:

```python
output = _resolve_output_from_flags(settings, output_format, quiet)  # constructed early
try:
    container = ioc.build_container(settings)
    with container:
        use_case = container.resolve(SemvertagUseCase)
        use_case.run()
except SemvertagError as err:
    output.error(str(err))
    raise typer.Exit(code=err.exit_code) from err
```

Or resolve output from the container — but then catch the exception path needs an extracted fallback for early-container-failure cases (e.g., a malformed CLI overlay raises `ValueError` inside `apply_cli_overlay`). Easier: construct output early.

### Client lifecycle

`httpx2.Client` must be closed at end of run. Two acceptable patterns:

1. **modern-di `CacheSettings` finalizer:** register the client Factory with `cache_settings=providers.CacheSettings(finalizer=lambda c: c.close())` so when the container is closed (its `__exit__` runs), the client's `close()` fires. This is the production-grade path.

2. **`with container:` context manager** (autosemver_reference precedent at `_autosemver_reference/__main__.py:35-36`): the Container's `__enter__`/`__exit__` already handles cleanup of all `CacheSettings` finalizers. Combining this with (1) gives clean per-CLI-run lifecycle.

For tests, `MockTransport` has no IO to close, so the finalizer is a no-op — safe to register unconditionally.

> Document the chosen lifecycle pattern in deferred-work (Task 7.4). It will inform Story 3.x's doctor-subcommand client construction.

### Learnings from Stories 1.1–1.6 (carried forward)

[Source: 1-1, 1-2, 1-3, 1-4, 1-5, 1-6 — all Dev Agent Records + Review Findings]

- **Architecture sketches leave seams unspecified.** Stories 1.2 (`model_validator(mode="before")` for AliasChoices), 1.3 (`error()` method on Output), 1.4 (`inner` injection seam on RetryingTransport), 1.5 (`_request_failed_message` helper), 1.6 (the `_pick_latest_semver_tag` shape we're recommending here) all added structural seams the sketches didn't name. **For this story:** expect to discover at least one additional seam — most likely around (a) how the container injects MockTransport (test seam), (b) how the entrypoint passes `quiet`/`output_format` to the Output factory, or (c) how `project_id=None` is gated (ConfigError at use-case start vs. at provider construction). Document each seam in Dev Notes + Debug Log References.
- **Auto-typing-final aggressively rewrites code.** Pre-annotate `typing.Final` on every module-level constant — including in the new test files. Story 1.2's conftest got auto-rewritten unexpectedly when constants were missing the annotation.
- **`tests/**/*.py` per-file-ignores include `S101` + `SLF001`** (pyproject.toml:80). New integration tests use `assert` freely (S101 ignore) and may need to reach into `_transport`/`ioc` internals for monkeypatching (SLF001 ignore covers that).
- **`uv build` is a per-story acceptance bar** (Story 1.1 review patch). Run alongside `just test` before marking review (Task 8.6 covers this).
- **Code-review cycle produces Patches / Deferred / Dismissed buckets.** Story 1.3 took 8 patches; Story 1.4 fewer; Story 1.5 took 17 patches plus 8 deferred items; Story 1.6 took 0 patches + 9 deferred. **This story is bigger than 1.6 (multiple new files, integration tests with real CLI invocations, container plumbing).** Expect a non-trivial patch count. Mitigate by hitting `just lint-ci` + `uv build` + `just test` clean before flipping to `review`.
- **`# pragma: no cover` is a smell — get to coverage by writing real tests** (Story 1.5 lesson). Exception: the `if __name__ == "__main__":` block in `__main__.py` is the documented exception (matches `_autosemver_reference/__main__.py:34-36` precedent — the block is exercised by `python -m semvertag`, not by import-time test execution).
- **`tests/conftest.py` (top-level) is the integration-fixture surface** (Story 1.5 introduced it). New integration tests **import from `tests.conftest`** (`GITLAB_PROJECT_ID`, `GITLAB_ENDPOINT`, `default_handler`, `compose_handler`) — do NOT redefine these constants locally.
- **`tests/unit/conftest.py` exists** but unit tests do NOT depend on `tests/conftest.py` (Story 1.6 lesson). The story's integration tests live under `tests/integration/`, so `tests/conftest.py` IS available to them via standard pytest scoping. If you extract shared CLI fixtures, the natural home is a new `tests/integration/conftest.py`.
- **`pytest -o "addopts="` in Justfile recipes overrides `pyproject.toml addopts` but NOT `PYTEST_ADDOPTS` env var** (Story 1.6 review note). This story does not introduce new Justfile recipes (Task 7.2 confirms), so the concern does not apply here.
- **GitLab integration tests reach into `_transport` to monkeypatch `time.sleep` / `random.uniform`** (Story 1.5 deferred-work). The 5xx-retry test in AC9 must use the same pattern (`tests/integration/test_gitlab_provider.py:848-849, 862-863, 876-877` for the precedent).
- **Settings-layer fields with default values are backward-compat additions** (Story 1.2 stability stance). Adding `project_id: int | None = None` in Task 1.1 does NOT break Story 1.2's 10 settings tests; verify with `just test tests/unit/test_settings.py` before proceeding.
- **AliasChoices vs. manual env-resolution split** (Story 1.2 deferred-work). `_settings.py` already has both: token aliases use the `model_validator(mode="before")` + `_TOKEN_ALIASES_BY_PATH` pattern; non-token fields use pydantic-settings' built-in env resolution. For `project_id` + `CI_PROJECT_ID`, the cleanest path is to extend the token-alias pattern (it surfaces in `_provenance` correctly out of the box) — but `validation_alias=pydantic.AliasChoices(...)` would also work if you handle provenance recording separately. Pick whichever surfaces in `_provenance` correctly without a refactor; document the choice.

### Coverage interaction

This story's new files have the following coverage targets:

| File | Target |
|---|---|
| `semvertag/_use_case.py` | ≥85% line (global gate). Branch coverage NOT required (no 100% gate on use-case files). |
| `semvertag/ioc.py` | ≥85% line. Lazy imports inside creator functions count as branches but are exercised by AC8 tests. |
| `semvertag/__main__.py` | ≥85% line. The `if __name__ == "__main__":` block is `# pragma: no cover` per the autosemver_reference precedent. |
| `tests/integration/test_cli_main_verb.py` | Not measured (`tests/*` in `[tool.coverage.run] omit`). |
| `tests/integration/test_cli_quiet_json_matrix.py` | Not measured. |
| `semvertag/_settings.py` | Maintains current coverage (Story 1.2's gate). Task 1.3 adds new tests for `project_id` aliasing — verify global ≥85% still passes. |

> **Coverage gate verification command:** `just test` produces the term-missing report. `just test-branch-strategies` continues to scope only to `branch_prefix.py` (Story 1.6's gate); it should remain green.

### Anti-patterns to avoid

(Architecture §Anti-Patterns to Avoid lines 1039–1049 — every bullet applies here. Highlighting the ones this story is most likely to trip over:)

- **`print()` anywhere outside `_output.py`** — including in `__main__.py` and `_use_case.py`. Route everything through `output.progress(...)` / `output.emit(...)` / `output.error(...)`.
- **Bare `Exception` catches** — catch `SemvertagError`, `BrokenPipeError`, `OSError` specifically; let everything else bubble (Typer prints a traceback, which is fine for "should-not-happen" failures).
- **Module-level singletons of stateful clients** — no `_GITLAB_CLIENT: typing.Final = httpx2.Client(...)` at module scope in `ioc.py`. The client is a per-CLI-run resource constructed inside the Factory creator.
- **`sys.exit(...)` outside `__main__.py`** — and even there, prefer `typer.Exit(code=...)` (the architecture-mandated form, lines 381, 1306).
- **Multi-paragraph docstrings or comments restating WHAT the code does** — CLAUDE.md / architecture §Comment Policy. The only place comments are appropriate in this story: explaining WHY `from err` vs `from None` for the BrokenPipeError path; explaining WHY the http client lifecycle uses CacheSettings finalizer if non-obvious.
- **`from __future__ import annotations`** — keep annotations evaluated; use `typing.TYPE_CHECKING` for forward refs.

### Files this story touches

| File | Action | Notes |
|---|---|---|
| `semvertag/_use_case.py` | **NEW** | `SemvertagUseCase` frozen dataclass; `run() -> RunResult` orchestration. |
| `semvertag/ioc.py` | **NEW** | Four `modern_di.Group` subclasses + `UseCasesGroup`; `ALL_GROUPS`; `build_container(settings, *, inner_transport=None)` helper. |
| `semvertag/__main__.py` | **NEW** | Typer entrypoint; `MAIN_APP` constant; `main` callback with all flags; exception→exit-code conversion; `--version`; `--install-completion` (typer built-in); `python -m semvertag` invocation block. |
| `semvertag/_settings.py` | **UPDATE** | Add `project_id: int | None = None`; extend env-alias machinery to handle `CI_PROJECT_ID` → `SEMVERTAG_PROJECT_ID`. **Do NOT rename / re-default any existing field.** Story 1.2 regression canary must hold. |
| `tests/integration/conftest.py` | **NEW** (recommended) | `_RUNNER` constant; `cli_runner`, `cli_env`, `patched_container` fixtures shared by the two new test files. |
| `tests/integration/test_cli_main_verb.py` | **NEW** | Five tests covering AC8. |
| `tests/integration/test_cli_quiet_json_matrix.py` | **NEW** | Nine tests covering AC9 (4 cells + 5 exit codes). |
| `tests/unit/test_settings.py` | **UPDATE** | Add 2–3 tests for `project_id` + `CI_PROJECT_ID` alias resolution (Task 1.3). |
| `tests/unit/test_provenance.py` | **UPDATE** | Add provenance test for `project_id` (env via `SEMVERTAG_PROJECT_ID` vs env via `CI_PROJECT_ID` vs cli via `--project-id` vs default `None`). |
| `pyproject.toml` | **NO CHANGE** | `[project.scripts] semvertag = "semvertag.__main__:main"` already declared (line 29). |
| `Justfile` | **NO CHANGE** | Existing `test` recipe covers the new integration tests. |
| `_bmad/sprint-status.yaml` | **UPDATE** | `1-7-…: ready-for-dev` → `in-progress` → `review`; bump `last_updated_note`. |
| `_bmad/deferred-work.md` | **UPDATE** | Append a new section `## Deferred from: story 1-7-…` with the resolved decisions / non-blockers per Task 7.4. |
| `_bmad/1-7-wire-di-groups-and-typer-entrypoint.md` (this file) | **UPDATE** | Status, all task/subtask checkboxes, Dev Agent Record, File List, Change Log. |
| **Do-not-touch** (regression canaries) | — | `_transport.py`, `_errors.py`, `_redact.py`, `_output.py`, `_types.py`, `strategies/_base.py`, `strategies/branch_prefix.py`, `strategies/conventional_commits.py`, `providers/_base.py`, `providers/gitlab.py`, `tests/conftest.py`, `tests/unit/conftest.py`, `tests/unit/test_branch_prefix_strategy.py`, `tests/integration/test_gitlab_provider.py`, `tests/test_smoke.py`. |

### Testing standards

(Architecture §Test Architecture lines 548–581.)

- **Three test layers** — this story adds integration-layer tests (Layer 2). No new unit tests except the Settings updates in Task 1.3.
- **`typer.testing.CliRunner` + `httpx2.MockTransport`** — the documented Layer-2 pattern.
- **`mix_stderr=False`** on the CliRunner so FR38 assertions are checkable.
- **One assertion-cluster per test; parametrize for variations** (Story 1.6 §Testing standards).
- **Test function naming:** `test_<verb>_<outcome>_when_<condition>` (architecture line 911; Story 1.6 §Testing standards).
- **`typing.Final` on test-level constants** (architecture line 923; Story 1.6 §Testing standards) — applies to integration tests too.

### Project Structure Notes

After this story:

- `semvertag/_use_case.py`, `semvertag/ioc.py`, `semvertag/__main__.py` are complete and stable for Epic 1. Story 2.1 extends `ioc.py:StrategiesGroup` (adds `conventional_commits_strategy` Factory) and `_use_case.py:_status_for_no_bump` (adds the `"no_conforming_commit"` branch). Story 3.x extends `__main__.py` with the `doctor` subcommand registration and `ioc.py` with a new `DoctorGroup` (or extends `ProvidersGroup` if the doctor reuses the same Provider factory). Story 4.x does not modify any of these files.
- `semvertag/_settings.py` gains `project_id` + its alias chain. After this story, Settings carries 6 top-level fields (strategy, provider, default_branch, request_timeout, project_id, plus the four nested config containers) — still well under any per-module LOC concern.
- Module count after this story: `_settings.py` + `_types.py` + `_errors.py` + `_redact.py` + `_output.py` + `_transport.py` + `_use_case.py` (NEW) + `__main__.py` (NEW) + `ioc.py` (NEW) + `providers/_base.py` + `providers/gitlab.py` + `strategies/_base.py` + `strategies/branch_prefix.py` + `strategies/conventional_commits.py` = **14 substantive code files**. Architecture's projected ~1,200 LOC at end of Epic 1 remains on-track — `_use_case.py` is ~80 LOC (orchestration + helpers), `ioc.py` is ~60 LOC (5 groups + builder + ALL_GROUPS), `__main__.py` is ~120 LOC (callback signature + overlay assembly + exception handling).
- `tests/integration/test_cli_main_verb.py` and `tests/integration/test_cli_quiet_json_matrix.py` are the new integration-test surfaces. Story 3.2 mirrors them with `test_cli_doctor.py` (the third file projected in architecture line 1146).
- Story 1.7 is the **final story of Epic 1**. After Task 8.10 lands and code-review completes, sprint-status flips `epic-1-retrospective: optional` → run (or skip) at user discretion.

## References

- [Source: architecture.md#DI & Dependency Boundary lines 535–547] — Groups, lazy resolution, `[github]`/`[bitbucket]` extras dropped from v1.0
- [Source: architecture.md#Implementation Patterns §DI Group Conventions lines 804–836] — Group naming; `ALL_GROUPS` typing; active-selection pattern
- [Source: architecture.md#Decision Impact Analysis §Implementation sequence line 592] — this story is Step 7
- [Source: architecture.md#Integration Points & Data Flow §Startup data flow lines 1222–1238] — env→Settings→Container→UseCase chain
- [Source: architecture.md#Integration Points & Data Flow §Main verb run-time flow lines 1240–1268] — the provider/strategy/output call sequence the use case must implement
- [Source: architecture.md#Integration Points & Data Flow §Error flow lines 1288–1310] — exception→exit-code chain; `__main__.py` is the single mapping point
- [Source: architecture.md#Error Model & Exit Codes lines 379–408] — exit-code-to-subclass mapping; redaction defense-in-depth
- [Source: architecture.md#Output Architecture lines 410–439] — Output protocol; stream discipline; `--quiet` + `--json` composition
- [Source: architecture.md#Configuration Resolution lines 441–494] — Settings shape; CLI overlay
- [Source: architecture.md#CLI Flag Naming lines 837–851] — kebab-case flags; nested-config flattening; long-form-only at v1.0
- [Source: architecture.md#Provider Implementation Pattern lines 972–1003] — Provider protocol surface
- [Source: architecture.md#Strategy Implementation Pattern lines 1005–1017] — BumpStrategy frozen-dataclass shape
- [Source: architecture.md#Frozen-Dataclass Conventions lines 695–727] — `frozen=True, slots=True, kw_only=True`
- [Source: architecture.md#Anti-Patterns to Avoid lines 1039–1049] — every banned pattern
- [Source: architecture.md#Test Architecture lines 548–581] — three test layers; CliRunner + MockTransport
- [Source: epics.md#Story 1.7 lines 502–544] — original epic scoping; ACs reflected here with implementation detail
- [Source: prd.md FR1, FR2, FR3, FR4, FR5, FR6, FR7, FR8, FR9, FR10] — main-verb behavior
- [Source: prd.md FR33–FR39] — CLI surface & output (flags, stable exit codes, stream discipline, `--quiet --json` composition)
- [Source: prd.md NFR1, NFR2, NFR6, NFR8, NFR10, NFR25] — performance, no-op semantics, fail-closed, redaction, stability
- [Source: 1-1-bootstrap-public-scaffolding-from-modern-di.md (Status: done)] — `pyproject.toml [project.scripts] semvertag = "semvertag.__main__:main"` precondition; deferred-work line 7 resolves with this story
- [Source: 1-2-settings-layer-with-aliaschoices-and-provenance.md (Status: done)] — `Settings` shape; `apply_cli_overlay`; token-alias machinery; provenance recording
- [Source: 1-3-errors-runresult-output-redaction.md (Status: done)] — `SemvertagError` hierarchy; `RunResult`; `RichOutput`/`JsonOutput`; deferred-work item about `BrokenPipeError` at the entrypoint resolves with this story (AC7)
- [Source: 1-4-retryingtransport-with-retry-policy.md (Status: done)] — `RetryingTransport(inner=...)` constructor for tests
- [Source: 1-5-gitlabprovider-four-endpoints-via-httpx2.md (Status: done)] — `GitLabProvider(config=..., project_id=..., client=...)` constructor signature; `tests/conftest.py:GITLAB_*` constants; `compose_handler` helper; `_translate_status` exit-code mapping precedent
- [Source: 1-6-branchprefixstrategy-100-branch-coverage.md (Status: done)] — `BranchPrefixStrategy(config=settings.branch_prefix)` constructor; `BumpStrategy.decide(commit) -> Bump` protocol shape; `_types.py:Bump` enum
- [Source: _autosemver_reference/__main__.py:11-36] — Typer entrypoint pattern (`MAIN_APP: typing.Final = typer.Typer()`; `Container(groups=ioc.ALL_GROUPS)`; `modern_di_typer.setup_di`; `with container: MAIN_APP()`)
- [Source: _autosemver_reference/ioc.py:1-43] — Groups + `ALL_GROUPS` pattern; `kwargs={...}` Factory construction
- [Source: _autosemver_reference/use_cases/autosemver_use_case.py:14-62] — orchestration shape; `semver.Version.parse(...)` usage; branch-prefix logic
- [Source: modern-di-typer/main.py:24-30] — `setup_di(app, container)` API for wiring DI into Typer
- [Source: modern-di-typer/tests/test_commands.py:13-72] — `@inject` + `FromDI(...)` patterns
- [Source: modern-di/modern_di/container.py:30-55] — `Container(context={Settings: instance})` injection mechanism
- [Source: modern-di/modern_di/providers/factory.py:32-60] — `Factory(creator=..., scope=Scope.APP, cache_settings=...)` API; type-parsed kwargs from creator signature
- [Source: semvertag/_settings.py:164-180] — `apply_cli_overlay(settings, overrides)` signature; `(value, "--flag-name")` tuple format
- [Source: tests/conftest.py:1-69] — integration-fixture surface; `GITLAB_PROJECT_ID = 999`; `default_handler`; `compose_handler`; `gitlab_client` fixture pattern
- [Source: tests/integration/test_gitlab_provider.py:848-849, 862-863, 876-877] — `monkeypatch.setattr(_transport.time, "sleep", lambda *_: None)` precedent for fast retry-exhaustion tests
- [Source: pyproject.toml:29] — `[project.scripts] semvertag = "semvertag.__main__:main"`
- [Source: pyproject.toml:80] — `"tests/**/*.py" = ["S101", "SLF001"]` per-file-ignores
- [Source: pyproject.toml:83] — `addopts = "--cov=. --cov-report term-missing"`
- [Source: pyproject.toml:90] — `omit = ["_autosemver_reference/*", "_bmad/*", "tests/*"]`
- [Source: Justfile:19-26] — `test`, `test-branch`, `test-branch-strategies` recipes
- [Source: _bmad/deferred-work.md] — pre-existing entries resolved by this story (Story 1.1 line 7: console script; Story 1.3 line 30: `BrokenPipeError` at entrypoint)

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context) — bmad-dev-story workflow

### Debug Log References

### Completion Notes List

### File List

### Change Log
