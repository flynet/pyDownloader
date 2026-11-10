"""Header reuse and HTTP fetch helpers (spec 6.1)."""

from __future__ import annotations

import httpx
import pytest

from pydownloader.download.http import (
    FetchError,
    capture_headers,
    clean_headers,
    cookie_header,
    fetch_bytes,
    fetch_text,
    head_info,
    merge_cookies,
)
from pydownloader.util.ranges import ByteRange

PAGE = "https://site.example/watch/42"


def test_capture_headers_canonical_casing():
    captured = capture_headers(
        {
            "referer": PAGE,
            "user-agent": "Mozilla/5.0",
            "cookie": "sid=1",
            "accept-language": "ru,en",
            "content-length": "12",
            "connection": "keep-alive",
        }
    )
    assert captured["Referer"] == PAGE
    assert captured["User-Agent"] == "Mozilla/5.0"
    assert captured["Cookie"] == "sid=1"
    # Only the headers needed for the request are kept.
    assert "Content-Length" not in captured
    assert "Connection" not in captured


def test_capture_headers_fallback_to_page_url():
    captured = capture_headers({"user-agent": "UA"}, page_url=PAGE)
    assert captured["Referer"] == PAGE
    assert captured["Origin"] == "https://site.example"


def test_capture_headers_keeps_anti_bot_headers():
    captured = capture_headers(
        {"sec-ch-ua": '"Chromium", "Not A(Brand"', "sec-fetch-site": "same-site"}
    )
    assert captured["sec-ch-ua"] == '"Chromium", "Not A(Brand"'
    assert captured["sec-fetch-site"] == "same-site"


def test_cookie_header_from_context_cookies():
    cookies = [
        {"name": "sid", "value": "1"},
        {"name": "lang", "value": "ru"},
        {"name": "empty", "value": None},
    ]
    assert cookie_header(cookies) == "sid=1; lang=ru; empty="


def test_merge_cookies_context_wins():
    merged = merge_cookies({"Cookie": "sid=1; lang=ru"}, [{"name": "sid", "value": "2"}])
    assert merged["Cookie"] == "sid=2; lang=ru"
    merged = merge_cookies({"Referer": PAGE}, [])
    assert merged == {"Referer": PAGE}


def test_clean_headers_drops_non_latin1_values():
    headers = clean_headers({"User-Agent": "UA\u2026", "Referer": PAGE})
    assert "User-Agent" not in headers
    assert headers["Referer"] == PAGE


class FakeResponse:
    def __init__(
        self, status_code: int, text: str = "", content: bytes = b"", headers: dict | None = None
    ):
        self.status_code = status_code
        self.text = text
        self.content = content
        self.headers = headers or {}


class FakeClient:
    """Stand-in for ``httpx.Client``; the calls are recorded for assertions."""

    calls: list[tuple[str, dict]] = []
    response = FakeResponse(200, text="#EXTM3U\n")

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, headers=None):
        FakeClient.calls.append((url, dict(headers or {})))
        return FakeClient.response

    def head(self, url, headers=None):
        FakeClient.calls.append((url, dict(headers or {})))
        return FakeClient.response


@pytest.fixture
def client(monkeypatch):
    FakeClient.calls = []
    FakeClient.response = FakeResponse(200, text="#EXTM3U\n")
    monkeypatch.setattr(httpx, "Client", FakeClient)
    return FakeClient


def test_fetch_text_records_headers_and_redirects(client):
    body = fetch_text("https://cdn.example.com/a.m3u8", {"Referer": PAGE})
    assert body == "#EXTM3U\n"
    url, headers = client.calls[0]
    assert url == "https://cdn.example.com/a.m3u8"
    assert headers["Referer"] == PAGE


def test_fetch_text_status_error(client):
    client.response = FakeResponse(403, text="denied")
    with pytest.raises(FetchError, match="HTTP 403"):
        fetch_text("https://cdn.example.com/a.m3u8", {})


def test_fetch_text_network_error_is_fetch_error(client, monkeypatch):
    def boom(self, url, headers=None):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(FakeClient, "get", boom)
    with pytest.raises(FetchError, match="Сетевая ошибка"):
        fetch_text("https://cdn.example.com/a.m3u8", {})


def test_fetch_bytes_returns_content(client):
    client.response = FakeResponse(200, content=b"segment bytes")
    assert fetch_bytes("https://cdn.example.com/seg.ts", {"Referer": PAGE}) == b"segment bytes"


def test_fetch_bytes_slices_when_the_server_ignores_range(client):
    client.response = FakeResponse(200, content=b"0123456789")
    body = fetch_bytes("https://cdn.example.com/v", {}, ByteRange(start=2, length=4))
    assert body == b"2345"


def test_fetch_bytes_keeps_a_short_200_body(client):
    # Some CDNs answer a Range with 200 and exactly the requested part.
    client.response = FakeResponse(200, content=b"2345")
    body = fetch_bytes("https://cdn.example.com/v", {}, ByteRange(start=2, length=4))
    assert body == b"2345"


def test_head_info_size_and_ranges(client):
    client.response = FakeResponse(
        200, headers={"content-length": "12345", "accept-ranges": "bytes"}
    )
    assert head_info("https://cdn.example.com/a.mp4", {}) == (12345, True)
    client.response = FakeResponse(200, headers={"content-length": "12345"})
    assert head_info("https://cdn.example.com/a.mp4", {}) == (12345, False)
