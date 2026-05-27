# Deferred Work

Tracking issues raised during code review that were intentionally not fixed in-cycle. Each entry has a one-line reason for deferral so future reviews and planning can decide when to act.

## Deferred from: code review of 1-1-bootstrap-public-scaffolding-from-modern-di (2026-05-26)

- `semvertag` console script references missing `semvertag.__main__:main` [pyproject.toml:34] — Story 1.7 lands the typer entrypoint; bootstrap intentionally ships package skeleton only.
- `just install` mixes `uv lock --upgrade` with `uv sync --frozen` — every install re-locks, hurting reproducibility for new contributors. Template-inherited from modern-di; revisit if/when semvertag diverges from template's install policy.
- Duplicate `--cov` flags between `addopts = "--cov=. --cov-report term-missing"` and CI's `just test . --cov=. --cov-report xml`. Reports merge into both `term-missing` and `xml` outputs; positional `.` also overrides `testpaths = ["tests"]`. Template-inherited.
- `uv_build` build-backend unpinned (`requires = ["uv_build"]`) — future major release can break reproducible builds. Template-inherited.
- `eof-fixer .` walks repo root (`.venv/`, `_autosemver_reference/`, `_bmad/`) [Justfile:9, Justfile:20] — relies on the tool's default exclude behavior. Template-inherited; `auto-typing-final` scoping is a separate decision in the story.
- `<org>` URL placeholders in `pyproject.toml [project.urls]` and `mkdocs.yml repo_url`/`extra.social` — spec-acknowledged; pre-launch resolution per Launch Decisions Pending in prd.md.
- `codecov-action@v4.0.1` pinned to an early-v4 patch with known token-handling bugs. Template-inherited; consider bumping when next touching CI.
- No fork-safe guard on codecov upload — fork PRs lack `CODECOV_TOKEN` and the action fails noisily on every external contribution. Template-inherited.
- No `timeout-minutes` on CI jobs — runaway jobs default to GitHub's 360-minute limit. Template-inherited.
- No explicit `permissions:` block on the workflow — defaults to repo-configured `GITHUB_TOKEN` permissions; broader-than-needed blast radius. Template-inherited.
- `setup-uv` `cache-dependency-glob: "**/pyproject.toml"` misaligned with `uv lock --upgrade` running every install — cache key doesn't change on lock-only updates. Template-inherited; moot until install/lock policy changes.
- `.gitignore` carries `plan.md` entry inherited from modern-di — leaks template author's personal workflow into every downstream project. Template-inherited.
- `.gitignore` uses `__pycache__/*` rather than `__pycache__/` — ignores contents but leaves empty `__pycache__` dirs stageable. Template-inherited.
- Production dependencies (`typer`, `rich`, `semver`, `pydantic-settings`, `modern-di-typer`, `httpx2`) carry no version pins or lower bounds. NFR12 commit-lockfile policy partially mitigates installation drift but does not protect against breaking upstream releases when consumers install fresh.
- `[tool.uv.build-backend]` declares no sdist `source-exclude` — `_autosemver_reference/`, `_bmad/`, `docs/`, top-level dotfiles may all ship inside the sdist when `uv build` runs. Revisit at first PyPI publish (Story 4.2).
- Concurrency `group: ${{ github.head_ref || github.run_id }}` falls back to unique `run_id` on push events — concurrent main-branch runs are never cancelled. Template-inherited.
- `actions/checkout@v4` default `fetch-depth: 1` and no `fetch-tags: true` — fine while only the smoke test exists, but a semver-tagging tool will need git history + tags once provider tests land (Story 1.5+).
- `uv sync --all-extras` is a no-op (no `[project.optional-dependencies]` declared) [Justfile:5]. Template-inherited; harmless today but confusing for new contributors.

## Deferred from: code review of 1-3-errors-runresult-output-redaction (2026-05-27)

- Token-family coverage gaps in `_redact.py:6-11` — `gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`, AWS `AKIA`/`ASIA`, OpenAI `sk-*`, Slack `xox*`, Stripe `sk_live_*`, Azure SAS `sig=`, Bitbucket `ATCTT…`. AC7 explicitly scoped this story to four families; Task 3.3 flagged the rest for Story 1.5/3.x.
- Full git SHAs (40+ hex chars) inside error/progress messages are redacted to `***` [`_redact.py:10`] — accepted architectural trade-off; revisit when token-family expansion happens.
- `BrokenPipeError` / `OSError` on `sys.stdout.write` and `Console.print` [`_output.py:30, 33, 36, 48-50, 53`] — `semvertag ... | head` will traceback today. Belongs to Story 1.7 CLI top-level handler.
- `build_rich_output` / `build_json_output` have no `force_terminal` / `color_system` override [`_output.py:66-78`] — Story 1.7 wires CLI flags; revisit when `--no-color` / `--color=always` semantics are decided.
- `JsonOutput.emit` doesn't pass the serialized payload through `redact()` [`_output.py:47-50`] — if `RunResult.reason` ever carries a token (e.g. provider error text), it leaks unredacted in JSON output. Decide in Story 1.5/1.7 when reason values are populated.
- Long Rich messages wrap at default `width=80` and may break single-line log expectations [`_output.py:30, 33`] — redaction is applied pre-wrap so security is unaffected; add `soft_wrap=True`/`no_wrap=True` only if downstream log parsers complain.
- Marginal redact-test coverage gaps: `redact("")`, multi-line input, two adjacent tokens, uppercase-only hex, hex bordered by `-`/`_`/`.`/`:` [`tests/unit/test_redact.py`] — beyond AC8 text; 100% line coverage already met.
- AC9 narrative example uses 19-char token body (`"glpat-RealToken1234567890"`) while pattern requires ≥20 [spec `1-3-...md` AC9 narrative] — cosmetic spec fix; tests use a 20+-char fixture.
- Dev Agent Record §Debug Log References doesn't mention the extra token families Task 3.3 asked the dev to note for Story 1.5/3.x — recorded here so the next refactor sees the list.

## Deferred from: code review of 1-4-retryingtransport-with-retry-policy (2026-05-27)

- Response objects from failed retry attempts are discarded without `response.close()` [`semvertag/_transport.py:33-39`] — harmless under `MockTransport`, but real `httpx2.HTTPTransport` may leak a connection back to the pool on each discarded 5xx. Architecture sketch (story line 309) also discards. Verify in Story 1.5 GitLabProvider integration tests; add `response.close()` to the retry loop if pool drainage shows leakage.
- `RETRYABLE_EXCEPTIONS` omits `httpx2.ConnectTimeout` and `httpx2.PoolTimeout` [`semvertag/_transport.py:10-15`] — AC1 fixes the tuple to these exact 4 types. `ConnectTimeout` is the most glaring omission; production retry layers commonly include it. Changing the tuple requires an AC1 revision in a future story.
- Retries apply to non-idempotent methods (POST/PATCH) unconditionally — `handle_request` does not inspect `request.method` [`semvertag/_transport.py:27-49`]. semvertag's only POST is tag creation; the GitLabProvider (Story 1.5) translates 409 "tag already exists" so duplicate-tag risk is mitigated downstream. Revisit if a non-idempotent endpoint without server-side idempotency ever lands.

## Deferred from: code review of 1-5-gitlabprovider-four-endpoints-via-httpx2 (2026-05-27)

- `_translate_status` hardcodes "Retries exhausted after 3 attempts" in the 429 / 5xx cause messages [`semvertag/providers/gitlab.py:336, 339`] — spec AC7 prescribes the exact strings, so the implementation is correct, but the text silently drifts if `_transport.MAX_ATTEMPTS` ever changes. Revisit if/when the retry policy is tunable.
- `_TAG_EXISTS_FRAGMENT = "already exists"` is English-only [`semvertag/providers/gitlab.py:78, 168`] — A GitLab server with `Accept-Language: fr` returns "le tag existe déjà" and the substring match fails; duplicate-tag errors fall into the generic "Request rejected by GitLab: 400" path. Fix requires either an explicit `Accept-Language: en` header in `_auth_headers()` (architectural choice) or matching GitLab's structured-error-code (`{"message": {"tag_name": ["already exists"]}}`) instead of free-text.
- `tests/conftest.py::_default_handler` returns 201 for ANY POST to `/repository/tags` regardless of payload [`tests/conftest.py:398-399`] — payload-shape regressions in `create_tag` would not surface in fixtures that rely on the default handler. Tighten when adding payload-strict default behavior.
- `tests/conftest.py::_default_handler` falls back to 404 for unknown paths, which the provider translates to `ConfigError("project not found")` — a typo in any URL builder in `gitlab.py` would be misdiagnosed as a project-not-found error rather than failing loudly [`tests/conftest.py:400`]. Consider raising `AssertionError` (or `httpx2.Response(599)`) from the fallback so unintended requests fail fast.
- No pagination-loop detection in `list_tags` — a broken proxy returning the same `Link: rel="next"` URL each iteration burns up to 100 calls and accumulates duplicate tags before tripping the cap [`semvertag/providers/gitlab.py:128-147`]. Add a `seen: set[str]` guard if seen in the wild.
- `_MAX_TAG_PAGES * _TAGS_PER_PAGE = 10_000` hard ceiling is unreachable for legitimately large monorepos (Linux kernel mirrors, per-deploy tag projects) [`semvertag/providers/gitlab.py:64-65`] — spec mandates the 100-page cap; revisit if real users hit it.
- `raise ProviderAPIError(...) from exc` chains `httpx2.RequestError`, whose `__str__` typically includes the request URL [`semvertag/providers/gitlab.py:42-43, 68-69, 84-85, 106-107`] — if `SEMVERTAG_GITLAB__ENDPOINT` ever contains userinfo (e.g. `https://oauth2:token@gitlab.example`, an anti-pattern), credentials surface in traceback / logs via `__cause__`. Defense-in-depth: either redact endpoint userinfo at construction or use `raise ... from None` for the request-error path.
- Integration tests reach into `semvertag._transport` to monkey-patch `time.sleep` / `random.uniform` [`tests/integration/test_gitlab_provider.py:848-849, 862-863, 876-877`] — tight coupling to internals. Any refactor of `_transport` (e.g., switching to `secrets.SystemRandom` or moving the sleep call) silently breaks the no-op patching and tests start really sleeping. Would require exposing a `sleep_fn` / `jitter_fn` seam on `RetryingTransport`.
