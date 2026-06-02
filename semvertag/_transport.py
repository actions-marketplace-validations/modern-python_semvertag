import datetime
import email.utils
import random
import time
import typing

import httpx2


RETRYABLE_STATUSES: typing.Final[frozenset[int]] = frozenset({408, 429, 500, 502, 503, 504})
RETRYABLE_EXCEPTIONS: typing.Final[tuple[type[BaseException], ...]] = (
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
        self._inner: httpx2.BaseTransport = inner or httpx2.HTTPTransport()

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        start: typing.Final = time.monotonic()
        last_response: httpx2.Response | None = None
        last_exc: BaseException | None = None
        attempt = 0
        while True:
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
            attempt += 1
        if last_response is not None:
            return last_response
        assert last_exc is not None  # noqa: S101
        raise last_exc

    def close(self) -> None:
        self._inner.close()


def _compute_sleep(attempt: int, last_response: httpx2.Response | None) -> float:
    backoff: typing.Final = random.uniform(0.0, BACKOFF_BASE_SECONDS * (2**attempt))  # noqa: S311
    if last_response is not None and last_response.status_code in RETRYABLE_STATUSES:
        parsed: typing.Final = _parse_retry_after(last_response.headers.get("retry-after"), time.time())
        if parsed is not None:
            return max(parsed, backoff)
    return backoff


def _parse_retry_after(value: str | None, now_epoch: float) -> float | None:
    if value is None:
        return None
    stripped: typing.Final = value.strip()
    if not stripped:
        return None
    try:
        seconds = float(stripped)
    except (TypeError, ValueError):
        pass
    else:
        return seconds if seconds >= 0.0 else None
    try:
        parsed_dt = email.utils.parsedate_to_datetime(stripped)
        if parsed_dt.tzinfo is None:
            parsed_dt = parsed_dt.replace(tzinfo=datetime.timezone.utc)
        delta: typing.Final = parsed_dt.timestamp() - now_epoch
    except (TypeError, ValueError, OverflowError):
        return None
    return max(0.0, delta)
