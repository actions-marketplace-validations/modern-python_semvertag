import typing

import httpware
import httpx2

from semvertag._errors import AuthError, ConfigError, ProviderAPIError
from semvertag.providers._errors import translate_create_tag_bad_request, translate_gitlab


_PROJECT_ID = 4242

_DUMMY_REQUEST: typing.Final[httpx2.Request] = httpx2.Request(
    "GET", "https://gitlab.example.com/api/v4/projects/4242/repository/tags"
)


def _response(status: int, *, body: bytes = b"") -> httpx2.Response:
    r = httpx2.Response(status_code=status, content=body)
    r.request = _DUMMY_REQUEST
    return r


def _status_error(cls: type[httpware.StatusError], status: int, body: bytes = b"") -> httpware.StatusError:
    return cls(_response(status, body=body))


# translate_gitlab — status errors


def test_translate_gitlab_401_becomes_auth_error_with_token_guidance() -> None:
    result = translate_gitlab(_status_error(httpware.UnauthorizedError, 401), project_id=_PROJECT_ID)
    assert isinstance(result, AuthError)
    assert "Token rejected" in str(result)
    assert "SEMVERTAG_TOKEN" in str(result)


def test_translate_gitlab_403_becomes_auth_error_with_scope_guidance() -> None:
    result = translate_gitlab(_status_error(httpware.ForbiddenError, 403), project_id=_PROJECT_ID)
    assert isinstance(result, AuthError)
    assert "403" in str(result)
    assert "api" in str(result) or "write_repository" in str(result)


def test_translate_gitlab_404_becomes_config_error_with_project_id() -> None:
    result = translate_gitlab(_status_error(httpware.NotFoundError, 404), project_id=_PROJECT_ID)
    assert isinstance(result, ConfigError)
    assert f"project_id={_PROJECT_ID}" in str(result)


def test_translate_gitlab_422_becomes_config_error() -> None:
    result = translate_gitlab(_status_error(httpware.UnprocessableEntityError, 422), project_id=_PROJECT_ID)
    assert isinstance(result, ConfigError)
    assert "422" in str(result)


def test_translate_gitlab_429_becomes_provider_api_error() -> None:
    result = translate_gitlab(_status_error(httpware.RateLimitedError, 429), project_id=_PROJECT_ID)
    assert isinstance(result, ProviderAPIError)
    assert "rate limit" in str(result).lower()


def test_translate_gitlab_500_becomes_provider_api_error() -> None:
    result = translate_gitlab(_status_error(httpware.InternalServerError, 500), project_id=_PROJECT_ID)
    assert isinstance(result, ProviderAPIError)
    assert "500" in str(result)


def test_translate_gitlab_503_becomes_provider_api_error() -> None:
    result = translate_gitlab(_status_error(httpware.ServiceUnavailableError, 503), project_id=_PROJECT_ID)
    assert isinstance(result, ProviderAPIError)


def test_translate_gitlab_unknown_4xx_falls_back_to_provider_api_error() -> None:
    # 418 is not specially mapped; ClientStatusError is the fallback for unknown 4xx
    result = translate_gitlab(_status_error(httpware.ClientStatusError, 418), project_id=_PROJECT_ID)
    assert isinstance(result, ProviderAPIError)
    assert "418" in str(result)


# translate_gitlab — transport errors


def test_translate_gitlab_timeout_becomes_provider_api_error() -> None:
    exc = httpware.TimeoutError("read timed out")
    result = translate_gitlab(exc, project_id=_PROJECT_ID)
    assert isinstance(result, ProviderAPIError)
    assert "timed out" in str(result).lower()


def test_translate_gitlab_network_error_becomes_provider_api_error() -> None:
    exc = httpware.NetworkError("connection refused")
    result = translate_gitlab(exc, project_id=_PROJECT_ID)
    assert isinstance(result, ProviderAPIError)


def test_translate_gitlab_retry_budget_exhausted_becomes_provider_api_error() -> None:
    exc = httpware.RetryBudgetExhaustedError(last_response=None, last_exception=None, attempts=3)
    result = translate_gitlab(exc, project_id=_PROJECT_ID)
    assert isinstance(result, ProviderAPIError)
    assert "retr" in str(result).lower()


def test_translate_gitlab_unknown_client_error_falls_back_to_provider_api_error() -> None:
    exc = httpware.ClientError("some unknown httpware error")
    result = translate_gitlab(exc, project_id=_PROJECT_ID)
    assert isinstance(result, ProviderAPIError)
    assert "ClientError" in str(result)


# translate_create_tag_bad_request


def test_translate_create_tag_bad_request_already_exists_becomes_config_error() -> None:
    raw = _status_error(httpware.BadRequestError, 400, body=b'{"message":"Tag already exists"}')
    assert isinstance(raw, httpware.BadRequestError)
    result = translate_create_tag_bad_request(raw, tag_name="v1.2.3")
    assert isinstance(result, ConfigError)
    assert "v1.2.3" in str(result)
    assert "already exists" in str(result).lower()


def test_translate_create_tag_bad_request_already_exists_is_case_insensitive() -> None:
    raw = _status_error(httpware.BadRequestError, 400, body=b'{"message":"Tag ALREADY EXISTS"}')
    assert isinstance(raw, httpware.BadRequestError)
    result = translate_create_tag_bad_request(raw, tag_name="v1.2.3")
    assert isinstance(result, ConfigError)
    assert "already exists" in str(result).lower()


def test_translate_create_tag_bad_request_other_400_becomes_generic_config_error() -> None:
    raw = _status_error(httpware.BadRequestError, 400, body=b'{"message":"bad ref format"}')
    assert isinstance(raw, httpware.BadRequestError)
    result = translate_create_tag_bad_request(raw, tag_name="v1.2.3")
    assert isinstance(result, ConfigError)
    assert "v1.2.3" not in str(result)
    assert "400" in str(result)


def test_translate_gitlab_decode_error_becomes_provider_api_error() -> None:
    underlying = ValueError("input should be a valid dictionary")
    exc = httpware.DecodeError(
        response=_response(200, body=b"null"),
        model=type("FakeModel", (), {}),
        original=underlying,
    )
    result = translate_gitlab(exc, project_id=_PROJECT_ID)
    assert isinstance(result, ProviderAPIError)
    assert "FakeModel" in str(result)
    assert "valid dictionary" in str(result).lower()
