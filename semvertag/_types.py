import dataclasses
import typing


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class ConfigSource:
    layer: typing.Literal["cli", "env", "default"]
    detail: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class RunResult:
    schema_version: str = "1.0"
    strategy: str
    bump: str
    status: str
    tag: str | None
    commit: str | None
    reason: str | None
