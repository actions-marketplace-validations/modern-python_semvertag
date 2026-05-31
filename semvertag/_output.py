import dataclasses
import json
import sys
import typing

import rich.console

from semvertag._redact import redact
from semvertag._types import RunResult


_COMMIT_SHORT_LEN: typing.Final = 7


class Output(typing.Protocol):
    def progress(self, message: str) -> None: ...
    def emit(self, result: RunResult) -> None: ...
    def error(self, message: str) -> None: ...


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class RichOutput:
    info_console: rich.console.Console
    error_console: rich.console.Console
    quiet: bool = False

    def progress(self, message: str) -> None:
        if self.quiet:
            return
        self.info_console.print(redact(message), markup=False, highlight=False)

    def emit(self, result: RunResult) -> None:
        self.info_console.print(redact(_format_result(result)), markup=False, highlight=False)

    def error(self, message: str) -> None:
        self.error_console.print(redact(message), markup=False, highlight=False)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class JsonOutput:
    error_console: rich.console.Console
    quiet: bool = False

    def progress(self, message: str) -> None:
        _ = message

    def emit(self, result: RunResult) -> None:
        payload: typing.Final = json.dumps(dataclasses.asdict(result), separators=(",", ":"))
        sys.stdout.write(payload + "\n")
        sys.stdout.flush()

    def error(self, message: str) -> None:
        self.error_console.print(redact(message), markup=False, highlight=False)


def _format_result(result: RunResult) -> str:
    if result.status == "created":
        short: typing.Final = (result.commit or "")[:_COMMIT_SHORT_LEN]
        return f"Created tag {result.tag} on commit {short} (strategy: {result.strategy}, bump: {result.bump})"
    return (
        f"No tag created (status: {result.status}, strategy: {result.strategy}, "
        f"bump: {result.bump}, reason: {result.reason})"
    )


def build_rich_output(*, quiet: bool = False) -> RichOutput:
    return RichOutput(
        info_console=rich.console.Console(),
        error_console=rich.console.Console(stderr=True),
        quiet=quiet,
    )


def build_json_output(*, quiet: bool = False) -> JsonOutput:
    return JsonOutput(
        error_console=rich.console.Console(stderr=True),
        quiet=quiet,
    )
