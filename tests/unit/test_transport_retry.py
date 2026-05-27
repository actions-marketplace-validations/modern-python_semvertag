import email.utils
import pathlib
import shutil
import subprocess
import typing

import httpx2
import pytest

from semvertag import _transport
from semvertag._transport import (
    BACKOFF_BASE_SECONDS,
    MAX_ATTEMPTS,
    MAX_WALL_SECONDS,
    RETRYABLE_EXCEPTIONS,
    RETRYABLE_STATUSES,
    RetryingTransport,
)


_REQUEST_URL: typing.Final = "http://example.invalid/path"
_EXPECTED_RETRYABLE_STATUSES: typing.Final = frozenset({408, 429, 500, 502, 503, 504})
_EXPECTED_MAX_ATTEMPTS: typing.Final = 3
_EXPECTED_MAX_WALL_SECONDS: typing.Final = 30.0
_EXPECTED_BACKOFF_BASE_SECONDS: typing.Final = 1.0
_FIXED_WALL_EPOCH: typing.Final = 1_700_000_000.0
_RETRY_AFTER_DELTA_SECONDS: typing.Final = 5
_BACKOFF_BETWEEN_FIRST_AND_SECOND: typing.Final = 1.0
_BACKOFF_BETWEEN_SECOND_AND_THIRD: typing.Final = 2.0
_BUDGET_OVERFLOW_MONOTONIC: typing.Final = 31.0
_STATIC_4XX_STATUSES: typing.Final = (401, 403, 404, 422)
_SINGLE_CALL: typing.Final = 1
_PAST_HTTP_DATE_OFFSET_SECONDS: typing.Final = 60.0
_OK_STATUS: typing.Final = 200
_SERVICE_UNAVAILABLE_STATUS: typing.Final = 503


class _CloseRecorder(httpx2.BaseTransport):
    def __init__(self) -> None:
        self.close_calls: int = 0

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:  # noqa: ARG002
        return httpx2.Response(200)

    def close(self) -> None:
        self.close_calls += 1


class _SequenceHandler:
    def __init__(
        self,
        responses: list[httpx2.Response | type[BaseException] | BaseException],
    ) -> None:
        self._responses = responses
        self.calls: int = 0

    def __call__(self, request: httpx2.Request) -> httpx2.Response:  # noqa: ARG002
        if self.calls >= len(self._responses):
            msg = f"_SequenceHandler exhausted: call #{self.calls + 1}, only {len(self._responses)} configured"
            raise AssertionError(msg)
        item: typing.Final = self._responses[self.calls]
        self.calls += 1
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, type) and issubclass(item, BaseException):
            msg = "simulated"
            raise item(msg)
        return item


def _make_transport(handler: _SequenceHandler) -> RetryingTransport:
    return RetryingTransport(inner=httpx2.MockTransport(handler))


@pytest.fixture
def instant_clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    sleep_calls: list[float] = []
    monkeypatch.setattr(_transport.time, "sleep", sleep_calls.append)
    monkeypatch.setattr(_transport.time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(_transport.time, "time", lambda: _FIXED_WALL_EPOCH)
    monkeypatch.setattr(_transport.random, "uniform", lambda lo, hi: hi)  # noqa: ARG005
    return sleep_calls


def test_module_constants_match_architecture_values() -> None:
    assert RETRYABLE_STATUSES == _EXPECTED_RETRYABLE_STATUSES
    assert (
        httpx2.ConnectError,
        httpx2.ReadTimeout,
        httpx2.WriteTimeout,
        httpx2.RemoteProtocolError,
    ) == RETRYABLE_EXCEPTIONS
    assert MAX_ATTEMPTS == _EXPECTED_MAX_ATTEMPTS
    assert MAX_WALL_SECONDS == _EXPECTED_MAX_WALL_SECONDS
    assert BACKOFF_BASE_SECONDS == _EXPECTED_BACKOFF_BASE_SECONDS


def test_module_public_surface_is_only_retrying_transport() -> None:
    assert _transport.__all__ == ("RetryingTransport",)


def test_default_inner_is_http_transport_when_no_arg() -> None:
    transport: typing.Final = RetryingTransport()
    assert isinstance(transport._inner, httpx2.HTTPTransport)
    transport.close()


def test_returns_coalesced_200_when_500_500_200(instant_clock: list[float]) -> None:
    handler: typing.Final = _SequenceHandler(
        [httpx2.Response(500), httpx2.Response(500), httpx2.Response(200)],
    )
    transport: typing.Final = _make_transport(handler)
    with httpx2.Client(transport=transport) as client:
        response = client.get(_REQUEST_URL)
    assert response.status_code == _OK_STATUS
    assert handler.calls == _EXPECTED_MAX_ATTEMPTS
    assert instant_clock == [_BACKOFF_BETWEEN_FIRST_AND_SECOND, _BACKOFF_BETWEEN_SECOND_AND_THIRD]


def test_returns_last_503_when_all_attempts_exhausted(instant_clock: list[float]) -> None:
    handler: typing.Final = _SequenceHandler(
        [httpx2.Response(503), httpx2.Response(503), httpx2.Response(503)],
    )
    transport: typing.Final = _make_transport(handler)
    with httpx2.Client(transport=transport) as client:
        response = client.get(_REQUEST_URL)
    assert response.status_code == _SERVICE_UNAVAILABLE_STATUS
    assert handler.calls == _EXPECTED_MAX_ATTEMPTS
    assert instant_clock == [_BACKOFF_BETWEEN_FIRST_AND_SECOND, _BACKOFF_BETWEEN_SECOND_AND_THIRD]


@pytest.mark.parametrize(
    ("header_value", "expected_sleep"),
    [
        ("7", 7.0),
        (" 7 ", 7.0),
        ("7.5", 7.5),
    ],
)
def test_honors_retry_after_seconds_when_429_followed_by_200(
    instant_clock: list[float],
    header_value: str,
    expected_sleep: float,
) -> None:
    handler: typing.Final = _SequenceHandler(
        [
            httpx2.Response(429, headers={"Retry-After": header_value}),
            httpx2.Response(200),
        ],
    )
    transport: typing.Final = _make_transport(handler)
    with httpx2.Client(transport=transport) as client:
        response = client.get(_REQUEST_URL)
    assert response.status_code == _OK_STATUS
    assert instant_clock == [expected_sleep]


def test_honors_retry_after_http_date_when_429_followed_by_200(
    instant_clock: list[float],
) -> None:
    future_epoch: typing.Final = _FIXED_WALL_EPOCH + _RETRY_AFTER_DELTA_SECONDS
    http_date: typing.Final = email.utils.formatdate(future_epoch, usegmt=True)
    handler: typing.Final = _SequenceHandler(
        [
            httpx2.Response(429, headers={"Retry-After": http_date}),
            httpx2.Response(200),
        ],
    )
    transport: typing.Final = _make_transport(handler)
    with httpx2.Client(transport=transport) as client:
        response = client.get(_REQUEST_URL)
    assert response.status_code == _OK_STATUS
    assert instant_clock == [float(_RETRY_AFTER_DELTA_SECONDS)]


def test_falls_back_to_backoff_when_retry_after_http_date_is_in_the_past(
    instant_clock: list[float],
) -> None:
    past_epoch: typing.Final = _FIXED_WALL_EPOCH - _PAST_HTTP_DATE_OFFSET_SECONDS
    http_date: typing.Final = email.utils.formatdate(past_epoch, usegmt=True)
    handler: typing.Final = _SequenceHandler(
        [
            httpx2.Response(429, headers={"Retry-After": http_date}),
            httpx2.Response(200),
        ],
    )
    transport: typing.Final = _make_transport(handler)
    with httpx2.Client(transport=transport) as client:
        response = client.get(_REQUEST_URL)
    assert response.status_code == _OK_STATUS
    assert instant_clock == [_BACKOFF_BETWEEN_FIRST_AND_SECOND]


def test_treats_naive_http_date_as_utc_not_local(instant_clock: list[float]) -> None:
    # formatdate(..., usegmt=False, localtime=False) emits "-0000" (RFC 5322 "unknown TZ"),
    # which parsedate_to_datetime returns as a NAIVE datetime. .timestamp() on a naive
    # datetime uses the host's local timezone; the parser must coerce to UTC so the delta
    # is independent of CI host timezone.
    future_epoch: typing.Final = _FIXED_WALL_EPOCH + _RETRY_AFTER_DELTA_SECONDS
    http_date_no_zone: typing.Final = email.utils.formatdate(future_epoch, usegmt=False, localtime=False)
    handler: typing.Final = _SequenceHandler(
        [
            httpx2.Response(429, headers={"Retry-After": http_date_no_zone}),
            httpx2.Response(200),
        ],
    )
    transport: typing.Final = _make_transport(handler)
    with httpx2.Client(transport=transport) as client:
        response = client.get(_REQUEST_URL)
    assert response.status_code == _OK_STATUS
    assert instant_clock == [float(_RETRY_AFTER_DELTA_SECONDS)]


def test_falls_back_to_backoff_when_retry_after_is_garbage(instant_clock: list[float]) -> None:
    handler: typing.Final = _SequenceHandler(
        [
            httpx2.Response(429, headers={"Retry-After": "banana"}),
            httpx2.Response(200),
        ],
    )
    transport: typing.Final = _make_transport(handler)
    with httpx2.Client(transport=transport) as client:
        response = client.get(_REQUEST_URL)
    assert response.status_code == _OK_STATUS
    assert instant_clock == [_BACKOFF_BETWEEN_FIRST_AND_SECOND]


def test_falls_back_to_backoff_when_retry_after_seconds_is_negative(
    instant_clock: list[float],
) -> None:
    handler: typing.Final = _SequenceHandler(
        [
            httpx2.Response(429, headers={"Retry-After": "-5"}),
            httpx2.Response(200),
        ],
    )
    transport: typing.Final = _make_transport(handler)
    with httpx2.Client(transport=transport) as client:
        response = client.get(_REQUEST_URL)
    assert response.status_code == _OK_STATUS
    assert instant_clock == [_BACKOFF_BETWEEN_FIRST_AND_SECOND]


def test_falls_back_to_backoff_when_retry_after_is_empty(instant_clock: list[float]) -> None:
    handler: typing.Final = _SequenceHandler(
        [
            httpx2.Response(429, headers={"Retry-After": "   "}),
            httpx2.Response(200),
        ],
    )
    transport: typing.Final = _make_transport(handler)
    with httpx2.Client(transport=transport) as client:
        response = client.get(_REQUEST_URL)
    assert response.status_code == _OK_STATUS
    assert instant_clock == [_BACKOFF_BETWEEN_FIRST_AND_SECOND]


def test_uses_backoff_when_429_has_no_retry_after_header(instant_clock: list[float]) -> None:
    handler: typing.Final = _SequenceHandler(
        [httpx2.Response(429), httpx2.Response(200)],
    )
    transport: typing.Final = _make_transport(handler)
    with httpx2.Client(transport=transport) as client:
        response = client.get(_REQUEST_URL)
    assert response.status_code == _OK_STATUS
    assert instant_clock == [_BACKOFF_BETWEEN_FIRST_AND_SECOND]


def test_honors_retry_after_when_503_has_seconds_header(instant_clock: list[float]) -> None:
    handler: typing.Final = _SequenceHandler(
        [
            httpx2.Response(503, headers={"Retry-After": "7"}),
            httpx2.Response(200),
        ],
    )
    transport: typing.Final = _make_transport(handler)
    with httpx2.Client(transport=transport) as client:
        response = client.get(_REQUEST_URL)
    assert response.status_code == _OK_STATUS
    assert instant_clock == [7.0]


@pytest.mark.parametrize("exc_cls", RETRYABLE_EXCEPTIONS)
def test_swallows_retryable_exception_when_followed_by_200(
    instant_clock: list[float],
    exc_cls: type[BaseException],
) -> None:
    handler: typing.Final = _SequenceHandler([exc_cls, httpx2.Response(200)])
    transport: typing.Final = _make_transport(handler)
    with httpx2.Client(transport=transport) as client:
        response = client.get(_REQUEST_URL)
    assert response.status_code == _OK_STATUS
    assert instant_clock == [_BACKOFF_BETWEEN_FIRST_AND_SECOND]


@pytest.mark.parametrize("exc_cls", RETRYABLE_EXCEPTIONS)
def test_reraises_last_exception_when_all_attempts_raise(
    instant_clock: list[float],
    exc_cls: type[BaseException],
) -> None:
    handler: typing.Final = _SequenceHandler([exc_cls, exc_cls, exc_cls])
    transport: typing.Final = _make_transport(handler)
    with httpx2.Client(transport=transport) as client, pytest.raises(exc_cls):
        client.get(_REQUEST_URL)
    assert instant_clock == [_BACKOFF_BETWEEN_FIRST_AND_SECOND, _BACKOFF_BETWEEN_SECOND_AND_THIRD]


def test_propagates_non_retryable_exception_immediately(instant_clock: list[float]) -> None:
    handler: typing.Final = _SequenceHandler([OSError("not retryable"), httpx2.Response(200)])
    transport: typing.Final = _make_transport(handler)
    with httpx2.Client(transport=transport) as client, pytest.raises(OSError, match="not retryable"):
        client.get(_REQUEST_URL)
    assert instant_clock == []
    assert handler.calls == _SINGLE_CALL


@pytest.mark.parametrize("status", _STATIC_4XX_STATUSES)
def test_skips_retry_when_static_4xx(instant_clock: list[float], status: int) -> None:
    handler: typing.Final = _SequenceHandler([httpx2.Response(status), httpx2.Response(200)])
    transport: typing.Final = _make_transport(handler)
    with httpx2.Client(transport=transport) as client:
        response = client.get(_REQUEST_URL)
    assert response.status_code == status
    assert handler.calls == _SINGLE_CALL
    assert instant_clock == []


def test_returns_2xx_immediately_without_sleeping(instant_clock: list[float]) -> None:
    handler: typing.Final = _SequenceHandler([httpx2.Response(200)])
    transport: typing.Final = _make_transport(handler)
    with httpx2.Client(transport=transport) as client:
        response = client.get(_REQUEST_URL)
    assert response.status_code == _OK_STATUS
    assert handler.calls == _SINGLE_CALL
    assert instant_clock == []


def test_stops_retrying_when_wall_budget_would_be_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_calls: list[float] = []
    monkeypatch.setattr(_transport.time, "sleep", sleep_calls.append)
    monkeypatch.setattr(_transport.random, "uniform", lambda lo, hi: hi)  # noqa: ARG005
    monotonic_values: typing.Final = iter([0.0, _BUDGET_OVERFLOW_MONOTONIC])
    monkeypatch.setattr(_transport.time, "monotonic", lambda: next(monotonic_values))

    handler: typing.Final = _SequenceHandler(
        [httpx2.Response(503), httpx2.Response(503), httpx2.Response(503)],
    )
    transport: typing.Final = _make_transport(handler)
    with httpx2.Client(transport=transport) as client:
        response = client.get(_REQUEST_URL)

    assert response.status_code == _SERVICE_UNAVAILABLE_STATUS
    assert handler.calls == _SINGLE_CALL
    assert sleep_calls == []


def test_stops_retrying_when_wall_budget_would_be_exceeded_for_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_calls: list[float] = []
    monkeypatch.setattr(_transport.time, "sleep", sleep_calls.append)
    monkeypatch.setattr(_transport.random, "uniform", lambda lo, hi: hi)  # noqa: ARG005
    monotonic_values: typing.Final = iter([0.0, _BUDGET_OVERFLOW_MONOTONIC])
    monkeypatch.setattr(_transport.time, "monotonic", lambda: next(monotonic_values))

    handler: typing.Final = _SequenceHandler([httpx2.ConnectError, httpx2.Response(200)])
    transport: typing.Final = _make_transport(handler)
    with httpx2.Client(transport=transport) as client, pytest.raises(httpx2.ConnectError):
        client.get(_REQUEST_URL)
    assert sleep_calls == []
    assert handler.calls == _SINGLE_CALL


def test_close_delegates_to_inner_close() -> None:
    inner: typing.Final = _CloseRecorder()
    transport: typing.Final = RetryingTransport(inner=inner)
    transport.close()
    assert inner.close_calls == _SINGLE_CALL


def test_retry_logic_is_single_owner_via_grep() -> None:
    grep: typing.Final = shutil.which("grep")
    if grep is None:
        pytest.skip("grep not available")
    semvertag_dir: typing.Final = pathlib.Path(__file__).resolve().parents[2] / "semvertag"
    forbidden: typing.Final = ("tenacity", "httpx-retries", "httpx_retries")
    for needle in forbidden:
        result = subprocess.run(  # noqa: S603
            [grep, "-rn", needle, str(semvertag_dir)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.stdout == "", f"Forbidden token {needle!r} found:\n{result.stdout}"

    retry_after_hits: typing.Final = subprocess.run(  # noqa: S603
        [grep, "-rln", "Retry-After", str(semvertag_dir)],
        check=False,
        capture_output=True,
        text=True,
    )
    matched_files: typing.Final = {
        pathlib.Path(line).name for line in retry_after_hits.stdout.strip().splitlines() if line
    }
    assert matched_files <= {"_transport.py"}, f"Retry-After referenced outside _transport.py: {matched_files}"
