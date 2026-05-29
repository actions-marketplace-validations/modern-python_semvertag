import typing

import pytest

from semvertag._redact import redact


_GITLAB_TOKEN: typing.Final = "glpat-AbCdEf1234567890ABCD"
_GITHUB_TOKEN: typing.Final = "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345"
_GITHUB_OAUTH_TOKEN: typing.Final = "gho_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345"
_GITHUB_USER_TOKEN: typing.Final = "ghu_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345"
_GITHUB_SERVER_TOKEN: typing.Final = "ghs_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345"
_GITHUB_REFRESH_TOKEN: typing.Final = "ghr_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345"
_GITHUB_FINE_GRAINED_PAT: typing.Final = "github_pat_11ABCDEFG0aBcDeFgHiJ_aBcDeFgHiJkLmNoPqRsTu"
_BITBUCKET_TOKEN: typing.Final = "ATBB0a1b2c3d4e5f6g7h8i9j0KLm"
_HEX_TOKEN: typing.Final = "a" * 40
_REDACTED: typing.Final = "***"
_NO_TOKEN_TEXT: typing.Final = "nothing sensitive here"
_SECRET_STR_RENDER: typing.Final = "**********"
_TOKEN_FAMILIES: typing.Final = (
    _GITLAB_TOKEN,
    _GITHUB_TOKEN,
    _GITHUB_OAUTH_TOKEN,
    _GITHUB_USER_TOKEN,
    _GITHUB_SERVER_TOKEN,
    _GITHUB_REFRESH_TOKEN,
    _GITHUB_FINE_GRAINED_PAT,
    _BITBUCKET_TOKEN,
    _HEX_TOKEN,
)


def test_redacts_gitlab_pat_pattern() -> None:
    assert redact(f"Token is {_GITLAB_TOKEN} here") == f"Token is {_REDACTED} here"


def test_redacts_github_pat_pattern() -> None:
    assert redact(f"Authorization: {_GITHUB_TOKEN}") == f"Authorization: {_REDACTED}"


def test_redacts_bitbucket_app_password_pattern() -> None:
    assert redact(f"Bearer {_BITBUCKET_TOKEN}") == f"Bearer {_REDACTED}"


def test_redacts_generic_hex_token_pattern() -> None:
    assert redact(f"Hash: {_HEX_TOKEN}") == f"Hash: {_REDACTED}"


@pytest.mark.parametrize("token", _TOKEN_FAMILIES)
def test_preserves_surrounding_text_when_redacting(token: str) -> None:
    result: typing.Final = redact(f"prefix {token} suffix")
    assert result == f"prefix {_REDACTED} suffix"


def test_returns_input_unchanged_when_no_tokens_present() -> None:
    assert redact(_NO_TOKEN_TEXT) == _NO_TOKEN_TEXT


@pytest.mark.parametrize("token", _TOKEN_FAMILIES)
def test_redaction_is_idempotent(token: str) -> None:
    once: typing.Final = redact(f"pre {token} post")
    twice: typing.Final = redact(once)
    assert once == twice


def test_redaction_is_idempotent_on_no_token_input() -> None:
    once: typing.Final = redact(_NO_TOKEN_TEXT)
    twice: typing.Final = redact(once)
    assert once == twice == _NO_TOKEN_TEXT


def test_redaction_does_not_match_inside_longer_alphanumeric_blob() -> None:
    embedded: typing.Final = "z" * 10 + _HEX_TOKEN + "z" * 10
    assert redact(embedded) == embedded


def test_composes_with_secret_str_render() -> None:
    assert redact(_SECRET_STR_RENDER) == _SECRET_STR_RENDER


def test_redacts_token_only_input_to_marker_only() -> None:
    assert redact(_GITLAB_TOKEN) == _REDACTED


@pytest.mark.parametrize(
    "token",
    [
        _GITHUB_OAUTH_TOKEN,
        _GITHUB_USER_TOKEN,
        _GITHUB_SERVER_TOKEN,
        _GITHUB_REFRESH_TOKEN,
        _GITHUB_FINE_GRAINED_PAT,
    ],
)
def test_redacts_github_token_family_variants(token: str) -> None:
    assert redact(f"Authorization: {token}") == f"Authorization: {_REDACTED}"


_GITHUB_PREFIXES_MIN: typing.Final = (
    "gho_" + "A" * 20,
    "ghu_" + "A" * 20,
    "ghs_" + "A" * 20,
    "ghr_" + "A" * 20,
    "github_pat_" + "A" * 20,
)


@pytest.mark.parametrize("token", _GITHUB_PREFIXES_MIN)
def test_redacts_github_token_at_minimum_body_length(token: str) -> None:
    assert redact(f"Authorization: {token}") == f"Authorization: {_REDACTED}"


@pytest.mark.parametrize("token", _GITHUB_PREFIXES_MIN)
def test_redacts_github_token_at_start_and_end_of_input(token: str) -> None:
    assert redact(f"{token} trailing") == f"{_REDACTED} trailing"
    assert redact(f"leading {token}") == f"leading {_REDACTED}"


@pytest.mark.parametrize(
    "token",
    [
        _GITHUB_OAUTH_TOKEN,
        _GITHUB_USER_TOKEN,
        _GITHUB_SERVER_TOKEN,
        _GITHUB_REFRESH_TOKEN,
        _GITHUB_FINE_GRAINED_PAT,
    ],
)
def test_redacts_github_token_when_followed_by_word_boundary_punctuation(token: str) -> None:
    assert redact(f"({token})") == f"({_REDACTED})"
    assert redact(f"[{token}]") == f"[{_REDACTED}]"
    assert redact(f"{token}.") == f"{_REDACTED}."
