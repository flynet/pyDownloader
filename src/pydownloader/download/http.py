"""HTTP with the headers captured from the browser (spec 6.1).

The browser has already fetched the manifest successfully, so repeating the
request with the same ``Referer``/``Origin``/``User-Agent``/``Cookie`` gives the
same bytes. Anti-bot headers (``sec-ch-ua``, ``sec-fetch-*``) are kept, because
some CDNs reject requests without them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from pydownloader.util.ranges import ByteRange
from pydownloader.util.urls import origin_of

#: Headers copied from the intercepted request, in lower case for lookup.
CAPTURED_HEADERS = (
    "referer",
    "origin",
    "user-agent",
    "cookie",
    "accept",
    "accept-language",
    "accept-encoding",
    "sec-ch-ua",
    "sec-ch-ua-mobile",
    "sec-ch-ua-platform",
    "sec-fetch-dest",
    "sec-fetch-mode",
    "sec-fetch-site",
    "x-requested-with",
)
CANONICAL = {
    "referer": "Referer",
    "origin": "Origin",
    "user-agent": "User-Agent",
    "cookie": "Cookie",
    "accept": "Accept",
    "accept-language": "Accept-Language",
    "accept-encoding": "Accept-Encoding",
}
DEFAULT_TIMEOUT = 20.0


class FetchError(RuntimeError):
    """The request failed (network error or HTTP status 400 and above)."""


def capture_headers(request_headers: Mapping[str, str], page_url: str = "") -> dict[str, str]:
    """Canonical headers from the headers of the intercepted browser request.

    ``Referer``/``Origin`` fall back to the page URL when the browser request
    did not carry them.
    """
    lower = {key.lower(): value for key, value in request_headers.items()}
    headers: dict[str, str] = {}
    for key in CAPTURED_HEADERS:
        value = lower.get(key)
        if value:
            headers[CANONICAL.get(key, key)] = value
    if page_url:
        headers.setdefault("Referer", page_url)
        headers.setdefault("Origin", origin_of(page_url))
    return headers


def cookie_header(cookies: Sequence[Mapping[str, Any]]) -> str:
    """``Cookie`` value from ``playwright.context.cookies(url)``."""
    pairs = []
    for cookie in cookies:
        name = cookie.get("name")
        if name:
            pairs.append(f"{name}={cookie.get('value') or ''}")
    return "; ".join(pairs)


def merge_cookies(
    headers: Mapping[str, str], cookies: Sequence[Mapping[str, Any]]
) -> dict[str, str]:
    """Merge the cookies of the browser context into the captured headers.

    Cookies from the context win over the captured request cookies, because the
    context is the current state of the session.
    """
    merged = dict(headers)
    seen: dict[str, str] = {}
    existing = merged.get("Cookie", "")
    for part in existing.split(";"):
        if "=" in part:
            name, value = part.split("=", 1)
            seen[name.strip()] = value.strip()
    for cookie in cookies:
        cname = cookie.get("name")
        if cname:
            seen[str(cname)] = str(cookie.get("value") or "")
    if seen:
        merged["Cookie"] = "; ".join(f"{name}={value}" for name, value in seen.items())
    return merged


def _printable(value: str) -> str:
    """Header values must be encodable as latin-1; drop anything that is not."""
    try:
        value.encode("latin-1")
    except UnicodeEncodeError:
        return ""
    return value


def clean_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Header dictionary safe for ``httpx``."""
    return {key: value for key, value in headers.items() if value and _printable(value)}


def fetch_text(url: str, headers: Mapping[str, str], timeout: float = DEFAULT_TIMEOUT) -> str:
    """``GET`` a manifest body, following redirects. Raises :class:`FetchError`."""
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            response = client.get(url, headers=clean_headers(headers))
    except httpx.HTTPError as exc:
        raise FetchError(f"Сетевая ошибка: {exc}") from exc
    if response.status_code >= 400:
        raise FetchError(f"HTTP {response.status_code} для {url}")
    return response.text


def fetch_bytes(
    url: str,
    headers: Mapping[str, str],
    byte_range: ByteRange | None = None,
    timeout: float = 60.0,
) -> bytes:
    """``GET`` one media segment as bytes. Raises :class:`FetchError`.

    ``byte_range`` adds a ``Range`` header, which is how a part of a single
    file is read (``EXT-X-BYTERANGE`` and DASH ``SegmentBase``).
    """
    request_headers = clean_headers(headers)
    if byte_range is not None:
        request_headers["Range"] = f"bytes={byte_range.start}-{byte_range.end}"
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            response = client.get(url, headers=request_headers)
    except httpx.HTTPError as exc:
        raise FetchError(f"Сетевая ошибка: {exc}") from exc
    if response.status_code >= 400:
        raise FetchError(f"HTTP {response.status_code} для {url}")
    return response.content


def head_info(
    url: str, headers: Mapping[str, str], timeout: float = DEFAULT_TIMEOUT
) -> tuple[int | None, bool]:
    """``HEAD`` request: the file size and whether the server accepts ``Range``.

    Raises :class:`FetchError` on failure.
    """
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            response = client.head(url, headers=clean_headers(headers))
    except httpx.HTTPError as exc:
        raise FetchError(f"Сетевая ошибка: {exc}") from exc
    if response.status_code >= 400:
        raise FetchError(f"HTTP {response.status_code} для {url}")
    length = response.headers.get("content-length")
    size = int(length) if length and length.isdigit() else None
    return size, response.headers.get("accept-ranges", "").lower() == "bytes"
