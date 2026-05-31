# Story 1.4: RetryingTransport with NFR7 retry policy

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a CI pipeline operator,
I want semvertag to automatically retry transient provider API failures (5xx, connection reset, 429) with exponential backoff and a bounded wall budget,
so that my CI doesn't fail on a momentary GitLab API hiccup, but also doesn't hang indefinitely.

## Acceptance Criteria

### AC1 — Module constants are `typing.Final` with architecture-binding values

**Given** `semvertag/_transport.py` exists as a new module
**When** I import its module-level constants
**Then** the following are exposed, each annotated `typing.Final`, with these exact values:

| Name | Type | Value |
|---|---|---|
| `RETRYABLE_STATUSES` | `frozenset[int]` | `frozenset({408, 429, 500, 502, 503, 504})` |
| `RETRYABLE_EXCEPTIONS` | `tuple[type[BaseException], ...]` | `(httpx2.ConnectError, httpx2.ReadTimeout, httpx2.WriteTimeout, httpx2.RemoteProtocolError)` |
| `MAX_ATTEMPTS` | `int` | `3` |
| `MAX_WALL_SECONDS` | `float` | `30.0` |
| `BACKOFF_BASE_SECONDS` | `float` | `1.0` |

**And** changing any of those values would be a behavior change visible in tests — they are not dead constants.

### AC2 — 5xx responses retried with exponential backoff + full jitter, capped at `MAX_ATTEMPTS`

**Given** `RetryingTransport` wraps an inner transport that returns `500 → 500 → 200` over three sequential calls
**When** `client.get(...)` is issued through the retrying transport
**Then** `Response.status_code == 200` and exactly **three** inner-handler invocations occur
**And** between attempts the transport sleeps for a value drawn from `random.uniform(0, BACKOFF_BASE_SECONDS * 2 ** n)` where `n` is the zero-indexed retry number (0 → after 1st failure, 1 → after 2nd)
**And** the sleep call goes through the module-imported `time.sleep` so tests can monkeypatch a single seam
**And** `random.uniform` is invoked via the module-imported `random` so tests can monkeypatch jitter to a deterministic value
**And when** the inner transport returns `503` on **all** attempts up to `MAX_ATTEMPTS`, the transport surfaces the **last** `Response` to the caller (does NOT raise) — translation into `ProviderAPIError` is the downstream provider's job (Story 1.5)

### AC3 — 429 with `Retry-After` header in seconds form

**Given** the inner transport returns `429` with `Retry-After: 7` followed by `200`
**When** the request flows through `RetryingTransport`
**Then** the transport sleeps **at least** 7.0 seconds (via `time.sleep`) before the second attempt
**And** the seconds-form parser tolerates leading/trailing whitespace and integer/decimal values per RFC 9110 §10.2.3 (`"7"`, `" 7 "`, `"7.5"` → 7.0, 7.0, 7.5)
**And** the final `Response.status_code == 200`

### AC4 — 429 with `Retry-After` header in HTTP-date form

**Given** the inner transport returns `429` with `Retry-After: <HTTP-date>` (RFC 7231 IMF-fixdate) followed by `200`, where the HTTP-date is **5 seconds in the future** relative to `time.monotonic()` at handle time
**When** the request flows through `RetryingTransport`
**Then** the HTTP-date is parsed via `email.utils.parsedate_to_datetime` and converted to a non-negative seconds-from-now delta
**And** the transport sleeps for that delta (or longer per backoff math; whichever is greater) before the next attempt
**And when** the parsed HTTP-date is in the past, the sleep falls back to the normal exponential-backoff value (delta ≥ 0; never negative sleep)
**And when** `Retry-After` is unparseable garbage (`"banana"`), the transport falls back to the normal exponential-backoff value and the attempt proceeds (no exception raised)

### AC5 — 30-second wall budget stops retries

**Given** `MAX_WALL_SECONDS = 30.0` and a clock fixture where `time.monotonic()` advances on each call
**When** the cumulative elapsed time at the moment a retry would fire (`now − start + planned_sleep`) would exceed 30.0
**Then** the transport stops retrying — it does NOT sleep, does NOT re-invoke the inner transport, and surfaces the **most recent** `Response` or re-raises the **most recent** `RETRYABLE_EXCEPTIONS` instance
**And** the budget check fires BEFORE the sleep, so the transport never holds the caller past the 30s wall

### AC6 — Retryable transport exceptions retried

**Given** the inner transport raises one of `httpx2.ConnectError`, `httpx2.ReadTimeout`, `httpx2.WriteTimeout`, `httpx2.RemoteProtocolError` on attempt 1, then returns `200` on attempt 2
**When** the request flows through `RetryingTransport`
**Then** `Response.status_code == 200` and the exception is swallowed (caller sees the eventual 200)
**And when** the same exception type is raised on all `MAX_ATTEMPTS`, the transport re-raises the **last** exception instance with `raise … from prior_exc` chaining preserved (the dev MAY chain across attempts or simply re-raise; chaining is preferred when straightforward)
**And** non-retryable exceptions (e.g. `httpx2.HTTPStatusError`, generic `OSError`, `KeyboardInterrupt`, `SystemExit`) propagate immediately on the first attempt — no retry, no swallowing

### AC7 — Static 4xx (excluding 408/429) is NOT retried

**Given** the inner transport returns `401`, `403`, `404`, or `422` on the first attempt
**When** the request flows through `RetryingTransport`
**Then** the transport returns that `Response` immediately after exactly **one** inner-handler invocation
**And** no `time.sleep` is called
**And** the dev-agent guidance is explicit: translation into `AuthError` (401/403) or `ConfigError` (404/422) belongs to the **provider** (Story 1.5), not to this transport

### AC8 — Constructor accepts an injectable inner transport; `close()` delegates

**Given** `RetryingTransport.__init__(self, inner: httpx2.BaseTransport | None = None)` is the public construction surface
**When** I instantiate `RetryingTransport()` with no arg
**Then** it constructs and owns an `httpx2.HTTPTransport()` as `self._inner`
**And when** I pass `RetryingTransport(inner=httpx2.MockTransport(handler))`, the mock transport is used end-to-end — this is how every test in `test_transport_retry.py` wires the inner sequence
**And when** `transport.close()` is called, it invokes `self._inner.close()` (delegation; no extra teardown)
**And** the class subclasses `httpx2.BaseTransport` directly so it is consumable wherever a `BaseTransport` is expected (`httpx2.Client(transport=...)`)

### AC9 — Single-ownership invariant (no retry logic anywhere else)

**Given** the architecture mandate: "`_transport.py` is the one place retries live" [arch §Retry & Rate-Limit Handling line 498; §Anti-Patterns line 1048; §Architectural Boundaries lines 1175, 1193, 1215]
**When** I grep the repo (excluding `_bmad/`, `_autosemver_reference/`, `docs/`, `tests/`) for retry, backoff, jitter, sleep loops, Retry-After parsing, or `time.monotonic()`-based budget tracking
**Then** the only matches are inside `semvertag/_transport.py`
**And** no provider (`providers/*.py`) imports `tenacity`, `httpx-retries`, or any third-party retry library
**And** no module other than `_transport.py` imports `random` for jitter purposes (other random use is allowed if architecturally justified)

### AC10 — Unit-test coverage

**Given** `tests/unit/test_transport_retry.py` covers every AC above with `httpx2.MockTransport` as the inner-transport seam
**When** `just test` runs
**Then** every test passes, the suite produces the documented scenarios from epics §Story 1.4:
- `500 → 500 → 200` (AC2 happy path; 3 attempts; coalesced final 200)
- `429 + Retry-After: 7 → 200` (AC3)
- `429 + Retry-After: <HTTP-date 5s future> → 200` (AC4)
- `503 × 3 → exhaustion returns last 503` (AC2 exhaustion; AC5 not triggered)
- `ConnectError → 200` (AC6)
- `ConnectError × 3 → exhaustion re-raises last ConnectError` (AC6 exhaustion)
- `static 4xx → no retry, no sleep` (AC7; parametrize 401/403/404/422)
- `wall-budget exhaustion → stop retrying without sleep` (AC5; fake clock that jumps past 30s after attempt 1)
- `unparseable Retry-After → falls back to exponential backoff` (AC4 robustness)
- `close() delegates to inner.close()` (AC8)
**And** line coverage on `semvertag/_transport.py` is ≥95% (well above NFR22's 85% line bar; this module is small and critical)

## Tasks / Subtasks

- [x] 1. Create `semvertag/_transport.py` module skeleton (AC: 1, 8, 9)
  - [x] 1.1 Global imports at the top: `import random`, `import time`, `import typing`, `import email.utils`, `import httpx2`. No `from __future__ import annotations`. No function-local imports.
  - [x] 1.2 Define module-level constants in the exact order and with the values listed in AC1, each annotated `typing.Final`. Match the architecture sketch at `architecture.md` lines 500–510.
  - [x] 1.3 Define `class RetryingTransport(httpx2.BaseTransport):` with an `__init__(self, inner: httpx2.BaseTransport | None = None)` that stores `self._inner = inner or httpx2.HTTPTransport()`. Document the deviation from §Frozen-Dataclass Conventions inline only if questioned — see Dev Notes §Why RetryingTransport is not a frozen dataclass.
  - [x] 1.4 Implement `close(self) -> None: self._inner.close()` (AC8).
  - [x] 1.5 Export public surface: `__all__: typing.Final = ("RetryingTransport",)`. Constants are module-public but not re-exported (they ARE the surface for monkeypatch in tests).

- [x] 2. Implement `handle_request` core loop (AC: 2, 5, 6, 7)
  - [x] 2.1 Signature: `def handle_request(self, request: httpx2.Request) -> httpx2.Response:` matching `httpx2.BaseTransport.handle_request`.
  - [x] 2.2 Initialize `start = time.monotonic()`, `last_response: httpx2.Response | None = None`, `last_exc: BaseException | None = None`.
  - [x] 2.3 Loop `for attempt in range(MAX_ATTEMPTS):`. Inside: call `self._inner.handle_request(request)`. Catch `RETRYABLE_EXCEPTIONS` as `exc` → store `last_exc = exc`, set `last_response = None`, continue the retry-decision branch. **Do not** catch a bare `Exception`.
  - [x] 2.4 On success branch (no exception): inspect `response.status_code`. If `status_code not in RETRYABLE_STATUSES` → return `response` immediately (covers AC7 static 4xx pass-through and all 2xx/3xx).
  - [x] 2.5 If `status_code in RETRYABLE_STATUSES` → store `last_response = response`, `last_exc = None`, fall through to retry-decision branch.
  - [x] 2.6 Retry-decision branch: if `attempt == MAX_ATTEMPTS - 1` (last attempt) → break out of loop. Otherwise compute `sleep_seconds = self._compute_sleep(attempt, last_response)` (helper from Task 4). Check `time.monotonic() - start + sleep_seconds > MAX_WALL_SECONDS` → if true, break (AC5: budget check fires BEFORE sleep). Otherwise `time.sleep(sleep_seconds)` and continue.
  - [x] 2.7 After loop: if `last_response is not None` → return it (AC2 exhaustion). Else if `last_exc is not None` → `raise last_exc` (AC6 exhaustion; `raise last_exc` preserves traceback because Python re-raises the exception object with its original `__traceback__`). The `from prior_exc` chaining option is acceptable but not required.

- [x] 3. Implement Retry-After parser helper `_parse_retry_after` (AC: 3, 4)
  - [x] 3.1 Module-level function `def _parse_retry_after(value: str | None, now_epoch: float) -> float | None:`. Returns seconds-to-sleep, or `None` if header is missing/unparseable.
  - [x] 3.2 If `value is None` or `value.strip() == ""` → return `None`.
  - [x] 3.3 Try `float(value.strip())` first (seconds form). If parses and is non-negative, return it. Reject negative seconds → return `None` (caller falls back to backoff).
  - [x] 3.4 Else try `email.utils.parsedate_to_datetime(value)` (HTTP-date form). If parses, compute `(parsed_dt.timestamp() - now_epoch)`. Clamp to `max(0.0, …)` (AC4 past-date fallback). Return the clamped value.
  - [x] 3.5 On `ValueError`, `TypeError`, or `OverflowError` from either parse path → return `None`.
  - [x] 3.6 `now_epoch` is a parameter (not `time.time()` inline) so tests can pin the wall clock. The caller passes `time.time()` (NOT `time.monotonic()`; HTTP-date is wall-clock-relative).

- [x] 4. Implement sleep-computation helper `_compute_sleep` (AC: 2, 3, 4)
  - [x] 4.1 Module-level function or instance method (your call): `_compute_sleep(attempt: int, last_response: httpx2.Response | None) -> float`. Attempt is the zero-indexed completed attempt count (0 after the first failure).
  - [x] 4.2 Default backoff: `random.uniform(0.0, BACKOFF_BASE_SECONDS * (2 ** attempt))`. **Full jitter** per AWS-Architecture-Blog "Exponential Backoff and Jitter" — the upper bound grows exponentially, the actual draw is uniform over `[0, upper]`.
  - [x] 4.3 If `last_response is not None` and `last_response.status_code == 429`, call `_parse_retry_after(last_response.headers.get("retry-after"), time.time())`. If it returns a non-None value, return `max(parsed, backoff)` — honoring the server's stated wait AND respecting the backoff floor.
  - [x] 4.4 Header lookup is via `last_response.headers.get("retry-after")` (httpx2 headers are case-insensitive — confirmed against installed `httpx2 v2.2.0`).

- [x] 5. Write unit tests in `tests/unit/test_transport_retry.py` (AC: 2–8, 10)
  - [x] 5.1 Top of file: global imports per project convention. Module-level constants annotated `typing.Final` (per `tests/**` auto-typing-final scope).
  - [x] 5.2 Build a small helper `_sequence_handler(responses: list[httpx2.Response | type[BaseException]])` that returns a closure capturing a call counter and yielding/raising the next item per call. This is the inner-handler for `httpx2.MockTransport(handler)`.
  - [x] 5.3 Default fixture `def _make_transport(handler) -> RetryingTransport: return RetryingTransport(inner=httpx2.MockTransport(handler))`.
  - [x] 5.4 Monkeypatch `_transport.time.sleep` to a recorder (capture sleep durations in a list). Tests should assert sleep was called the expected number of times with the expected magnitudes. **Do NOT** allow real sleeps in CI.
  - [x] 5.5 Monkeypatch `_transport.random.uniform` to a deterministic returner (e.g. `lambda lo, hi: hi`) so backoff math is testable as exact equality.
  - [x] 5.6 Monkeypatch `_transport.time.monotonic` to a deterministic counter (e.g. `itertools.count(start=0.0, step=0.0).__next__` for "instant", or a fake-clock fixture that advances per call). Required for AC5 budget tests.
  - [x] 5.7 Cover the 10 scenarios listed in AC10. Parametrize 4xx-no-retry (AC7) over `[401, 403, 404, 422]`. Parametrize retryable-exception happy path (AC6) over the four `RETRYABLE_EXCEPTIONS` types.
  - [x] 5.8 AC9 grep guard: add a single test `test_retry_logic_is_single_owner` that runs `grep -rn` (via `subprocess.run`) for `tenacity`, `httpx-retries`, and `Retry-After` across `semvertag/` and asserts the only matches are in `_transport.py`. Use `subprocess.run([...], check=False, capture_output=True, text=True)`. Skip if `grep` is missing (`pytest.skip` on `FileNotFoundError`).
  - [x] 5.9 AC8 close-delegation test: build a tracker class that records `close()` invocations and pass it as `inner=`. Assert `transport.close()` triggers exactly one delegated close.
  - [x] 5.10 Test naming `test_<verb>_<outcome>_when_<condition>` per architecture §Test Naming.

- [x] 6. Run the local quality gates and verify the package builds (AC: 1–10)
  - [x] 6.1 `just lint` — runs `eof-fixer .`, `ruff format`, `ruff check --fix`, `ty check`. Must end clean.
  - [x] 6.2 `just lint-ci` — same gates in `--check`/`--no-fix` mode (matches CI).
  - [x] 6.3 `just test` — full suite. Confirm all prior tests still pass (no regression from Stories 1.1–1.3). Confirm new file's line coverage ≥95% in the `term-missing` report.
  - [x] 6.4 `uv build` — package builds clean (Story 1.1 review patch elevated this to a per-story bar).
  - [x] 6.5 Behavioral smoke check (optional but recommended): construct `httpx2.Client(transport=RetryingTransport(inner=httpx2.MockTransport(lambda r: httpx2.Response(200))))` and issue a `client.get("http://example.invalid")`. Confirm `200`. Confirm `client.close()` (which calls `transport.close()`) raises no errors. This is a sanity check, not a story acceptance gate — leave out of the test suite to avoid net access surprises in CI.

- [x] 7. Update Dev Agent Record + File List + Status (AC: 1–10)
  - [x] 7.1 Append entries to **Dev Agent Record** below: Agent Model Used, Debug Log References (any deviations), Completion Notes List, File List, Change Log.
  - [x] 7.2 Move Status from `ready-for-dev` → `in-progress` when work starts, → `review` when code-review is ready. (Story moves to `done` ONLY after code-review.)
  - [x] 7.3 Update `_bmad/sprint-status.yaml` `development_status[1-4-retryingtransport-with-retry-policy]` matching the status transitions above. Also bump `last_updated:` to the current date.
  - [x] 7.4 If any deferred items surface (token-family expansions, doctor-only response shapes, etc.) — append them to `_bmad/deferred-work.md` under a new "## Deferred from: code review of 1-4-retryingtransport-with-retry-policy" heading. Do NOT silently leave them undocumented.

## Dev Notes

### Story framing

This is **Step 4 of the architecture's Implementation Sequence**: "RetryingTransport — httpx2 BaseTransport subclass with NFR7 retry policy. Unit-tested with `httpx2.MockTransport` simulating 5xx/429/timeout sequences." [Source: architecture.md#Decision Impact Analysis §Implementation sequence line 589]

Stories 1.1–1.3 built scaffolding, `_settings.py` (with `request_timeout: float = 8.0` clamped ≤10.0), `_types.py` (`ConfigSource`, `RunResult`), `_errors.py` (`SemvertagError → ConfigError/AuthError/ProviderAPIError`), `_redact.py`, `_output.py`. **Story 1.4 introduces ONE new module — `semvertag/_transport.py` — and ONE new test file — `tests/unit/test_transport_retry.py`.** Nothing else in `semvertag/` is modified.

The reference repo `_autosemver_reference/` does NOT carry a retry transport (Raiffeisen internal autosemver predates the httpx2-for-all-providers decision and used `python-gitlab`'s default behavior with no custom retry). It is therefore **not a behavioral reference** for this story. The target is entirely architecture-driven.

### Critical architectural constraints

These come from `architecture.md` and are non-negotiable for this story:

1. **`_transport.py` is THE retry choke point.** Architecture §Cross-cutting concerns line 153 + §Anti-Patterns line 1048 + §Architectural Boundaries lines 1175, 1193, 1215 all repeat this. No provider, no use case, no Settings reader, no doctor check may implement retry logic. Tests must enforce this (AC9 grep guard).
2. **No external retry dependency.** Architecture §Retry & Rate-Limit Handling line 498: "No external dep (no `tenacity`)." ~50–70 LOC including jitter and budget tracking. Stdlib only: `random`, `time`, `email.utils`. [Source: architecture.md line 498]
3. **Constants are `typing.Final`.** Architecture §Module-Level Constants lines 930–940 lists `RETRYABLE_STATUSES: typing.Final = …`, `MAX_ATTEMPTS: typing.Final = 3` — these are the SAME constants this story introduces. Match exactly. [Source: architecture.md lines 935–938]
4. **`httpx2.BaseTransport` subclass.** Architecture line 513: `class RetryingTransport(httpx2.BaseTransport):`. Public surface is the `handle_request(request) -> Response` override + `close()`. Confirmed against installed `httpx2 v2.2.0` (uv.lock:229). [Source: architecture.md line 513]
5. **Honor `Retry-After` first; backoff second.** Architecture line 521: "honor `Retry-After` header when present (429 most often); otherwise base 1s × 2^n with full jitter." Both seconds-form AND HTTP-date forms must parse. Use stdlib `email.utils.parsedate_to_datetime` for the HTTP-date case — it handles IMF-fixdate, RFC 850, and asctime per RFC 7231 §7.1.1.1. [Source: architecture.md line 521]
6. **Non-retryable 4xx is fail-closed.** Architecture line 523: "4xx (except 408/429) exit immediately via `AuthError` (401/403) or `ConfigError` (404/422); fail-closed per NFR8." This story does NOT raise those — it returns the 4xx `Response` and lets the **provider** translate it. The provider lands in Story 1.5. [Source: architecture.md line 523; epics.md AC at line 425]
7. **Per-request timeout lives on the Client, not on the transport.** Architecture lines 519, 952–954: `httpx2.Client(transport=RetryingTransport(...), timeout=settings.request_timeout)`. The transport itself doesn't know about timeout. The budget math `3 attempts × 8s + ~3s backoff = ~27s` is the architectural justification for the 30s wall — and that's enforced by `MAX_WALL_SECONDS`, NOT by the per-request timeout. **Do NOT** add a `timeout` parameter to `RetryingTransport.__init__`.
8. **Frozen-dataclass convention does NOT apply.** Architecture §Frozen-Dataclass Conventions lines 695–727 covers **domain types** (Commit, Tag, CheckResult, RunResult, ConfigSource). `RetryingTransport` is infrastructure that subclasses `httpx2.BaseTransport`, which itself has an `__init__` and `close`. A frozen dataclass cannot subclass a non-frozen class cleanly, and the inner-transport reference must be settable in `__init__`. Plain `class RetryingTransport(httpx2.BaseTransport):` with explicit `__init__` is the architecture-blessed shape (sketch at line 513 omits a body but the natural reading is "regular class"). **No documented deviation required**; this is consistent with §Frozen-Dataclass scope ("domain types").
9. **Sleep & monotonic are module-attribute calls, not from-imports.** `import time` at the top, then `time.sleep(...)` and `time.monotonic()` and `time.time()` inside the methods. Same for `import random` → `random.uniform(...)`. This is what makes the module monkeypatchable in tests (`monkeypatch.setattr(_transport.time, "sleep", recorder)`). `from time import sleep` would bind the original into the module namespace and break test mocking. [Source: project convention; also `_settings.py` uses module-attribute access for `os.environ`.]
10. **No `print()`, no bare `Exception`, no `from __future__ import annotations`, no function-local imports, `# ty: ignore` (not `# type: ignore`).** All carried from `architecture.md` §Anti-Patterns lines 1039–1049 and global `CLAUDE.md`.

### Why `RetryingTransport` is not a frozen dataclass (consolidated rationale)

`httpx2.BaseTransport` is a regular class with `handle_request` (abstract) and `close()` (concrete). `RetryingTransport` needs to (a) accept an injectable inner transport at construction time (for testability via `MockTransport`), and (b) hold mutable state-free behavior — there is no mutable state beyond the inner-transport reference. A frozen dataclass with `slots=True` could express (b) but loses (a) because frozen prohibits any post-`__init__` mutation, AND because subclassing `httpx2.BaseTransport` (not a dataclass) plus a frozen dataclass is friction not paid for by any benefit.

**Decision:** plain class, explicit `__init__(self, inner=None)`, no `@dataclasses.dataclass`. Consistent with how `Settings(BaseSettings)` is a pydantic class, not a dataclass — the frozen-dataclass convention applies to domain types, not infrastructure-class subclasses.

This is NOT a documented deviation requiring a Debug Log entry; it is the natural application of architecture §Frozen-Dataclass Conventions which scopes to "all domain types."

### Inner-transport injection (the testability seam)

The architecture sketch at line 513 shows `class RetryingTransport(httpx2.BaseTransport):` but doesn't specify constructor. The **necessary** seam is an injectable inner transport:

```python
class RetryingTransport(httpx2.BaseTransport):
    def __init__(self, inner: httpx2.BaseTransport | None = None) -> None:
        self._inner = inner or httpx2.HTTPTransport()

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        ...

    def close(self) -> None:
        self._inner.close()
```

This makes every retry test trivial — pass `httpx2.MockTransport(handler)` as `inner` and the handler controls the simulated response sequence. Production code (Story 1.5's `GitLabProvider`) constructs `RetryingTransport()` with no args, getting a real `HTTPTransport`. No documented deviation needed — this is filling in a missing constructor detail the architecture sketch left open.

### Sleep / clock / jitter monkeypatching contract (testing standard for this module)

The three test-determinism seams in `_transport.py` are:

| Module attribute | Real implementation | Test substitution |
|---|---|---|
| `time.sleep` | blocks for given seconds | recorder that appends to a list and returns immediately |
| `time.monotonic` | process-monotonic clock | fake-clock fixture; either `lambda: 0.0` (instant) or an advancing counter |
| `time.time` | wall clock (used by Retry-After HTTP-date math) | pinned `lambda: 1_700_000_000.0` or similar |
| `random.uniform` | uniform draw | `lambda lo, hi: hi` for upper-bound jitter, or `lambda lo, hi: lo` for floor |

Use `monkeypatch.setattr(_transport.time, "sleep", recorder)`. **Not** `monkeypatch.setattr("time.sleep", recorder)` — the latter patches the global stdlib `time`, which is process-wide and risks polluting unrelated tests; the former patches only the symbol `_transport` sees.

### Retry-After parsing — concrete cases

**Seconds form** (RFC 9110 §10.2.3): non-negative number of seconds. Spec is integer-only; in practice servers send float-ish strings. Tolerate `float()` parsing of stripped input. Reject negative (server misbehavior → fall back to backoff). Reject empty string after strip.

**HTTP-date form** (RFC 7231 §7.1.1.1): IMF-fixdate (`Sun, 06 Nov 1994 08:49:37 GMT`), RFC 850 (`Sunday, 06-Nov-94 08:49:37 GMT`), or asctime (`Sun Nov  6 08:49:37 1994`). All three handled by stdlib `email.utils.parsedate_to_datetime` (Python 3.10+ supports all three; verified against project's `requires-python = ">=3.10,<4"`).

Conversion to seconds-from-now: `(parsed_dt.timestamp() - now_wall)`, clamped to `max(0.0, …)`. Past-dated `Retry-After` → 0 seconds (caller will still apply backoff floor via `max(parsed, backoff)`).

**Unparseable garbage** (`"banana"`, `""`, `"-5"`, missing header entirely) → return `None`. Caller falls back to exponential backoff.

### Wall-budget math

NFR7: 3 attempts, ≤30s total wall time. Per-request timeout is 8s. Worst case: 3 × 8s + sum(backoff) ≤ 30s. With `BACKOFF_BASE_SECONDS = 1.0` and full jitter, expected backoff between attempts 1→2 is `E[uniform(0, 1)] = 0.5s`, between attempts 2→3 is `E[uniform(0, 2)] = 1.0s`. Expected total wall = 3×8 + 0.5 + 1.0 = 25.5s. Worst-case backoff (jitter = upper bound every time) = 3×8 + 1 + 2 = 27s. **The wall-budget guard exists to cover edge cases where Retry-After tells us to wait an unreasonable amount of time, not normal operation.**

The check is `time.monotonic() - start + planned_sleep > MAX_WALL_SECONDS`. It fires BEFORE the sleep — never sleep past the budget. When it fires, the loop breaks and the most recent state (response or exception) is surfaced.

### Single-ownership invariant — practical enforcement

AC9 mandates the AC-level grep guard. Practically:

```python
def test_retry_logic_is_single_owner(tmp_path: pathlib.Path) -> None:
    import subprocess
    semvertag_dir = pathlib.Path(__file__).parents[2] / "semvertag"
    forbidden = ["tenacity", "httpx-retries", "httpx_retries"]
    for needle in forbidden:
        try:
            result = subprocess.run(
                ["grep", "-rn", needle, str(semvertag_dir)],
                check=False, capture_output=True, text=True,
            )
        except FileNotFoundError:
            pytest.skip("grep not available")
        assert result.stdout == "", f"Forbidden import {needle!r} found: {result.stdout}"
    # "Retry-After" should only appear in _transport.py
    result = subprocess.run(
        ["grep", "-rln", "Retry-After", str(semvertag_dir)],
        check=False, capture_output=True, text=True,
    )
    matched_files = {pathlib.Path(line).name for line in result.stdout.strip().splitlines() if line}
    assert matched_files <= {"_transport.py"}, f"Retry-After referenced outside _transport.py: {matched_files}"
```

This is a structural test. It costs ~50ms and is the closest we get to a compile-time guarantee that the choke-point invariant holds.

### File-by-file targets

| Target file | NEW / UPDATE | Purpose |
|---|---|---|
| `semvertag/_transport.py` | **NEW** | `RetryingTransport(httpx2.BaseTransport)` + 5 module-level `typing.Final` constants + `_parse_retry_after` + `_compute_sleep` helpers |
| `tests/unit/test_transport_retry.py` | **NEW** | AC2–AC10 — full retry-policy test matrix using `httpx2.MockTransport` as inner |

**Files this story does NOT touch:**

| File | Story |
|---|---|
| `semvertag/_settings.py` | Story 1.2; `request_timeout` already lives there. **Do not** add retry-related fields here. |
| `semvertag/_types.py` | Stories 1.2/1.3; transport returns raw `httpx2.Response` — no new domain type needed. |
| `semvertag/_errors.py` | Story 1.3; transport does NOT raise `SemvertagError` subclasses — translation is the provider's job (1.5). |
| `semvertag/_redact.py`, `_output.py` | Story 1.3; transport has no console output. |
| `semvertag/providers/*` | Story 1.5; transport is consumed by `GitLabProvider` next story. |
| `semvertag/strategies/*` | Stories 1.6 / 2.1 |
| `semvertag/_use_case.py`, `ioc.py`, `__main__.py` | Story 1.7 |
| `semvertag/doctor/*` | Story 3.x |
| `pyproject.toml` | No changes. `httpx2` is already a project dependency (`pyproject.toml:25`); the constraint that it must be ≥2.2.0 is enforced by `uv.lock:229–240`. Pinning the lower bound in `pyproject.toml` is on the deferred-work list from Story 1.1 review — leave alone for this story. |
| `Justfile`, `.github/workflows/*` | No changes expected. |
| `tests/conftest.py` (root) | The shared `httpx2.MockTransport` fixture pattern documented at architecture.md lines 558–578 is for **integration** tests (Story 1.5+). Unit tests in this story construct mock transports inline. **Do not** add a top-level `conftest.py`. |
| `tests/unit/conftest.py` | The Story 1.2 `clean_settings_env` fixture is irrelevant — this story has no Settings dependency. Leave the file alone. |

### Sketch — the complete module (orientation only; verify against architecture during implementation)

This sketch is informative, not authoritative. The architecture document and the ACs above are authoritative.

```python
# semvertag/_transport.py
import email.utils
import random
import time
import typing

import httpx2


RETRYABLE_STATUSES: typing.Final = frozenset({408, 429, 500, 502, 503, 504})
RETRYABLE_EXCEPTIONS: typing.Final = (
    httpx2.ConnectError,
    httpx2.ReadTimeout,
    httpx2.WriteTimeout,
    httpx2.RemoteProtocolError,
)
MAX_ATTEMPTS: typing.Final = 3
MAX_WALL_SECONDS: typing.Final = 30.0
BACKOFF_BASE_SECONDS: typing.Final = 1.0


class RetryingTransport(httpx2.BaseTransport):
    def __init__(self, inner: httpx2.BaseTransport | None = None) -> None:
        self._inner = inner or httpx2.HTTPTransport()

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        start = time.monotonic()
        last_response: httpx2.Response | None = None
        last_exc: BaseException | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = self._inner.handle_request(request)
            except RETRYABLE_EXCEPTIONS as exc:
                last_exc, last_response = exc, None
            else:
                if response.status_code not in RETRYABLE_STATUSES:
                    return response
                last_response, last_exc = response, None
            if attempt == MAX_ATTEMPTS - 1:
                break
            sleep_seconds = _compute_sleep(attempt, last_response)
            if time.monotonic() - start + sleep_seconds > MAX_WALL_SECONDS:
                break
            time.sleep(sleep_seconds)
        if last_response is not None:
            return last_response
        assert last_exc is not None  # noqa: S101 — loop invariant; one of the two is always set after a completed iteration
        raise last_exc

    def close(self) -> None:
        self._inner.close()


def _compute_sleep(attempt: int, last_response: httpx2.Response | None) -> float:
    backoff = random.uniform(0.0, BACKOFF_BASE_SECONDS * (2 ** attempt))
    if last_response is not None and last_response.status_code == 429:
        parsed = _parse_retry_after(last_response.headers.get("retry-after"), time.time())
        if parsed is not None:
            return max(parsed, backoff)
    return backoff


def _parse_retry_after(value: str | None, now_epoch: float) -> float | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    try:
        seconds = float(stripped)
    except (TypeError, ValueError):
        seconds = None
    else:
        return seconds if seconds >= 0.0 else None
    try:
        parsed_dt = email.utils.parsedate_to_datetime(stripped)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed_dt is None:
        return None
    return max(0.0, parsed_dt.timestamp() - now_epoch)


__all__: typing.Final = ("RetryingTransport",)
```

**Note on the inline `assert` at the end of `handle_request`:** ruff's `S101` (use of `assert`) is per-file-ignored only for `tests/**/*.py` per `pyproject.toml:80`. In `semvertag/_transport.py` it will fire. Either (a) rewrite the post-loop branch as `if last_response is not None: return last_response; if last_exc is not None: raise last_exc; raise RuntimeError("RetryingTransport loop invariant violated")` (cleaner, no `assert`), or (b) add `# noqa: S101` with a one-line comment explaining the loop invariant. **Option (a) is preferred** — silent `RuntimeError` is fine for an "impossible" branch, and it documents intent without lint suppression.

### Testing standards

- **Framework**: `pytest` + `pytest-cov` + `pytest-randomly` + `pytest-xdist` — already in `[dependency-groups] dev`. No pyproject changes needed.
- **HTTP transport**: `httpx2.MockTransport(handler)` as the inner. Construct one per test (or per scenario fixture).
- **Stream / output**: this module has no console output. No Rich, no JSON, no redaction concerns in this story.
- **Env isolation**: not needed — `_transport.py` reads no environment variables.
- **Time / sleep / random control**: monkeypatch on `_transport.time.sleep`, `_transport.time.monotonic`, `_transport.time.time`, `_transport.random.uniform` per the contract table above.
- **Coverage gate**: ≥85% line per NFR22; this story aims for ≥95% line on `semvertag/_transport.py` (file is small and critical). Branch coverage is NOT a project-wide gate at this story — only `strategies/branch_prefix.py` and `strategies/conventional_commits.py` get the 100%-branch gate (per Stories 1.6 / 2.1).
- **Test naming**: `test_<verb>_<outcome>_when_<condition>` per architecture §Test Naming lines 916–921.
- **Module-level test constants get `typing.Final`** (auto-typing-final scope per Justfile, includes `tests/`).
- **`assert` is OK in tests** (`tests/**/*.py` has `S101` and `SLF001` per-file-ignored per pyproject.toml:79–80).
- **Parameterize** the static-4xx-no-retry case (AC7) over `[401, 403, 404, 422]` and the retryable-exception happy path (AC6) over the four `RETRYABLE_EXCEPTIONS` types.

### Anti-patterns to avoid

- `print()` anywhere — including dev-aid `print(f"attempt={attempt}")`. Use a debugger or `caplog` if needed.
- `from __future__ import annotations` — banned project-wide.
- Bare `Exception` catches — must be `except RETRYABLE_EXCEPTIONS as exc:`. Catching `Exception` would swallow `KeyboardInterrupt` (well, no — `KeyboardInterrupt` is a `BaseException`, not `Exception`), `MemoryError`, `RuntimeError`, etc.
- Function-local imports — `PLC0415` enforced; global imports only.
- `# type: ignore` — use `# ty: ignore` (global `CLAUDE.md`).
- Module-level singletons of stateful clients — every test constructs a fresh `RetryingTransport(inner=…)`.
- Re-imports inside the retry loop — e.g. importing `time` inside `handle_request`. Global imports only.
- Hardcoded sleep values in tests — assert against the monkeypatched recorder's recorded values, not against real wall time.
- Real network in tests — `httpx2.MockTransport` is the ONLY allowed inner transport in `test_transport_retry.py`.
- `tenacity`, `httpx-retries`, or any third-party retry dep — explicit architecture decision (line 498).
- `raise last_exc from last_exc` — Python idiom is `raise last_exc` (re-raise preserves traceback automatically) OR `raise X from prior` (chained). Self-chaining is meaningless.
- Coupling to the Settings layer — the transport does NOT read `Settings.request_timeout`. Timeout is enforced on the `httpx2.Client(timeout=...)`, set by Story 1.7's wiring.

### Learnings from Stories 1.1–1.3 (carried forward)

[Source: 1-1-bootstrap-public-scaffolding-from-modern-di.md#Dev Agent Record + 1-2-settings-layer-with-aliaschoices-and-provenance.md#Dev Agent Record + 1-3-errors-runresult-output-redaction.md#Dev Agent Record]

- **Architecture sketches sometimes leave seams unspecified.** Story 1.2 needed `model_validator(mode="before")` because the sketched `validation_alias` shape didn't behave on nested fields. Story 1.3 added an `error()` method to the Output protocol that wasn't in the sketch. **For this story:** the architecture sketch at line 513 leaves `__init__` empty; the inner-transport injection is the missing seam. Treat as a "fill-in", not a documented deviation.
- **Auto-typing-final aggressively rewrites code.** Pre-annotate `typing.Final` on every module-level constant in the new files so the lint pass doesn't surprise you. (Story 1.2's conftest got auto-rewritten from `yield None` → `return None`.)
- **`tests/**/*.py` per-file-ignores include `S101` (assert) and `SLF001` (private-attribute access).** This story may need `SLF001` to peek `transport._inner` in close-delegation assertions. The ignore is already active — no pyproject change needed.
- **`uv build` is a per-story acceptance bar** (Story 1.1's review patch). Run alongside `just test`.
- **`just install` re-locks with `uv lock --upgrade` every run.** Expect minor dep drift (Story 1.2 saw typer 0.26.0 → 0.26.1, Story 1.3 was clean). Not a regression as long as `just test` passes.
- **No `print()` even in tests** — `PLE0704`-adjacent rules under `select=["ALL"]`. Capture-and-assert on stream contents or monkeypatch recorders instead.
- **Module-level singleton anti-pattern was specifically dismissed-as-noise in 1.3's review for `Console()`** because both impls construct consoles inside `build_*_output` factories, not at module scope. This story has no `Console` use, but the lesson applies: don't construct `httpx2.HTTPTransport()` at module scope as a "shared inner." Construct it in `__init__` per-instance.
- **The Code Review will produce a Patches / Deferred / Dismissed bucketization (Blind Hunter + Edge Case Hunter + Acceptance Auditor).** Story 1.3 took 8 patches in-cycle and 9 deferred. Plan for a similar review cycle; the more rigorous the ACs and Dev Notes here, the smaller the patch set on the other side.

### Coverage-omit interaction

`tests/*` is in `[tool.coverage.run] omit`, so the test file doesn't count toward coverage. `semvertag/_transport.py` IS measured. Target ≥95% line.

Branches expected in the loop:
1. Exception-on-attempt path × {first/middle/last attempt}
2. 5xx-on-attempt path × {first/middle/last attempt}
3. 2xx/3xx/static-4xx (non-retryable) early return × {first/middle/last attempt}
4. Wall-budget break-before-sleep
5. Loop-exhaustion → return last response
6. Loop-exhaustion → raise last exception

The 10 scenarios in AC10 cover all 6 branches at least once. Aim for 100% branch with the current test matrix; pytest-cov's `--cov-branch` flag is not on by default (only `just test-branch` enables it). Not gated by CI for this module, but a good local sanity check.

### Architecture section pointers (for the dev agent's quick lookup)

- §Retry & Rate-Limit Handling — lines 496–523 — the entire policy: 3 attempts, 30s wall, exponential + jitter, Retry-After honoring, no-retry 4xx.
- §Module-Level Constants — lines 930–940 — `typing.Final` discipline; the actual constant values for `RETRYABLE_STATUSES` and `MAX_ATTEMPTS`.
- §Anti-Patterns to Avoid — lines 1039–1049 — including "HTTP retry logic outside `_transport.py`" line 1048.
- §Architectural Boundaries — lines 1168–1219 — `_transport.py` listed as the sole retry choke point at lines 1175, 1193, 1215.
- §Test Architecture — lines 548–581 — three-layer model; this story is unit-only (Layer 1).
- §Test Naming & File Organization — lines 888–928 — file naming, function naming, `typing.Final` on test constants.
- §Decision Impact Analysis §Implementation sequence — line 589 — this story is "Step 4."
- §Type-Annotation Style — lines 728–743 — `typing.Final`, no `from __future__ import annotations`.
- §Comment Policy — lines 942–957 — no comments unless the WHY is non-obvious; example at line 952–954 is the architectural justification snippet for per-request timeout discipline (NOT a comment to copy verbatim).
- §Implementation Patterns §Enforcement Guidelines — lines 1019–1037.

### Project Structure Notes

After this story:

- `semvertag/_transport.py` is complete and stable. Nothing else in v1.0 will modify it (Stories 1.5+ consume it via `httpx2.Client(transport=RetryingTransport())`).
- Module count after this story: `_settings.py` + `_types.py` + `_errors.py` + `_redact.py` + `_output.py` + `_transport.py` + `strategies/branch_prefix.py` + `strategies/conventional_commits.py` = 8 files of substantive code. Still well under NFR21's 1,500-LOC soft target.
- `semvertag/__init__.py` is intentionally empty (Story 1.1 pattern); `_transport.py` is module-level-importable from outside via `from semvertag._transport import RetryingTransport`. **Do not** re-export from `__init__.py` — `_*.py` are internal modules NOT covered by NFR25 stability.
- Story 1.5 (`GitLabProvider`) is the first consumer. The provider's `httpx2.Client` will be constructed with `transport=RetryingTransport()` (no arg) in production and `transport=RetryingTransport(inner=MockTransport(handler))` in integration tests.

### References

- [Source: architecture.md#Retry & Rate-Limit Handling lines 496–523] — full policy spec, code sketch, backoff strategy, non-retryable behavior
- [Source: architecture.md#Module-Level Constants lines 930–940] — `typing.Final` constants, exact values for `RETRYABLE_STATUSES` and `MAX_ATTEMPTS`
- [Source: architecture.md#Anti-Patterns to Avoid lines 1039–1049] — bans `print()`, bare `Exception`, function-local imports, retry logic outside `_transport.py`
- [Source: architecture.md#Architectural Boundaries lines 1168–1219] — `_transport.py` as sole retry choke point (lines 1175, 1193, 1215)
- [Source: architecture.md#Test Architecture lines 548–581] — three test layers, `httpx2.MockTransport` fixture pattern (used here inline, not via shared conftest)
- [Source: architecture.md#Test Naming & File Organization lines 888–928] — test function naming, `typing.Final` on test constants
- [Source: architecture.md#Decision Impact Analysis line 589] — this story is Implementation Sequence Step 4
- [Source: architecture.md#Type-Annotation Style lines 728–743] — `typing.Final`, no `from __future__ import annotations`, built-in generics
- [Source: architecture.md#Comment Policy lines 942–957] — no comments unless WHY is non-obvious
- [Source: architecture.md#Frozen-Dataclass Conventions lines 695–727] — scope is "domain types"; infrastructure subclasses are out of scope (rationale in §Why RetryingTransport is not a frozen dataclass)
- [Source: epics.md#Epic 1 Story 1.4 lines 398–429] — the original BDD ACs this story restates and expands
- [Source: prd.md#NFR7 line 101] — 3 attempts, ≤30s wall, exponential backoff + jitter, exit code 4 on exhaustion
- [Source: prd.md#NFR1 line 93] — ≤30s p95 end-to-end runtime — the constraint NFR7 must fit within
- [Source: prd.md#NFR8 line 102] — fail-closed auth/scope; non-retryable 401/403/404/422 belong here
- [Source: prd.md#NFR23 line 123] — `ty` clean, `ruff check ALL` clean
- [Source: pyproject.toml lines 19–26] — `httpx2` declared as dependency; lower-bound pinning deferred per Story 1.1
- [Source: uv.lock lines 229–240] — httpx2 v2.2.0 actually installed
- [Source: semvertag/_settings.py:60] — `request_timeout: float = 8.0` lives in Settings, not in transport
- [Source: semvertag/_errors.py current contents] — `SemvertagError → ConfigError/AuthError/ProviderAPIError` with `exit_code` class attrs; transport does NOT raise these
- [Source: tests/unit/conftest.py current contents] — `clean_settings_env` fixture from Story 1.2 (not used here; left alone)
- [Source: Justfile:7–11, 19–23] — `just lint`, `just test`, `just lint-ci`, `uv build` quality gates
- [Source: 1-1-bootstrap-public-scaffolding-from-modern-di.md] — bootstrap learnings; `uv build` is per-story bar
- [Source: 1-2-settings-layer-with-aliaschoices-and-provenance.md#Dev Agent Record] — architecture-sketch-vs-library-reality lesson; auto-typing-final lesson
- [Source: 1-3-errors-runresult-output-redaction.md#Dev Agent Record] — review-bucketization lesson (Patches / Deferred / Dismissed); module-level singleton anti-pattern noise discussion
- [Source: ~/.claude/CLAUDE.md] — global rules: `# ty: ignore` (not `# type: ignore`), global imports, no `from __future__ import annotations`
- [Source: _autosemver_reference/] — has NO retry transport; not a behavioral reference for this story

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context) — bmad-dev-story workflow

### Debug Log References

- **Empty-body branch removed from `_parse_retry_after`.** The story's reference sketch carries `if parsed_dt is None: return None` after `email.utils.parsedate_to_datetime`. In Python 3.10+ that function never returns `None` — it raises `TypeError`/`ValueError` on bad input — so the branch is structurally dead and would have cost a `# pragma: no cover` to satisfy the 95% line bar. Replaced with `try: parsed_dt = …; delta = parsed_dt.timestamp() - now_epoch; except (TypeError, ValueError, OverflowError): return None`. Semantically equivalent (both paths surface "unparseable → None") and gives us a real exception envelope around `.timestamp()` overflow, which the original sketch left outside the try.
- **Post-loop "impossible" branch used `RuntimeError`, not `assert`.** Per the sketch's "option (a)" preference (story line 396), wrote `raise RuntimeError(msg)  # pragma: no cover` instead of `assert last_exc is not None  # noqa: S101`. Documents intent without lint suppression.
- **AC9 grep test uses `shutil.which("grep")` instead of catching `FileNotFoundError`.** The sketch's `try/except FileNotFoundError` shape trips ruff `S607` (partial executable path) and the `# noqa: S607` placement is fragile under ruff's auto-fix (RUF100 strips it from lines that don't directly contain the violation span). Resolving the absolute path up front via `shutil.which` removes the S607 trigger entirely, makes the skip condition explicit, and is functionally identical.
- **Introduced private constant `_RETRY_AFTER_STATUS: typing.Final = 429`** in `_transport.py` so `_compute_sleep`'s 429 check isn't a PLR2004 magic-number violation. Not a public surface change — AC1's 5 mandated constants are unchanged. Same shape as `_settings.py:34` (`_REQUEST_TIMEOUT_CEILING`).

### Completion Notes List

- All 10 ACs (AC1–AC10) verified by `tests/unit/test_transport_retry.py` — 32 tests, all green, randomized order via `pytest-randomly`.
- `semvertag/_transport.py` line coverage: **100%** (the one `RuntimeError` invariant-violation path is `# pragma: no cover`'d on both the `msg = …` and `raise` lines).
- Full suite: **110 tests passed**, no regressions in Stories 1.1–1.3 modules.
- `just lint`, `just lint-ci`, `uv build` all clean.
- No new project dependencies — stdlib `random`, `time`, `email.utils`, `typing` plus the already-declared `httpx2`.
- No edits to `pyproject.toml`, `Justfile`, `_settings.py`, `_errors.py`, `_types.py`, `_redact.py`, `_output.py`, or any provider/strategy file. Single-module addition as scoped.
- AC9 grep guard passes — `tenacity`, `httpx-retries`, and `httpx_retries` are absent from `semvertag/`; `Retry-After` appears nowhere (the module reads the header via lowercase `"retry-after"`), so the single-owner invariant holds.

### File List

- **New:** `semvertag/_transport.py` (84 LOC including blanks; 64 statements per coverage)
- **New:** `tests/unit/test_transport_retry.py` (373 LOC; 32 tests covering AC1–AC10 + close delegation + grep single-owner guard)
- **Modified:** `_bmad/sprint-status.yaml` (`1-4-…: ready-for-dev` → `in-progress` → `review`; `last_updated` and `last_updated_note` bumped)
- **Modified:** `_bmad/1-4-retryingtransport-with-retry-policy.md` (Status, all task/subtask checkboxes, Dev Agent Record, File List, Change Log)

### Change Log

- 2026-05-27 — Added `semvertag/_transport.py`: `RetryingTransport(httpx2.BaseTransport)` with NFR7 retry policy (3 attempts, 30s wall, full-jitter exponential backoff, RFC 9110 `Retry-After` honoring for both seconds and HTTP-date forms, fail-closed on non-retryable 4xx).
- 2026-05-27 — Added `tests/unit/test_transport_retry.py`: 32 tests covering all 10 ACs plus single-ownership grep guard and close-delegation.
- 2026-05-27 — Bumped sprint-status to `review` for `1-4-retryingtransport-with-retry-policy`.

## Review Findings

l**Review date:** 2026-05-27
**Reviewers:** Blind Hunter + Edge Case Hunter + Acceptance Auditor (parallel)
**Acceptance Auditor verdict:** all 10 ACs PASS, 0 violations, 4 acceptable documented deviations.

### Patches

- [x] [Review][Patch] Broaden `Retry-After` honoring from 429-only to the full `RETRYABLE_STATUSES` set [`semvertag/_transport.py:59`] — RFC 9110 §10.2.3 defines `Retry-After` for 503 (and 3xx) as well; architecture line 521 says "429 most often" implying others exist. **Applied:** gate is now `last_response.status_code in RETRYABLE_STATUSES`; `_RETRY_AFTER_STATUS` constant removed; `test_honors_retry_after_when_503_has_seconds_header` added.

- [x] [Review][Patch] Naive HTTP-date `.timestamp()` interprets as local timezone, not UTC [`semvertag/_transport.py:79-80`] — `email.utils.parsedate_to_datetime` returns a **timezone-aware** datetime for IMF-fixdate but a **naive** datetime for asctime / RFC 5322 "-0000" forms. `.timestamp()` on a naive datetime uses the **local** timezone, producing a delta wrong by the CI host's offset (up to ±14h). **Applied:** `_parse_retry_after` now coerces naive → UTC via `datetime.timezone.utc` before `.timestamp()`; `import datetime` added; `test_treats_naive_http_date_as_utc_not_local` added.

- [x] [Review][Patch] `_SequenceHandler.__call__` raises an opaque `IndexError` if the inner-handler is called more times than the test set up [`tests/unit/test_transport_retry.py:57-65`] — regression noise rather than a clear policy assertion. **Applied:** early bounds check now raises `AssertionError` with `_SequenceHandler exhausted: call #N, only M configured`.

### Deferred

- [x] [Review][Defer] Response objects from failed retry attempts are discarded without `response.close()` [`semvertag/_transport.py:33-39`] — under `MockTransport` this is harmless (no socket held), but under real `httpx2.HTTPTransport` a discarded 5xx response keeps its underlying connection from being released to the pool. The architecture sketch (story line 309) also discards. Defer to the GitLabProvider integration tests in Story 1.5 — confirm connection-pool drainage in a multi-retry scenario and add `response.close()` to the retry loop if leakage is observed.

- [x] [Review][Defer] `RETRYABLE_EXCEPTIONS` omits `httpx2.ConnectTimeout` and `httpx2.PoolTimeout` [`semvertag/_transport.py:10-15`] — AC1 fixes the tuple to exactly these 4 types, but `ConnectTimeout` (transient, idempotent-safe) is the most glaring omission; production retry layers commonly include it. Changing the tuple is an AC1 modification, so defer to a future story / architecture revision.

- [x] [Review][Defer] Retries apply to non-idempotent methods (POST/PATCH) unconditionally — `handle_request` does not inspect `request.method` [`semvertag/_transport.py:27-49`]. semvertag's only POST is tag creation, which the GitLabProvider (Story 1.5) translates 409 "tag already exists" to a clean error, so duplicate-tag risk is mitigated downstream — but the policy is implicit. Defer to a future architectural discussion about whether to filter retries by method.

### Dismissed (noise / spec-mandated / false positives)

- 26 lower-severity findings dismissed: stylistic nits (tuple equality order, `_REQUEST_URL = ".invalid"`, magic-constant interaction in 429+seconds test, `__all__` excluding monkeypatch constants), spec-mandated patterns (deterministic `uniform → hi` stub, `instant_clock` zeroing `monotonic` for non-budget tests, grep-based AC9 guard, `# pragma: no cover` on `RuntimeError` invariant), spec-version-bound dead handlers (Python ≥3.10 means `parsedate_to_datetime` never returns `None`, so the AttributeError concern is out-of-scope), and walks where the budget-guard correctly catches `inf` from `Retry-After: "inf"` and the `seconds >= 0.0` filter catches `nan` (both pathological-input concerns turn out to be safe-by-construction in the current code).
