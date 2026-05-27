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
