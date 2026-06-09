import io
import typing

import pytest
import rich.console

from semvertag._output import JsonOutput, RichOutput, build_json_output, build_rich_output
from semvertag._types import RunResult


_GITLAB_TOKEN: typing.Final = "glpat-AbCdEf1234567890ABCD"
_REDACTED: typing.Final = "***"
_PROGRESS_MESSAGE: typing.Final = "Detected strategy: branch-prefix"
_ERROR_MESSAGE: typing.Final = "ConfigError: bad config"
_EXAMPLE_RESULT: typing.Final = RunResult(
    strategy="branch-prefix",
    bump="minor",
    status="created",
    tag="1.2.0",
    commit="a2b4d12abc1234567890",
    reason=None,
)


def _make_pair(*, quiet: bool = False) -> tuple[RichOutput, io.StringIO, io.StringIO]:
    stdout_buf: typing.Final = io.StringIO()
    stderr_buf: typing.Final = io.StringIO()
    info_console: typing.Final = rich.console.Console(file=stdout_buf, force_terminal=False, color_system=None)
    error_console: typing.Final = rich.console.Console(file=stderr_buf, force_terminal=False, color_system=None)
    output: typing.Final = RichOutput(info_console=info_console, error_console=error_console, quiet=quiet)
    return output, stdout_buf, stderr_buf


def test_progress_writes_to_stdout_when_not_quiet() -> None:
    output, stdout_buf, stderr_buf = _make_pair()
    output.progress(_PROGRESS_MESSAGE)
    assert _PROGRESS_MESSAGE in stdout_buf.getvalue()
    assert stderr_buf.getvalue() == ""


def test_progress_is_no_op_when_quiet() -> None:
    output, stdout_buf, stderr_buf = _make_pair(quiet=True)
    output.progress(_PROGRESS_MESSAGE)
    assert stdout_buf.getvalue() == ""
    assert stderr_buf.getvalue() == ""


def test_emit_renders_result_to_stdout() -> None:
    output, stdout_buf, stderr_buf = _make_pair()
    output.emit(_EXAMPLE_RESULT)
    stdout_text: typing.Final = stdout_buf.getvalue()
    assert "1.2.0" in stdout_text
    assert "a2b4d12" in stdout_text
    assert stderr_buf.getvalue() == ""


def test_emit_renders_when_quiet() -> None:
    output, stdout_buf, _stderr = _make_pair(quiet=True)
    output.emit(_EXAMPLE_RESULT)
    assert "1.2.0" in stdout_buf.getvalue()


def test_error_writes_to_stderr_when_not_quiet() -> None:
    output, stdout_buf, stderr_buf = _make_pair()
    output.error(_ERROR_MESSAGE)
    assert _ERROR_MESSAGE in stderr_buf.getvalue()
    assert stdout_buf.getvalue() == ""


def test_error_writes_to_stderr_when_quiet() -> None:
    output, _stdout, stderr_buf = _make_pair(quiet=True)
    output.error(_ERROR_MESSAGE)
    assert _ERROR_MESSAGE in stderr_buf.getvalue()


def test_redacts_tokens_in_progress_message() -> None:
    output, stdout_buf, _stderr = _make_pair()
    output.progress(f"Using {_GITLAB_TOKEN} now")
    stdout_text: typing.Final = stdout_buf.getvalue()
    assert _GITLAB_TOKEN not in stdout_text
    assert _REDACTED in stdout_text


def test_redacts_tokens_in_error_message() -> None:
    output, _stdout, stderr_buf = _make_pair()
    output.error(f"failed with {_GITLAB_TOKEN}")
    stderr_text: typing.Final = stderr_buf.getvalue()
    assert _GITLAB_TOKEN not in stderr_text
    assert _REDACTED in stderr_text


@pytest.mark.parametrize("quiet", [False, True])
def test_matrix_keeps_stderr_for_errors(quiet: bool) -> None:
    output, _stdout, stderr_buf = _make_pair(quiet=quiet)
    output.error(_ERROR_MESSAGE)
    assert _ERROR_MESSAGE in stderr_buf.getvalue()


@pytest.mark.parametrize(
    "status",
    ["no_merge_commit", "no_conforming_commit", "already_tagged", "no_tags"],
)
def test_emit_renders_non_created_status_to_stdout(status: str) -> None:
    output, stdout_buf, _stderr = _make_pair()
    no_tag_result: typing.Final = RunResult(
        strategy="branch-prefix",
        bump="none",
        status=status,
        tag=None,
        commit=None,
        reason=status,
    )
    output.emit(no_tag_result)
    assert status in stdout_buf.getvalue()


@pytest.mark.parametrize("quiet", [False, True])
def test_rich_matrix_no_interleaving_in_full_sequence(quiet: bool) -> None:
    output, stdout_buf, stderr_buf = _make_pair(quiet=quiet)
    output.progress(_PROGRESS_MESSAGE)
    output.emit(_EXAMPLE_RESULT)
    output.error(_ERROR_MESSAGE)
    stdout_text: typing.Final = stdout_buf.getvalue()
    stderr_text: typing.Final = stderr_buf.getvalue()
    assert "1.2.0" in stdout_text
    assert (_PROGRESS_MESSAGE in stdout_text) is (not quiet)
    assert _ERROR_MESSAGE in stderr_text
    assert _ERROR_MESSAGE not in stdout_text
    assert _PROGRESS_MESSAGE not in stderr_text
    assert "1.2.0" not in stderr_text


def test_build_rich_output_constructs_two_consoles() -> None:
    built: typing.Final = build_rich_output()
    assert isinstance(built, RichOutput)
    assert built.info_console is not built.error_console
    assert built.error_console.stderr is True
    assert built.quiet is False


def test_build_json_output_returns_json_output_with_quiet_passthrough() -> None:
    built: typing.Final = build_json_output(quiet=True)
    assert isinstance(built, JsonOutput)
    assert built.quiet is True
    assert built.error_console.stderr is True


def test_emit_renders_dry_run_with_would_create_phrasing() -> None:
    output, stdout_buf, _stderr = _make_pair()
    dry_run_result: typing.Final = RunResult(
        strategy="branch-prefix",
        bump="minor",
        status="dry_run",
        tag="1.2.0",
        commit="a2b4d12abc1234567890",
        reason=None,
    )
    output.emit(dry_run_result)
    stdout_text: typing.Final = stdout_buf.getvalue()
    assert "Dry run" in stdout_text
    assert "would create tag 1.2.0" in stdout_text
    assert "a2b4d12" in stdout_text
    assert "branch-prefix" in stdout_text
    assert "minor" in stdout_text
