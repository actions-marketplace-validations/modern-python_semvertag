import collections.abc
import typing

import httpx2
import pydantic
import pytest

from semvertag._settings import GitLabConfig
from semvertag.providers._http import HttpClient
from semvertag.providers.gitlab import GitLabProvider, _translate_status, gitlab_auth_headers


GITLAB_PROJECT_ID: typing.Final = 999
GITLAB_ENDPOINT: typing.Final = "https://gitlab.example.test"
GITLAB_TOKEN: typing.Final = "glpat-XXXXXXXXXXXXXXXXXXXX"
_REQUEST_TIMEOUT: typing.Final = 8.0


HandlerCallable: typing.TypeAlias = collections.abc.Callable[[httpx2.Request], httpx2.Response]


def _make_status_translator(project_id: int) -> typing.Callable[[int], None]:
    def translator(status: int) -> None:
        _translate_status(status, project_id)

    return translator


def default_handler(request: httpx2.Request) -> httpx2.Response:
    method: typing.Final = request.method
    path: typing.Final = request.url.path
    project_path: typing.Final = f"/api/v4/projects/{GITLAB_PROJECT_ID}"

    if method == "GET" and path == project_path:
        return httpx2.Response(200, json={"default_branch": "main"})
    if method == "GET" and path == f"{project_path}/repository/commits":
        return httpx2.Response(
            200,
            json=[{"id": "a2b4d12", "message": "default test commit"}],
        )
    if method == "GET" and path == f"{project_path}/repository/tags":
        return httpx2.Response(200, json=[])
    if method == "POST" and path == f"{project_path}/repository/tags":
        return httpx2.Response(201, json={"name": "default-tag"})
    return httpx2.Response(404, json={"message": "404 Not Found"})


def compose_handler(
    base: HandlerCallable,
    overrides: dict[tuple[str, str], httpx2.Response],
) -> HandlerCallable:
    def composed(request: httpx2.Request) -> httpx2.Response:
        request_method: typing.Final = request.method.upper()
        request_path: typing.Final = request.url.path
        for (method, path_prefix), response in overrides.items():
            if request_method == method.upper() and request_path.startswith(path_prefix):
                return response
        return base(request)

    return composed


@pytest.fixture
def gitlab_transport() -> httpx2.MockTransport:
    return httpx2.MockTransport(default_handler)


@pytest.fixture
def gitlab_client(gitlab_transport: httpx2.MockTransport) -> collections.abc.Iterator[httpx2.Client]:
    with httpx2.Client(transport=gitlab_transport, base_url=GITLAB_ENDPOINT, timeout=_REQUEST_TIMEOUT) as client:
        yield client


@pytest.fixture
def gitlab_http(gitlab_client: httpx2.Client) -> HttpClient:
    config: typing.Final = GitLabConfig(endpoint=GITLAB_ENDPOINT, token=pydantic.SecretStr(GITLAB_TOKEN))
    return HttpClient(
        client=gitlab_client,
        auth_headers=lambda: gitlab_auth_headers(config.token),
        status_translator=_make_status_translator(GITLAB_PROJECT_ID),
    )


@pytest.fixture
def gitlab_provider(gitlab_http: HttpClient) -> GitLabProvider:
    config: typing.Final = GitLabConfig(endpoint=GITLAB_ENDPOINT, token=pydantic.SecretStr(GITLAB_TOKEN))
    return GitLabProvider(config=config, project_id=GITLAB_PROJECT_ID, http=gitlab_http)
