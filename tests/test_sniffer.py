"""The sniffer pump loop: intercepted manifest bodies reach the pipeline."""

from __future__ import annotations

import time
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


class FakePage:
    """A page of the browser: the address it is opened on is recorded."""

    def __init__(self) -> None:
        self.opened: list[str] = []

    def goto(self, url: str) -> None:
        self.opened.append(url)

    def title(self) -> str:
        return "Site"


class FakeContext:
    def __init__(self) -> None:
        self.pages = [FakePage()]

    def cookies(self, url: str) -> list:
        return []


def test_go_puts_the_address_in_the_queue_of_the_pump_loop(qapp):
    """The GUI thread hands the address over, the pump loop of the thread opens it.

    The page object belongs to the event loop of the sniffer thread, so «Go» writes
    the address into the queue and the pump loop opens the page there (spec 4.2 p.4).
    """
    registry = SourceRegistry()
    sniffer = SnifferThread(FakeBrowser(), Path("."), registry, QualityFilter(1080))
    sniffer.go("https://site.example/watch/42")

    context = FakeContext()
    sniffer._drain(context)

    assert context.pages[0].opened == ["https://site.example/watch/42"]
    # The page is remembered, so «Open browser» opens this address again.
    assert sniffer.last_url == "https://site.example/watch/42"


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


def make_sniffer(start_url: str = "") -> SnifferThread:
    return SnifferThread(FakeBrowser(), Path("."), SourceRegistry(), QualityFilter(1080), start_url)


def test_the_browser_is_not_open_before_the_thread_runs(qapp):
    sniffer = make_sniffer("https://site.example/player")
    # The address of the page is known from the start, so «Open browser» has an
    # address to reopen before any page was seen.
    assert sniffer.last_url == "https://site.example/player"
    assert not sniffer.is_browser_open()


def test_last_page_of_the_browser_is_remembered(qapp):
    sniffer = make_sniffer("https://site.example/player")
    event = ResponseEvent(
        url="https://cdn.example.com/video/master.m3u8",
        page_url="https://site.example/watch/42",
        page_title="Clip",
        content_type="application/json",
        request_headers={},
    )
    sniffer._events.put(event)

    sniffer._drain(FakeContext())

    assert sniffer.last_url == "https://site.example/watch/42"


def test_cookies_of_a_closed_browser_are_answered_without_a_timeout(qapp):
    """No context means nothing to read: waiting 10 s per segment stalls the task."""
    sniffer = make_sniffer()
    started = time.monotonic()

    assert sniffer.request_cookies("https://site.example") == []
    assert time.monotonic() - started < 1.0


def test_open_browser_state_follows_the_context(qapp):
    sniffer = make_sniffer()
    sniffer._context = FakeContext()
    assert sniffer.is_browser_open()
    sniffer.stop()
    assert not sniffer.is_browser_open()
