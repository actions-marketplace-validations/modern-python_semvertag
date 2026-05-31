# BMad → Superpowers migration + httpx2 wrapper pilot

**Date:** 2026-05-31
**Status:** Approved, ready for plan
**Author:** brainstorm session (Superpowers `brainstorming` skill)

## Context

semvertag is mid-Epic 4 (4/8 stories done; 4.4–4.8 in backlog) under the BMad
workflow. BMad has produced 14 dense story files (60–90 KB each), a PRD, an
architecture document, three retrospectives, and a `sprint-status.yaml` tracker
inside `_bmad/`.

Two pains drive the switch:

1. **Process is too slow.** The contextualise → implement → code-review loop
   per story carries too much ceremony for the remaining work.
2. **Resulting code feels overengineered and complex.** Concrete example: every
   method in `semvertag/providers/gitlab.py` repeats a 6-step defensive dance
   (build URL, catch `RequestError`, translate status, catch `DecodingError`,
   validate shape, extract with `KeyError` handling). A base wrapper around
   `httpx2` would erase most of it.

This spec covers two bundled sub-projects:

- **Migration mechanics:** hard cutover from BMad to Superpowers.
- **httpx2 wrapper pilot:** first real piece of work executed under the new
  flow — small enough to learn the rhythm, directly addresses one
  overengineering complaint.

A broader simplification pass on the rest of the codebase (`_settings.py`,
`ioc.py`, `doctor/`, `_use_case.py`) is **deferred to a follow-up brainstorm**
once the wrapper has validated the new workflow.

## Decisions

| Question | Decision |
| --- | --- |
| Disposition of BMad workspace | Hard cutover, archive everything |
| Scope of this spec | Migration mechanics + httpx2 wrapper pilot bundled |
| Superpowers stack depth | Full stack from day one (TDD, worktrees, code-review subagents, verification gates) |
| Remaining 4.4–4.8 backlog | Dropped. Re-decide each item fresh later, individually, only if still needed |
| GitHub provider as part of wrapper work | No. YAGNI. Wrapper is justified by what it deletes today in `gitlab.py` |

## Section 1 — Workspace cutover

### File moves

- `_bmad/` → `_archive/bmad/` (via `git mv`). Joins `_autosemver_reference/`
  as a read-only sibling. Nothing inside is deleted.
- No retro extraction, no PRD distillation, no "what we still believe" summary.
  If past decisions are needed, open the archive.
- `.claude/settings.local.json` stays untouched.

### New directories

```
docs/superpowers/specs/   — brainstorm outputs (one per piece of work)
docs/superpowers/plans/   — writing-plans outputs (one per spec)
```

`specs/` is created as part of writing this spec (it lives there). `plans/` is
created at the same time and remains empty until the writing-plans step runs;
it gets a `.gitkeep` so the empty dir tracks in git.

### `CLAUDE.md` (new, repo-root)

There is no repo-level `CLAUDE.md` today (only the user-global one). Add one,
30–50 lines, covering:

- Workflow is Superpowers: brainstorm → writing-plans → executing-plans (or
  subagent-driven-development), with TDD by default, worktrees for feature
  isolation, code-review subagents, verification-before-completion gates.
- Spec/plan locations: `docs/superpowers/specs/` and `docs/superpowers/plans/`.
- `_archive/bmad/` is reference-only — historical decisions, do not edit, do
  not extend.
- `_autosemver_reference/` is behavioral reference only (existing convention).
- Commit-message convention: imperative present-tense scoped messages
  (`providers: add HttpClient base`). No more `land story X.Y …` or
  `contextualise story X.Y` prefixes.
- Test stack and lint commands (mirror what `Justfile` already documents).

### Artefacts with no replacement in the new workflow

These move to `_archive/bmad/` with everything else (nothing is deleted), but
nothing in the Superpowers flow takes their place:

- `_bmad/sprint-status.yaml` — Superpowers uses in-session `TaskList` plus git
  log between sessions. No standing tracker file.
- `implementation-readiness-report-*.md`, `prd-validation-report.md`,
  `deferred-work.md` — ceremony artefacts.

### Verification gate before Phase 2

`just lint-ci`, `uv run pytest`, `mkdocs build --strict` all green. None should
care about doc moves, but verify rather than assume.

## Section 2 — httpx2 wrapper design

### Goal

Erase the 6-step defensive dance from every method in `gitlab.py` so call
sites read like "GET this path → here's a dict", with status / JSON / shape
errors handled once in one place.

### Shape — composition, not inheritance

Today `GitLabProvider` is a frozen dataclass holding `client: httpx2.Client`.
Replace that field with `http: HttpClient`, where `HttpClient` is a small
class wrapping `httpx2.Client` plus two injected callables: one for
auth-header construction, one for status-code translation. Both are provider-
specific; the wrapper itself stays generic.

The provider stays a flat dataclass with no base class. Reasons:

- No MRO surprises.
- DI wiring (`semvertag/ioc.py`) stays one-shot.
- A future GitHub provider just composes the same `HttpClient` with a
  different auth callable.

### `HttpClient` API (approximate)

```python
class HttpClient:
    client: httpx2.Client
    auth_headers: Callable[[], dict[str, str]]
    status_translator: Callable[[int], None]  # raises typed errors; no-op on success

    def request_dict(self, method: str, url: str, **kwargs) -> dict: ...
    def request_list(self, method: str, url: str, **kwargs) -> list: ...
    def request_raw(self, method: str, url: str, **kwargs) -> httpx2.Response: ...
```

Final API surface is decided at planning time; treat this as illustrative.

- `request_dict` / `request_list` run the request with auth headers, catch
  `httpx2.RequestError` → `ProviderAPIError`, call `status_translator`,
  decode JSON, validate shape, return.
- `request_raw` is an escape hatch for `create_tag` (needs raw status for the
  "already exists" 400 branch) and `list_tags` pagination (needs the `Link`
  header).
- `status_translator` is injected at construction — `_translate_status` keeps
  living at module level in `gitlab.py`. The wrapper never knows GitLab's
  specific error messages.

### What stays in `providers/gitlab.py`

- URL building (`_url`).
- `_translate_status` and all GitLab-specific error messages.
- The four `check_*` methods (provider-semantic).
- Pagination helpers (`_next_page_url`, `_same_origin`, `_LINK_ENTRY_RE`).
- The `create_tag` "already exists" 400 branch (uses `request_raw`).

### Explicit non-goals

- **No retry logic in the wrapper** — `RetryingTransport` already handles
  retries one level below.
- **No redaction logic in the wrapper** — `_redact.py` handles that at output
  time.
- **No async surface** — semvertag is sync. Adding async is hypothetical.
- **No `ProviderBase` abstract class.** The `Provider` Protocol stays the
  only shared shape.
- **No GitHub provider built preemptively.** Wrapper is built for GitLab.
  GitHub validates the design later when actually needed.

### Expected delta

- `gitlab.py`: ~380 LOC → ~200 LOC (rough estimate, not a hard gate).
- Tests stay structurally similar; per-method tests get shorter because
  malformed-JSON and `RequestError` cases live in one shared `HttpClient` test
  file.
- `ioc.py`: one new node for `HttpClient`, GitLab group field renames
  `client` → `http`.

## Section 3 — Execution sequencing

### Phase 1 — Migration scaffolding

Direct-to-`main`, no worktree, no PR. Mechanical, low-risk, not subject to TDD.

1. `chore: archive _bmad/ as reference` — `git mv _bmad _archive/bmad`.
2. `chore: track empty docs/superpowers/plans/` — `plans/` was created during
   this brainstorm but is empty; add a `.gitkeep` so it tracks. (`specs/`
   already tracks because this spec lives in it.)
3. `docs: add project CLAUDE.md` — the 30–50 line file described in Section 1.

**Gate:** `just lint-ci`, `uv run pytest`, `mkdocs build --strict` all green.

### Phase 2 — Wrapper pilot

Spawn a worktree (`using-git-worktrees` skill). Inside the worktree:

1. **`HttpClient` red → green, alone.** Write
   `tests/test_providers/test_http_client.py` covering:
   - Happy-path dict.
   - Happy-path list.
   - `RequestError` → `ProviderAPIError`.
   - Malformed JSON → `ProviderAPIError`.
   - Wrong shape (list when dict expected) → `ProviderAPIError`.
   - `status_translator` hook fires before JSON decode (so a 401 raises
     `AuthError` rather than trying to decode the error body).

   Build `HttpClient` minimally to make each test green. Commit when the new
   file is self-contained.

2. **Refactor `GitLabProvider` method-by-method.** For each of
   `get_default_branch`, `get_latest_commit_on_default_branch`, `list_tags`,
   `create_tag`, and the four `check_*` methods: rewrite the body to use
   `HttpClient`. Run `uv run pytest tests/test_providers/test_gitlab.py` —
   existing tests stay green (the parity guarantee, no test changes needed).
   Commit per-method or in 2–3 logical batches.

3. **DI wiring** (`semvertag/ioc.py`) — add an `HttpClient` provider node,
   wire it into the GitLab group, drop the raw `client` field from
   `GitLabProvider`. Single commit.

4. **Cleanup** — delete dead helpers (e.g. `_safe_get` if no longer needed),
   trim `_translate_status` if call sites changed.

5. **Pre-review verification gate** (`verification-before-completion` skill):
   - `just lint-ci`
   - `uv run pytest`
   - branch coverage at 100% on `providers/` (existing standard)
   - `mkdocs build --strict`

   No "all tests pass" claims without showing the command output.

6. **Code review** — invoke `requesting-code-review` skill to spawn a review
   subagent against the worktree branch. Address findings via
   `receiving-code-review` (which forces verification rather than blind
   acceptance).

7. **Land** — `finishing-a-development-branch` skill to merge back to `main`.
   PR or fast-forward, developer's call.

## Success criteria

This spec is "done" when **all** of the following hold:

- `_bmad/` is gone from the working tree (lives at `_archive/bmad/`).
- `docs/superpowers/specs/` contains this spec and the implementation plan
  derived from it.
- Repo-root `CLAUDE.md` exists and points at the Superpowers flow.
- `HttpClient` exists in `semvertag/providers/` (or chosen location) and is
  used by every method in `gitlab.py`.
- All existing tests still pass; no behavioral changes to the GitLab provider.
- `gitlab.py` is meaningfully shorter (target ~40–50% LOC reduction; soft
  signal — if the wrapper doesn't shrink it, the wrapper isn't pulling
  weight).
- Branch coverage on `providers/` remains at 100%.

## Out of scope

Deferred to separate later brainstorms:

- Simplification pass on `_settings.py`, `ioc.py`, `doctor/`, `_use_case.py`,
  and other "overengineered code" complaints.
- Any of the dropped Epic 4 backlog items (4.4 mkdocs site content, 4.5
  migration guides, 4.6 trust-surface markdown, 4.7 README hero + issue
  templates, 4.8 shadow-mode parity validation). Each gets re-decided
  individually, only if still needed.
- GitHub provider implementation.
- Async support.
- Migration of CI workflow conventions (Justfile, GitHub Actions) to anything
  Superpowers-specific — they stay as-is.
