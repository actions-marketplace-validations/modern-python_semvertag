import typing

import pytest

from semvertag._errors import AuthError, ConfigError, ProviderAPIError, SemvertagError


_SUBCLASSES: typing.Final = (ConfigError, AuthError, ProviderAPIError)
_GENERIC_EXIT_CODE: typing.Final = 1
_CONFIG_EXIT_CODE: typing.Final = 2
_AUTH_EXIT_CODE: typing.Final = 3
_PROVIDER_EXIT_CODE: typing.Final = 4
_SAMPLE_MESSAGE: typing.Final = "AuthFailed: token missing scope. Add scope and retry."


def test_semvertag_error_has_exit_code_one() -> None:
    assert SemvertagError.exit_code == _GENERIC_EXIT_CODE


def test_config_error_has_exit_code_two() -> None:
    assert ConfigError.exit_code == _CONFIG_EXIT_CODE


def test_auth_error_has_exit_code_three() -> None:
    assert AuthError.exit_code == _AUTH_EXIT_CODE


def test_provider_api_error_has_exit_code_four() -> None:
    assert ProviderAPIError.exit_code == _PROVIDER_EXIT_CODE


@pytest.mark.parametrize("cls", _SUBCLASSES)
def test_subclasses_inherit_from_semvertag_error(cls: type[SemvertagError]) -> None:
    assert issubclass(cls, SemvertagError)


def test_exception_message_is_positional_args_zero() -> None:
    err: typing.Final = AuthError(_SAMPLE_MESSAGE)
    assert err.args == (_SAMPLE_MESSAGE,)
    assert str(err) == _SAMPLE_MESSAGE


def test_repr_round_trip_preserves_message() -> None:
    err: typing.Final = AuthError(_SAMPLE_MESSAGE)
    assert repr(err) == f"AuthError({_SAMPLE_MESSAGE!r})"


def _raise_auth_from_value_error(original: ValueError) -> None:
    try:
        raise original
    except ValueError as exc:
        raise AuthError(_SAMPLE_MESSAGE) from exc


def test_chained_from_exc_preserves_cause() -> None:
    original: typing.Final = ValueError("orig")
    with pytest.raises(AuthError) as exc_info:
        _raise_auth_from_value_error(original)
    assert exc_info.value.__cause__ is original
