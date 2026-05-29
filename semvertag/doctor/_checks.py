import typing

from semvertag._errors import AuthError, ConfigError, ProviderAPIError, SemvertagError
from semvertag._types import CheckResult
from semvertag.providers._base import Provider


_CHAIN_METHODS: typing.Final = (
    ("token", "check_token"),
    ("scopes", "check_scopes"),
    ("project_access", "check_project_access"),
    ("protected_tags", "check_protected_tags"),
)
_SKIPPED_CAUSE_TEMPLATE: typing.Final = "Skipped: blocked by {name} check."

# Cause fragments shadow GitLabProvider's cause vocabulary (`providers/gitlab.py`); update in
# lockstep when wording changes there. See story 3-1.
_AUTH_CAUSE_FRAGMENTS: typing.Final = (
    "Token rejected",
    "Token blocked",
    "Token missing",
    "Token cannot read",
    "Token has no access",
)
_CONFIG_CAUSE_FRAGMENTS: typing.Final = (
    "GitLab project not found",
    "GitLab version too old",
)
_PROVIDER_API_CAUSE_FRAGMENTS: typing.Final = (
    "GitLab unreachable",
    "Unexpected GitLab response",
)
_DOMINANCE: typing.Final = (
    AuthError.exit_code,
    ProviderAPIError.exit_code,
    ConfigError.exit_code,
    SemvertagError.exit_code,
)


def run_checks(provider: Provider) -> list[CheckResult]:
    results: list[CheckResult] = []
    blocking_check: str | None = None
    for name, method_name in _CHAIN_METHODS:
        if blocking_check is not None:
            results.append(
                CheckResult(
                    name=name,
                    status="skipped",
                    cause=_SKIPPED_CAUSE_TEMPLATE.format(name=blocking_check),
                ),
            )
            continue
        result = getattr(provider, method_name)()
        results.append(result)
        if result.status == "failed":
            blocking_check = name
    return results


def _exit_code_for_failed_check(result: CheckResult) -> int:
    if any(fragment in result.cause for fragment in _AUTH_CAUSE_FRAGMENTS):
        return AuthError.exit_code
    if any(fragment in result.cause for fragment in _CONFIG_CAUSE_FRAGMENTS):
        return ConfigError.exit_code
    if any(fragment in result.cause for fragment in _PROVIDER_API_CAUSE_FRAGMENTS):
        return ProviderAPIError.exit_code
    return SemvertagError.exit_code


def resolve_exit_code(results: list[CheckResult]) -> int:
    failed_codes: typing.Final = [_exit_code_for_failed_check(r) for r in results if r.status == "failed"]
    if not failed_codes:
        return 0
    return next(code for code in _DOMINANCE if code in failed_codes)


__all__: typing.Final = ("resolve_exit_code", "run_checks")
