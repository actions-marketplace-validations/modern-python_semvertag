import collections.abc
import json as json_module
import typing

import httpx2
import pytest
from typer.testing import CliRunner

from semvertag import ioc
from semvertag.__main__ import MAIN_APP
from tests.conftest import HandlerCallable
from tests.integration.conftest import (
    GITLAB_PROJECT_ID,
    GITLAB_TOKEN,
)


_PROJECT_PATH: typing.Final = f"/api/v4/projects/{GITLAB_PROJECT_ID}"
_USER_PATH: typing.Final = "/api/v4/user"
_TOKEN_INTROSPECTION_PATH: typing.Final = "/api/v4/personal_access_tokens/self"
_PROTECTED_TAGS_PATH: typing.Final = f"{_PROJECT_PATH}/protected_tags"
_TAGS_POST_PATH: typing.Final = f"{_PROJECT_PATH}/repository/tags"

_EXIT_SUCCESS: typing.Final = 0
_EXIT_CONFIG_ERROR: typing.Final = 2
_EXIT_AUTH_ERROR: typing.Final = 3
_EXIT_PROVIDER_API_ERROR: typing.Final = 4

_EXPECTED_CHECK_COUNT: typing.Final = 4
_EXPECTED_REDACTED_TOKEN: typing.Final = "***" + GITLAB_TOKEN[-4:]
_SCHEMA_VERSION: typing.Final = "1.0"
_CHECK_NAMES: typing.Final = ("token", "scopes", "project_access", "protected_tags")
_EXPECTED_TOKEN_PASS_CAUSE: typing.Final = "Token recognized by GitLab API."
_EXPECTED_SCOPES_FAIL_CAUSE: typing.Final = "Token missing 'api' scope. Add it to the SEMVERTAG_TOKEN scopes on GitLab."
_EXPECTED_CONFIG_KEYS: typing.Final = (
    "strategy",
    "project_id",
    "default_branch",
    "gitlab.endpoint",
    "gitlab.token",
)


def _doctor_handler(
    *,
    user_status: int = 200,
    scopes_status: int = 200,
    scopes_payload: dict[str, typing.Any] | None = None,
    project_status: int = 200,
    protected_tags_status: int = 200,
) -> HandlerCallable:
    resolved_scopes: typing.Final = scopes_payload if scopes_payload is not None else {"scopes": ["api"]}

    def handler(request: httpx2.Request) -> httpx2.Response:
        method: typing.Final = request.method
        path: typing.Final = request.url.path
        if method == "GET" and path == _USER_PATH:
            return httpx2.Response(user_status, json={"id": 1, "username": "ci-bot"})
        if method == "GET" and path == _TOKEN_INTROSPECTION_PATH:
            return httpx2.Response(scopes_status, json=resolved_scopes)
        if method == "GET" and path == _PROJECT_PATH:
            return httpx2.Response(project_status, json={"default_branch": "main"})
        if method == "GET" and path == _PROTECTED_TAGS_PATH:
            return httpx2.Response(protected_tags_status, json=[])
        return httpx2.Response(404, json={"message": "404 Not Found"})

    return handler


def _recording_wrapper(
    base: HandlerCallable,
    recorded: list[httpx2.Request],
) -> HandlerCallable:
    def wrapper(request: httpx2.Request) -> httpx2.Response:
        recorded.append(request)
        return base(request)

    return wrapper


def _assert_no_post_to_tags(recorded: list[httpx2.Request]) -> None:
    leaked: typing.Final = [r for r in recorded if r.method == "POST" and r.url.path == _TAGS_POST_PATH]
    assert leaked == [], f"unexpected POST to {_TAGS_POST_PATH}: {leaked!r}"


def _parse_json_envelope(stdout: str) -> dict[str, typing.Any]:
    lines: typing.Final = [line for line in stdout.splitlines() if line.strip()]
    assert len(lines) == 1, f"expected exactly one JSON line, got: {lines!r}"
    return json_module.loads(lines[0])


def test_emits_configuration_and_checks_sections_when_all_pass(
    cli_env: None,  # noqa: ARG001
    install_mock_transport: collections.abc.Callable[[HandlerCallable], None],
    cli_runner: CliRunner,
) -> None:
    recorded: list[httpx2.Request] = []
    install_mock_transport(_recording_wrapper(_doctor_handler(), recorded))

    result: typing.Final = cli_runner.invoke(MAIN_APP, ["doctor"])

    assert result.exit_code == _EXIT_SUCCESS, result.output + result.stderr
    assert "Configuration" in result.stdout
    assert "Checks" in result.stdout
    for name in _CHECK_NAMES:
        assert name in result.stdout, f"missing check name {name!r} in stdout"
    assert "gitlab.token" in result.stdout
    assert result.stderr == ""
    _assert_no_post_to_tags(recorded)


def test_emits_single_line_json_envelope_when_all_pass_and_json_flag(
    cli_env: None,  # noqa: ARG001
    install_mock_transport: collections.abc.Callable[[HandlerCallable], None],
    cli_runner: CliRunner,
) -> None:
    recorded: list[httpx2.Request] = []
    install_mock_transport(_recording_wrapper(_doctor_handler(), recorded))

    result: typing.Final = cli_runner.invoke(MAIN_APP, ["doctor", "--json"])

    assert result.exit_code == _EXIT_SUCCESS, result.output + result.stderr
    payload: typing.Final = _parse_json_envelope(result.stdout)
    assert next(iter(payload.keys())) == "schema_version"
    assert payload["schema_version"] == _SCHEMA_VERSION
    assert tuple(payload.keys())[:3] == ("schema_version", "configuration", "checks")
    assert len(payload["checks"]) == _EXPECTED_CHECK_COUNT
    assert [c["name"] for c in payload["checks"]] == list(_CHECK_NAMES)
    for check in payload["checks"]:
        assert check["status"] == "passed", f"expected passed for {check['name']}, got {check!r}"
    for key in _EXPECTED_CONFIG_KEYS:
        assert key in payload["configuration"], f"AC8: configuration missing key {key!r}"
    assert payload["configuration"]["gitlab.token"]["layer"] == "env"
    assert payload["configuration"]["gitlab.token"]["detail"] == "SEMVERTAG_TOKEN"
    assert payload["configuration"]["project_id"]["layer"] == "env"
    assert payload["configuration"]["project_id"]["detail"] == "SEMVERTAG_PROJECT_ID"
    assert payload["configuration"]["gitlab.endpoint"]["layer"] == "env"
    assert payload["configuration"]["strategy"]["layer"] == "default"
    assert payload["configuration"]["default_branch"]["layer"] == "default"
    assert result.stderr == ""
    _assert_no_post_to_tags(recorded)


def test_reports_token_failed_and_three_skipped_when_user_endpoint_returns_401(
    cli_env: None,  # noqa: ARG001
    install_mock_transport: collections.abc.Callable[[HandlerCallable], None],
    cli_runner: CliRunner,
) -> None:
    recorded: list[httpx2.Request] = []
    install_mock_transport(_recording_wrapper(_doctor_handler(user_status=401), recorded))

    result: typing.Final = cli_runner.invoke(MAIN_APP, ["doctor"])

    assert result.exit_code == _EXIT_AUTH_ERROR
    assert "token" in result.stdout
    assert "failed" in result.stdout
    assert "skipped" in result.stdout
    assert "Skipped: blocked by token check." in result.stdout
    _assert_no_post_to_tags(recorded)


def test_emits_json_envelope_with_token_failed_when_user_endpoint_returns_401_and_json_flag(
    cli_env: None,  # noqa: ARG001
    install_mock_transport: collections.abc.Callable[[HandlerCallable], None],
    cli_runner: CliRunner,
) -> None:
    recorded: list[httpx2.Request] = []
    install_mock_transport(_recording_wrapper(_doctor_handler(user_status=401), recorded))

    result: typing.Final = cli_runner.invoke(MAIN_APP, ["doctor", "--json"])

    assert result.exit_code == _EXIT_AUTH_ERROR
    payload: typing.Final = _parse_json_envelope(result.stdout)
    assert payload["checks"][0]["name"] == "token"
    assert payload["checks"][0]["status"] == "failed"
    assert "Token rejected" in payload["checks"][0]["cause"]
    for skipped in payload["checks"][1:]:
        assert skipped["status"] == "skipped"
        assert skipped["cause"] == "Skipped: blocked by token check."
    _assert_no_post_to_tags(recorded)


def test_reports_scopes_failed_when_introspection_payload_lacks_api_scope(
    cli_env: None,  # noqa: ARG001
    install_mock_transport: collections.abc.Callable[[HandlerCallable], None],
    cli_runner: CliRunner,
) -> None:
    recorded: list[httpx2.Request] = []
    install_mock_transport(
        _recording_wrapper(
            _doctor_handler(scopes_payload={"scopes": ["read_repository"]}),
            recorded,
        ),
    )

    result: typing.Final = cli_runner.invoke(MAIN_APP, ["doctor", "--json"])

    assert result.exit_code == _EXIT_AUTH_ERROR
    payload: typing.Final = _parse_json_envelope(result.stdout)
    assert payload["checks"][0]["status"] == "passed"
    assert payload["checks"][0]["cause"] == _EXPECTED_TOKEN_PASS_CAUSE
    assert payload["checks"][1]["name"] == "scopes"
    assert payload["checks"][1]["status"] == "failed"
    assert payload["checks"][1]["cause"] == _EXPECTED_SCOPES_FAIL_CAUSE
    assert payload["checks"][2]["status"] == "skipped"
    assert payload["checks"][2]["cause"] == "Skipped: blocked by scopes check."
    assert payload["checks"][3]["status"] == "skipped"
    assert payload["checks"][3]["cause"] == "Skipped: blocked by scopes check."
    _assert_no_post_to_tags(recorded)


def test_reports_project_access_failed_when_projects_endpoint_returns_404(
    cli_env: None,  # noqa: ARG001
    install_mock_transport: collections.abc.Callable[[HandlerCallable], None],
    cli_runner: CliRunner,
) -> None:
    recorded: list[httpx2.Request] = []
    install_mock_transport(_recording_wrapper(_doctor_handler(project_status=404), recorded))

    result: typing.Final = cli_runner.invoke(MAIN_APP, ["doctor", "--json"])

    assert result.exit_code == _EXIT_CONFIG_ERROR
    payload: typing.Final = _parse_json_envelope(result.stdout)
    assert payload["checks"][0]["status"] == "passed"
    assert payload["checks"][1]["status"] == "passed"
    assert payload["checks"][2]["name"] == "project_access"
    assert payload["checks"][2]["status"] == "failed"
    assert "GitLab project not found" in payload["checks"][2]["cause"]
    assert payload["checks"][3]["status"] == "skipped"
    assert payload["checks"][3]["cause"] == "Skipped: blocked by project_access check."
    _assert_no_post_to_tags(recorded)


def test_reports_protected_tags_failed_when_protected_tags_endpoint_returns_401(
    cli_env: None,  # noqa: ARG001
    install_mock_transport: collections.abc.Callable[[HandlerCallable], None],
    cli_runner: CliRunner,
) -> None:
    recorded: list[httpx2.Request] = []
    install_mock_transport(_recording_wrapper(_doctor_handler(protected_tags_status=401), recorded))

    result: typing.Final = cli_runner.invoke(MAIN_APP, ["doctor", "--json"])

    assert result.exit_code == _EXIT_AUTH_ERROR
    payload: typing.Final = _parse_json_envelope(result.stdout)
    assert payload["checks"][0]["status"] == "passed"
    assert payload["checks"][1]["status"] == "passed"
    assert payload["checks"][2]["status"] == "passed"
    assert payload["checks"][3]["name"] == "protected_tags"
    assert payload["checks"][3]["status"] == "failed"
    assert "Token cannot read protected_tags" in payload["checks"][3]["cause"]
    _assert_no_post_to_tags(recorded)


def test_redacts_token_to_last_four_in_both_human_and_json_output(
    cli_env: None,  # noqa: ARG001
    install_mock_transport: collections.abc.Callable[[HandlerCallable], None],
    cli_runner: CliRunner,
) -> None:
    human_recorded: list[httpx2.Request] = []
    install_mock_transport(_recording_wrapper(_doctor_handler(), human_recorded))
    human_result: typing.Final = cli_runner.invoke(MAIN_APP, ["doctor"])
    json_recorded: list[httpx2.Request] = []
    install_mock_transport(_recording_wrapper(_doctor_handler(), json_recorded))
    json_result: typing.Final = cli_runner.invoke(MAIN_APP, ["doctor", "--json"])

    assert GITLAB_TOKEN not in human_result.stdout, "raw token leaked to human stdout"
    assert GITLAB_TOKEN not in human_result.stderr, "raw token leaked to stderr"
    assert _EXPECTED_REDACTED_TOKEN in human_result.stdout

    payload: typing.Final = _parse_json_envelope(json_result.stdout)
    payload_str: typing.Final = json_module.dumps(payload)
    assert GITLAB_TOKEN not in payload_str, "raw token leaked to JSON envelope"
    assert payload["configuration"]["gitlab.token"]["value"] == _EXPECTED_REDACTED_TOKEN
    assert payload["configuration"]["gitlab.token"]["layer"] == "env"
    assert payload["configuration"]["gitlab.token"]["detail"] == "SEMVERTAG_TOKEN"
    _assert_no_post_to_tags(human_recorded)
    _assert_no_post_to_tags(json_recorded)


def test_exits_zero_and_shows_help_listing_four_checks_when_help_flag_set(
    install_mock_transport: collections.abc.Callable[[HandlerCallable], None],
    cli_runner: CliRunner,
) -> None:
    recorded: list[httpx2.Request] = []
    install_mock_transport(_recording_wrapper(_doctor_handler(), recorded))
    result: typing.Final = cli_runner.invoke(MAIN_APP, ["doctor", "--help"])

    assert result.exit_code == _EXIT_SUCCESS
    for name in _CHECK_NAMES:
        assert name in result.output, f"--help missing check name {name!r}"
    assert "--json" in result.output
    _assert_no_post_to_tags(recorded)


def test_exits_with_config_error_when_project_id_missing_under_doctor(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner: CliRunner,
    install_mock_transport: collections.abc.Callable[[HandlerCallable], None],
) -> None:
    monkeypatch.setenv("SEMVERTAG_TOKEN", GITLAB_TOKEN)
    recorded: list[httpx2.Request] = []
    install_mock_transport(_recording_wrapper(_doctor_handler(), recorded))

    result: typing.Final = cli_runner.invoke(MAIN_APP, ["doctor"])

    assert result.exit_code == _EXIT_CONFIG_ERROR
    assert "Project id missing" in result.stderr
    _assert_no_post_to_tags(recorded)


def test_emits_json_envelope_with_passed_checks_when_overlay_sets_token_via_flag(
    install_mock_transport: collections.abc.Callable[[HandlerCallable], None],
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEMVERTAG_PROJECT_ID", str(GITLAB_PROJECT_ID))
    monkeypatch.setenv("SEMVERTAG_GITLAB__ENDPOINT", "https://gitlab.example.test")
    recorded: list[httpx2.Request] = []
    install_mock_transport(_recording_wrapper(_doctor_handler(), recorded))

    result: typing.Final = cli_runner.invoke(
        MAIN_APP,
        ["doctor", "--token", GITLAB_TOKEN, "--json"],
    )

    assert result.exit_code == _EXIT_SUCCESS, result.output + result.stderr
    payload: typing.Final = _parse_json_envelope(result.stdout)
    assert payload["configuration"]["gitlab.token"]["layer"] == "cli"
    assert payload["configuration"]["gitlab.token"]["detail"] == "--token"
    assert payload["configuration"]["gitlab.token"]["value"] == _EXPECTED_REDACTED_TOKEN
    _assert_no_post_to_tags(recorded)


def test_exits_with_provider_api_error_when_user_endpoint_returns_500(
    cli_env: None,  # noqa: ARG001
    install_mock_transport: collections.abc.Callable[[HandlerCallable], None],
    cli_runner: CliRunner,
    monkeypatch: typing.Any,  # noqa: ANN401
) -> None:
    from semvertag import _transport  # noqa: PLC0415

    monkeypatch.setattr(_transport.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(_transport.random, "uniform", lambda *_a, **_k: 0.0)
    recorded: list[httpx2.Request] = []
    install_mock_transport(_recording_wrapper(_doctor_handler(user_status=500), recorded))

    result: typing.Final = cli_runner.invoke(MAIN_APP, ["doctor", "--json"])

    assert result.exit_code == _EXIT_PROVIDER_API_ERROR
    payload: typing.Final = _parse_json_envelope(result.stdout)
    assert payload["checks"][0]["status"] == "failed"
    assert "Unexpected GitLab response" in payload["checks"][0]["cause"]
    _assert_no_post_to_tags(recorded)


def test_redacts_token_in_stderr_when_doctor_emits_error_with_token_in_message(
    cli_env: None,  # noqa: ARG001
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # AC11: stderr redaction on the doctor path. Forces an ImportError whose
    # message embeds a glpat token-pattern and verifies output.error -> redact
    # strips it before stderr emission. install_mock_transport is intentionally
    # NOT used — it re-patches ioc.build_container and would clobber the forced
    # ImportError; we want the error path, not the network path.
    leaked: typing.Final = "glpat-XXXXXXXXXXXXXXXXXXXX"

    def _raise_with_token(*_a: object, **_k: object) -> typing.NoReturn:
        msg: typing.Final = f"forced failure embedding {leaked} in message"
        raise ImportError(msg)

    monkeypatch.setattr(ioc, "build_container", _raise_with_token)

    result: typing.Final = cli_runner.invoke(MAIN_APP, ["doctor"])

    assert result.exit_code == _EXIT_CONFIG_ERROR
    assert leaked not in result.stderr, f"raw token leaked to stderr: {result.stderr!r}"
    assert "Required module unavailable" in result.stderr
