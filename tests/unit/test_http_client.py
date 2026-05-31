import typing

import httpx2
import pydantic
import pytest

from semvertag._errors import ProviderAPIError
from semvertag.providers._http import HttpClient


_BASE_URL: typing.Final = "https://example.test"
_EXPECTED_COUNT: typing.Final = 7


class _SampleResponse(pydantic.BaseModel):
    name: str
    count: int


def _build_client(handler: typing.Callable[[httpx2.Request], httpx2.Response]) -> HttpClient:
    transport: typing.Final = httpx2.MockTransport(handler)
    inner: typing.Final = httpx2.Client(transport=transport, base_url=_BASE_URL)
    return HttpClient(
        client=inner,
        auth_headers=lambda: {"X-Test-Auth": "token-xyz"},
        status_translator=lambda _status: None,
    )


def test_request_returns_validated_schema_instance_on_happy_path() -> None:
    def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"name": "alice", "count": _EXPECTED_COUNT})

    http: typing.Final = _build_client(handler)
    result: typing.Final = http.request("GET", "/things/1", schema=_SampleResponse)
    assert isinstance(result, _SampleResponse)
    assert result.name == "alice"
    assert result.count == _EXPECTED_COUNT


def test_request_translates_request_error_to_provider_api_error() -> None:
    def handler(_request: httpx2.Request) -> httpx2.Response:
        msg: typing.Final = "connection refused"
        raise httpx2.ConnectError(msg)

    http: typing.Final = _build_client(handler)
    with pytest.raises(ProviderAPIError, match="request failed"):
        http.request("GET", "/things/1", schema=_SampleResponse)


def test_request_translates_malformed_json_to_provider_api_error() -> None:
    def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, text="this is not json")

    http: typing.Final = _build_client(handler)
    with pytest.raises(ProviderAPIError, match="malformed JSON"):
        http.request("GET", "/things/1", schema=_SampleResponse)
