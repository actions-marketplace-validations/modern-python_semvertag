import re
import typing


_REDACTION: typing.Final = "***"
_TOKEN_PATTERN: typing.Final = re.compile(
    r"glpat-[A-Za-z0-9_\-]{20,}"
    r"|ghp_[A-Za-z0-9]{20,}"
    r"|ATBB[A-Za-z0-9]{20,}"
    r"|\b[0-9a-fA-F]{32,}\b",
)


def redact(text: str) -> str:
    return _TOKEN_PATTERN.sub(_REDACTION, text)


__all__: typing.Final = ("redact",)
