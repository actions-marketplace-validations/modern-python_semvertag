import dataclasses
import typing

import pytest

from semvertag._errors import AuthError, ConfigError, ProviderAPIError, SemvertagError
from semvertag._types import CheckResult, Commit, Tag
from semvertag.doctor._checks import resolve_exit_code, run_checks


_SAMPLE_AUTH_CAUSE: typing.Final = "Token rejected by GitLab. Verify SEMVERTAG_TOKEN is valid."
_SAMPLE_CONFIG_CAUSE: typing.Final = "GitLab project not found: project_id=999. Verify CI_PROJECT_ID or --project-id."
_SAMPLE_PROVIDER_API_CAUSE: typing.Final = "GitLab unreachable (ConnectError). Check SEMVERTAG_GITLAB__ENDPOINT."
_SAMPLE_GENERIC_CAUSE: typing.Final = "Some unexpected condition not covered by any fragment."

_PASSED_TOKEN: typing.Final = CheckResult(
    name="token",
    status="passed",
    cause="Token recognized by GitLab API.",
)
_PASSED_SCOPES: typing.Final = CheckResult(
    name="scopes",
    status="passed",
    cause="Token carries 'api' scope.",
)
_PASSED_PROJECT_ACCESS: typing.Final = CheckResult(
    name="project_access",
    status="passed",
    cause="Project visible: project_id=999.",
)
_PASSED_PROTECTED_TAGS: typing.Final = CheckResult(
    name="protected_tags",
    status="passed",
    cause="Protected-tag configuration is readable.",
)
_FAILED_TOKEN: typing.Final = CheckResult(
    name="token",
    status="failed",
    cause=_SAMPLE_AUTH_CAUSE,
)
_FAILED_SCOPES: typing.Final = CheckResult(
    name="scopes",
    status="failed",
    cause="Token missing 'api' scope. Add it to the SEMVERTAG_TOKEN scopes on GitLab.",
)
_FAILED_PROJECT_ACCESS: typing.Final = CheckResult(
    name="project_access",
    status="failed",
    cause=_SAMPLE_CONFIG_CAUSE,
)
_FAILED_PROTECTED_TAGS: typing.Final = CheckResult(
    name="protected_tags",
    status="failed",
    cause=_SAMPLE_PROVIDER_API_CAUSE,
)


@dataclasses.dataclass
class _StubProvider:
    name: str = "stub"
    token_result: CheckResult = _PASSED_TOKEN
    scopes_result: CheckResult = _PASSED_SCOPES
    project_access_result: CheckResult = _PASSED_PROJECT_ACCESS
    protected_tags_result: CheckResult = _PASSED_PROTECTED_TAGS
    call_log: list[str] = dataclasses.field(default_factory=list)

    def get_default_branch(self) -> str:
        msg = "_StubProvider.get_default_branch must not be called by doctor chain"
        raise AssertionError(msg)

    def get_latest_commit_on_default_branch(self) -> Commit:
        msg = "_StubProvider.get_latest_commit_on_default_branch must not be called by doctor chain"
        raise AssertionError(msg)

    def list_tags(self) -> list[Tag]:
        msg = "_StubProvider.list_tags must not be called by doctor chain"
        raise AssertionError(msg)

    def create_tag(self, name: str, commit_sha: str) -> None:  # noqa: ARG002
        msg = "_StubProvider.create_tag must not be called by doctor chain"
        raise AssertionError(msg)

    def check_token(self) -> CheckResult:
        self.call_log.append("token")
        return self.token_result

    def check_scopes(self) -> CheckResult:
        self.call_log.append("scopes")
        return self.scopes_result

    def check_project_access(self) -> CheckResult:
        self.call_log.append("project_access")
        return self.project_access_result

    def check_protected_tags(self) -> CheckResult:
        self.call_log.append("protected_tags")
        return self.protected_tags_result


def _skipped(name: str, blocking: str) -> CheckResult:
    return CheckResult(
        name=name,
        status="skipped",
        cause=f"Skipped: blocked by {blocking} check.",
    )


def test_returns_four_passed_results_in_declared_order_when_every_check_passes() -> None:
    provider: typing.Final = _StubProvider()
    results: typing.Final = run_checks(provider)
    assert results == [
        _PASSED_TOKEN,
        _PASSED_SCOPES,
        _PASSED_PROJECT_ACCESS,
        _PASSED_PROTECTED_TAGS,
    ]
    assert provider.call_log == ["token", "scopes", "project_access", "protected_tags"]


def test_skips_three_subsequent_checks_when_token_fails() -> None:
    provider: typing.Final = _StubProvider(token_result=_FAILED_TOKEN)
    results: typing.Final = run_checks(provider)
    assert results == [
        _FAILED_TOKEN,
        _skipped("scopes", blocking="token"),
        _skipped("project_access", blocking="token"),
        _skipped("protected_tags", blocking="token"),
    ]
    assert provider.call_log == ["token"]


def test_skips_two_subsequent_checks_when_scopes_fails() -> None:
    provider: typing.Final = _StubProvider(scopes_result=_FAILED_SCOPES)
    results: typing.Final = run_checks(provider)
    assert results == [
        _PASSED_TOKEN,
        _FAILED_SCOPES,
        _skipped("project_access", blocking="scopes"),
        _skipped("protected_tags", blocking="scopes"),
    ]
    assert provider.call_log == ["token", "scopes"]


def test_skips_only_protected_tags_when_project_access_fails() -> None:
    provider: typing.Final = _StubProvider(project_access_result=_FAILED_PROJECT_ACCESS)
    results: typing.Final = run_checks(provider)
    assert results == [
        _PASSED_TOKEN,
        _PASSED_SCOPES,
        _FAILED_PROJECT_ACCESS,
        _skipped("protected_tags", blocking="project_access"),
    ]
    assert provider.call_log == ["token", "scopes", "project_access"]


def test_returns_failure_at_last_step_with_no_skipped_when_protected_tags_fails() -> None:
    provider: typing.Final = _StubProvider(protected_tags_result=_FAILED_PROTECTED_TAGS)
    results: typing.Final = run_checks(provider)
    assert results == [
        _PASSED_TOKEN,
        _PASSED_SCOPES,
        _PASSED_PROJECT_ACCESS,
        _FAILED_PROTECTED_TAGS,
    ]
    assert provider.call_log == ["token", "scopes", "project_access", "protected_tags"]


def test_resolves_exit_code_to_zero_when_every_result_is_passed() -> None:
    results: typing.Final = [
        _PASSED_TOKEN,
        _PASSED_SCOPES,
        _PASSED_PROJECT_ACCESS,
        _PASSED_PROTECTED_TAGS,
    ]
    assert resolve_exit_code(results) == 0


def test_resolves_exit_code_to_zero_for_empty_results() -> None:
    assert resolve_exit_code([]) == 0


def test_resolves_exit_code_to_zero_when_results_contain_only_passed_and_skipped() -> None:
    results: typing.Final = [
        _PASSED_TOKEN,
        _skipped("scopes", blocking="token"),
        _skipped("project_access", blocking="token"),
    ]
    assert resolve_exit_code(results) == 0


@pytest.mark.parametrize(
    "fragment",
    [
        "Token rejected",
        "Token blocked",
        "Token missing",
        "Token cannot read",
        "Token has no access",
    ],
)
def test_resolves_exit_code_to_auth_when_cause_contains_auth_fragment(fragment: str) -> None:
    results: typing.Final = [
        CheckResult(name="token", status="failed", cause=f"prefix {fragment} suffix"),
    ]
    assert resolve_exit_code(results) == AuthError.exit_code


@pytest.mark.parametrize(
    "fragment",
    ["GitLab project not found", "GitLab version too old"],
)
def test_resolves_exit_code_to_config_when_cause_contains_config_fragment(fragment: str) -> None:
    results: typing.Final = [
        CheckResult(name="project_access", status="failed", cause=f"prefix {fragment} suffix"),
    ]
    assert resolve_exit_code(results) == ConfigError.exit_code


@pytest.mark.parametrize(
    "fragment",
    ["GitLab unreachable", "Unexpected GitLab response"],
)
def test_resolves_exit_code_to_provider_api_when_cause_contains_provider_api_fragment(
    fragment: str,
) -> None:
    results: typing.Final = [
        CheckResult(name="token", status="failed", cause=f"prefix {fragment} suffix"),
    ]
    assert resolve_exit_code(results) == ProviderAPIError.exit_code


def test_resolves_exit_code_to_generic_when_cause_matches_no_known_fragment() -> None:
    results: typing.Final = [
        CheckResult(name="token", status="failed", cause=_SAMPLE_GENERIC_CAUSE),
    ]
    assert resolve_exit_code(results) == SemvertagError.exit_code


def _failed(name: str, code: int) -> CheckResult:
    cause_by_code: typing.Final = {
        AuthError.exit_code: _SAMPLE_AUTH_CAUSE,
        ConfigError.exit_code: _SAMPLE_CONFIG_CAUSE,
        ProviderAPIError.exit_code: _SAMPLE_PROVIDER_API_CAUSE,
        SemvertagError.exit_code: _SAMPLE_GENERIC_CAUSE,
    }
    return CheckResult(name=name, status="failed", cause=cause_by_code[code])


@pytest.mark.parametrize(
    ("failed_codes", "expected"),
    [
        ((SemvertagError.exit_code,), SemvertagError.exit_code),
        ((ConfigError.exit_code,), ConfigError.exit_code),
        ((AuthError.exit_code,), AuthError.exit_code),
        ((ProviderAPIError.exit_code,), ProviderAPIError.exit_code),
        ((SemvertagError.exit_code, ConfigError.exit_code), ConfigError.exit_code),
        ((SemvertagError.exit_code, AuthError.exit_code), AuthError.exit_code),
        ((SemvertagError.exit_code, ProviderAPIError.exit_code), ProviderAPIError.exit_code),
        ((ConfigError.exit_code, AuthError.exit_code), AuthError.exit_code),
        ((ConfigError.exit_code, ProviderAPIError.exit_code), ProviderAPIError.exit_code),
        ((AuthError.exit_code, ProviderAPIError.exit_code), AuthError.exit_code),
        (
            (SemvertagError.exit_code, ConfigError.exit_code, AuthError.exit_code),
            AuthError.exit_code,
        ),
        (
            (SemvertagError.exit_code, ConfigError.exit_code, ProviderAPIError.exit_code),
            ProviderAPIError.exit_code,
        ),
        (
            (SemvertagError.exit_code, AuthError.exit_code, ProviderAPIError.exit_code),
            AuthError.exit_code,
        ),
        (
            (ConfigError.exit_code, AuthError.exit_code, ProviderAPIError.exit_code),
            AuthError.exit_code,
        ),
        (
            (
                SemvertagError.exit_code,
                ConfigError.exit_code,
                AuthError.exit_code,
                ProviderAPIError.exit_code,
            ),
            AuthError.exit_code,
        ),
    ],
)
def test_resolves_dominant_exit_code_when_multiple_checks_fail(
    failed_codes: tuple[int, ...],
    expected: int,
) -> None:
    results: typing.Final = [_failed(name=f"slot_{i}", code=code) for i, code in enumerate(failed_codes)]
    assert resolve_exit_code(results) == expected
