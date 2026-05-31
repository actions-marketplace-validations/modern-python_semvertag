import dataclasses
import re
import typing
import urllib.parse

import httpx2
import pydantic

from semvertag._errors import AuthError, ConfigError, ProviderAPIError
from semvertag._settings import GitLabConfig
from semvertag._types import Commit, Tag
from semvertag.providers._http import HttpClient


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
_HTTP_TOO_MANY_REQUESTS: typing.Final = 429
_HTTP_SERVER_ERROR_MIN: typing.Final = 500
_HTTP_SERVER_ERROR_MAX: typing.Final = 600

_TAG_EXISTS_FRAGMENT: typing.Final = "already exists"


class _ProjectResponse(pydantic.BaseModel):
    default_branch: str | None


class _CommitItem(pydantic.BaseModel):
    id: str
    message: str


class _TagCommit(pydantic.BaseModel):
    id: str


class _TagItem(pydantic.BaseModel):
    name: str
    commit: _TagCommit


# RFC 8288 Link header: <uri-reference>;param=value;param="value";...
_LINK_ENTRY_RE: typing.Final = re.compile(
    r"<\s*(?P<url>[^>]*?)\s*>(?P<params>(?:\s*;\s*[^,;]+)*)",
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class GitLabProvider:
    name: typing.ClassVar[str] = "gitlab"
    config: GitLabConfig
    project_id: int
    http: HttpClient

    def get_default_branch(self) -> str:
        project = self.http.request(
            "GET",
            self._url(f"{_API_PREFIX}/{self.project_id}"),
            schema=_ProjectResponse,
        )
        if not project.default_branch:
            msg = "Default branch missing from GitLab response. Verify the project has a default branch configured."
            raise ConfigError(msg)
        return project.default_branch

    def get_latest_commit_on_default_branch(self) -> Commit:
        default_branch: typing.Final = self.get_default_branch()
        items = self.http.request_many(
            "GET",
            self._url(f"{_API_PREFIX}/{self.project_id}/repository/commits"),
            schema=_CommitItem,
            params={"ref_name": default_branch, "per_page": 1},
        )
        if not items:
            msg = f"No commits on default branch '{default_branch}'. The branch appears empty."
            raise ProviderAPIError(msg)
        head = items[0]
        return Commit(sha=head.id, message=head.message)

    def list_tags(self) -> list[Tag]:
        tags: list[Tag] = []
        base_url: typing.Final = self._url(f"{_API_PREFIX}/{self.project_id}/repository/tags")
        url: str = base_url
        params: dict[str, typing.Any] | None = {"per_page": _TAGS_PER_PAGE, "page": 1}
        for _ in range(_MAX_TAG_PAGES):
            response = self.http.request_raw("GET", url, params=params)
            _translate_status(response.status_code, self.project_id)
            items = _validate_tag_list(response)
            tags.extend(Tag(name=item.name, commit_sha=item.commit.id) for item in items)
            next_url = _next_page_url(response, current_url=url)
            if next_url is None:
                return tags
            if not _same_origin(next_url, self.config.endpoint):
                msg = (
                    "GitLab pagination Link header points to a different host than SEMVERTAG_GITLAB__ENDPOINT. "
                    "Refusing to follow to protect credentials."
                )
                raise ProviderAPIError(msg)
            url, params = next_url, None
        msg = (
            f"Tag pagination exceeded {_MAX_TAG_PAGES} pages. "
            "The project has an unexpected number of tags; please file an issue."
        )
        raise ProviderAPIError(msg)

    def create_tag(self, name: str, commit_sha: str) -> None:
        response = self.http.request_raw(
            "POST",
            self._url(f"{_API_PREFIX}/{self.project_id}/repository/tags"),
            json={"tag_name": name, "ref": commit_sha},
        )
        if response.status_code == _HTTP_CREATED:
            return
        if response.status_code == _HTTP_BAD_REQUEST:
            body_message = ""
            try:
                payload = response.json()
                body_message = str(payload.get("message", "")) if isinstance(payload, dict) else ""
            except (ValueError, httpx2.DecodingError):
                pass
            if _TAG_EXISTS_FRAGMENT in body_message.lower():
                msg = f"Tag already exists: '{name}'. The tag was created by a concurrent run or previous invocation."
                raise ConfigError(msg)
            msg = "Request rejected by GitLab: 400. Check tag name format and that the referenced commit exists."
            raise ConfigError(msg)
        _translate_status(response.status_code, self.project_id)

    def _url(self, path: str) -> str:
        return f"{self.config.endpoint.rstrip('/')}{path}"


def gitlab_auth_headers(token: pydantic.SecretStr) -> dict[str, str]:
    return {_PRIVATE_TOKEN_HEADER: token.get_secret_value()}


def _translate_status(status: int, project_id: int) -> None:
    if status in {_HTTP_OK, _HTTP_CREATED}:
        return
    if status == _HTTP_UNAUTHORIZED:
        msg = "Token rejected: 401. Verify SEMVERTAG_TOKEN is valid and has 'api' scope."
        raise AuthError(msg)
    if status == _HTTP_FORBIDDEN:
        msg = (
            "Token missing scope or insufficient permission: 403. "
            "Add 'api' or 'write_repository' to the SEMVERTAG_TOKEN scopes on GitLab."
        )
        raise AuthError(msg)
    if status == _HTTP_NOT_FOUND:
        msg = f"GitLab project not found: project_id={project_id}. Verify CI_PROJECT_ID or --project-id."
        raise ConfigError(msg)
    if status == _HTTP_UNPROCESSABLE:
        msg = "Request rejected by GitLab: 422. Check tag name format and that the referenced commit exists."
        raise ConfigError(msg)
    if status == _HTTP_TOO_MANY_REQUESTS:
        msg = "GitLab rate limit: 429. Retries exhausted after 3 attempts; try again later."
        raise ProviderAPIError(msg)
    if _HTTP_SERVER_ERROR_MIN <= status < _HTTP_SERVER_ERROR_MAX:
        msg = f"GitLab API failure: {status}. Retries exhausted after 3 attempts. Try again or check GitLab status."
        raise ProviderAPIError(msg)
    msg = f"Unexpected GitLab response: {status}. Please file an issue."
    raise ProviderAPIError(msg)


def _next_page_url(response: httpx2.Response, current_url: str) -> str | None:
    link_header: typing.Final = response.headers.get("link")
    if not link_header:
        return None
    for match in _LINK_ENTRY_RE.finditer(link_header):
        url_part = match.group("url").strip()
        if not url_part:
            continue
        if "next" in _parse_rel_values(match.group("params")):
            return urllib.parse.urljoin(current_url, url_part)
    return None


def _validate_tag_list(response: httpx2.Response) -> list[_TagItem]:
    try:
        payload = response.json()
    except (ValueError, httpx2.DecodingError) as exc:
        msg = "GitLab tags response malformed JSON."
        raise ProviderAPIError(msg) from exc
    if not isinstance(payload, list):
        msg = "GitLab tags response shape invalid: expected list."
        raise ProviderAPIError(msg)
    try:
        return [_TagItem.model_validate(item) for item in payload]
    except pydantic.ValidationError as exc:
        msg = f"GitLab tags response shape invalid: {exc}"
        raise ProviderAPIError(msg) from exc


def _parse_rel_values(params_blob: str) -> set[str]:
    for raw_param in params_blob.split(";"):
        param = raw_param.strip()
        if not param:
            continue
        name, _, value = param.partition("=")
        if name.strip().lower() != "rel":
            continue
        cleaned = value.strip().strip('"').strip("'").lower()
        return set(cleaned.split())
    return set()


def _same_origin(url: str, endpoint: str) -> bool:
    parsed: typing.Final = urllib.parse.urlsplit(url)
    expected: typing.Final = urllib.parse.urlsplit(endpoint)
    return parsed.scheme == expected.scheme and parsed.netloc == expected.netloc
