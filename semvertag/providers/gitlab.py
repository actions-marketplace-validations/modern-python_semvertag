import dataclasses
import re
import typing
import urllib.parse

import httpware
import httpx2
import pydantic

from semvertag._errors import ConfigError, ProviderAPIError
from semvertag._settings import GitLabConfig
from semvertag._types import Commit, Tag
from semvertag.providers import _errors


_API_PREFIX: typing.Final = "/api/v4/projects"
_TAGS_PER_PAGE: typing.Final = 100
_MAX_TAG_PAGES: typing.Final = 100


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
    http: httpware.Client

    def get_default_branch(self) -> str:
        try:
            response = self.http.send(
                self.http.build_request(
                    "GET",
                    f"{_API_PREFIX}/{self.project_id}",
                )
            )
        except httpware.ClientError as exc:
            raise _errors.translate_gitlab(exc, project_id=self.project_id) from exc
        project = _validate_project_response(response)
        if not project.default_branch:
            msg = "Default branch missing from GitLab response. Verify the project has a default branch configured."
            raise ConfigError(msg)
        return project.default_branch

    def get_latest_commit_on_default_branch(self) -> Commit:
        default_branch: typing.Final = self.get_default_branch()
        try:
            response = self.http.send(
                self.http.build_request(
                    "GET",
                    f"{_API_PREFIX}/{self.project_id}/repository/commits",
                    params={"ref_name": default_branch, "per_page": 1},
                )
            )
        except httpware.ClientError as exc:
            raise _errors.translate_gitlab(exc, project_id=self.project_id) from exc
        items = _validate_commit_list(response)
        if not items:
            msg = f"No commits on default branch '{default_branch}'. The branch appears empty."
            raise ProviderAPIError(msg)
        head = items[0]
        return Commit(sha=head.id, message=head.message)

    def list_tags(self) -> list[Tag]:
        tags: list[Tag] = []
        url: str = f"{_API_PREFIX}/{self.project_id}/repository/tags"
        params: dict[str, typing.Any] | None = {"per_page": _TAGS_PER_PAGE, "page": 1}
        for _ in range(_MAX_TAG_PAGES):
            try:
                response = self.http.send(self.http.build_request("GET", url, params=params))
            except httpware.ClientError as exc:
                raise _errors.translate_gitlab(exc, project_id=self.project_id) from exc
            items = _validate_tag_list(response)
            tags.extend(Tag(name=item.name, commit_sha=item.commit.id) for item in items)
            next_url = _next_page_url(response, current_url=str(response.request.url))
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
        try:
            self.http.send(
                self.http.build_request(
                    "POST",
                    f"{_API_PREFIX}/{self.project_id}/repository/tags",
                    json={"tag_name": name, "ref": commit_sha},
                )
            )
        except httpware.BadRequestError as exc:
            raise _errors.translate_create_tag_bad_request(exc, tag_name=name) from exc
        except httpware.ClientError as exc:
            raise _errors.translate_gitlab(exc, project_id=self.project_id) from exc


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


_TModel = typing.TypeVar("_TModel", bound=pydantic.BaseModel)


def _validate_obj(response: httpx2.Response, model: type[_TModel], *, label: str) -> _TModel:
    try:
        payload = response.json()
    except (ValueError, httpx2.DecodingError) as exc:
        msg = f"GitLab {label} response malformed JSON."
        raise ProviderAPIError(msg) from exc
    if not isinstance(payload, dict):
        msg = f"GitLab {label} response shape invalid: expected object."
        raise ProviderAPIError(msg)
    try:
        return model.model_validate(payload)
    except pydantic.ValidationError as exc:
        msg = f"GitLab {label} response shape invalid: {exc}"
        raise ProviderAPIError(msg) from exc


def _validate_project_response(response: httpx2.Response) -> _ProjectResponse:
    return _validate_obj(response, _ProjectResponse, label="project")


def _validate_tag_list(response: httpx2.Response) -> list[_TagItem]:
    return _validate_list(response, _TagItem, label="tags")


def _validate_commit_list(response: httpx2.Response) -> list[_CommitItem]:
    return _validate_list(response, _CommitItem, label="commits")


def _validate_list(response: httpx2.Response, model: type[_TModel], *, label: str) -> list[_TModel]:
    try:
        payload = response.json()
    except (ValueError, httpx2.DecodingError) as exc:
        msg = f"GitLab {label} response malformed JSON."
        raise ProviderAPIError(msg) from exc
    if not isinstance(payload, list):
        msg = f"GitLab {label} response shape invalid: expected list."
        raise ProviderAPIError(msg)
    try:
        return [model.model_validate(item) for item in payload]
    except pydantic.ValidationError as exc:
        msg = f"GitLab {label} response shape invalid: {exc}"
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
