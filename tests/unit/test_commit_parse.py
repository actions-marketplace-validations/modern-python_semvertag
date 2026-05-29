import typing

import pytest

from semvertag._commit_parse import body_lines, subject_line


_LS: typing.Final = "\u2028"
_PS: typing.Final = "\u2029"


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("", ""),
        ("   ", ""),
        ("\n\n", ""),
        ("feat: add thing", "feat: add thing"),
        ("feat: add thing\n", "feat: add thing"),
        ("feat: add thing\r\n", "feat: add thing"),
        ("\n\nfeat: with leading blanks", "feat: with leading blanks"),
        ("first line\nsecond line", "first line"),
        ("first line\r\nsecond line\r\n", "first line"),
        (f"first line{_LS}second line", "first line"),
        (f"first line{_PS}second line", "first line"),
        ("   trimmed trailing   \nnext", "   trimmed trailing"),
    ],
)
def test_subject_line_returns_first_non_blank_with_trailing_whitespace_stripped(
    message: str,
    expected: str,
) -> None:
    assert subject_line(message) == expected


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("", []),
        ("only subject", []),
        ("subject\nstill subject\nno blank yet", ["still subject", "no blank yet"]),
        ("subject\n\nfooter1", ["footer1"]),
        ("subject\n\nfooter1\nfooter2", ["footer1", "footer2"]),
        ("subject\r\n\r\nfooter\r\n", ["footer"]),
        ("\n\nsubject\n\nfooter", ["footer"]),
        ("subject\n\n\n\nfooter-after-many-blanks", ["footer-after-many-blanks"]),
        ("subject\n\nfooter1\n\nfooter2", ["footer1", "footer2"]),
        ("subject\n\nBREAKING CHANGE: removed thing", ["BREAKING CHANGE: removed thing"]),
        ("subject\nBREAKING CHANGE: no blank separator", ["BREAKING CHANGE: no blank separator"]),
        ("subject\n\nfooter   ", ["footer"]),
    ],
)
def test_body_lines_returns_lines_after_subject(
    message: str,
    expected: list[str],
) -> None:
    assert body_lines(message) == expected


def test_body_lines_strips_carriage_returns_from_crlf_input() -> None:
    msg: typing.Final = "feat: x\r\n\r\nBREAKING CHANGE: y\r\n"
    result: typing.Final = body_lines(msg)
    assert result == ["BREAKING CHANGE: y"]
    assert all("\r" not in line for line in result)
