import typing

import httpware

from semvertag._errors import AuthError, ConfigError, ProviderAPIError


_TAG_EXISTS_FRAGMENT: typing.Final = "already exists"


def _translate_gitlab_auth(exc: httpware.StatusError) -> Exception:
    if isinstance(exc, httpware.UnauthorizedError):
        return AuthError("Token rejected: 401. Verify SEMVERTAG_TOKEN is valid and has 'api' scope.")
    return AuthError(
        "Token missing scope or insufficient permission: 403. "
        "Add 'api' or 'write_repository' to the SEMVERTAG_TOKEN scopes on GitLab."
    )


def _translate_gitlab_status(exc: httpware.StatusError, *, project_id: int) -> Exception:
    if isinstance(exc, (httpware.UnauthorizedError, httpware.ForbiddenError)):
        return _translate_gitlab_auth(exc)
    if isinstance(exc, httpware.NotFoundError):
        return ConfigError(f"GitLab project not found: project_id={project_id}. Verify CI_PROJECT_ID or --project-id.")
    if isinstance(exc, httpware.UnprocessableEntityError):
        return ConfigError(
            "Request rejected by GitLab: 422. Check tag name format and that the referenced commit exists."
        )
    if isinstance(exc, httpware.RateLimitedError):
        return ProviderAPIError("GitLab rate limit: 429. Retries exhausted after 3 attempts; try again later.")
    if isinstance(exc, httpware.ServerStatusError):
        return ProviderAPIError(
            f"GitLab API failure: {exc.response.status_code}. "
            "Retries exhausted after 3 attempts. Try again or check GitLab status."
        )
    return ProviderAPIError(f"Unexpected GitLab response: {exc.response.status_code}. Please file an issue.")


def _translate_gitlab_transport(exc: httpware.ClientError) -> Exception:
    if isinstance(exc, httpware.TimeoutError):
        return ProviderAPIError("GitLab request timed out. Try again or increase SEMVERTAG_REQUEST_TIMEOUT.")
    if isinstance(exc, httpware.RetryBudgetExhaustedError):
        return ProviderAPIError(f"GitLab retries exhausted after {exc.attempts} attempts. Try again later.")
    if isinstance(exc, httpware.NetworkError):
        return ProviderAPIError("GitLab unreachable. Check network connectivity.")
    return ProviderAPIError(f"GitLab request failed: {type(exc).__name__}")


def translate_gitlab(exc: httpware.ClientError, *, project_id: int) -> Exception:
    """
    Translate an httpware ClientError into the semvertag domain error for GitLab.

    Handles both status errors (4xx/5xx) and transport-layer failures
    (network, timeout, retry budget exhaustion).
    """
    if isinstance(exc, httpware.StatusError):
        return _translate_gitlab_status(exc, project_id=project_id)
    return _translate_gitlab_transport(exc)


def translate_create_tag_bad_request(exc: httpware.BadRequestError, *, tag_name: str) -> Exception:
    """create_tag's 400 has an 'already exists' special case; everything else is a generic 400."""
    body = exc.response.text
    if _TAG_EXISTS_FRAGMENT in body.lower():
        return ConfigError(
            f"Tag already exists: '{tag_name}'. The tag was created by a concurrent run or previous invocation."
        )
    return ConfigError("Request rejected by GitLab: 400. Check tag name format and that the referenced commit exists.")
