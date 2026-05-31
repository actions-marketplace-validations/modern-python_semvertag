import typing

import httpx2
import pydantic
import pytest

from semvertag._errors import AuthError, ProviderAPIError
from semvertag.providers._http import HttpClient


_BASE_URL: typing.Final = "https://example.test"
_EXPECTED_COUNT: typing.Final = 7
_EXPECTED_ITEMS: typing.Final = 2
_UNAUTHORIZED_STATUS: typing.Final = 401


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


def test_request_translates_missing_field_to_provider_api_error() -> None:
    def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"name": "alice"})  # missing 'count'

    http: typing.Final = _build_client(handler)
    with pytest.raises(ProviderAPIError, match="response shape"):
        http.request("GET", "/things/1", schema=_SampleResponse)


def test_request_translates_wrong_field_type_to_provider_api_error() -> None:
    def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"name": "alice", "count": "seven"})

    http: typing.Final = _build_client(handler)
    with pytest.raises(ProviderAPIError, match="response shape"):
        http.request("GET", "/things/1", schema=_SampleResponse)


def test_status_translator_runs_before_json_decode_and_validation() -> None:
    def handler(_request: httpx2.Request) -> httpx2.Response:
        # Body is HTML, not JSON — would fail both decode and schema validation.
        return httpx2.Response(_UNAUTHORIZED_STATUS, text="<html>Unauthorized</html>")

    def translator(status: int) -> None:
        if status == _UNAUTHORIZED_STATUS:
            msg = "token rejected"
            raise AuthError(msg)

    http: typing.Final = HttpClient(
        client=httpx2.Client(transport=httpx2.MockTransport(handler), base_url=_BASE_URL),
        auth_headers=dict,
        status_translator=translator,
    )

    with pytest.raises(AuthError, match="token rejected"):
        http.request("GET", "/things/1", schema=_SampleResponse)


def test_request_many_returns_list_of_validated_instances() -> None:
    def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=[{"name": "a", "count": 1}, {"name": "b", "count": _EXPECTED_ITEMS}])

    http: typing.Final = _build_client(handler)
    result: typing.Final = http.request_many("GET", "/things", schema=_SampleResponse)
    assert len(result) == _EXPECTED_ITEMS
    assert all(isinstance(item, _SampleResponse) for item in result)
    assert result[0].name == "a"
    assert result[1].count == _EXPECTED_ITEMS


def test_request_many_translates_dict_payload_to_provider_api_error() -> None:
    def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"not": "a list"})

    http: typing.Final = _build_client(handler)
    with pytest.raises(ProviderAPIError, match="expected list"):
        http.request_many("GET", "/things", schema=_SampleResponse)


_TEAPOT_STATUS: typing.Final = 418
_SERVER_ERROR_STATUS: typing.Final = 500


def test_request_raw_returns_response_with_auth_headers_applied() -> None:
    captured_headers: dict[str, str] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured_headers.update(request.headers)
        return httpx2.Response(_TEAPOT_STATUS, text="teapot")

    http: typing.Final = _build_client(handler)
    response: typing.Final = http.request_raw("GET", "/teapot")
    assert response.status_code == _TEAPOT_STATUS
    assert response.text == "teapot"
    assert captured_headers.get("x-test-auth") == "token-xyz"


def test_request_raw_does_not_call_status_translator() -> None:
    call_count = {"n": 0}

    def translator(_status: int) -> None:
        call_count["n"] += 1

    def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(_SERVER_ERROR_STATUS, text="server error")

    http: typing.Final = HttpClient(
        client=httpx2.Client(transport=httpx2.MockTransport(handler), base_url=_BASE_URL),
        auth_headers=dict,
        status_translator=translator,
    )
    response: typing.Final = http.request_raw("GET", "/whatever")
    assert response.status_code == _SERVER_ERROR_STATUS
    assert call_count["n"] == 0


def test_request_raw_translates_request_error_to_provider_api_error() -> None:
    def handler(_request: httpx2.Request) -> httpx2.Response:
        msg: typing.Final = "timed out"
        raise httpx2.ReadTimeout(msg)

    http: typing.Final = _build_client(handler)
    with pytest.raises(ProviderAPIError, match="request failed"):
        http.request_raw("GET", "/whatever")
