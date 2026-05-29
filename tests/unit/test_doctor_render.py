import dataclasses
import io
import json as json_module
import typing

import pydantic
import pytest
import rich.console

from semvertag._output import RichOutput
from semvertag._settings import Settings, apply_cli_overlay
from semvertag._types import CheckResult
from semvertag.doctor._render import (
    ConfigSourceView,
    DoctorResult,
    build_doctor_result,
    render_doctor_human,
    render_doctor_json,
)


_DISTINGUISHABLE_TOKEN: typing.Final = "glpat-1234567890abcdefghPQRS"
_DISTINGUISHABLE_LAST_4: typing.Final = "PQRS"
_SHORT_TOKEN: typing.Final = "abc"
_REDACTED_EMPTY: typing.Final = "***"
_REDACTED_DISTINGUISHABLE: typing.Final = "***" + _DISTINGUISHABLE_LAST_4
_REDACTED_SHORT: typing.Final = "***"
_DEFAULT_BRANCH_MAIN: typing.Final = "main"
_PROJECT_ID_AS_STR: typing.Final = "999"
_REQUEST_TIMEOUT_AS_STR: typing.Final = "8.0"
_SCHEMA_VERSION: typing.Final = "1.0"
_EXPECTED_DOCTOR_RESULT_FIELDS: typing.Final = ("schema_version", "configuration", "checks")
_EXPECTED_CONFIG_SOURCE_VIEW_FIELDS: typing.Final = ("value", "layer", "detail")
_RENDER_FIXTURE_CHECK_COUNT: typing.Final = 2


@pytest.mark.usefixtures("clean_settings_env")
def test_doctor_result_field_order_is_schema_version_configuration_checks() -> None:
    field_names: typing.Final = tuple(f.name for f in dataclasses.fields(DoctorResult))
    assert field_names == _EXPECTED_DOCTOR_RESULT_FIELDS


@pytest.mark.usefixtures("clean_settings_env")
def test_config_source_view_field_order_is_value_layer_detail() -> None:
    field_names: typing.Final = tuple(f.name for f in dataclasses.fields(ConfigSourceView))
    assert field_names == _EXPECTED_CONFIG_SOURCE_VIEW_FIELDS


@pytest.mark.usefixtures("clean_settings_env")
def test_redacts_glpat_secret_str_to_last_four_when_token_is_long(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEMVERTAG_TOKEN", _DISTINGUISHABLE_TOKEN)
    settings: typing.Final = Settings()
    result: typing.Final = build_doctor_result(settings, checks=[])
    assert result.configuration["gitlab.token"].value == _REDACTED_DISTINGUISHABLE


@pytest.mark.usefixtures("clean_settings_env")
def test_redacts_empty_secret_str_to_triple_star_only() -> None:
    settings: typing.Final = Settings()
    assert settings.gitlab.token.get_secret_value() == ""
    result: typing.Final = build_doctor_result(settings, checks=[])
    assert result.configuration["gitlab.token"].value == _REDACTED_EMPTY


@pytest.mark.usefixtures("clean_settings_env")
def test_redacts_short_secret_to_triple_star_only_when_below_four_chars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEMVERTAG_TOKEN", _SHORT_TOKEN)
    settings: typing.Final = Settings()
    result: typing.Final = build_doctor_result(settings, checks=[])
    assert result.configuration["gitlab.token"].value == _REDACTED_SHORT


@pytest.mark.usefixtures("clean_settings_env")
def test_renders_string_default_branch_via_str_when_env_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEMVERTAG_DEFAULT_BRANCH", _DEFAULT_BRANCH_MAIN)
    settings: typing.Final = Settings()
    result: typing.Final = build_doctor_result(settings, checks=[])
    assert result.configuration["default_branch"].value == _DEFAULT_BRANCH_MAIN


@pytest.mark.usefixtures("clean_settings_env")
def test_renders_int_project_id_via_str_when_env_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEMVERTAG_PROJECT_ID", _PROJECT_ID_AS_STR)
    settings: typing.Final = Settings()
    result: typing.Final = build_doctor_result(settings, checks=[])
    assert result.configuration["project_id"].value == _PROJECT_ID_AS_STR


@pytest.mark.usefixtures("clean_settings_env")
def test_renders_float_request_timeout_via_str_with_default_value() -> None:
    settings: typing.Final = Settings()
    result: typing.Final = build_doctor_result(settings, checks=[])
    assert result.configuration["request_timeout"].value == _REQUEST_TIMEOUT_AS_STR


@pytest.mark.usefixtures("clean_settings_env")
def test_renders_bool_quiet_via_str_with_default_false() -> None:
    settings: typing.Final = Settings()
    result: typing.Final = build_doctor_result(settings, checks=[])
    assert result.configuration["quiet"].value == "False"


@pytest.mark.usefixtures("clean_settings_env")
def test_doctor_result_default_schema_version_is_one_zero() -> None:
    settings: typing.Final = Settings()
    result: typing.Final = build_doctor_result(settings, checks=[])
    assert result.schema_version == _SCHEMA_VERSION


@pytest.mark.usefixtures("clean_settings_env")
def test_asdict_first_top_level_key_is_schema_version() -> None:
    settings: typing.Final = Settings()
    result: typing.Final = build_doctor_result(settings, checks=[])
    payload: typing.Final = dataclasses.asdict(result)
    assert next(iter(payload.keys())) == "schema_version"
    assert payload["schema_version"] == _SCHEMA_VERSION
    assert tuple(payload.keys())[:3] == _EXPECTED_DOCTOR_RESULT_FIELDS


@pytest.mark.usefixtures("clean_settings_env")
def test_asdict_nested_config_source_view_field_order_matches_declaration() -> None:
    settings: typing.Final = Settings()
    result: typing.Final = build_doctor_result(settings, checks=[])
    payload: typing.Final = dataclasses.asdict(result)
    first_field_key: typing.Final = next(iter(result.configuration.keys()))
    nested: typing.Final = payload["configuration"][first_field_key]
    assert tuple(nested.keys()) == _EXPECTED_CONFIG_SOURCE_VIEW_FIELDS


@pytest.mark.usefixtures("clean_settings_env")
def test_records_env_layer_and_detail_when_token_resolved_from_semvertag_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEMVERTAG_TOKEN", _DISTINGUISHABLE_TOKEN)
    settings: typing.Final = Settings()
    result: typing.Final = build_doctor_result(settings, checks=[])
    assert result.configuration["gitlab.token"].layer == "env"
    assert result.configuration["gitlab.token"].detail == "SEMVERTAG_TOKEN"


@pytest.mark.usefixtures("clean_settings_env")
def test_records_default_layer_and_detail_when_no_env_set() -> None:
    settings: typing.Final = Settings()
    result: typing.Final = build_doctor_result(settings, checks=[])
    assert result.configuration["strategy"].layer == "default"
    assert result.configuration["strategy"].detail == "default"


@pytest.mark.usefixtures("clean_settings_env")
def test_records_cli_layer_when_apply_cli_overlay_overrides_strategy() -> None:
    base_settings: typing.Final = Settings()
    overridden: typing.Final = apply_cli_overlay(
        base_settings,
        {"strategy": ("conventional-commits", "--strategy")},
    )
    result: typing.Final = build_doctor_result(overridden, checks=[])
    assert result.configuration["strategy"].value == "conventional-commits"
    assert result.configuration["strategy"].layer == "cli"
    assert result.configuration["strategy"].detail == "--strategy"


@pytest.mark.usefixtures("clean_settings_env")
def test_records_cli_layer_for_nested_token_when_overlay_sets_gitlab_token() -> None:
    base_settings: typing.Final = Settings()
    overridden: typing.Final = apply_cli_overlay(
        base_settings,
        {"gitlab.token": (pydantic.SecretStr(_DISTINGUISHABLE_TOKEN), "--token")},
    )
    result: typing.Final = build_doctor_result(overridden, checks=[])
    assert result.configuration["gitlab.token"].value == _REDACTED_DISTINGUISHABLE
    assert result.configuration["gitlab.token"].layer == "cli"
    assert result.configuration["gitlab.token"].detail == "--token"


@pytest.mark.usefixtures("clean_settings_env")
def test_includes_every_provenance_key_in_configuration_dict() -> None:
    settings: typing.Final = Settings()
    result: typing.Final = build_doctor_result(settings, checks=[])
    assert set(result.configuration.keys()) == set(settings._provenance.keys())


@pytest.mark.usefixtures("clean_settings_env")
def test_passes_check_results_through_to_doctor_result_verbatim() -> None:
    settings: typing.Final = Settings()
    sample_checks: typing.Final = [
        CheckResult(name="token", status="passed", cause="Token recognized by GitLab API."),
        CheckResult(name="scopes", status="passed", cause="Token carries 'api' scope."),
    ]
    result: typing.Final = build_doctor_result(settings, checks=sample_checks)
    assert result.checks == sample_checks


def _make_doctor_result_for_render() -> DoctorResult:
    configuration: typing.Final = {
        "strategy": ConfigSourceView(value="branch-prefix", layer="default", detail="default"),
        "gitlab.token": ConfigSourceView(value="***PQRS", layer="env", detail="SEMVERTAG_TOKEN"),
    }
    checks: typing.Final = [
        CheckResult(name="token", status="passed", cause="Token recognized by GitLab API."),
        CheckResult(name="scopes", status="failed", cause="Token missing 'api' scope. Add it."),
    ]
    return DoctorResult(configuration=configuration, checks=checks)


def _capture_rich_output() -> tuple[RichOutput, io.StringIO]:
    buffer: typing.Final = io.StringIO()
    info_console: typing.Final = rich.console.Console(file=buffer, width=200, force_terminal=False)
    error_console: typing.Final = rich.console.Console(file=io.StringIO(), stderr=True)
    return RichOutput(info_console=info_console, error_console=error_console), buffer


def test_render_doctor_human_writes_configuration_and_checks_sections_to_info_console() -> None:
    doctor_result: typing.Final = _make_doctor_result_for_render()
    output, buffer = _capture_rich_output()
    render_doctor_human(doctor_result, output)
    rendered: typing.Final = buffer.getvalue()
    assert "Configuration" in rendered
    assert "Checks" in rendered
    assert "strategy" in rendered
    assert "gitlab.token" in rendered
    assert "***PQRS" in rendered
    assert "token" in rendered
    assert "scopes" in rendered
    assert "passed" in rendered
    assert "failed" in rendered


def test_render_doctor_human_renders_every_configuration_row() -> None:
    configuration: typing.Final = {
        f"field_{i}": ConfigSourceView(value=f"value_{i}", layer="default", detail="default") for i in range(5)
    }
    doctor_result: typing.Final = DoctorResult(configuration=configuration, checks=[])
    output, buffer = _capture_rich_output()
    render_doctor_human(doctor_result, output)
    rendered: typing.Final = buffer.getvalue()
    for i in range(5):
        assert f"field_{i}" in rendered
        assert f"value_{i}" in rendered


def test_render_doctor_human_renders_every_check_row_with_redacted_cause() -> None:
    configuration: typing.Final[dict[str, ConfigSourceView]] = {}
    checks: typing.Final = [
        CheckResult(name=name, status="passed", cause=f"Cause for {name}.")
        for name in ("token", "scopes", "project_access", "protected_tags")
    ]
    doctor_result: typing.Final = DoctorResult(configuration=configuration, checks=checks)
    output, buffer = _capture_rich_output()
    render_doctor_human(doctor_result, output)
    rendered: typing.Final = buffer.getvalue()
    for name in ("token", "scopes", "project_access", "protected_tags"):
        assert name in rendered
        assert f"Cause for {name}." in rendered


def test_render_doctor_json_writes_single_line_envelope_to_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    doctor_result: typing.Final = _make_doctor_result_for_render()
    render_doctor_json(doctor_result)
    captured: typing.Final = capsys.readouterr()
    lines: typing.Final = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 1
    payload: typing.Final = json_module.loads(lines[0])
    assert next(iter(payload.keys())) == "schema_version"
    assert payload["schema_version"] == _SCHEMA_VERSION
    assert payload["configuration"]["gitlab.token"]["value"] == "***PQRS"
    assert len(payload["checks"]) == _RENDER_FIXTURE_CHECK_COUNT
    assert payload["checks"][0]["name"] == "token"
    assert payload["checks"][1]["status"] == "failed"
    assert captured.err == ""


def test_render_doctor_json_uses_compact_separators_with_no_whitespace(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Use a fixture whose strings legitimately contain `": "` and `", "` (e.g.,
    # cause text like `"Unexpected GitLab response: 500."`). The compact
    # separators contract is about the encoder's structural separators between
    # keys and values — not about absence of those substrings inside string
    # values. Verify by re-encoding the parsed payload with the compact
    # separators and asserting byte-identity.
    configuration: typing.Final = {
        "strategy": ConfigSourceView(value="branch-prefix", layer="default", detail="default"),
    }
    checks: typing.Final = [
        CheckResult(name="token", status="failed", cause="Unexpected GitLab response: 500. Retried 3 times."),
    ]
    doctor_result: typing.Final = DoctorResult(configuration=configuration, checks=checks)
    render_doctor_json(doctor_result)
    captured: typing.Final = capsys.readouterr()
    line: typing.Final = captured.out.rstrip("\n")
    payload: typing.Final = json_module.loads(line)
    expected: typing.Final = json_module.dumps(payload, separators=(",", ":"))
    assert line == expected
    assert '","' in line
    assert '":' in line
