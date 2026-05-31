import collections.abc
import dataclasses
import typing

import httpx2
import pydantic

from semvertag._errors import ProviderAPIError


T = typing.TypeVar("T", bound=pydantic.BaseModel)

AuthHeaders: typing.TypeAlias = collections.abc.Callable[[], dict[str, str]]
StatusTranslator: typing.TypeAlias = collections.abc.Callable[[int], None]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class HttpClient:
    client: httpx2.Client
    auth_headers: AuthHeaders
    status_translator: StatusTranslator

    def request(self, method: str, url: str, *, schema: type[T], **kwargs: typing.Any) -> T:  # noqa: ANN401
        response = self._request_translated(method, url, **kwargs)
        payload = self._decode_json(response)
        try:
            return schema.model_validate(payload)
        except pydantic.ValidationError as exc:
            msg = f"response shape invalid: {exc}"
            raise ProviderAPIError(msg) from exc

    def request_many(self, method: str, url: str, *, schema: type[T], **kwargs: typing.Any) -> list[T]:  # noqa: ANN401
        response = self._request_translated(method, url, **kwargs)
        payload = self._decode_json(response)
        if not isinstance(payload, list):
            msg = f"response shape invalid: expected list, got {type(payload).__name__}"
            raise ProviderAPIError(msg)
        try:
            return [schema.model_validate(item) for item in payload]
        except pydantic.ValidationError as exc:
            msg = f"response shape invalid: {exc}"
            raise ProviderAPIError(msg) from exc

    def request_raw(self, method: str, url: str, **kwargs: typing.Any) -> httpx2.Response:  # noqa: ANN401
        try:
            return self.client.request(method, url, headers=self.auth_headers(), **kwargs)
        except httpx2.RequestError as exc:
            msg = f"request failed: {type(exc).__name__}"
            raise ProviderAPIError(msg) from exc

    def _request_translated(self, method: str, url: str, **kwargs: typing.Any) -> httpx2.Response:  # noqa: ANN401
        response = self.request_raw(method, url, **kwargs)
        self.status_translator(response.status_code)
        return response

    @staticmethod
    def _decode_json(response: httpx2.Response) -> typing.Any:  # noqa: ANN401
        try:
            return response.json()
        except (ValueError, httpx2.DecodingError) as exc:
            msg = "malformed JSON in response body"
            raise ProviderAPIError(msg) from exc
