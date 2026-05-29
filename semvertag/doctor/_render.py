import dataclasses
import json
import sys
import typing

import pydantic
import rich.table
import rich.text

from semvertag._output import RichOutput
from semvertag._redact import redact
from semvertag._settings import Settings
from semvertag._types import CheckResult


_REDACTED_PREFIX: typing.Final = "***"
_TOKEN_SUFFIX_LEN: typing.Final = 4
_DEFAULT_SCHEMA_VERSION: typing.Final = "1.0"
_TOKEN_PATH_SUFFIX: typing.Final = ".token"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class ConfigSourceView:
    value: str
    layer: typing.Literal["cli", "env", "default"]
    detail: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class DoctorResult:
    schema_version: str = _DEFAULT_SCHEMA_VERSION
    configuration: dict[str, ConfigSourceView]
    checks: list[CheckResult]


def _redact_token(secret_value: str) -> str:
    # Deterministic last-4 redaction for the structured configuration slot;
    # the regex in _redact.py is for free-text leakage detection, not this.
    # `<=` (not `<`): a 4-char secret would otherwise be fully disclosed via [-4:].
    if len(secret_value) <= _TOKEN_SUFFIX_LEN:
        return _REDACTED_PREFIX
    return _REDACTED_PREFIX + secret_value[-_TOKEN_SUFFIX_LEN:]


def _format_setting_value(field_path: str, settings: Settings) -> str:
    current: typing.Any = settings
    for part in field_path.split("."):
        current = getattr(current, part)
    # Path-based OR type-based redaction: spec AC2 keys on the dotted-path
    # ending in `.token`, but any SecretStr field is also redacted as defense
    # against a future token field that isn't typed as SecretStr.
    if field_path.endswith(_TOKEN_PATH_SUFFIX) or isinstance(current, pydantic.SecretStr):
        secret_value: typing.Final = (
            current.get_secret_value() if isinstance(current, pydantic.SecretStr) else str(current)
        )
        return _redact_token(secret_value)
    return redact(str(current))


def build_doctor_result(settings: Settings, checks: list[CheckResult]) -> DoctorResult:
    configuration: dict[str, ConfigSourceView] = {}
    for field_path, config_source in settings._provenance.items():  # noqa: SLF001
        configuration[field_path] = ConfigSourceView(
            value=_format_setting_value(field_path, settings),
            layer=config_source.layer,
            detail=config_source.detail,
        )
    return DoctorResult(configuration=configuration, checks=checks)


def render_doctor_human(doctor_result: DoctorResult, output: RichOutput) -> None:
    config_table: typing.Final = rich.table.Table(title="Configuration")
    config_table.add_column("Setting")
    config_table.add_column("Value")
    config_table.add_column("Layer")
    config_table.add_column("Detail")
    for key, view in doctor_result.configuration.items():
        config_table.add_row(
            rich.text.Text(key),
            rich.text.Text(view.value),
            rich.text.Text(view.layer),
            rich.text.Text(view.detail),
        )
    output.info_console.print(config_table)

    checks_table: typing.Final = rich.table.Table(title="Checks")
    checks_table.add_column("Check")
    checks_table.add_column("Status")
    checks_table.add_column("Cause")
    for check in doctor_result.checks:
        checks_table.add_row(
            rich.text.Text(check.name),
            rich.text.Text(check.status),
            rich.text.Text(redact(check.cause)),
        )
    output.info_console.print(checks_table)


def render_doctor_json(doctor_result: DoctorResult) -> None:
    # Writes directly to sys.stdout (mirrors JsonOutput.emit pattern) because
    # JsonOutput.emit takes a RunResult, not a DoctorResult — different envelope.
    payload: typing.Final = json.dumps(dataclasses.asdict(doctor_result), separators=(",", ":"))
    sys.stdout.write(payload + "\n")
    sys.stdout.flush()


__all__: typing.Final = (
    "ConfigSourceView",
    "DoctorResult",
    "build_doctor_result",
    "render_doctor_human",
    "render_doctor_json",
)
