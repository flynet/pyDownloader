"""The sniffer pump loop: intercepted manifest bodies reach the pipeline."""

from __future__ import annotations

import time
from pathlib import Path

from pydownloader.browser.events import ResponseEvent
from pydownloader.browser.sniffer import THUMBNAIL_ATTEMPTS, SnifferThread, youtube_thumbnail
from pydownloader.manifest.quality import QualityFilter
from pydownloader.manifest.registry import SourceEntry, SourceRegistry

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


class FakeImagePage(FakePage):
    """A page that paints one still of its video, as a real player page does."""

    def __init__(self, still: str) -> None:
        super().__init__()
        self.still = still
        self.evaluations = 0

    def evaluate(self, script: str) -> str:
        self.evaluations += 1
        return self.still


def test_the_still_of_a_page_is_read_once_and_resolved(qapp):
    """The picture the page painted is read from its DOM, a relative address resolved."""
    sniffer = make_sniffer()
    page = FakeImagePage("/img/still.jpg")
    page_url = "https://site.example/watch/42"

    assert sniffer._thumbnail_of(page, page_url) == "https://site.example/img/still.jpg"
    # The address is remembered: a later response of the same page does not ask its
    # DOM again, so the listener stays cheap (spec 4.4).
    assert sniffer._thumbnail_of(page, page_url) == "https://site.example/img/still.jpg"
    assert page.evaluations == 1


def test_a_page_without_a_still_is_asked_only_a_few_times(qapp):
    """A page with no picture is asked on a few responses, then left alone (spec 4.1)."""
    sniffer = make_sniffer()
    page = FakeImagePage("")
    page_url = "https://site.example/audio"

    for _ in range(THUMBNAIL_ATTEMPTS + 2):
        assert sniffer._thumbnail_of(page, page_url, force=True) == ""
    assert page.evaluations == THUMBNAIL_ATTEMPTS


def test_a_burst_of_responses_asks_the_dom_of_a_page_once(qapp):
    """The still is looked up once a second, not once per response of a burst (spec 4.4)."""
    sniffer = make_sniffer()
    page = FakeImagePage("")
    page_url = "https://site.example/watch/42"

    for _ in range(10):
        assert sniffer._thumbnail_of(page, page_url) == ""
    assert page.evaluations == 1


class FakeFrame(FakePage):
    """A frame of a page: a player often lives in one, not in the main frame."""

    def __init__(self, still: str) -> None:
        super().__init__()
        self.still = still

    def evaluate(self, script: str) -> str:
        return self.still


class FakeFramedPage(FakePage):
    def __init__(self, still: str) -> None:
        super().__init__()
        self.frames = [FakeFrame(""), FakeFrame(still)]


def test_the_still_is_searched_in_the_frames_of_a_page(qapp):
    """A player in an iframe keeps its still in the frame, not in the page (spec 4.1)."""
    sniffer = make_sniffer()
    page = FakeFramedPage("https://cdn.example.com/frame.jpg")

    found = sniffer._thumbnail_of(page, "https://site.example/watch/42")

    assert found == "https://cdn.example.com/frame.jpg"


def test_a_frame_painted_by_the_player_is_kept_as_a_data_url(qapp):
    """A canvas frame is already bytes in the address: nothing is fetched (spec 4.1)."""
    sniffer = make_sniffer()
    still = "data:image/jpeg;base64,AAAA"
    page = FakeImagePage(still)

    assert sniffer._thumbnail_of(page, "https://site.example/watch/42") == still


def test_the_still_request_carries_the_headers_of_the_page(qapp):
    """The image host gets the referer and the cookies the browser would send (spec 4.1)."""
    sniffer = make_sniffer()
    sniffer._context = FakeContext()
    entry = SourceEntry(
        id="s1",
        kind="mp4",
        url="https://cdn.example.com/movie.mp4",
        normalized="mp4:https://cdn.example.com/movie.mp4",
        page_url="https://site.example/watch/42",
        headers={"User-Agent": "Test/1.0"},
    )

    sniffer._attach_thumbnail(entry, FakeImagePage("https://cdn.example.com/still.jpg"))

    assert entry.thumbnail == "https://cdn.example.com/still.jpg"
    assert entry.thumbnail_headers["Referer"] == "https://site.example/watch/42"
    assert entry.thumbnail_headers["User-Agent"] == "Test/1.0"


def test_a_reported_source_carries_the_still_of_its_page(qapp):
    """The entry that reaches the window has the address of the picture of its page."""
    registry = SourceRegistry()
    sniffer = SnifferThread(FakeBrowser(), Path("."), registry, QualityFilter(1080))
    found = []
    sniffer.source_found.connect(found.append)
    page = FakeImagePage("https://cdn.example.com/still.jpg")
    event = ResponseEvent(
        url="https://cdn.example.com/video/movie.mp4",
        page_url="https://site.example/watch/42",
        content_type="video/mp4",
        content_length=5 * 1024 * 1024,
        request_headers={},
        page=page,
    )
    sniffer._events.put(event)

    sniffer._drain(FakeContext())

    assert len(found) == 1
    assert found[0].thumbnail == "https://cdn.example.com/still.jpg"
    # The Playwright page is not kept by the event: its tab may be closed.
    assert event.page is None


def test_the_cover_of_a_youtube_video_is_known_from_its_id():
    assert youtube_thumbnail("abc123") == "https://i.ytimg.com/vi/abc123/mqdefault.jpg"
