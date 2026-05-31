import collections.abc
import dataclasses
import typing

import httpx2
import pydantic


T = typing.TypeVar("T", bound=pydantic.BaseModel)

AuthHeaders: typing.TypeAlias = collections.abc.Callable[[], dict[str, str]]
StatusTranslator: typing.TypeAlias = collections.abc.Callable[[int], None]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class HttpClient:
    client: httpx2.Client
    auth_headers: AuthHeaders
    status_translator: StatusTranslator

    def request(self, method: str, url: str, *, schema: type[T], **kwargs: typing.Any) -> T:  # noqa: ANN401
        response = self.client.request(method, url, headers=self.auth_headers(), **kwargs)
        payload = response.json()
        return schema.model_validate(payload)


__all__: typing.Final = ("AuthHeaders", "HttpClient", "StatusTranslator")
