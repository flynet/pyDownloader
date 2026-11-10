"""The sniffer pump loop: intercepted manifest bodies reach the pipeline."""

from __future__ import annotations

from pathlib import Path

from pydownloader.browser.events import ResponseEvent
from pydownloader.browser.sniffer import SnifferThread
from pydownloader.manifest.quality import QualityFilter
from pydownloader.manifest.registry import SourceRegistry

MASTER_URL = "https://cdn.example.com/video/master.m3u8"
VARIANT_1080 = "https://cdn.example.com/video/video/1080.m3u8?token=abc"


class FakeBrowser:
    label = "test"


class FakeResponse:
    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


class FakeContext:
    def cookies(self, url: str) -> list:
        return []


def test_drain_parses_the_intercepted_body_without_a_second_request(qapp, monkeypatch, read):
    registry = SourceRegistry()
    sniffer = SnifferThread(FakeBrowser(), Path("."), registry, QualityFilter(1080))
    fetched: list[str] = []

    def fetch(url: str, headers: dict) -> str | None:
        fetched.append(url)
        return None

    monkeypatch.setattr(sniffer, "_fetch", fetch)
    event = ResponseEvent(
        url=MASTER_URL,
        content_type="application/vnd.apple.mpegurl",
        request_headers={},
    )
    # The body the browser already downloaded: a signed CDN would reject a
    # second GET for the same path (phncdn answers HTTP 410).
    event.response = FakeResponse(read("master.m3u8"))
    sniffer._events.put(event)

    sniffer._drain(FakeContext())

    assert fetched == [VARIANT_1080]
    assert event.body is not None and "#EXTM3U" in event.body
    entries = registry.entries()
    assert len(entries) == 1
    assert entries[0].height == 1080
