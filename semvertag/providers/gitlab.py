import dataclasses
import re
import typing
import urllib.parse

import httpx2

from semvertag._errors import AuthError, ConfigError, ProviderAPIError
from semvertag._settings import GitLabConfig
from semvertag._types import CheckResult, Commit, Tag


_API_PREFIX: typing.Final = "/api/v4/projects"
_USER_PATH: typing.Final = "/api/v4/user"
_TOKEN_INTROSPECTION_PATH: typing.Final = "/api/v4/personal_access_tokens/self"
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
_API_SCOPE: typing.Final = "api"

# RFC 8288 Link header: <uri-reference>;param=value;param="value";...
_LINK_ENTRY_RE: typing.Final = re.compile(
    r"<\s*(?P<url>[^>]*?)\s*>(?P<params>(?:\s*;\s*[^,;]+)*)",
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class GitLabProvider:
    name: typing.ClassVar[str] = "gitlab"
    config: GitLabConfig
    project_id: int
    client: httpx2.Client

    def get_default_branch(self) -> str:
        url: typing.Final = self._url(f"{_API_PREFIX}/{self.project_id}")
        try:
            response = self.client.get(url, headers=self._auth_headers())
        except httpx2.RequestError as exc:
            raise ProviderAPIError(_request_failed_message(exc)) from exc
        _translate_status(response.status_code, self.project_id)
        try:
            payload = response.json()
        except (ValueError, httpx2.DecodingError) as exc:
            msg = "GitLab project response malformed. Check SEMVERTAG_GITLAB__ENDPOINT and project ID."
            raise ProviderAPIError(msg) from exc
        if not isinstance(payload, dict) or "default_branch" not in payload:
            msg = "GitLab project response malformed. Check SEMVERTAG_GITLAB__ENDPOINT and project ID."
            raise ProviderAPIError(msg)
        default_branch = payload["default_branch"]
        if not isinstance(default_branch, str) or not default_branch:
            msg = "Default branch missing from GitLab response. Verify the project has a default branch configured."
            raise ConfigError(msg)
        return default_branch

    def get_latest_commit_on_default_branch(self) -> Commit:
        default_branch: typing.Final = self.get_default_branch()
        url: typing.Final = self._url(f"{_API_PREFIX}/{self.project_id}/repository/commits")
        try:
            response = self.client.get(
                url,
                params={"ref_name": default_branch, "per_page": 1},
                headers=self._auth_headers(),
            )
        except httpx2.RequestError as exc:
            raise ProviderAPIError(_request_failed_message(exc)) from exc
        _translate_status(response.status_code, self.project_id)
        try:
            items = response.json()
        except (ValueError, httpx2.DecodingError) as exc:
            msg = "GitLab commits response malformed. Check SEMVERTAG_GITLAB__ENDPOINT and project ID."
            raise ProviderAPIError(msg) from exc
        if not isinstance(items, list):
            msg = "GitLab commits response malformed. Check SEMVERTAG_GITLAB__ENDPOINT and project ID."
            raise ProviderAPIError(msg)
        if not items:
            msg = f"No commits on default branch '{default_branch}'. The branch appears empty."
            raise ProviderAPIError(msg)
        try:
            head = items[0]
            return Commit(sha=head["id"], message=head["message"])
        except (KeyError, TypeError) as exc:
            msg = "GitLab commit object missing expected keys. Check SEMVERTAG_GITLAB__ENDPOINT and project ID."
            raise ProviderAPIError(msg) from exc

    def list_tags(self) -> list[Tag]:
        tags: list[Tag] = []
        base_url: typing.Final = self._url(f"{_API_PREFIX}/{self.project_id}/repository/tags")
        url: str = base_url
        params: dict[str, typing.Any] | None = {"per_page": _TAGS_PER_PAGE, "page": 1}
        for _ in range(_MAX_TAG_PAGES):
            try:
                response = self.client.get(url, params=params, headers=self._auth_headers())
            except httpx2.RequestError as exc:
                raise ProviderAPIError(_request_failed_message(exc)) from exc
            _translate_status(response.status_code, self.project_id)
            try:
                payload = response.json()
            except (ValueError, httpx2.DecodingError) as exc:
                msg = "GitLab tags response malformed. Check SEMVERTAG_GITLAB__ENDPOINT and project ID."
                raise ProviderAPIError(msg) from exc
            if not isinstance(payload, list):
                msg = "GitLab tags response malformed. Check SEMVERTAG_GITLAB__ENDPOINT and project ID."
                raise ProviderAPIError(msg)
            try:
                tags.extend(Tag(name=item["name"], commit_sha=item["commit"]["id"]) for item in payload)
            except (KeyError, TypeError) as exc:
                msg = "GitLab tag object missing expected keys. Check SEMVERTAG_GITLAB__ENDPOINT and project ID."
                raise ProviderAPIError(msg) from exc
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
        url: typing.Final = self._url(f"{_API_PREFIX}/{self.project_id}/repository/tags")
        try:
            response = self.client.post(
                url,
                json={"tag_name": name, "ref": commit_sha},
                headers=self._auth_headers(),
            )
        except httpx2.RequestError as exc:
            raise ProviderAPIError(_request_failed_message(exc)) from exc
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

    def check_token(self) -> CheckResult:
        url: typing.Final = self._url(_USER_PATH)
        response, error_type = self._safe_get(url)
        if response is None:
            return CheckResult(
                name="token",
                status="failed",
                cause=f"GitLab unreachable ({error_type}). Check SEMVERTAG_GITLAB__ENDPOINT.",
            )
        if response.status_code == _HTTP_OK:
            return CheckResult(name="token", status="passed", cause="Token recognized by GitLab API.")
        if response.status_code == _HTTP_UNAUTHORIZED:
            return CheckResult(
                name="token",
                status="failed",
                cause="Token rejected by GitLab. Verify SEMVERTAG_TOKEN is valid.",
            )
        if response.status_code == _HTTP_FORBIDDEN:
            return CheckResult(
                name="token",
                status="failed",
                cause="Token blocked or lacks permission on /api/v4/user. Verify SEMVERTAG_TOKEN is not blocked.",
            )
        return CheckResult(
            name="token",
            status="failed",
            cause=f"Unexpected GitLab response: {response.status_code}.",
        )

    def check_scopes(self) -> CheckResult:
        url: typing.Final = self._url(_TOKEN_INTROSPECTION_PATH)
        response, error_type = self._safe_get(url)
        if response is None:
            cause = f"GitLab unreachable ({error_type}). Check SEMVERTAG_GITLAB__ENDPOINT."
        elif response.status_code == _HTTP_OK:
            return _evaluate_scopes_payload(response)
        elif response.status_code in {_HTTP_UNAUTHORIZED, _HTTP_FORBIDDEN}:
            cause = "Token missing 'api' scope. Add it to the SEMVERTAG_TOKEN scopes on GitLab."
        elif response.status_code == _HTTP_NOT_FOUND:
            cause = "GitLab version too old (< 15.0): missing /personal_access_tokens/self endpoint."
        else:
            cause = f"Unexpected GitLab response: {response.status_code}."
        return CheckResult(name="scopes", status="failed", cause=cause)

    def check_project_access(self) -> CheckResult:
        url: typing.Final = self._url(f"{_API_PREFIX}/{self.project_id}")
        response, error_type = self._safe_get(url)
        if response is None:
            return CheckResult(
                name="project_access",
                status="failed",
                cause=f"GitLab unreachable ({error_type}). Check SEMVERTAG_GITLAB__ENDPOINT.",
            )
        if response.status_code == _HTTP_OK:
            return CheckResult(
                name="project_access",
                status="passed",
                cause=f"Project visible: project_id={self.project_id}.",
            )
        if response.status_code == _HTTP_UNAUTHORIZED:
            return CheckResult(
                name="project_access",
                status="failed",
                cause="Token rejected by GitLab. Verify SEMVERTAG_TOKEN is valid.",
            )
        if response.status_code == _HTTP_FORBIDDEN:
            return CheckResult(
                name="project_access",
                status="failed",
                cause=f"Token has no access to project_id={self.project_id}.",
            )
        if response.status_code == _HTTP_NOT_FOUND:
            return CheckResult(
                name="project_access",
                status="failed",
                cause=f"GitLab project not found: project_id={self.project_id}. Verify CI_PROJECT_ID or --project-id.",
            )
        return CheckResult(
            name="project_access",
            status="failed",
            cause=f"Unexpected GitLab response: {response.status_code}.",
        )

    def check_protected_tags(self) -> CheckResult:
        url: typing.Final = self._url(f"{_API_PREFIX}/{self.project_id}/protected_tags")
        response, error_type = self._safe_get(url)
        if response is None:
            return CheckResult(
                name="protected_tags",
                status="failed",
                cause=f"GitLab unreachable ({error_type}). Check SEMVERTAG_GITLAB__ENDPOINT.",
            )
        if response.status_code == _HTTP_OK:
            return CheckResult(
                name="protected_tags",
                status="passed",
                cause="Protected-tag configuration is readable.",
            )
        if response.status_code in {_HTTP_UNAUTHORIZED, _HTTP_FORBIDDEN}:
            return CheckResult(
                name="protected_tags",
                status="failed",
                cause="Token cannot read protected_tags. Add 'read_repository' or 'api' to scopes.",
            )
        if response.status_code == _HTTP_NOT_FOUND:
            return CheckResult(
                name="protected_tags",
                status="failed",
                cause=f"GitLab project not found: project_id={self.project_id}. Verify CI_PROJECT_ID or --project-id.",
            )
        return CheckResult(
            name="protected_tags",
            status="failed",
            cause=f"Unexpected GitLab response: {response.status_code}.",
        )

    def _auth_headers(self) -> dict[str, str]:
        return {_PRIVATE_TOKEN_HEADER: self.config.token.get_secret_value()}

    def _url(self, path: str) -> str:
        return f"{self.config.endpoint.rstrip('/')}{path}"

    def _safe_get(self, url: str) -> tuple[httpx2.Response | None, str | None]:
        try:
            return self.client.get(url, headers=self._auth_headers()), None
        except httpx2.RequestError as exc:
            return None, type(exc).__name__


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


def _evaluate_scopes_payload(response: httpx2.Response) -> CheckResult:
    try:
        payload = response.json()
    except (ValueError, httpx2.DecodingError):
        payload = None
    if not isinstance(payload, dict):
        return CheckResult(
            name="scopes",
            status="failed",
            cause="GitLab token introspection response malformed. Check SEMVERTAG_GITLAB__ENDPOINT.",
        )
    scopes = payload.get("scopes", [])
    if not isinstance(scopes, list):
        scopes = []
    if _API_SCOPE in scopes:
        return CheckResult(name="scopes", status="passed", cause="Token carries 'api' scope.")
    return CheckResult(
        name="scopes",
        status="failed",
        cause="Token missing 'api' scope. Add it to the SEMVERTAG_TOKEN scopes on GitLab.",
    )


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


def _request_failed_message(exc: httpx2.RequestError) -> str:
    return f"GitLab request failed: {type(exc).__name__}. Check SEMVERTAG_GITLAB__ENDPOINT and network connectivity."


__all__: typing.Final = ("GitLabProvider",)
