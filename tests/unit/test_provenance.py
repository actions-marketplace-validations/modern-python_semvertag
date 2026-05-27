import typing

import pydantic
import pytest

from semvertag._settings import Settings, apply_cli_overlay
from semvertag._types import ConfigSource


_NESTED_TOKEN: typing.Final = "tok-nested"
_FLAT_SEMVERTAG_TOKEN: typing.Final = "tok-flat"
_CI_JOB_TOKEN_VALUE: typing.Final = "tok-ci"
_GITLAB_TOKEN_VALUE: typing.Final = "tok-gitlab-native"
_CUSTOM_ENDPOINT: typing.Final = "https://gitlab.example.com"
_CLI_STRATEGY_FLAG: typing.Final = "--strategy"
_CLI_TOKEN_FLAG: typing.Final = "--token"
_CLI_TOKEN_VALUE: typing.Final = "tok-cli"
_EXPECTED_KEYS: typing.Final = (
    "strategy",
    "provider",
    "default_branch",
    "request_timeout",
    "gitlab.endpoint",
    "gitlab.token",
    "github.token",
    "branch_prefix.minor",
    "branch_prefix.patch",
    "branch_prefix.merge_mark_text",
    "conventional_commits.minor_types",
    "conventional_commits.patch_types",
)


@pytest.mark.usefixtures("clean_settings_env")
def test_provenance_records_default_when_no_env_set() -> None:
    settings: typing.Final = Settings()
    assert settings._provenance["strategy"] == ConfigSource(layer="default", detail="default")
    assert settings._provenance["provider"] == ConfigSource(layer="default", detail="default")
    assert settings._provenance["gitlab.endpoint"] == ConfigSource(layer="default", detail="default")
    assert settings._provenance["gitlab.token"] == ConfigSource(layer="default", detail="default")


@pytest.mark.usefixtures("clean_settings_env")
def test_provenance_records_env_var_name_when_native_token_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CI_JOB_TOKEN", _CI_JOB_TOKEN_VALUE)
    settings: typing.Final = Settings()
    assert settings._provenance["gitlab.token"] == ConfigSource(layer="env", detail="CI_JOB_TOKEN")


@pytest.mark.usefixtures("clean_settings_env")
def test_provenance_records_semvertag_token_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEMVERTAG_TOKEN", _FLAT_SEMVERTAG_TOKEN)
    monkeypatch.setenv("GITLAB_TOKEN", _GITLAB_TOKEN_VALUE)
    settings: typing.Final = Settings()
    assert settings._provenance["gitlab.token"] == ConfigSource(layer="env", detail="SEMVERTAG_TOKEN")


@pytest.mark.usefixtures("clean_settings_env")
def test_provenance_records_nested_form_when_double_underscore_var_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEMVERTAG_GITLAB__TOKEN", _NESTED_TOKEN)
    monkeypatch.setenv("SEMVERTAG_TOKEN", _FLAT_SEMVERTAG_TOKEN)
    settings: typing.Final = Settings()
    assert settings._provenance["gitlab.token"] == ConfigSource(layer="env", detail="SEMVERTAG_GITLAB__TOKEN")


@pytest.mark.usefixtures("clean_settings_env")
def test_provenance_records_endpoint_env_var_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEMVERTAG_GITLAB__ENDPOINT", _CUSTOM_ENDPOINT)
    settings: typing.Final = Settings()
    assert settings._provenance["gitlab.endpoint"] == ConfigSource(
        layer="env",
        detail="SEMVERTAG_GITLAB__ENDPOINT",
    )


@pytest.mark.usefixtures("clean_settings_env")
def test_cli_overlay_records_cli_layer_and_flag_detail() -> None:
    settings: typing.Final = Settings()
    overlaid: typing.Final = apply_cli_overlay(
        settings,
        {"strategy": ("conventional-commits", _CLI_STRATEGY_FLAG)},
    )
    assert overlaid.strategy == "conventional-commits"
    assert overlaid._provenance["strategy"] == ConfigSource(layer="cli", detail=_CLI_STRATEGY_FLAG)


@pytest.mark.usefixtures("clean_settings_env")
def test_cli_overlay_preserves_unrelated_provenance_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CI_JOB_TOKEN", _CI_JOB_TOKEN_VALUE)
    settings: typing.Final = Settings()
    pre_token_source: typing.Final = settings._provenance["gitlab.token"]
    overlaid: typing.Final = apply_cli_overlay(
        settings,
        {"strategy": ("conventional-commits", _CLI_STRATEGY_FLAG)},
    )
    assert overlaid._provenance["gitlab.token"] == pre_token_source
    assert overlaid._provenance["provider"] == settings._provenance["provider"]


@pytest.mark.usefixtures("clean_settings_env")
def test_cli_overlay_beats_env_for_overridden_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEMVERTAG_TOKEN", _FLAT_SEMVERTAG_TOKEN)
    settings: typing.Final = Settings()
    overlaid: typing.Final = apply_cli_overlay(
        settings,
        {"gitlab.token": (pydantic.SecretStr(_CLI_TOKEN_VALUE), _CLI_TOKEN_FLAG)},
    )
    assert overlaid.gitlab.token.get_secret_value() == _CLI_TOKEN_VALUE
    assert overlaid._provenance["gitlab.token"] == ConfigSource(layer="cli", detail=_CLI_TOKEN_FLAG)


@pytest.mark.usefixtures("clean_settings_env")
def test_every_documented_field_has_a_provenance_entry() -> None:
    settings: typing.Final = Settings()
    recorded: typing.Final = set(settings._provenance.keys())
    missing: typing.Final = set(_EXPECTED_KEYS) - recorded
    assert missing == set(), f"Missing provenance entries: {sorted(missing)}"
