import re
import typing
import urllib.parse

import httpx2


# RFC 8288 Link header: <uri-reference>;param=value;param="value";...
LINK_ENTRY_RE: typing.Final = re.compile(
    r"<\s*(?P<url>[^>]*?)\s*>(?P<params>(?:\s*;\s*[^,;]+)*)",
)


def next_page_url(response: httpx2.Response, *, current_url: str) -> str | None:
    """Walk the response's Link header and return the absolute URL of rel='next', or None."""
    link_header = response.headers.get("link")
    if not link_header:
        return None
    for match in LINK_ENTRY_RE.finditer(link_header):
        url_part = match.group("url").strip()
        if not url_part:
            continue
        if "next" in _parse_rel_values(match.group("params")):
            return urllib.parse.urljoin(current_url, url_part)
    return None


def same_origin(url: str, endpoint: str) -> bool:
    """Return True if `url` shares scheme + netloc with `endpoint`. Guards credential leaks."""
    parsed = urllib.parse.urlsplit(url)
    expected = urllib.parse.urlsplit(endpoint)
    return parsed.scheme == expected.scheme and parsed.netloc == expected.netloc


def _parse_rel_values(params_blob: str) -> set[str]:
    for raw_param in params_blob.split(";"):
        param = raw_param.strip()
        if not param:
            continue
        name, _, value = param.partition("=")
        if name.strip().lower() != "rel":
            continue
        cleaned = value.strip().strip('"').strip("'").lower()
        return set(cleaned.split())
    return set()
