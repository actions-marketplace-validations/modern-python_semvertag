import typing

import httpx2

from semvertag._link_pagination import _parse_rel_values, next_page_url


_CURRENT_URL: typing.Final = "https://gitlab.example.test/api/v4/projects/999/repository/tags"


def _link_header_response(link_header: str) -> httpx2.Response:
    return httpx2.Response(200, headers={"link": link_header}, json=[])


def test_next_page_url_skips_entries_with_empty_uri_reference() -> None:
    response: typing.Final = _link_header_response('<>; rel="next"')
    assert next_page_url(response, current_url=_CURRENT_URL) is None


def test_next_page_url_returns_none_when_link_header_absent() -> None:
    response: typing.Final = httpx2.Response(200, json=[])
    assert next_page_url(response, current_url=_CURRENT_URL) is None


def test_next_page_url_returns_none_when_only_non_next_rel_present() -> None:
    response: typing.Final = _link_header_response(f'<{_CURRENT_URL}?page=1>; rel="prev"')
    assert next_page_url(response, current_url=_CURRENT_URL) is None


def test_parse_rel_values_returns_empty_set_when_no_rel_param_present() -> None:
    assert _parse_rel_values("; foo=bar; baz=qux") == set()


def test_parse_rel_values_skips_non_rel_params_before_finding_rel() -> None:
    assert _parse_rel_values('; foo="bar"; rel="next"') == {"next"}
