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
    "project_id",
    "quiet",
    "gitlab.endpoint",
    "gitlab.token",
    "github.token",
    "branch_prefix.minor",
    "branch_prefix.patch",
    "branch_prefix.merge_mark_text",
    "conventional_commits.minor_types",
    "conventional_commits.patch_types",
)
_PROJECT_ID_SEMVERTAG: typing.Final = "999"
_PROJECT_ID_CI: typing.Final = "777"
_CLI_PROJECT_ID_FLAG: typing.Final = "--project-id"
_CLI_DEFAULT_BRANCH_FLAG: typing.Final = "--default-branch"
_CLI_QUIET_FLAG: typing.Final = "--quiet"


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


@pytest.mark.usefixtures("clean_settings_env")
def test_provenance_records_semvertag_project_id_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEMVERTAG_PROJECT_ID", _PROJECT_ID_SEMVERTAG)
    settings: typing.Final = Settings()
    assert settings._provenance["project_id"] == ConfigSource(layer="env", detail="SEMVERTAG_PROJECT_ID")


@pytest.mark.usefixtures("clean_settings_env")
def test_provenance_records_ci_project_id_when_only_native_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CI_PROJECT_ID", _PROJECT_ID_CI)
    settings: typing.Final = Settings()
    assert settings._provenance["project_id"] == ConfigSource(layer="env", detail="CI_PROJECT_ID")


@pytest.mark.usefixtures("clean_settings_env")
def test_provenance_records_default_for_project_id_when_unset() -> None:
    settings: typing.Final = Settings()
    assert settings._provenance["project_id"] == ConfigSource(layer="default", detail="default")


@pytest.mark.usefixtures("clean_settings_env")
def test_cli_overlay_records_provenance_for_project_id() -> None:
    settings: typing.Final = Settings()
    overlaid: typing.Final = apply_cli_overlay(
        settings,
        {"project_id": (42, _CLI_PROJECT_ID_FLAG)},
    )
    assert overlaid.project_id == 42  # noqa: PLR2004
    assert overlaid._provenance["project_id"] == ConfigSource(layer="cli", detail=_CLI_PROJECT_ID_FLAG)


@pytest.mark.usefixtures("clean_settings_env")
def test_cli_overlay_records_provenance_for_default_branch() -> None:
    settings: typing.Final = Settings()
    overlaid: typing.Final = apply_cli_overlay(
        settings,
        {"default_branch": ("develop", _CLI_DEFAULT_BRANCH_FLAG)},
    )
    assert overlaid.default_branch == "develop"
    assert overlaid._provenance["default_branch"] == ConfigSource(layer="cli", detail=_CLI_DEFAULT_BRANCH_FLAG)


@pytest.mark.usefixtures("clean_settings_env")
def test_cli_overlay_records_provenance_for_quiet() -> None:
    settings: typing.Final = Settings()
    overlaid: typing.Final = apply_cli_overlay(
        settings,
        {"quiet": (True, _CLI_QUIET_FLAG)},
    )
    assert overlaid.quiet is True
    assert overlaid._provenance["quiet"] == ConfigSource(layer="cli", detail=_CLI_QUIET_FLAG)


@pytest.mark.usefixtures("clean_settings_env")
def test_cli_overlay_strategy_wins_over_conflicting_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEMVERTAG_STRATEGY", "branch-prefix")
    settings: typing.Final = Settings()
    assert settings.strategy == "branch-prefix"
    overlaid: typing.Final = apply_cli_overlay(
        settings,
        {"strategy": ("conventional-commits", _CLI_STRATEGY_FLAG)},
    )
    assert overlaid.strategy == "conventional-commits"
    assert overlaid._provenance["strategy"] == ConfigSource(layer="cli", detail=_CLI_STRATEGY_FLAG)


@pytest.mark.usefixtures("clean_settings_env")
def test_cli_overlay_provider_wins_over_conflicting_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEMVERTAG_PROVIDER", "gitlab")
    settings: typing.Final = Settings()
    assert settings.provider == "gitlab"
    overlaid: typing.Final = apply_cli_overlay(
        settings,
        {"provider": ("github", "--provider")},
    )
    assert overlaid.provider == "github"
    assert overlaid._provenance["provider"] == ConfigSource(layer="cli", detail="--provider")


@pytest.mark.usefixtures("clean_settings_env")
def test_env_quiet_survives_when_cli_flag_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEMVERTAG_QUIET", "true")
    settings: typing.Final = Settings()
    assert settings.quiet is True
    overlaid: typing.Final = apply_cli_overlay(settings, {})
    assert overlaid.quiet is True
    assert overlaid._provenance["quiet"].layer == "env"
