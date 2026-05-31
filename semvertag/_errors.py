import typing


class SemvertagError(Exception):
    exit_code: typing.ClassVar[int] = 1


class ConfigError(SemvertagError):
    exit_code: typing.ClassVar[int] = 2


class AuthError(SemvertagError):
    exit_code: typing.ClassVar[int] = 3


class ProviderAPIError(SemvertagError):
    exit_code: typing.ClassVar[int] = 4
