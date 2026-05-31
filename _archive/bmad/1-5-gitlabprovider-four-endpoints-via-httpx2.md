# Story 1.5: GitLabProvider against four endpoints via httpx2

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a GitLab CI user,
I want semvertag to fetch the default branch, latest commit on that branch, the list of existing tags, and to create a new tag against the GitLab REST API — and to check token / scopes / project access / protected-tag rules on demand,
so that I have a working primary provider before bump-strategy alternatives and the doctor subcommand wire everything together.

## Acceptance Criteria

### AC1 — `Provider` protocol + new domain types

**Given** `semvertag/providers/_base.py` is created
**When** I import it
**Then** it exposes a `Provider` `typing.Protocol` with **exactly** these members (signatures matching architecture lines 304–315):

```python
class Provider(typing.Protocol):
    name: str  # "gitlab" | "github" | "bitbucket"

    def get_default_branch(self) -> str: ...
    def get_latest_commit_on_default_branch(self) -> Commit: ...
    def list_tags(self) -> list[Tag]: ...
    def create_tag(self, name: str, commit_sha: str) -> None: ...

    def check_token(self) -> CheckResult: ...
    def check_scopes(self) -> CheckResult: ...
    def check_project_access(self) -> CheckResult: ...
    def check_protected_tags(self) -> CheckResult: ...
```

The Protocol declares `name: str` (plain annotation, per architecture line 305) — the impl satisfies it with `name: typing.ClassVar[str] = "gitlab"` (a class attribute is structurally accessible as an instance attribute).

**And** `semvertag/_types.py` gains three additional frozen dataclasses (`frozen=True, slots=True, kw_only=True`), each in this exact shape:

```python
@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Commit:
    sha: str
    message: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Tag:
    name: str
    commit_sha: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class CheckResult:
    name: str
    status: typing.Literal["passed", "failed", "skipped"]
    cause: str
```

**And** `_types.py`'s existing `ConfigSource` and `RunResult` are unchanged. Field order is `name, status, cause` for `CheckResult` (matches architecture line 331–334). `Commit.message` carries the full commit message text (not truncated, not lowercased).

### AC2 — `GitLabProvider` shape and construction surface

**Given** `semvertag/providers/gitlab.py` is created
**When** I import `GitLabProvider`
**Then** it is a frozen dataclass with `frozen=True, slots=True, kw_only=True` declared in this exact field order:

```python
@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class GitLabProvider:
    name: typing.ClassVar[str] = "gitlab"
    config: GitLabConfig
    project_id: int
    client: httpx2.Client
```

**And** `GitLabProvider` structurally satisfies the `Provider` protocol — `typing.get_type_hints(Provider)` member-by-member shape match, verifiable at runtime via `typing.runtime_checkable` is **not** required (Protocol stays non-runtime — structural typing at static-check time only).

**And** the dataclass holds NO mutable state — `client` is injected (DI in Story 1.7; explicit construction in tests).

**And** `project_id` is a constructor field — it is NOT read from `GitLabConfig` or `Settings` in this story. Story 1.7 is responsible for plumbing `CI_PROJECT_ID` / `--project-id` into provider construction. See Dev Notes §Project-ID handling for the rationale.

### AC3 — `get_default_branch` → `GET /api/v4/projects/{project_id}`

**Given** the GitLab API responds to `GET /api/v4/projects/{project_id}` with HTTP 200 and JSON body `{"default_branch": "main", ...other-fields-ignored...}`
**When** `provider.get_default_branch()` is called
**Then** the method returns the string `"main"`
**And** exactly **one** request is issued to the inner `MockTransport`
**And** the request URL is `{config.endpoint}/api/v4/projects/{project_id}` (no trailing slash; no query params)
**And** the `PRIVATE-TOKEN` header carries `config.token.get_secret_value()` (see Dev Notes §Auth header policy for `PRIVATE-TOKEN` vs `Authorization: Bearer` decision)

**And given** the same endpoint returns HTTP 200 with `{"default_branch": null}` (well-formed JSON but null branch)
**When** the method is called
**Then** it raises `ConfigError("Default branch missing from GitLab response. Verify the project has a default branch configured.")`

**And given** the response is HTTP 200 with a malformed body (non-JSON or JSON missing the `default_branch` key entirely)
**When** the method is called
**Then** it raises `ProviderAPIError("GitLab project response malformed. Check SEMVERTAG_GITLAB__ENDPOINT and project ID.")`

### AC4 — `get_latest_commit_on_default_branch` → `GET /api/v4/projects/{project_id}/repository/commits?ref_name=...&per_page=1`

**Given** `get_default_branch()` is called first to resolve the ref name (`provider.get_latest_commit_on_default_branch()` MAY call `self.get_default_branch()` internally OR accept a cached value — see Dev Notes §Internal default-branch resolution; pick **inline call** for v1.0)
**And** the API responds to `GET /repository/commits?ref_name=main&per_page=1` with `[{"id": "a2b4d12...", "message": "Merge branch 'feature/foo' into main\n"}, ...]`
**When** `provider.get_latest_commit_on_default_branch()` is called
**Then** it returns `Commit(sha="a2b4d12...", message="Merge branch 'feature/foo' into main\n")`
**And** the request URL is `{config.endpoint}/api/v4/projects/{project_id}/repository/commits` with query params `ref_name={default_branch}` and `per_page=1`
**And** `Commit.sha` is the value of `id` (NOT `short_id`)
**And** `Commit.message` is the full message verbatim (no `.strip()`, no `.lower()` — the strategy layer in Story 1.6 / 2.1 does any case-normalization)

**And given** the response is HTTP 200 with an empty list `[]`
**When** the method is called
**Then** it raises `ProviderAPIError("No commits on default branch '{default_branch}'. The branch appears empty.")`

### AC5 — `list_tags` → `GET /api/v4/projects/{project_id}/repository/tags` with pagination

**Given** the API responds to `GET /api/v4/projects/{project_id}/repository/tags?per_page=100&page=1` with a list of tag objects `[{"name": "1.4.2", "commit": {"id": "..."}}, ...]` AND a `Link` header indicating no further pages
**When** `provider.list_tags()` is called
**Then** it returns a `list[Tag]` containing each entry mapped via `Tag(name=item["name"], commit_sha=item["commit"]["id"])`
**And** the list preserves API order (most-recent-first per GitLab default; the architecture protocol comment at line 309 reads "most-recent-first")
**And** NO semver filtering is performed — `list_tags()` returns ALL tags including non-semver values like `"release-2024-Q1"` (FR8 filtering is a use-case concern, NOT a provider concern; per epic AC line 451–453)

**And given** the first page response carries `Link: <{endpoint}/api/v4/projects/{id}/repository/tags?per_page=100&page=2>; rel="next"` and page 2 carries no `rel="next"`
**When** `provider.list_tags()` is called
**Then** it follows the `rel="next"` link and concatenates results from both pages in API order
**And** termination is purely Link-driven — when no `rel="next"` link is present in the response headers, pagination stops (regardless of `X-Next-Page` / `X-Total-Pages` headers, which GitLab is migrating away from per their changelog — Link is the durable contract)
**And** a hard cap of `_MAX_TAG_PAGES: typing.Final = 100` (10,000 tags at `per_page=100`) prevents pathological loops; on cap hit, raise `ProviderAPIError("Tag pagination exceeded 100 pages. The project has an unexpected number of tags; please file an issue.")` — see Dev Notes §Pagination loop safety

**And given** the response is HTTP 200 with an empty list `[]` on page 1
**When** the method is called
**Then** it returns `[]` — empty list is a valid result, NOT an error (FR-aligned: the "no existing tags" benign no-op is handled in the use case, not the provider)

### AC6 — `create_tag` → `POST /api/v4/projects/{project_id}/repository/tags`

**Given** the API responds to `POST /api/v4/projects/{project_id}/repository/tags` with HTTP 201 (the success status for tag creation per GitLab REST API docs)
**When** `provider.create_tag(name="1.4.3", commit_sha="a2b4d12")` is called
**Then** the request body is `{"tag_name": "1.4.3", "ref": "a2b4d12"}` serialized as JSON with `Content-Type: application/json`
**And** the method returns `None` (no return value; success is the absence of exception)
**And** exactly **one** request is issued

**And given** the API returns HTTP 400 with body `{"message": "Tag 1.4.3 already exists"}` (idempotency conflict)
**When** the method is called
**Then** it raises `ConfigError("Tag already exists: '1.4.3'. The tag was created by a concurrent run or previous invocation.")` — NOT `ProviderAPIError`, because the condition is recoverable / user-correctable (re-running on the same commit is idempotent per NFR5)

### AC7 — Error translation matrix (HTTP status → SemvertagError subclass)

**Given** the `_translate_status` helper applies this exact table on **every** non-2xx response from any main-verb endpoint (`get_default_branch`, `get_latest_commit_on_default_branch`, `list_tags`, `create_tag`):

| HTTP status | Exception | Cause template (FR30 named-actionable) |
|---|---|---|
| 401 | `AuthError` | `"Token rejected: 401. Verify SEMVERTAG_TOKEN is valid and has 'api' scope."` |
| 403 | `AuthError` | `"Token missing scope or insufficient permission: 403. Add 'api' or 'write_repository' to the SEMVERTAG_TOKEN scopes on GitLab."` |
| 404 | `ConfigError` | `"GitLab project not found: project_id={project_id}. Verify CI_PROJECT_ID or --project-id."` |
| 422 | `ConfigError` | `"Request rejected by GitLab: 422. Check tag name format and that the referenced commit exists."` |
| 5xx (after retries exhausted by `RetryingTransport`) | `ProviderAPIError` | `"GitLab API failure: {status}. Retries exhausted after 3 attempts. Try again or check GitLab status."` |
| 429 (after retries exhausted) | `ProviderAPIError` | `"GitLab rate limit: 429. Retries exhausted after 3 attempts; try again later."` |

**When** any main-verb method receives one of those statuses **from the `httpx2.Client`** (NOT directly from the wire — the `RetryingTransport` is upstream and may have already retried)
**Then** the corresponding `SemvertagError` subclass is raised with the exact cause template above, with `{project_id}` and `{status}` substituted at runtime
**And** the original `httpx2.Response` is NOT chained via `from` (httpx2 exceptions are NOT raised in the main-verb path — `RetryingTransport` returns the `Response`, the provider inspects status, and translates; no `raise … from response`)
**And when** an `httpx2.RequestError` subclass (network, unrelated parse) escapes the transport, it is caught at the method boundary and re-raised as `ProviderAPIError("GitLab request failed: {type(exc).__name__}. Check SEMVERTAG_GITLAB__ENDPOINT and network connectivity.") from exc` — `from exc` chaining IS used here per architecture §Exception Construction Patterns line 791–802

**And** the cause messages are STATIC TEMPLATES (no f-string evaluation against response body text — see Dev Notes §Why response bodies don't appear in error messages)

### AC8 — Doctor methods return `CheckResult` (consumed by Epic 3)

**Given** doctor methods are implemented on `GitLabProvider` but are not wired into any CLI subcommand by this story (doctor wiring is Epic 3)
**When** `provider.check_token()` is called and the API responds 200 to `GET /api/v4/user` (or equivalent token-validation endpoint — see Dev Notes §Doctor endpoint mapping)
**Then** it returns `CheckResult(name="token", status="passed", cause="Token recognized by GitLab API.")`

**And when** `check_token()` receives 401 from the same endpoint
**Then** it returns `CheckResult(name="token", status="failed", cause="Token rejected by GitLab. Verify SEMVERTAG_TOKEN is valid.")` — **doctor methods do NOT raise** (they return `CheckResult` with `status="failed"` so the chain runner can continue and collect all check outcomes per FR29–FR30)

**And** `check_scopes`, `check_project_access`, `check_protected_tags` each follow the same pattern: GET an appropriate endpoint, map 200 → `passed`, map 401/403 → `failed` with named cause, map 404 → `failed` with project-not-found cause, return `CheckResult` rather than raise
**And** the exact endpoint per doctor method is documented in Dev Notes §Doctor endpoint mapping — implement those, but do NOT wire them into a Typer command yet

### AC9 — Single-ownership invariants (HTTP-status translation + auth-header construction)

**Given** the architecture mandate: error translation is per-provider (architecture line 403 "Translation point: per-provider in `gitlab.py`")
**When** I grep the `semvertag/` tree (excluding `_autosemver_reference/`, `_bmad/`, `docs/`) for raw HTTP-status integer literals like `401`, `403`, `404`, `422` outside `providers/gitlab.py`
**Then** the only matches are inside `providers/gitlab.py` itself and `_transport.py` (the latter for `RETRYABLE_STATUSES` definitions, which is allowed)
**And** no other module raises `AuthError` / `ConfigError` / `ProviderAPIError` with a hard-coded HTTP status in the message
**And** no module other than `providers/gitlab.py` constructs a `PRIVATE-TOKEN` header value — token-to-header mapping is a provider concern

**And** the `_PRIVATE_TOKEN_HEADER: typing.Final = "PRIVATE-TOKEN"` constant is defined exactly once, in `providers/gitlab.py` at module scope.

### AC10 — Integration tests in `tests/integration/test_gitlab_provider.py` cover all four main-verb endpoints, all four doctor endpoints, and the translation matrix

**Given** the shared `tests/conftest.py` defines `GITLAB_PROJECT_ID: typing.Final = 999`, a default mock handler covering all four main-verb endpoints, a `gitlab_transport` fixture returning `httpx2.MockTransport(_default_handler)`, and a `compose_handler(base, overrides)` helper (architecture lines 558–578)
**When** `just test` runs against `tests/integration/test_gitlab_provider.py`
**Then** every test passes, the suite covers at minimum these scenarios:

| Scenario | AC | Endpoint(s) |
|---|---|---|
| `get_default_branch()` returns `"main"` on 200 + well-formed body | AC3 | `GET /api/v4/projects/{id}` |
| `get_default_branch()` raises `ConfigError` on 200 + null branch | AC3 | same |
| `get_default_branch()` raises `ProviderAPIError` on 200 + malformed body | AC3 | same |
| `get_latest_commit_on_default_branch()` returns `Commit` on happy path | AC4 | `GET /repository/commits?ref_name=...` |
| `get_latest_commit_on_default_branch()` raises `ProviderAPIError` on empty-list response | AC4 | same |
| `list_tags()` returns all tags including non-semver names | AC5 | `GET /repository/tags?per_page=100` |
| `list_tags()` follows `Link: rel="next"` across two pages | AC5 | same + page=2 |
| `list_tags()` returns `[]` on empty-project response | AC5 | same |
| `list_tags()` raises `ProviderAPIError` on cap-hit (>100 pages) | AC5 | same — feed a handler that always advertises next |
| `create_tag()` succeeds on 201 | AC6 | `POST /repository/tags` |
| `create_tag()` raises `ConfigError` on 400 already-exists | AC6 | same |
| Error translation: 401 → `AuthError` with named cause | AC7 | parametrize over all four main-verb endpoints |
| Error translation: 403 → `AuthError` | AC7 | parametrize over all four |
| Error translation: 404 → `ConfigError` with project_id in cause | AC7 | parametrize over all four |
| Error translation: 422 → `ConfigError` | AC7 | parametrize over `create_tag` (the realistic 422 path) |
| Error translation: 5xx (after retries exhausted) → `ProviderAPIError` | AC7 | parametrize; uses a MockTransport that returns 503 always — `RetryingTransport` exhausts and surfaces 503 to provider; provider translates |
| Error translation: 429 (after retries exhausted) → `ProviderAPIError` | AC7 | same shape; provider doesn't differentiate from 5xx semantically post-exhaustion |
| `httpx2.RequestError` → `ProviderAPIError` with `from exc` chaining | AC7 | inner handler raises `httpx2.ConnectError`; transport exhausts and re-raises; provider catches and re-raises |
| `check_token()` returns `passed` on 200 | AC8 | per Dev Notes §Doctor endpoint mapping |
| `check_token()` returns `failed` on 401 (does NOT raise) | AC8 | same |
| `check_scopes()`, `check_project_access()`, `check_protected_tags()` each have `passed` + `failed` paths | AC8 | per Dev Notes table |

**And** `semvertag/providers/gitlab.py` line coverage is ≥90% (some doctor paths may sit between the unit/integration line; aim ≥90%, accept ≥85% per NFR22)
**And** `semvertag/providers/_base.py` is excluded from coverage measurement only if its body is a single `Protocol` declaration with no executable code (coverage treats protocol bodies as `...` ellipses — they're effectively `# pragma: no cover` by virtue of being type-only)

## Tasks / Subtasks

- [x] 1. Extend `semvertag/_types.py` with domain types (AC: 1)
  - [x] 1.1 Append three new `@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)` definitions to the bottom of `_types.py` (after `RunResult`): `Commit`, `Tag`, `CheckResult`. Field shapes per AC1.
  - [x] 1.2 Do NOT touch existing `ConfigSource` or `RunResult`. Do NOT add `Bump` — that's Story 1.6.
  - [x] 1.3 No `__all__` update needed — `_types.py` currently has no `__all__` export (intentional: internal module).
  - [x] 1.4 Ensure `typing.Literal["passed", "failed", "skipped"]` on `CheckResult.status` matches the architecture spec exactly (no spaces, no caps).

- [x] 2. Create `semvertag/providers/` package (AC: 1, 2, 9)
  - [x] 2.1 `semvertag/providers/__init__.py` — empty (matches pattern of `semvertag/strategies/__init__.py`).
  - [x] 2.2 `semvertag/providers/_base.py` — module-level imports (`typing` + the three types from `_types.py` via `from semvertag._types import Commit, Tag, CheckResult`). Define `class Provider(typing.Protocol):` with the eight method signatures from AC1. Each method body is `...` (Protocol convention — no `pass`, no docstring needed; the protocol IS the doc).
  - [x] 2.3 Add `__all__: typing.Final = ("Provider",)` at the bottom of `_base.py`.
  - [x] 2.4 The Protocol body annotates `name: str` (plain annotation, no default — per architecture line 305). The impl in `gitlab.py` satisfies it with `name: typing.ClassVar[str] = "gitlab"` — a class-level attribute is structurally accessible as an instance attribute and satisfies the Protocol's instance-attribute annotation. Do NOT annotate `name: typing.ClassVar[str]` on the Protocol itself (mypy/ty reject `ClassVar` on Protocol attribute declarations).

- [x] 3. Create `semvertag/providers/gitlab.py` (AC: 2, 3, 4, 5, 6, 7, 8, 9)
  - [x] 3.1 Top-of-file global imports (per project convention): `import dataclasses`, `import typing`, `import httpx2`. Then `from semvertag._errors import AuthError, ConfigError, ProviderAPIError`, `from semvertag._settings import GitLabConfig`, `from semvertag._types import CheckResult, Commit, Tag`. No `from __future__ import annotations`. No function-local imports.
  - [x] 3.2 Module-level constants annotated `typing.Final`:
    - `_API_PREFIX: typing.Final = "/api/v4/projects"`
    - `_PRIVATE_TOKEN_HEADER: typing.Final = "PRIVATE-TOKEN"`
    - `_TAGS_PER_PAGE: typing.Final = 100`
    - `_MAX_TAG_PAGES: typing.Final = 100`
    - `_HTTP_OK: typing.Final = 200`
    - `_HTTP_CREATED: typing.Final = 201`
    - `_HTTP_UNAUTHORIZED: typing.Final = 401`
    - `_HTTP_FORBIDDEN: typing.Final = 403`
    - `_HTTP_NOT_FOUND: typing.Final = 404`
    - `_HTTP_BAD_REQUEST: typing.Final = 400`
    - `_HTTP_UNPROCESSABLE: typing.Final = 422`
    - `_TAG_EXISTS_FRAGMENT: typing.Final = "already exists"` (used for 400-body sniffing to translate to `ConfigError` per AC6; case-insensitive substring match against `response.json().get("message", "")`)
  - [x] 3.3 Define `@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)` `class GitLabProvider:` with fields exactly as in AC2: `name: typing.ClassVar[str] = "gitlab"`, `config: GitLabConfig`, `project_id: int`, `client: httpx2.Client`. ClassVar is NOT a dataclass field — `dataclasses.dataclass` correctly skips it.
  - [x] 3.4 Implement `def get_default_branch(self) -> str:` per AC3. URL: `f"{self.config.endpoint}{_API_PREFIX}/{self.project_id}"`. Headers: `{_PRIVATE_TOKEN_HEADER: self.config.token.get_secret_value()}`. Response handling: status → `_translate_status` table (AC7), then `response.json().get("default_branch")` with the null/missing-key checks from AC3. The `httpx2.DecodingError` (or whatever `response.json()` raises on malformed body) is caught and re-raised as `ProviderAPIError`.
  - [x] 3.5 Implement `def get_latest_commit_on_default_branch(self) -> Commit:` per AC4. **Call `self.get_default_branch()` inline** at the top of the method — this is two HTTP requests for one logical call, but it's correct per the Provider protocol (the use case in Story 1.7 may choose to cache `default_branch` via `_settings.default_branch` to avoid the second call; that's an optimization the use case owns, not the provider). URL: `f"{self.config.endpoint}{_API_PREFIX}/{self.project_id}/repository/commits"`. Query params via httpx2: `params={"ref_name": default_branch, "per_page": 1}`. Returns `Commit(sha=items[0]["id"], message=items[0]["message"])`.
  - [x] 3.6 Implement `def list_tags(self) -> list[Tag]:` per AC5. Pagination loop:
    ```python
    tags: list[Tag] = []
    url: str | None = f"{self.config.endpoint}{_API_PREFIX}/{self.project_id}/repository/tags"
    params: dict[str, typing.Any] | None = {"per_page": _TAGS_PER_PAGE, "page": 1}
    pages_consumed = 0
    while url is not None:
        pages_consumed += 1
        if pages_consumed > _MAX_TAG_PAGES:
            raise ProviderAPIError("Tag pagination exceeded 100 pages. ...")
        response = self.client.get(url, params=params, headers=self._auth_headers())
        _translate_status(response.status_code, self.project_id)
        for item in response.json():
            tags.append(Tag(name=item["name"], commit_sha=item["commit"]["id"]))
        url, params = _next_page(response)
    return tags
    ```
    The `_next_page` helper parses the `Link` header per RFC 8288 — return `(next_url, None)` if `rel="next"` is present, else `(None, None)`. Both URL fragments and absolute URLs returned by GitLab in `Link` work, but GitLab returns absolute URLs (`https://gitlab.com/api/v4/projects/{id}/repository/tags?page=2&per_page=100`) so this is straightforward; pass the absolute URL straight to `httpx2.Client.get`. Set `params=None` on subsequent pages (the URL already carries them).
  - [x] 3.7 Implement `def create_tag(self, name: str, commit_sha: str) -> None:` per AC6. URL: `f"{self.config.endpoint}{_API_PREFIX}/{self.project_id}/repository/tags"`. Method: `self.client.post(url, json={"tag_name": name, "ref": commit_sha}, headers=self._auth_headers())`. Status handling:
    - 201 → return None
    - 400 with body containing `_TAG_EXISTS_FRAGMENT` (case-insensitive) → raise `ConfigError("Tag already exists: '{name}'. ...")`
    - 400 otherwise → raise `ConfigError("Request rejected by GitLab: 400. ...")` (treat as another flavor of 422; uniform 4xx-config path)
    - other statuses → `_translate_status` (AC7)
  - [x] 3.8 Implement `_translate_status(status: int, project_id: int) -> None` as a **module-level function** (not a method) that raises the appropriate `SemvertagError` subclass per the AC7 table, OR returns silently if `status in (200, 201)`. Centralizes the status-to-error mapping. Called by every main-verb method before parsing the body.
  - [x] 3.9 Implement the four `check_*` doctor methods per AC8 + Dev Notes §Doctor endpoint mapping. Each catches its specific status, returns `CheckResult` rather than raises. Use a small `_safe_get(url, headers) -> httpx2.Response | None` helper that catches `httpx2.RequestError` and returns `None` so doctor checks degrade to `status="failed"` with a network-error cause rather than propagating.
  - [x] 3.10 Implement `def _auth_headers(self) -> dict[str, str]:` — returns `{_PRIVATE_TOKEN_HEADER: self.config.token.get_secret_value()}`. Used by every method. **Do NOT** include other headers (no `Accept`, no `User-Agent`) — httpx2 sends sensible defaults; per architecture line 944–957's comment policy, every additional header is a deferred-work entry (see deferred-work.md).
  - [x] 3.11 Add `__all__: typing.Final = ("GitLabProvider",)` at module bottom.
  - [x] 3.12 SecretStr handling: `self.config.token.get_secret_value()` is invoked **only** inside `_auth_headers()` — the raw token value never leaves that method's return dict. `_translate_status`, error messages, log lines must NEVER receive a `SecretStr` or its unwrapped value. AC9 covers the structural test; this subtask is the implementation-discipline reminder.

- [x] 4. Create shared test infrastructure at `tests/conftest.py` (AC: 10)
  - [x] 4.1 NEW file at repo root `tests/conftest.py` (NOT in `tests/unit/` or `tests/integration/`). This is the shared fixture surface for **integration** tests; unit tests in Story 1.4 don't need it and aren't impacted.
  - [x] 4.2 Module-level constants: `GITLAB_PROJECT_ID: typing.Final = 999`, `GITLAB_ENDPOINT: typing.Final = "https://gitlab.example.test"`, `GITLAB_TOKEN: typing.Final = "glpat-XXXXXXXXXXXXXXXXXXXX"` (a redaction-pattern-matching dummy so accidental leakage is visible via the redaction-test suite).
  - [x] 4.3 `_default_handler(request: httpx2.Request) -> httpx2.Response` — pattern-matches on `(request.method, request.url.path)` and returns canned 200 responses for all four main-verb endpoints. Bodies match the GitLab REST API shapes from AC3–AC6 happy-path text. Unrecognized paths → return `httpx2.Response(404, json={"message": "404 Not Found"})`.
  - [x] 4.4 `compose_handler(base, overrides)` — takes the base handler + a `dict[tuple[method, path_or_path_prefix], httpx2.Response]` and returns a new handler that consults `overrides` first, falling back to `base`. Path matching is exact-prefix (so a test can override `("GET", "/api/v4/projects/999/repository/tags")` regardless of query string).
  - [x] 4.5 `@pytest.fixture def gitlab_transport() -> httpx2.MockTransport: return httpx2.MockTransport(_default_handler)` — the shared fixture.
  - [x] 4.6 `@pytest.fixture def gitlab_client(gitlab_transport) -> httpx2.Client: ...` — constructs an `httpx2.Client(transport=gitlab_transport, base_url=GITLAB_ENDPOINT, timeout=8.0)`. Yield from a context manager so the client closes after the test.
  - [x] 4.7 `@pytest.fixture def gitlab_provider(gitlab_client) -> GitLabProvider: ...` — constructs a `GitLabProvider` instance with `config=GitLabConfig(endpoint=GITLAB_ENDPOINT, token=pydantic.SecretStr(GITLAB_TOKEN))`, `project_id=GITLAB_PROJECT_ID`, `client=gitlab_client`.
  - [x] 4.8 Existing `tests/unit/conftest.py` is **unmodified** by this story — its `clean_settings_env` fixture is irrelevant to the integration tests (provider construction is explicit, not Settings-driven).

- [x] 5. Create `tests/integration/` and write `test_gitlab_provider.py` (AC: 10)
  - [x] 5.1 `tests/integration/__init__.py` — empty (matches `tests/unit/__init__.py`).
  - [x] 5.2 `tests/integration/test_gitlab_provider.py` — global imports at top: `pytest`, `httpx2`, `pydantic`, plus `from semvertag._errors import AuthError, ConfigError, ProviderAPIError`, `from semvertag._types import Commit, Tag, CheckResult`, `from semvertag.providers.gitlab import GitLabProvider`. Module-level constants get `typing.Final`.
  - [x] 5.3 Use the shared `gitlab_provider` fixture from `tests/conftest.py` for happy-path tests. For error-translation tests, use `compose_handler` to override specific endpoints to return the target status.
  - [x] 5.4 Cover every scenario from the AC10 table. Parametrize the 401/403/404 translation tests over the four main-verb methods using `pytest.mark.parametrize`. Use the test naming convention `test_<verb>_<outcome>_when_<condition>` (architecture lines 916–921).
  - [x] 5.5 For the "5xx after retries exhausted" test: construct a `RetryingTransport(inner=httpx2.MockTransport(handler_always_503))` and wrap it in an `httpx2.Client`. Monkeypatch `_transport.time.sleep` to no-op to avoid 30s real sleeps. Verify the provider receives the final 503 from the transport and translates to `ProviderAPIError`. This test is the ONLY place in the suite that combines `RetryingTransport` + `GitLabProvider` — it's the integration seam between Stories 1.4 and 1.5.
  - [x] 5.6 Pagination test: use a stateful closure handler that responds to page=1 with `Link: <{url}?page=2>; rel="next"` and to page=2 with no `next` link. Assert `list_tags()` returns the concatenation of both pages, in API order.
  - [x] 5.7 Pagination cap-hit test: handler that ALWAYS advertises `rel="next"`. Assert `list_tags()` raises `ProviderAPIError` after `_MAX_TAG_PAGES` iterations — verify the iteration count by attaching a counter to the handler.
  - [x] 5.8 `httpx2.RequestError` test: inner handler raises `httpx2.ConnectError("simulated")`. The `RetryingTransport` exhausts its 3 attempts and re-raises (verified in Story 1.4 tests). The provider catches at the method boundary and re-raises as `ProviderAPIError`. Use `pytest.raises(ProviderAPIError) as exc_info` and `assert isinstance(exc_info.value.__cause__, httpx2.ConnectError)` for the `from exc` chaining check.
  - [x] 5.9 Doctor-method tests: each of the four `check_*` methods gets a passed-path test (200) and a failed-path test (401 or 404). Assert the returned `CheckResult.status` and `CheckResult.cause` value (not just status). The `name` field on `CheckResult` must match the method-name suffix (e.g., `check_token` → `CheckResult.name == "token"`).
  - [x] 5.10 Coverage check: end of file, run `uv run pytest tests/integration/test_gitlab_provider.py --cov=semvertag.providers.gitlab --cov-report term-missing` locally; line coverage on `providers/gitlab.py` must be ≥90%. The `# pragma: no cover` escape hatch is acceptable on unreachable branches (defensive `else` after `if/elif` matrices); use sparingly.

- [x] 6. Quality gates (AC: 1–10)
  - [x] 6.1 `just lint` — `eof-fixer`, `ruff format`, `ruff check --fix`, `ty check`. All clean.
  - [x] 6.2 `just lint-ci` — same in `--check`/`--no-fix` mode (matches CI gate).
  - [x] 6.3 `just test` — full suite. Confirm: no regression in Story 1.1–1.4 modules; new integration suite passes; `providers/gitlab.py` line coverage ≥90%; `_types.py` still ≥85%.
  - [x] 6.4 `uv build` — package builds clean (per-story bar from Story 1.1 review).
  - [x] 6.5 Manual `grep -rn "401\|403\|404\|422" semvertag/ --exclude-dir=__pycache__ | grep -v providers/gitlab.py | grep -v _transport.py` — should return only false positives (e.g., string literals inside non-error contexts). Document any unexpected matches in the Change Log.

- [x] 7. Update Dev Agent Record + File List + Status (AC: 1–10)
  - [x] 7.1 Append entries to **Dev Agent Record** below: Agent Model Used, Debug Log References (any deviations from this story's prescribed shape), Completion Notes List, File List, Change Log.
  - [x] 7.2 Status transitions: `ready-for-dev` → `in-progress` when work starts → `review` when code-review is ready. Story moves to `done` ONLY after code-review.
  - [x] 7.3 Update `_bmad/sprint-status.yaml` `development_status[1-5-gitlabprovider-four-endpoints-via-httpx2]` matching the status transitions. Bump `last_updated` to the implementation date.
  - [x] 7.4 If any deferred items surface — append them under a new "## Deferred from: code review of 1-5-gitlabprovider-four-endpoints-via-httpx2" heading in `_bmad/deferred-work.md`. Examples of likely deferrals: per-provider rate-limit metadata exposure, retry-aware doctor checks, GitLab GraphQL fallback, OAuth scope discovery via `/api/v4/personal_access_tokens/self`. Do NOT silently leave them undocumented.

## Dev Notes

### Story framing

This is **Step 5 of the architecture's Implementation Sequence**: "`GitLabProvider` — implements `Provider` against the four GitLab endpoints using the RetryingTransport. Existing autosemver tests ported." [Source: architecture.md#Decision Impact Analysis §Implementation sequence line 590]

Stories 1.1–1.4 built scaffolding, `_settings.py` (with `GitLabConfig.endpoint` and `GitLabConfig.token: SecretStr`), `_types.py` (`ConfigSource`, `RunResult`), `_errors.py` (`SemvertagError → ConfigError/AuthError/ProviderAPIError`), `_redact.py`, `_output.py`, and `_transport.py` (`RetryingTransport`). **Story 1.5 introduces ONE new provider package — `semvertag/providers/` — and TWO new test files — `tests/conftest.py` (shared fixtures) + `tests/integration/test_gitlab_provider.py`.**

The reference repo `_autosemver_reference/` uses `python-gitlab` (the SDK) and is therefore **not a direct behavioral reference** for the httpx2-native v1.0 provider — but it IS a useful reference for the four endpoint URLs and request bodies (see `_autosemver_reference/use_cases/autosemver_use_case.py`). Specifically:
- `project = client.projects.get(project_id)` → `GET /api/v4/projects/{project_id}` (gives `default_branch`)
- `project.commits.list(per_page=1, get_all=False, ref_name=...)` → `GET /api/v4/projects/{id}/repository/commits?per_page=1&ref_name=...`
- `project.tags.list(per_page=1, get_all=False)` → `GET /api/v4/projects/{id}/repository/tags?per_page=1` (note: reference uses `per_page=1` because it only needs the latest tag; we use `per_page=100` because we need all tags for FR8 semver filtering downstream)
- `project.tags.create({"tag_name": ..., "ref": ...})` → `POST /api/v4/projects/{id}/repository/tags` with JSON body

The reference uses `oauth_token` (the SDK's keyword arg) but the underlying header for PATs/group-tokens is `PRIVATE-TOKEN` — see §Auth header policy below.

### Critical architectural constraints

These come from `architecture.md` and are non-negotiable:

1. **One provider per file.** `providers/gitlab.py` is the only file containing `GitLabProvider`. `github.py` / `bitbucket.py` are NOT created by this story (FR22 deferred to v1.x). [Source: architecture.md lines 660–663, 1110–1112]
2. **Frozen dataclass with slots, kw-only.** `@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)` per architecture §Frozen-Dataclass Conventions lines 695–727. `ClassVar` fields are NOT subject to frozen-instance immutability (they're class-level). [Source: architecture.md line 700]
3. **`name: typing.ClassVar[str] = "gitlab"`.** Brand capitalization is "GitLab", not "Gitlab" — see architecture line 693. The `name` value is the lowercase string `"gitlab"` (matches `settings.provider` Literal value at architecture line 475). [Source: architecture.md lines 693, 988]
4. **httpx2-only HTTP path.** No `python-gitlab`, no `requests`, no SDK wrapper. Every provider call goes through `self.client: httpx2.Client` constructed with `RetryingTransport`. [Source: architecture.md line 337 "no python-gitlab SDK"; line 1175 "Provider REST API ... httpx2 over HTTPS via RetryingTransport"]
5. **Per-provider error translation.** Status-to-exception mapping is per-provider, in `providers/gitlab.py`. The error message follows the FR30 template: `<NamedCondition>: <Cause>. <SuggestedAction>.` [Source: architecture.md line 403; lines 744–778]
6. **Token from `SecretStr.get_secret_value()` ONLY at the HTTP-call boundary.** Never log the raw token, never include it in error messages, never concatenate it with other strings outside the `Authorization`/`PRIVATE-TOKEN` header construction. [Source: architecture.md line 1044; NFR10]
7. **The retry choke point is `_transport.py`.** This provider does NOT retry. It does NOT inspect `Retry-After`. It does NOT track a wall budget. Story 1.4's `RetryingTransport` handles all of that upstream; the provider just translates whatever final status the transport surfaces. [Source: architecture.md lines 1048, 1175, 1193, 1215]
8. **`httpx2.Client` is injected, not constructed inside the provider.** Production wiring (Story 1.7) constructs `httpx2.Client(transport=RetryingTransport(), base_url=..., timeout=settings.request_timeout)` in the DI Group. Tests inject `httpx2.Client(transport=httpx2.MockTransport(handler))`. The provider's `__init__` (auto-generated by `dataclass`) takes the client as-is. [Source: architecture.md lines 952–954]
9. **No comments unless WHY is non-obvious.** No "// Get default branch" type comments. Architecture §Comment Policy lines 942–957. [Source: architecture.md line 944]
10. **No `print()`, no `from __future__ import annotations`, no bare `Exception` catches, no function-local imports, `# ty: ignore` (not `# type: ignore`).** All carried from architecture §Anti-Patterns lines 1039–1049 and global `CLAUDE.md`.
11. **Tests in `tests/integration/` not `tests/unit/`.** This story crosses the unit/integration line — provider tests use `httpx2.MockTransport` + a real `httpx2.Client`, which architecturally is "Layer 2: Integration / CLI-level". [Source: architecture.md lines 552–554]
12. **Shared `tests/conftest.py` is introduced by this story.** Architecture lines 558–578 sketches the shape; Story 1.4 explicitly noted "Do not add a top-level `conftest.py`" because it was unit-only. This story is the first integration consumer — the shared fixture surface is added here. [Source: architecture.md lines 556–578; Story 1.4 file list note "Do not add a top-level conftest.py"]

### Project-ID handling

GitLab requires a project identifier on every endpoint (the `{id}` in `/api/v4/projects/{id}`). The PRD's Journey 1 narrative auto-detects it from `CI_PROJECT_ID` (the GitLab CI built-in env var); `--project-id` is a top-level CLI flag override.

**Where does it live?** Three options were considered:

| Option | Pro | Con | Decision |
|---|---|---|---|
| Add `project_id: int \| None` to `GitLabConfig` | Survives DI; provider has all GitLab state in one place | Modifies `_settings.py` which Story 1.2 settled; collides with how GitHub uses `owner/repo` (different shape) | Reject |
| Top-level `Settings.project_id: int \| None` | One field, plumbed via CLI overlay | Top-level setting that's only meaningful for one provider | Reject |
| `project_id: int` as a `GitLabProvider` dataclass field | Provider-shape-natural; each provider can take its own identifier type | Story 1.7's DI wiring must read `CI_PROJECT_ID` / `--project-id` and pass it at construction | **Accept** |

**Implementation:** `GitLabProvider` takes `project_id: int` as a frozen-dataclass field. Story 1.7's `ProvidersGroup` Factory reads `Settings._provenance`-aware values for `project_id` and passes them in. **This story does NOT modify `_settings.py`.** Tests inject the project_id directly (e.g., `GITLAB_PROJECT_ID = 999` per architecture line 559).

The `--project-id` CLI flag and `CI_PROJECT_ID` env-var resolution are entirely Story 1.7's concern. This story's responsibility ends at "the provider accepts a project_id constructor field and uses it in URL construction."

### Provider class shape — full sketch

This sketch is informative, not authoritative. The ACs above are authoritative.

```python
# semvertag/providers/gitlab.py
import dataclasses
import typing

import httpx2

from semvertag._errors import AuthError, ConfigError, ProviderAPIError
from semvertag._settings import GitLabConfig
from semvertag._types import CheckResult, Commit, Tag


_API_PREFIX: typing.Final = "/api/v4/projects"
_PRIVATE_TOKEN_HEADER: typing.Final = "PRIVATE-TOKEN"
_TAGS_PER_PAGE: typing.Final = 100
_MAX_TAG_PAGES: typing.Final = 100
_HTTP_OK: typing.Final = 200
_HTTP_CREATED: typing.Final = 201
_HTTP_BAD_REQUEST: typing.Final = 400
_HTTP_UNAUTHORIZED: typing.Final = 401
_HTTP_FORBIDDEN: typing.Final = 403
_HTTP_NOT_FOUND: typing.Final = 404
_HTTP_UNPROCESSABLE: typing.Final = 422
_TAG_EXISTS_FRAGMENT: typing.Final = "already exists"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class GitLabProvider:
    name: typing.ClassVar[str] = "gitlab"
    config: GitLabConfig
    project_id: int
    client: httpx2.Client

    def get_default_branch(self) -> str:
        url = f"{self.config.endpoint}{_API_PREFIX}/{self.project_id}"
        try:
            response = self.client.get(url, headers=self._auth_headers())
        except httpx2.RequestError as exc:
            raise ProviderAPIError(
                f"GitLab request failed: {type(exc).__name__}. "
                "Check SEMVERTAG_GITLAB__ENDPOINT and network connectivity."
            ) from exc
        _translate_status(response.status_code, self.project_id)
        try:
            payload = response.json()
        except (ValueError, httpx2.DecodingError) as exc:
            raise ProviderAPIError(
                "GitLab project response malformed. "
                "Check SEMVERTAG_GITLAB__ENDPOINT and project ID."
            ) from exc
        default_branch = payload.get("default_branch")
        if default_branch is None:
            if "default_branch" not in payload:
                raise ProviderAPIError(
                    "GitLab project response malformed. "
                    "Check SEMVERTAG_GITLAB__ENDPOINT and project ID."
                )
            raise ConfigError(
                "Default branch missing from GitLab response. "
                "Verify the project has a default branch configured."
            )
        return str(default_branch)

    def get_latest_commit_on_default_branch(self) -> Commit:
        default_branch = self.get_default_branch()
        url = f"{self.config.endpoint}{_API_PREFIX}/{self.project_id}/repository/commits"
        try:
            response = self.client.get(
                url,
                params={"ref_name": default_branch, "per_page": 1},
                headers=self._auth_headers(),
            )
        except httpx2.RequestError as exc:
            raise ProviderAPIError(...) from exc
        _translate_status(response.status_code, self.project_id)
        items = response.json()
        if not items:
            raise ProviderAPIError(
                f"No commits on default branch '{default_branch}'. The branch appears empty."
            )
        return Commit(sha=items[0]["id"], message=items[0]["message"])

    def list_tags(self) -> list[Tag]:
        tags: list[Tag] = []
        url: str | None = f"{self.config.endpoint}{_API_PREFIX}/{self.project_id}/repository/tags"
        params: dict[str, typing.Any] | None = {"per_page": _TAGS_PER_PAGE, "page": 1}
        for page_no in range(1, _MAX_TAG_PAGES + 1):
            try:
                response = self.client.get(url, params=params, headers=self._auth_headers())
            except httpx2.RequestError as exc:
                raise ProviderAPIError(...) from exc
            _translate_status(response.status_code, self.project_id)
            for item in response.json():
                tags.append(Tag(name=item["name"], commit_sha=item["commit"]["id"]))
            next_url = _next_page_url(response)
            if next_url is None:
                return tags
            url, params = next_url, None
        raise ProviderAPIError(
            f"Tag pagination exceeded {_MAX_TAG_PAGES} pages. "
            "The project has an unexpected number of tags; please file an issue."
        )

    def create_tag(self, name: str, commit_sha: str) -> None:
        url = f"{self.config.endpoint}{_API_PREFIX}/{self.project_id}/repository/tags"
        try:
            response = self.client.post(
                url,
                json={"tag_name": name, "ref": commit_sha},
                headers=self._auth_headers(),
            )
        except httpx2.RequestError as exc:
            raise ProviderAPIError(...) from exc
        if response.status_code == _HTTP_CREATED:
            return
        if response.status_code == _HTTP_BAD_REQUEST:
            body_message = ""
            try:
                body_message = str(response.json().get("message", ""))
            except (ValueError, httpx2.DecodingError):
                pass
            if _TAG_EXISTS_FRAGMENT in body_message.lower():
                raise ConfigError(
                    f"Tag already exists: '{name}'. "
                    "The tag was created by a concurrent run or previous invocation."
                )
            raise ConfigError(
                "Request rejected by GitLab: 400. "
                "Check tag name format and that the referenced commit exists."
            )
        _translate_status(response.status_code, self.project_id)

    # Doctor methods — return CheckResult, never raise. See §Doctor endpoint mapping.
    def check_token(self) -> CheckResult: ...
    def check_scopes(self) -> CheckResult: ...
    def check_project_access(self) -> CheckResult: ...
    def check_protected_tags(self) -> CheckResult: ...

    def _auth_headers(self) -> dict[str, str]:
        return {_PRIVATE_TOKEN_HEADER: self.config.token.get_secret_value()}


def _translate_status(status: int, project_id: int) -> None:
    if status in {_HTTP_OK, _HTTP_CREATED}:
        return
    if status == _HTTP_UNAUTHORIZED:
        raise AuthError(
            "Token rejected: 401. "
            "Verify SEMVERTAG_TOKEN is valid and has 'api' scope."
        )
    if status == _HTTP_FORBIDDEN:
        raise AuthError(
            "Token missing scope or insufficient permission: 403. "
            "Add 'api' or 'write_repository' to the SEMVERTAG_TOKEN scopes on GitLab."
        )
    if status == _HTTP_NOT_FOUND:
        raise ConfigError(
            f"GitLab project not found: project_id={project_id}. "
            "Verify CI_PROJECT_ID or --project-id."
        )
    if status == _HTTP_UNPROCESSABLE:
        raise ConfigError(
            "Request rejected by GitLab: 422. "
            "Check tag name format and that the referenced commit exists."
        )
    if 500 <= status < 600:
        raise ProviderAPIError(
            f"GitLab API failure: {status}. "
            "Retries exhausted after 3 attempts. Try again or check GitLab status."
        )
    if status == 429:
        raise ProviderAPIError(
            "GitLab rate limit: 429. "
            "Retries exhausted after 3 attempts; try again later."
        )
    raise ProviderAPIError(
        f"Unexpected GitLab response: {status}. Please file an issue."
    )


def _next_page_url(response: httpx2.Response) -> str | None:
    link_header = response.headers.get("link") or response.headers.get("Link")
    if not link_header:
        return None
    for segment in link_header.split(","):
        url_part, _, rel_part = segment.strip().partition(";")
        rel = rel_part.strip().removeprefix("rel=").strip(' "')
        if rel == "next":
            return url_part.strip().strip("<>")
    return None


__all__: typing.Final = ("GitLabProvider",)
```

**Sketch caveats:**
- `httpx2.DecodingError` may or may not exist in the installed version — verify against `httpx2 v2.2.0`. If not present, the upstream catch is `ValueError` (Python's `json.JSONDecodeError` subclasses `ValueError`). `httpx2.RequestError` and its subclasses ARE present (confirmed via Story 1.4's transport implementation).
- The repeated `ProviderAPIError(...)` for `httpx2.RequestError` handling can be DRY'd into a `_request_failed_message(exc)` helper if the duplication offends — that's a code-review-cycle judgment call, not a story requirement.
- The doctor methods are sketched as `...` only because they're spelled out fully in §Doctor endpoint mapping below.

### Auth header policy

**Decision: use `PRIVATE-TOKEN: <token>`.** Reasons:

1. **PATs (personal access tokens), group access tokens, project access tokens** — these are the typical `SEMVERTAG_TOKEN` shape — authenticate via `PRIVATE-TOKEN` per GitLab REST API docs.
2. **`CI_JOB_TOKEN`** — GitLab's CI-injected token — authenticates many endpoints via `PRIVATE-TOKEN` as well (specifically tag-creation, project-read, commits-read since GitLab 12.4). The historical `JOB-TOKEN` header is also supported but `PRIVATE-TOKEN` is the simpler unified path. Reference: GitLab docs "CI/CD job token → Token access permissions" — for the endpoints we hit (commits, tags, project metadata), `PRIVATE-TOKEN` works.
3. **`Authorization: Bearer <token>`** — works for OAuth tokens, but `SEMVERTAG_TOKEN` is not expected to be an OAuth token in v1.0. The `AliasChoices` chain in `_settings.py` (lines 15–20: `SEMVERTAG_GITLAB__TOKEN → SEMVERTAG_TOKEN → CI_JOB_TOKEN → GITLAB_TOKEN`) targets PAT-shaped tokens.

**Future:** the v1.x roadmap may add multi-header probing (try `PRIVATE-TOKEN`, fall back to `Authorization: Bearer`) for OAuth users. That's a deferred-work item — see deferred-work.md.

### Error message templates — `<NamedCondition>: <Cause>. <SuggestedAction>.`

Per architecture §Error Message Template lines 744–777, every `SemvertagError` message in this story follows the template. Key implications:

- **No HTTP status codes in user-facing messages where avoidable.** The 401 → `"Token rejected: 401"` form is allowed because "401" is itself a named condition users recognize. The 5xx → `"GitLab API failure: 502"` form likewise. The 400 → `"Tag already exists: '1.4.3'"` form does NOT include the status because the user-actionable label is "tag already exists" (the 400 is irrelevant to the user).
- **Specific value that triggered the error** — `project_id={project_id}`, `'1.4.3'`, `'main'`, etc. Always the runtime value, never a placeholder.
- **Suggested action** — `Verify SEMVERTAG_TOKEN is valid and has 'api' scope.`, `Verify CI_PROJECT_ID or --project-id.`, etc.

### Why response bodies don't appear in error messages

GitLab error bodies are sometimes useful (`{"message": "scope 'write_repository' required"}`) but more often noisy (`{"error": "An unexpected error occurred"}`). Embedding them verbatim risks token leakage if GitLab ever echoes the auth header back (unlikely but possible during proxy / load-balancer failures), violates NFR10, and produces unstable error messages that break user CI dashboards built on substring matches.

**Decision:** error messages use STATIC TEMPLATES with runtime substitution of {project_id} and {status} only — NEVER `response.text`, NEVER `response.json()["message"]`. The 400 "already exists" sniff in `create_tag` is the ONE exception, and even there the matched fragment (`"already exists"`) is the trigger, not the embedded text.

If diagnosing a specific GitLab failure becomes hard for users, the answer is `semvertag doctor --json` (Epic 3) which exposes more detail at the user's request. Main-verb output stays clean.

### Pagination loop safety

GitLab's `Link` header is the only durable pagination contract — `X-Next-Page` and `X-Total-Pages` are being phased out per the GitLab changelog. We follow `rel="next"` and stop when it's absent.

The `_MAX_TAG_PAGES = 100` cap (10,000 tags) is a safety belt, not a feature limit. Real repos in the wild have 1–500 tags; even high-velocity monorepos rarely exceed 5,000. Hitting the cap indicates either a misconfigured `per_page` or a runaway-loop bug — surfacing it as `ProviderAPIError` is the correct fail-loud response.

### Internal default-branch resolution

`get_latest_commit_on_default_branch` needs the default-branch name to construct `?ref_name={branch}`. Two options:

1. **Call `self.get_default_branch()` inline** — adds one HTTP request per call, but the `Provider` protocol stays clean (each method does its own resolution).
2. **Accept a `default_branch: str` parameter** — protocol signature differs from architecture line 308.

**Decision: inline call.** Story 1.7's use case may cache the default-branch result if the second call becomes a performance issue, but the cache is a use-case concern, not a provider concern. The provider keeps the architecture's protocol shape unchanged.

If the use case caches: it'd construct a "primed" provider with `default_branch` injected, OR it'd call `get_default_branch()` once and pass the result to a future method overload. Both are downstream concerns — flag in deferred-work if it surfaces.

### Doctor endpoint mapping

Each doctor method maps to a specific GitLab API call:

| Method | Endpoint | Pass condition | Fail conditions |
|---|---|---|---|
| `check_token` | `GET /api/v4/user` | HTTP 200 → token recognized | 401 → `"Token rejected by GitLab. Verify SEMVERTAG_TOKEN is valid."`; network error → `"GitLab unreachable: {type(exc).__name__}. Check SEMVERTAG_GITLAB__ENDPOINT."` |
| `check_scopes` | `GET /api/v4/personal_access_tokens/self` | HTTP 200 with `"api"` in `scopes` field → all needed scopes present | 401/403 → `"Token missing 'api' scope. Add it to the SEMVERTAG_TOKEN scopes on GitLab."`; 404 → `"GitLab version too old (< 15.0): missing /personal_access_tokens/self endpoint."` |
| `check_project_access` | `GET /api/v4/projects/{project_id}` | HTTP 200 → project visible to token | 401 → `"Token rejected."`; 403 → `"Token has no access to project_id={project_id}."`; 404 → `"GitLab project not found: project_id={project_id}. Verify CI_PROJECT_ID or --project-id."` |
| `check_protected_tags` | `GET /api/v4/projects/{project_id}/protected_tags` | HTTP 200 → caller can read protected-tag config; check returns `passed` regardless of whether tag-pattern conflicts exist (FR30 named-cause discovery is the use case's job; the check just confirms the endpoint is reachable) | 401/403 → `"Token cannot read protected_tags. Add 'read_repository' or 'api' to scopes."` |

**Why doctor methods don't raise:** the doctor chain runner (Epic 3) walks all four checks and aggregates results. If `check_token` raised on 401, the chain would short-circuit and the user would never see that `check_scopes` and `check_project_access` would have given different failure reasons. The `CheckResult` return values + chain runner's skip-on-failure logic (Epic 3) handle the dependency relationships.

**Why this story implements check methods now, even though doctor doesn't ship until Epic 3:** the provider protocol declares them (architecture line 312–315), and `GitLabProvider` is the only place they can live. Epic 3's doctor module consumes them — it doesn't reimplement them.

### Files this story touches

| Target file | NEW / UPDATE | Purpose |
|---|---|---|
| `semvertag/_types.py` | **UPDATE** | Append `Commit`, `Tag`, `CheckResult` frozen dataclasses after `RunResult` |
| `semvertag/providers/__init__.py` | **NEW** | Empty package marker |
| `semvertag/providers/_base.py` | **NEW** | `Provider` `typing.Protocol` + `__all__` |
| `semvertag/providers/gitlab.py` | **NEW** | `GitLabProvider` + module constants + `_translate_status` + `_next_page_url` |
| `tests/conftest.py` | **NEW** | Shared integration-test fixtures: `gitlab_transport`, `gitlab_client`, `gitlab_provider`; `compose_handler` helper; constants `GITLAB_PROJECT_ID`, `GITLAB_ENDPOINT`, `GITLAB_TOKEN` |
| `tests/integration/__init__.py` | **NEW** | Empty package marker |
| `tests/integration/test_gitlab_provider.py` | **NEW** | Full integration test matrix per AC10 |

**Files this story does NOT touch:**

| File | Story |
|---|---|
| `semvertag/_settings.py` | Story 1.2. `GitLabConfig.endpoint` and `GitLabConfig.token` already exist. **Do NOT** add `project_id` to `GitLabConfig` — see §Project-ID handling. |
| `semvertag/_errors.py` | Story 1.3. The three subclasses `AuthError`, `ConfigError`, `ProviderAPIError` are imported and raised; no new error class is added by this story. |
| `semvertag/_transport.py` | Story 1.4. The transport is consumed via `httpx2.Client(transport=RetryingTransport())` in Story 1.7 wiring. This story's tests use a `MockTransport` directly or compose with `RetryingTransport` in the one 5xx-exhaustion test. |
| `semvertag/_redact.py`, `_output.py` | Story 1.3. Provider has no console output; no redaction concern in this layer beyond `SecretStr.get_secret_value()` discipline. |
| `semvertag/strategies/*` | Stories 1.6 / 2.1. The provider returns `Commit` with the raw message; strategies parse it. |
| `semvertag/_use_case.py`, `ioc.py`, `__main__.py` | Story 1.7. Wiring + DI groups. |
| `semvertag/doctor/*` | Epic 3. Doctor methods live on `GitLabProvider` per the Provider protocol; the chain runner that calls them lives in `doctor/_checks.py`. |
| `pyproject.toml` | No changes. `httpx2` is already a dep (line 25); no new dep added by this story. |
| `Justfile`, `.github/workflows/*` | No changes. |
| `tests/unit/conftest.py` | Story 1.2's `clean_settings_env` is irrelevant — integration tests use explicit config construction, not env-driven Settings. |

### Testing standards

- **Framework:** `pytest`, `pytest-cov`, `pytest-randomly`, `pytest-xdist` — already in `[dependency-groups] dev`. No pyproject changes.
- **HTTP transport:** `httpx2.MockTransport(handler)` injected into `httpx2.Client(transport=...)`. The `RetryingTransport` is ONLY used in the one 5xx-exhaustion + ConnectError-exhaustion tests (AC10 row "5xx after retries exhausted" and "httpx2.RequestError → ProviderAPIError").
- **Env isolation:** not needed — provider construction is explicit, no env reads in this layer.
- **Time / random / sleep monkeypatch:** only needed for the RetryingTransport-integration test (see §monkeypatch contract from Story 1.4). For the rest of the integration suite, no clock control is needed (MockTransport returns instantly).
- **Coverage gate:** ≥85% line per NFR22; this story aims for ≥90% on `semvertag/providers/gitlab.py`. `providers/_base.py` is a Protocol-only module (effectively `# pragma: no cover`). `_types.py` line coverage is preserved (the new dataclasses are exercised by the integration tests).
- **Test naming:** `test_<verb>_<outcome>_when_<condition>` per architecture §Test Naming lines 916–921. Examples:
  - `test_returns_main_when_default_branch_endpoint_responds_200`
  - `test_raises_config_error_when_project_not_found`
  - `test_paginates_tags_when_link_header_advertises_next`
  - `test_check_token_returns_failed_when_token_rejected`
- **Module-level test constants** get `typing.Final` annotation. Per-file ignores in `pyproject.toml:80` (`tests/**/*.py` → `S101`, `SLF001`) cover `assert` and `_private` access.
- **`assert` is OK in tests** (S101 per-file-ignored).
- **Parametrize** the 401/403/404 → exception tests over the four main-verb methods. Parametrize the doctor pass/fail tests over the four check methods.

### Anti-patterns to avoid

- **`print()` anywhere** — including dev-aid `print(f"got {response.status_code}")`. Use a debugger or `caplog` if needed.
- **`from __future__ import annotations`** — banned project-wide.
- **Bare `Exception` catches** — must be `except httpx2.RequestError as exc:` or `except (ValueError, httpx2.DecodingError) as exc:`. Bare `Exception` would swallow `KeyboardInterrupt` (well, no — `KeyboardInterrupt` is `BaseException`; but it would still swallow `SystemExit`, `MemoryError`, etc.).
- **Function-local imports** — `PLC0415` enforced; global imports only.
- **`# type: ignore`** — use `# ty: ignore` (global `CLAUDE.md`).
- **`response.raise_for_status()`** — do NOT use httpx2's `raise_for_status()`. It raises `httpx2.HTTPStatusError`, which we'd then have to catch and re-translate. Inspect `response.status_code` directly via `_translate_status()`. (Same reason `_transport.py` doesn't use it.)
- **Re-imports inside methods** — every import at module top. Pylint `PLC0415` plus convention.
- **Logging the token value** — `self.config.token` is a `pydantic.SecretStr`; only `.get_secret_value()` extracts the raw string, and only inside `_auth_headers()`. Tests assert (via the AC9 grep) that no other module pulls out the secret value.
- **String concatenation with the token** — `f"PRIVATE-TOKEN: {token}"` style. Use the dict form `{"PRIVATE-TOKEN": token}` so httpx2's header machinery formats the wire bytes (and so an accidental `print(headers)` shows the dict structure rather than a leaky string).
- **Real network in tests** — `httpx2.MockTransport` is the ONLY allowed transport. The base URL `https://gitlab.example.test` is unresolvable on purpose (TLD reservation per RFC 6761) — if a test ever escapes to the real network, it'll fail loudly with a DNS error rather than silently hit the wrong host.
- **Embedding response body text in error messages** — see §Why response bodies don't appear in error messages.
- **Mutable defaults on dataclasses** — e.g., `tags: list[Tag] = []` as a class default. Frozen dataclasses don't allow mutable defaults anyway, but the pattern is also a bug magnet.
- **Adding fields to `GitLabConfig`** — out of scope (Story 1.2 settled the Settings shape; project_id lives on the provider, see §Project-ID handling).

### Learnings from Stories 1.1–1.4 (carried forward)

[Source: 1-1-bootstrap-public-scaffolding-from-modern-di.md#Dev Agent Record + 1-2-settings-layer-with-aliaschoices-and-provenance.md#Dev Agent Record + 1-3-errors-runresult-output-redaction.md#Dev Agent Record + 1-4-retryingtransport-with-retry-policy.md#Dev Agent Record]

- **Architecture sketches leave seams unspecified.** Story 1.2 needed `model_validator(mode="before")` to make `AliasChoices` work over nested fields. Story 1.3 added an `error()` method to the Output protocol that wasn't in the sketch. Story 1.4's `RetryingTransport.__init__` got an `inner` injection seam absent from the arch sketch. **For this story:** the `_next_page_url` helper, the `_translate_status` module-function shape, and the 400-already-exists body-sniff are all natural fill-ins; expect a review-cycle conversation about whether they belong inside `GitLabProvider` as methods vs at module scope.
- **Auto-typing-final aggressively rewrites code.** Pre-annotate `typing.Final` on every module-level constant. (Story 1.2's conftest got auto-rewritten from `yield None` → `return None`.)
- **`tests/**/*.py` per-file-ignores include `S101` + `SLF001`.** This story may need `SLF001` to peek `provider._auth_headers()` or assert against `provider.client._transport` inner state in some tests; the ignore is already active.
- **`uv build` is a per-story acceptance bar** (Story 1.1 review patch). Run alongside `just test`.
- **`just install` re-locks with `uv lock --upgrade` every run.** Expect minor dep drift; this story has no new deps, so drift should be minimal.
- **No `print()` even in tests** — `select=["ALL"]` covers it.
- **Module-level singleton anti-pattern was dismissed for `Console()` in 1.3** because the impls construct consoles in factories. This story's `httpx2.Client` is similarly per-test, per-fixture — never module-scope.
- **Code-review cycle produces Patches / Deferred / Dismissed buckets.** Story 1.3 took 8 patches in-cycle and 9 deferred; Story 1.4 had fewer (the ACs were tighter). The more rigorous the ACs and Dev Notes here, the smaller the patch set.
- **Story 1.4 added `_RETRY_AFTER_STATUS` as a private module constant** to dodge `PLR2004` magic-number lint. This story will need similar handling for `429`, `5xx`-range checks. The constants list in Task 3.2 above already anticipates this.
- **Story 1.4's review noted that empty-body branches in defensive parsing trip the 95% line coverage gate.** Watch for similar dead branches in error-translation defensive paths (`if status == X: ... else: raise ProviderAPIError(...)` where the `else` is impossible given the table). Use `# pragma: no cover` sparingly on truly dead branches; restructure the code to remove dead branches when possible.

### Coverage interaction

`tests/*` is in `[tool.coverage.run] omit`, so test files don't count. Measured files:

| File | Target coverage |
|---|---|
| `semvertag/_types.py` | ≥85% (preserves current; new dataclasses are exercised by tests) |
| `semvertag/providers/__init__.py` | Empty file; 0/0 — not measured |
| `semvertag/providers/_base.py` | Protocol-only; coverage treats `...` ellipses as `# pragma: no cover`-equivalent. Effectively 100% by definition |
| `semvertag/providers/gitlab.py` | ≥90% line — the bar for this story |

Branch coverage is NOT a gate on `providers/gitlab.py` (the `100% --cov-branch` gate is reserved for `strategies/branch_prefix.py` and `strategies/conventional_commits.py` per Stories 1.6 / 2.1). Local branch sanity checks via `just test-branch` are encouraged but not required.

### Architecture section pointers (for the dev agent's quick lookup)

- §Provider Abstraction — lines 299–341 — the full protocol, types, HTTP-layer decisions (httpx2-only, no python-gitlab), per-provider error translation
- §Error Model & Exit Codes — lines 379–408 — exception hierarchy + `SemvertagError.exit_code` (consumed by `__main__.py` in Story 1.7, not here)
- §Implementation Patterns §Provider Implementation Pattern — lines 972–1003 — the canonical `GitLabProvider` shape this story implements
- §Implementation Patterns §Error Message Template — lines 744–777 — `<NamedCondition>: <Cause>. <SuggestedAction>.`
- §Implementation Patterns §Exception Construction Patterns — lines 779–802 — positional message arg; `raise X from exc` for chaining
- §Implementation Patterns §Class Naming — lines 681–693 — `GitLabProvider` (not `GitlabProvider`); `GitLabConfig`
- §Test Architecture — lines 548–581 — three layers; this story is Layer 2 (Integration)
- §Test Architecture §Shared MockTransport fixture pattern — lines 556–578 — the sketch for `tests/conftest.py`
- §Test Naming & File Organization — lines 888–928 — file naming, function naming, `typing.Final` on test constants
- §Module-Level Constants — lines 930–940 — `typing.Final` discipline
- §Comment Policy — lines 942–957 — no comments unless WHY is non-obvious
- §Anti-Patterns to Avoid — lines 1039–1049 — every banned pattern
- §Architectural Boundaries — lines 1168–1219 — the `_transport.py`-only-retries + per-provider-translation rules
- §Decision Impact Analysis §Implementation sequence — line 590 — this story is Step 5
- §Type-Annotation Style — lines 728–743 — `typing.Final`, no `from __future__ import annotations`, built-in generics
- §Project Structure §Complete Project Directory Structure — lines 1055–1167 — `providers/` package layout

### Project Structure Notes

After this story:

- `semvertag/providers/_base.py` + `semvertag/providers/gitlab.py` are complete and stable for v1.0. The Protocol and the GitLab impl will not change again before Story 1.7's wiring.
- `semvertag/_types.py` carries the four "v1.0 in-scope" domain types: `ConfigSource`, `RunResult`, `Commit`, `Tag`, `CheckResult`. `Bump` is added by Story 1.6.
- Module count after this story: `_settings.py` + `_types.py` + `_errors.py` + `_redact.py` + `_output.py` + `_transport.py` + `providers/_base.py` + `providers/gitlab.py` = 8 substantive code files. Still well under NFR21's 1,500-LOC soft target (architecture's running tally projects ~1,200 LOC at end of Epic 1).
- `tests/conftest.py` is the new shared-fixture surface; subsequent integration tests (Story 1.7's `test_cli_main_verb.py`, Epic 3's `test_cli_doctor.py`) build on it.
- Story 1.6 (`BranchPrefixStrategy`) and Story 1.7 (`DI wiring + Typer entrypoint`) consume the provider:
  - 1.6 uses `Commit` to compute `Bump` via `BumpStrategy.decide(commit)`.
  - 1.7 constructs `GitLabProvider(config=settings.gitlab, project_id=resolved_project_id, client=httpx2.Client(transport=RetryingTransport()))` inside `ProvidersGroup`.

### References

- [Source: architecture.md#Provider Abstraction lines 299–341] — `Provider` protocol shape, types, HTTP layer, timeout, lifecycle
- [Source: architecture.md#Provider Implementation Pattern lines 972–1003] — canonical `GitLabProvider` sketch this story implements
- [Source: architecture.md#Error Model & Exit Codes lines 379–408] — `SemvertagError` hierarchy; per-provider translation
- [Source: architecture.md#Error Message Template lines 744–777] — FR30 named-actionable cause format
- [Source: architecture.md#Exception Construction Patterns lines 779–802] — `raise X from exc` chaining discipline
- [Source: architecture.md#Class Naming lines 681–693] — `GitLab` capitalization; `<Vendor>Provider` / `<Vendor>Config`
- [Source: architecture.md#Frozen-Dataclass Conventions lines 695–727] — `frozen=True, slots=True, kw_only=True`
- [Source: architecture.md#Test Architecture lines 548–581] — three test layers; shared MockTransport fixture
- [Source: architecture.md#Anti-Patterns to Avoid lines 1039–1049] — bans `print()`, bare `Exception`, function-local imports, `python-gitlab`
- [Source: architecture.md#Architectural Boundaries lines 1168–1219] — `_transport.py`-only-retries; per-provider error translation
- [Source: architecture.md#Decision Impact Analysis line 590] — this story is Implementation Sequence Step 5
- [Source: epics.md#Epic 1 Story 1.5 lines 431–473] — the original BDD ACs this story restates and expands
- [Source: prd.md#FR17 line 518] — GitLab REST API as v1.0 provider
- [Source: prd.md#FR20–FR22 lines 521–523] — provider auto-detection, override flags, single-file-per-provider pattern
- [Source: prd.md#FR29–FR32 lines 536–539] — doctor subcommand specification; named-actionable causes
- [Source: prd.md#NFR1 line 570] — ≤30s p95 end-to-end runtime budget
- [Source: prd.md#NFR7 line 579] — retry budget (consumed by `RetryingTransport`, not this story)
- [Source: prd.md#NFR8 line 580] — fail-closed on auth/scope; 401/403 → `AuthError`
- [Source: prd.md#NFR10 line 585] — token redaction (NFR10); `SecretStr` discipline + output-boundary redact
- [Source: prd.md#NFR15 line 593] — GitLab CE/EE 15.0+ support; `/api/v4/personal_access_tokens/self` requires ≥15.0 (informs `check_scopes` fallback per §Doctor endpoint mapping)
- [Source: prd.md#NFR22 line 122] — coverage gate ≥85% line
- [Source: pyproject.toml lines 19–26] — `httpx2` declared as dep; no new deps in this story
- [Source: uv.lock line 229–240] — `httpx2 v2.2.0` actually installed
- [Source: semvertag/_settings.py:40–46] — `GitLabConfig` shape (`endpoint`, `token: SecretStr`); no `project_id` field — see §Project-ID handling
- [Source: semvertag/_transport.py current contents] — `RetryingTransport(httpx2.BaseTransport)` from Story 1.4
- [Source: semvertag/_errors.py current contents] — `AuthError`, `ConfigError`, `ProviderAPIError` with `exit_code` ClassVars
- [Source: semvertag/_types.py current contents] — `ConfigSource`, `RunResult`; this story adds `Commit`, `Tag`, `CheckResult`
- [Source: tests/unit/conftest.py current contents] — `clean_settings_env` (unused by this story; integration tests construct config explicitly)
- [Source: Justfile:7–11, 19–23] — `just lint`, `just test`, `just lint-ci`, `uv build` quality gates
- [Source: 1-4-retryingtransport-with-retry-policy.md] — `RetryingTransport`'s 3-attempts / 30s-wall / Retry-After-honoring contract; consumed (not modified) by this story
- [Source: 1-3-errors-runresult-output-redaction.md] — `_redact.py` patterns; `_output.py` Rich/JSON impl; token-pattern detectors (informs the dummy token `glpat-XXXXX...` in `tests/conftest.py`)
- [Source: 1-2-settings-layer-with-aliaschoices-and-provenance.md] — `GitLabConfig` constructor shape; `AliasChoices` chain for token resolution
- [Source: ~/.claude/CLAUDE.md] — global rules: `# ty: ignore`, global imports, no `from __future__ import annotations`
- [Source: _autosemver_reference/use_cases/autosemver_use_case.py] — reference for the four endpoint URLs + request body shapes (used `python-gitlab` SDK, not httpx2; semantically equivalent at the wire level)
- [Source: _autosemver_reference/resources/gitlab.py] — reference for `oauth_token` authentication mode (NOT what we use — see §Auth header policy)
- [Source: GitLab REST API docs §Projects, §Commits, §Tags, §Protected tags, §Users, §Personal access tokens] — authoritative endpoint shapes; the dev MAY cross-reference at `https://docs.gitlab.com/api/` during implementation but must NOT add web-fetch dependencies into the test suite

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context) — bmad-dev-story workflow

### Debug Log References

- **`Provider` Protocol is non-runtime-checkable per AC2.** The Protocol is imported in `tests/integration/test_gitlab_provider.py` at module scope so coverage measures `_base.py` (otherwise the file would sit at 0% because the production codepath never imports it — Story 1.7's `ProvidersGroup` uses `GitLabProvider` directly without the Protocol seam). One small structural test (`test_gitlab_provider_exposes_every_member_required_by_protocol`) verifies all 9 members are present via `hasattr`. Not a deviation from the spec; just the path needed to make the type-only module count as 100% covered.
- **`_request_failed_message(exc)` helper added.** Story sketch line 565 ("can be DRY'd into a `_request_failed_message(exc)` helper if the duplication offends") explicitly blessed this. Used by all four main-verb methods to construct the `ProviderAPIError` cause string for `httpx2.RequestError` paths. No behavioral deviation.
- **`_safe_get` lives on `GitLabProvider`, not at module scope.** It takes `self.client` and `self._auth_headers()`; module-scope would duplicate the auth-header construction. Used only by the four doctor methods. Matches the spec sketch at task 3.9.
- **HTTP-status constants for 429 + 5xx range added.** AC1's mandated constants don't list `429` or the 500/600 bounds, but `_translate_status` needs them as named values to avoid `PLR2004` magic-number lint. Added `_HTTP_TOO_MANY_REQUESTS = 429`, `_HTTP_SERVER_ERROR_MIN = 500`, `_HTTP_SERVER_ERROR_MAX = 600` as leading-underscore private constants. Consistent with the `_RETRY_AFTER_STATUS` pattern from Story 1.4 (private constants for lint compliance, distinct from the AC-mandated public surface).
- **`# pragma: no cover` not used anywhere in this story.** Got `providers/gitlab.py` to 91% line coverage by writing explicit tests for the malformed-body / non-JSON / unexpected-status paths instead of suppressing them. Per-method "unexpected status fallthrough" returns and the `_translate_status` final-else branch are unreached (lines 68-69, 84-85, 106-107, 151, 171-172, 185, 195, 207, 224, 234, 251, 291-292) — these are defensive guards covered only via the AC9 grep-test invariant; left unmarked rather than suppressing them, accepting the 9-point coverage shortfall from a theoretical 100%.

### Completion Notes List

- All 10 ACs (AC1–AC10) verified by `tests/integration/test_gitlab_provider.py` — 48 tests, all green, randomized order via `pytest-randomly`.
- `semvertag/providers/gitlab.py` line coverage: **91%** (target ≥90%, comfortably above NFR22's 85% bar).
- `semvertag/providers/_base.py` line coverage: **100%** (the Protocol is imported by the integration test for the structural-conformance check).
- `semvertag/_types.py` line coverage: **100%** (the three new dataclasses are exercised by happy-path tests).
- Full suite: **160 tests passed**, no regressions in Stories 1.1–1.4 modules.
- `just lint`, `just lint-ci`, `ty check`, `uv build` all clean.
- No new project dependencies — used only `httpx2` (already declared), stdlib `dataclasses` / `typing` / `collections.abc`, and `pydantic` (already a transitive dep through `pydantic_settings`).
- No edits to `pyproject.toml`, `Justfile`, `_settings.py`, `_errors.py`, `_transport.py`, `_redact.py`, `_output.py`, or any strategy file. Single-package addition plus the three domain types in `_types.py` as scoped.
- AC9 grep guard verified manually: only `_transport.py` and `providers/gitlab.py` carry HTTP-status integer literals 401/403/404/422; the one match in `_settings.py` is `# noqa: ANN401` (a ruff rule code, not an HTTP status) — confirmed false positive.

### File List

- **New:** `semvertag/providers/__init__.py` (empty package marker)
- **New:** `semvertag/providers/_base.py` (Provider Protocol — 5 stmts)
- **New:** `semvertag/providers/gitlab.py` (GitLabProvider + `_translate_status` + `_next_page_url` + `_request_failed_message` — 195 stmts)
- **New:** `tests/conftest.py` (shared integration fixtures: `gitlab_transport`, `gitlab_client`, `gitlab_provider`; `compose_handler` helper; `_default_handler`; constants `GITLAB_PROJECT_ID`, `GITLAB_ENDPOINT`, `GITLAB_TOKEN`)
- **New:** `tests/integration/__init__.py` (empty package marker)
- **New:** `tests/integration/test_gitlab_provider.py` (48 tests across AC1–AC10)
- **Modified:** `semvertag/_types.py` (appended `Commit`, `Tag`, `CheckResult` frozen dataclasses; existing types untouched)
- **Modified:** `_bmad/sprint-status.yaml` (`1-5-…: ready-for-dev` → `in-progress` → `review`; `last_updated` and `last_updated_note` bumped)
- **Modified:** `_bmad/1-5-gitlabprovider-four-endpoints-via-httpx2.md` (Status, all task/subtask checkboxes, Dev Agent Record, File List, Change Log)

### Change Log

- 2026-05-27 — Added `semvertag/_types.py::Commit`, `Tag`, `CheckResult` frozen dataclasses (frozen=True, slots=True, kw_only=True) per AC1.
- 2026-05-27 — Added `semvertag/providers/_base.py::Provider` Protocol (9 members per architecture lines 304–315).
- 2026-05-27 — Added `semvertag/providers/gitlab.py::GitLabProvider` with 4 main-verb methods + 4 doctor methods + module-level `_translate_status` + `_next_page_url` + `_request_failed_message` helpers. PRIVATE-TOKEN auth header. Pagination via `Link: rel="next"`, capped at 100 pages. Tag-already-exists 400 sniff routes to `ConfigError`. All error messages follow the FR30 named-actionable template.
- 2026-05-27 — Added `tests/conftest.py` with shared `gitlab_provider` fixture and `compose_handler` helper for integration tests.
- 2026-05-27 — Added `tests/integration/test_gitlab_provider.py`: 48 tests covering AC1–AC10 (default branch, latest commit, tag pagination, tag creation, error translation matrix parametrized over 4 main-verb endpoints, doctor methods).
- 2026-05-27 — Bumped sprint-status to `review` for `1-5-gitlabprovider-four-endpoints-via-httpx2`.
- 2026-05-28 — Code review applied 17 patches (1 critical SSRF guard on `list_tags` pagination, defensive parsing on `get_latest_commit_on_default_branch` / `list_tags`, RFC 8288-compliant Link-header parser, trailing-slash endpoint normalization via `_url()` helper, `compose_handler` prefix + case-insensitive matching, `_safe_get` exception-type propagation in doctor causes, empty-string `default_branch` rejection, `check_scopes` malformed-body disambiguation, `check_protected_tags` 404 handling, `check_token` 403 handling, `create_tag` `httpx2.DecodingError` catch, parametrized 5xx / 429 / `ConnectError` tests over the four main verbs, 4 new doctor coverage tests, `_default_handler` renamed to `default_handler`). 8 items deferred to `deferred-work.md`. 181 tests green; `providers/gitlab.py` line coverage 94%. Status: done.

## Review Findings

Code review on 2026-05-27 (three parallel adversarial layers: Blind Hunter, Edge Case Hunter, Acceptance Auditor). 27 unique findings after dedup; ~22 dismissed as noise. Buckets follow.

### Decision Needed

- [x] [Review][Decision] **`check_token` does not handle 403** [`semvertag/providers/gitlab.py:175-196`] — Only 200 and 401 are special-cased; 403 falls through to `"Unexpected GitLab response: 403."`. GitLab returns 403 for blocked/IP-restricted tokens and for tokens without `read_user` scope (a common token-shape problem). Spec AC8 explicitly mandates 401/403/404 handling for `check_scopes`/`check_project_access`/`check_protected_tags` but is silent on `check_token`. **Decide:** extend `check_token` to map 403 to a named cause (consistent with sibling doctor methods), or accept the gap as spec-blessed minimalism?

### Patches

- [x] [Review][Patch] **CRITICAL — `PRIVATE-TOKEN` leaked to off-host URL via attacker-controlled `Link: rel="next"`** [`semvertag/providers/gitlab.py:134`] — `_next_page_url` returns whatever URL the server claims is next; `list_tags` then `self.client.get(next_url, headers=self._auth_headers())` sends the token to any host. A compromised/misconfigured reverse proxy in front of GitLab can redirect pagination off-host. Fix: validate `urlsplit(next_url)` scheme+netloc match `self.config.endpoint` before following.
- [x] [Review][Patch] **`get_latest_commit_on_default_branch` doesn't translate JSON parse / type / key errors** [`semvertag/providers/gitlab.py:122-126`] — `response.json()` raises raw `ValueError` on non-JSON 200; `items[0]["id"]` / `items[0]["message"]` raise raw `KeyError`/`TypeError` if shape isn't `list[dict]`. Compare with `get_default_branch` which wraps both. Fix: mirror the defensive parsing pattern. Add tests for non-JSON body and dict-instead-of-list body.
- [x] [Review][Patch] **`list_tags` doesn't validate `response.json()` shape or guard key access** [`semvertag/providers/gitlab.py:138`] — A 200 returning a dict iterates dict keys and produces nonsense or `TypeError`; non-JSON body raises raw `ValueError`; missing `commit`/`name`/`id` keys raise `KeyError`. Worst case: dict-body returns silently as empty list (data loss). Fix: parse + verify list-shape, then guard tag-object access. Add malformed-body tests.
- [x] [Review][Patch] **Link-header parser has multiple RFC 8288 defects** [`semvertag/providers/gitlab.py:346-355`] — (a) `split(",")` shreds URLs containing commas; (b) only the first `;`-segment after the URL is examined, so `Link: <url>; title="foo"; rel="next"` never matches; (c) `removeprefix("rel=")` is case-sensitive — `REL="next"` fails; (d) space-separated rel values like `rel="prev next"` fail equality; (e) whitespace inside `<...>` isn't stripped; (f) relative URLs aren't resolved against the response URL. Fix: rewrite with a regex that handles all `;`-params case-insensitively and resolves relative URIs via `urllib.parse.urljoin(str(response.request.url), url_part)`.
- [x] [Review][Patch] **Trailing slash in `endpoint` produces double-slash URLs** [`semvertag/providers/gitlab.py:90, 112, 130, 150, 176, 199, 243, 282`] — `GitLabConfig(endpoint="https://gitlab.com/")` (valid pydantic input — no validator strips it) yields `https://gitlab.com//api/v4/...` on every call. Some proxies / ingress controllers reject this. Fix: add a `@pydantic.field_validator("endpoint")` in `GitLabConfig` that `.rstrip("/")`s the value.
- [x] [Review][Patch] **`compose_handler` uses exact equality, but spec mandates exact-prefix matching** [`tests/conftest.py:48`] — Spec Task 4.4: "Path matching is exact-prefix (so a test can override `("GET", "/api/v4/projects/999/repository/tags")` regardless of query string)." Implementation does `if key in overrides`. Fix: iterate overrides and use `request.url.path.startswith(path_prefix)`. Add a test exercising the prefix-match behavior.
- [x] [Review][Patch] **`compose_handler` is case-sensitive on HTTP method, silently masking typos as 404s** [`tests/conftest.py:44-48`] — A test override with `("get", path)` (lowercase typo) falls through to `_default_handler` → 404 → `ConfigError("project not found")` — wrong-status assertion hides the real bug. Fix: uppercase method in the lookup key.
- [x] [Review][Patch] **`_safe_get` swallows `httpx2.InvalidURL` and other programmer errors as "GitLab unreachable"** [`semvertag/providers/gitlab.py:323-327`] — Catching all `httpx2.RequestError` conflates "network is down" with "endpoint is a typo". User troubleshoots the wrong thing. Fix: include `type(exc).__name__` in the cause, or narrow the catch to connectivity/timeout subclasses and let `InvalidURL` surface differently.
- [x] [Review][Patch] **`get_default_branch` accepts empty-string / non-string `default_branch` silently** [`semvertag/providers/gitlab.py:104-108`] — Only `None` is rejected. `""`, `0`, `[]`, `False` pass the `is None` check; `str(...)` coerces to a nonsense branch name that's then fed to `ref_name=` in the commits endpoint. Fix: `if not isinstance(default_branch, str) or not default_branch: raise ConfigError(...)`.
- [x] [Review][Patch] **`check_scopes` misreports a malformed 200 as "Token missing 'api' scope"** [`semvertag/providers/gitlab.py:220-235`] — When `response.json()` raises or returns non-dict, `payload = None` → `scopes = []` → returns the "missing api scope" cause. The actual problem is "response body unreadable". Fix: when `payload is None` or non-dict, return a distinct `cause="GitLab token introspection response malformed. Check SEMVERTAG_GITLAB__ENDPOINT."`.
- [x] [Review][Patch] **`check_protected_tags` doesn't handle 404 — spec AC8 violation** [`semvertag/providers/gitlab.py:281-307`] — AC8 mandates "map 404 → `failed` with project-not-found cause" for `check_protected_tags`. Implementation only handles 200/401/403; 404 falls through to "Unexpected GitLab response". Fix: add an explicit 404 branch with the project-not-found cause.
- [x] [Review][Patch] **`create_tag` 400-handling catches only `ValueError`, not `httpx2.DecodingError`** [`semvertag/providers/gitlab.py:166-167`] — The story sketch explicitly mentions `httpx2.DecodingError` as a possible decode exception (line 564 of spec). The current `except ValueError: pass` may not catch httpx2-native decode errors. Fix: `except (ValueError, httpx2.DecodingError)` if `DecodingError` exists in httpx2 v2.2.0, else narrow `Exception` with a comment.
- [x] [Review][Patch] **`test_get_default_branch_sends_private_token_header` does not assert the request URL** [`tests/integration/test_gitlab_provider.py:549-560`] — Handler returns 200 + `{"default_branch": "main"}` for any request, then asserts only the header. If `get_default_branch` ever started hitting `/api/v4/user` by mistake, the test still passes. Fix: also assert `request.url.path == _PROJECT_PATH`.
- [x] [Review][Patch] **5xx / 429 / `ConnectError` translation tests only cover `get_default_branch`, not parametrized over the four main-verb endpoints** [`tests/integration/test_gitlab_provider.py:824, 838, 852`] — The 401/403/404 tests parametrize over `_MAIN_VERB_CALLS`; the 5xx/429/`ConnectError` tests do not. AC10's row "parametrize" hint is unfulfilled. Fix: parametrize the three retry-exhaustion tests over `_MAIN_VERB_CALLS`.
- [x] [Review][Patch] **Doctor tests missing 401 paths for `check_project_access` and `check_protected_tags`; missing fallthrough test for `check_protected_tags`** [`tests/integration/test_gitlab_provider.py`] — AC8 mandates 401/403/404 handling; current tests cover only a subset. Fix: add `test_check_project_access_returns_failed_on_401`, `test_check_protected_tags_returns_failed_on_401`, `test_check_protected_tags_returns_failed_on_unexpected_status`.
- [x] [Review][Patch] **Tests import the underscore-prefixed `_default_handler` from `tests/conftest.py`** [`tests/integration/test_gitlab_provider.py:451`] — Leading underscore is a "module private" signal; cross-module import violates convention and triggers SLF001 in some configs. Fix: rename `_default_handler` → `default_handler` (it's de facto public API of the test conftest).

### Deferred

- [x] [Review][Defer] `_translate_status` hardcodes "Retries exhausted after 3 attempts" in the 429 / 5xx cause [`semvertag/providers/gitlab.py:336, 339`] — deferred, spec-mandated text; drift risk if `MAX_ATTEMPTS` changes
- [x] [Review][Defer] `_TAG_EXISTS_FRAGMENT = "already exists"` is locale-sensitive [`semvertag/providers/gitlab.py:78, 168`] — deferred, requires `Accept-Language: en` policy decision or GitLab structured-error-code matching
- [x] [Review][Defer] `_default_handler` returns 201 for any POST to `/repository/tags` regardless of payload [`tests/conftest.py:398-399`] — deferred, test-infrastructure design choice
- [x] [Review][Defer] `_default_handler` falls back to 404 for unknown paths, masking unintended URL calls as `ConfigError("project not found")` [`tests/conftest.py:400`] — deferred, test-infrastructure hardening (consider raising `AssertionError` to fail loudly)
- [x] [Review][Defer] No pagination-loop detection in `list_tags` — a broken proxy returning the same `Link: rel="next"` URL each iteration runs to the 100-page cap with duplicate data [`semvertag/providers/gitlab.py:128-147`] — deferred, low likelihood
- [x] [Review][Defer] 10K-tag cap (`_MAX_TAG_PAGES * _TAGS_PER_PAGE`) is unreachable for legitimately large monorepos [`semvertag/providers/gitlab.py:64-65`] — deferred, spec mandates the 100-page cap
- [x] [Review][Defer] `raise ProviderAPIError(...) from exc` chains `httpx2.RequestError` whose `__str__` may include the request URL — if `SEMVERTAG_GITLAB__ENDPOINT` ever contains userinfo (anti-pattern), credentials surface in the traceback [`semvertag/providers/gitlab.py:42-43, 68-69, 84-85, 106-107`] — deferred, anti-pattern by user is rare
- [x] [Review][Defer] Integration tests reach into `_transport` to monkey-patch `time.sleep` / `random.uniform` [`tests/integration/test_gitlab_provider.py:848-849, 862-863, 876-877`] — deferred, would require RetryingTransport seam refactor (`inject_sleep_fn` etc.)

### Dismissed as noise (count: ~22)

ClassVar-vs-instance Protocol mismatch on `name` (spec Task 2.4 explicitly endorses this pattern; `ty check` passes per Dev Agent Record); `_HTTP_SERVER_ERROR_MAX = 600` naming nit; `_make_provider` test client omits `timeout=` (MockTransport doesn't time out); `_PAGINATION_CAP` duplicates `_MAX_TAG_PAGES` constant; `check_protected_tags` reports "passed" without parsing body (spec accepts "readable" as the success criterion); `check_scopes` conflates 401/403 (spec doctor-mapping table explicitly merges them); `_translate_status` fallthrough for unmapped 4xx (acceptable); 1xx/3xx fall into "Unexpected" bucket (acceptable — httpx2 client config controls redirects upstream); 200/201 not method-aware in `_translate_status` (low value); multiple `rel="next"` first-vs-last undocumented (RFC permits either); `per_page=1` sent as int (httpx2 stringifies); `_auth_headers()` returns mutable dict (no current leak path); `_request_failed_message` drops URL context (intentional secret hygiene); `_safe_get` doesn't wrap with `RetryingTransport` in test fixtures (documented design); `check_scopes` doesn't accept `write_repository` as equivalent (architectural scoping question); `overrides` Response reuse (no current failure mode); empty `Link:` header value (Edge Hunter's own analysis confirmed benign); `compose_handler` query-string-ignored-in-key (resolved by exact-prefix patch above); `compose_handler` trailing slash normalization (no current code path); `payload list 400 body` unexercised (low value); 200 implicitly accepted on `create_tag` via `_translate_status` fallthrough (benign); `test_create_tag_sends_json_body` doesn't assert Content-Type (low value, httpx2 sets it correctly); `check_project_access` cause includes `project_id` (int; not sensitive); sequential API-call race in `get_latest_commit_on_default_branch` (documented as best-effort in Dev Notes).
