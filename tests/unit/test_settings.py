import typing

import pydantic
import pytest

from semvertag._settings import GitLabConfig, Settings


_NESTED_TOKEN: typing.Final = "tok-nested"
_FLAT_SEMVERTAG_TOKEN: typing.Final = "tok-flat"
_CI_JOB_TOKEN_VALUE: typing.Final = "tok-ci"
_GITLAB_TOKEN_VALUE: typing.Final = "tok-gitlab-native"
_CUSTOM_ENDPOINT: typing.Final = "https://gitlab.example.com"
_TIMEOUT_OVER_CEILING: typing.Final = "99"
_TIMEOUT_UNDER_CEILING: typing.Final = "5.5"
_TIMEOUT_CEILING_VALUE: typing.Final = 10.0
_TIMEOUT_UNDER_VALUE: typing.Final = 5.5
_TIMEOUT_DEFAULT_VALUE: typing.Final = 8.0
_PLAINTEXT_SECRET: typing.Final = "plaintext-secret-marker"


@pytest.mark.usefixtures("clean_settings_env")
def test_uses_defaults_when_no_env_set() -> None:
    settings: typing.Final = Settings()
    assert settings.provider == "gitlab"
    assert settings.strategy == "branch-prefix"
    assert settings.default_branch is None
    assert settings.request_timeout == _TIMEOUT_DEFAULT_VALUE
    assert settings.gitlab.endpoint == "https://gitlab.com"
    assert settings.gitlab.token.get_secret_value() == ""
    assert settings.github.token.get_secret_value() == ""


@pytest.mark.usefixtures("clean_settings_env")
def test_resolves_token_from_ci_job_token_when_only_native_var_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CI_JOB_TOKEN", _CI_JOB_TOKEN_VALUE)
    settings: typing.Final = Settings()
    assert settings.gitlab.token.get_secret_value() == _CI_JOB_TOKEN_VALUE


@pytest.mark.usefixtures("clean_settings_env")
def test_prefers_semvertag_token_over_provider_native(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEMVERTAG_TOKEN", _FLAT_SEMVERTAG_TOKEN)
    monkeypatch.setenv("GITLAB_TOKEN", _GITLAB_TOKEN_VALUE)
    monkeypatch.setenv("CI_JOB_TOKEN", _CI_JOB_TOKEN_VALUE)
    settings: typing.Final = Settings()
    assert settings.gitlab.token.get_secret_value() == _FLAT_SEMVERTAG_TOKEN


@pytest.mark.usefixtures("clean_settings_env")
def test_prefers_nested_prefix_over_flat_semvertag_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEMVERTAG_GITLAB__TOKEN", _NESTED_TOKEN)
    monkeypatch.setenv("SEMVERTAG_TOKEN", _FLAT_SEMVERTAG_TOKEN)
    monkeypatch.setenv("CI_JOB_TOKEN", _CI_JOB_TOKEN_VALUE)
    settings: typing.Final = Settings()
    assert settings.gitlab.token.get_secret_value() == _NESTED_TOKEN


@pytest.mark.usefixtures("clean_settings_env")
def test_reads_nested_env_var_for_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEMVERTAG_GITLAB__ENDPOINT", _CUSTOM_ENDPOINT)
    settings: typing.Final = Settings()
    assert settings.gitlab.endpoint == _CUSTOM_ENDPOINT


@pytest.mark.usefixtures("clean_settings_env")
def test_secret_str_is_redacted_in_repr() -> None:
    gitlab: typing.Final = GitLabConfig(token=pydantic.SecretStr(_PLAINTEXT_SECRET))
    settings: typing.Final = Settings(gitlab=gitlab)
    assert _PLAINTEXT_SECRET not in repr(settings)
    assert _PLAINTEXT_SECRET not in repr(settings.gitlab)
    assert _PLAINTEXT_SECRET not in repr(settings.gitlab.token)
    assert _PLAINTEXT_SECRET not in str(settings.gitlab.token)
    assert "**********" in repr(settings.gitlab.token)


@pytest.mark.usefixtures("clean_settings_env")
def test_request_timeout_clamps_to_ten(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEMVERTAG_REQUEST_TIMEOUT", _TIMEOUT_OVER_CEILING)
    settings: typing.Final = Settings()
    assert settings.request_timeout == _TIMEOUT_CEILING_VALUE


@pytest.mark.usefixtures("clean_settings_env")
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (_TIMEOUT_UNDER_CEILING, _TIMEOUT_UNDER_VALUE),
        ("10.0", _TIMEOUT_CEILING_VALUE),
    ],
)
def test_request_timeout_passes_through_when_below_ten(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
    expected: float,
) -> None:
    monkeypatch.setenv("SEMVERTAG_REQUEST_TIMEOUT", raw)
    settings: typing.Final = Settings()
    assert settings.request_timeout == expected


@pytest.mark.usefixtures("clean_settings_env")
def test_request_timeout_rejects_non_positive_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEMVERTAG_REQUEST_TIMEOUT", "0")
    with pytest.raises(pydantic.ValidationError):
        Settings()
