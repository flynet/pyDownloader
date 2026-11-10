"""Sniffer thread: Playwright in its own thread, filters, Qt signals (spec 4.4).

Playwright runs the sync API inside :meth:`SnifferThread.run`, pumping its event
loop with a short ``wait_for_timeout``. The response handlers only put events in
a queue and return immediately; the pump loop drains the queue, resolves the
blocking calls (page title, cookies, manifest body) and emits Qt signals. No
widget is touched from this thread.
"""

from __future__ import annotations

import asyncio
import contextlib
import queue
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from playwright.sync_api import BrowserContext, sync_playwright
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget

from pydownloader.browser.events import CookieRequest, ResponseEvent
from pydownloader.browser.launcher import CHROMIUM_WARNING, BrowserChoice, launch_kwargs
from pydownloader.download.http import (
    FetchError,
    capture_headers,
    cookie_header,
    fetch_text,
    merge_cookies,
)
from pydownloader.manifest.pipeline import Outcome, ProbeHeight, process_event
from pydownloader.manifest.quality import Choice, QualityFilter
from pydownloader.manifest.registry import SourceRegistry
from pydownloader.youtube.api import (
    API_KEY,
    CLIENT_NAME,
    CLIENT_VERSION,
    PAGE_FETCH_SCRIPT,
    payload_template,
    video_id_from_url,
)
from pydownloader.youtube.player import parse_player, qualities, reason_of

#: Milliseconds of one pump step: the handlers fire while this call is running.
PUMP_MS = 200
#: How long a worker waits for cookies read in the sniffer thread.
COOKIES_TIMEOUT = 10.0
#: Pause between two inner-tube player requests of the same watch page, in seconds.
YOUTUBE_ATTEMPT_INTERVAL = 3.0


class SnifferThread(QThread):
    """Intercepts browser traffic and publishes the sources that passed the filters."""

    source_found = Signal(object)  # SourceEntry
    message = Signal(str)
    page_changed = Signal(str, str)  # url, title
    browser_closed = Signal()
    failed = Signal(str)

    def __init__(
        self,
        browser: BrowserChoice,
        profile_dir: Path,
        registry: SourceRegistry,
        quality: QualityFilter,
        start_url: str = "",
        probe_height: ProbeHeight | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.browser = browser
        self.profile_dir = profile_dir
        self.registry = registry
        self.quality = quality
        self.start_url = start_url
        self.probe_height = probe_height
        self._events: queue.Queue[ResponseEvent | CookieRequest] = queue.Queue()
        self._stop = False
        self._context: BrowserContext | None = None
        self._last_page: tuple[str, str] | None = None
        self._yt_last_id: str | None = None
        self._yt_failed_id: str | None = None
        self._yt_last_attempt = 0.0
        self._cached_ua = ""

    def stop(self) -> None:
        """Ask the loop to finish; the browser is closed at the end of ``run``."""
        self._stop = True

    def request_cookies(
        self, url: str, timeout: float = COOKIES_TIMEOUT
    ) -> Sequence[Mapping[str, object]]:
        """Cookies of the browser context for a URL (spec 6.1).

        Playwright objects are bound to the event loop of this thread, so the
        call is executed here by the pump loop; a download worker waits for it.
        """
        request = CookieRequest(url=url)
        self._events.put(request)
        if request.event.wait(timeout):
            return request.cookies
        return []

    def run(self) -> None:
        if sys.platform == "win32":
            # Playwright starts subprocesses; in a worker thread the proactor loop is required.
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        try:
            with sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(
                    **launch_kwargs(self.browser, self.profile_dir)
                )
                self._context = context
                context.on("response", self._on_response)
                self.message.emit(f"Браузер запущен: {self.browser.label}")
                if self.browser.is_bundled_chromium:
                    self.message.emit(CHROMIUM_WARNING)
                pages = context.pages
                page = pages[0] if pages else context.new_page()
                if self.start_url:
                    page.goto(self.start_url)
                while not self._stop:
                    pages = context.pages
                    if not pages:
                        self.message.emit("Браузер закрыт пользователем")
                        break
                    try:
                        pages[0].wait_for_timeout(PUMP_MS)
                    except Exception as exc:  # a page was closed or crashed
                        self.message.emit(f"Страница недоступна: {exc}")
                        continue
                    self._drain(context)
                    self._capture_youtube(context)
                context.close()
        except Exception as exc:
            self.failed.emit(f"Браузер: {exc}")
        self._context = None
        self.browser_closed.emit()

    def _on_response(self, response) -> None:
        """Handler of ``context.on("response")``: only enqueue, do nothing blocking."""
        try:
            # Media is fetched with GET; a POST body (YouTube SABR/UMP) is not a source.
            if response.request.method not in ("GET", "HEAD"):
                return
            page = response.frame.page
            headers = dict(response.request.headers)
            response_headers = dict(response.headers)
            length = response_headers.get("content-length")
            self._events.put(
                ResponseEvent(
                    url=response.url,
                    page_url=page.url,
                    status=response.status,
                    content_type=response_headers.get("content-type"),
                    content_length=int(length) if length and length.isdigit() else None,
                    content_range=response_headers.get("content-range"),
                    request_headers=headers,
                    page=page,
                )
            )
        except Exception:
            # A response of a closing page is not a source; never break the handler.
            return

    def _drain(self, context: BrowserContext) -> None:
        """Process the queued events and cookie requests in the pump loop.

        The events of one burst are handled in two passes: every URL is recorded
        first, so a manifest is processed with the signed URLs of its variants and
        segments already known. Families are synthesized last, once it is clear
        that no playlist owns their directory.
        """
        events: list[ResponseEvent] = []
        while True:
            try:
                item = self._events.get_nowait()
            except queue.Empty:
                break
            if isinstance(item, CookieRequest):
                item.cookies = context.cookies(item.url)
                item.event.set()
                continue
            events.append(item)
        for event in events:
            if event.page is not None:
                with contextlib.suppress(Exception):
                    event.page_title = event.page.title()
                # The registry may keep the event for family synthesis: do not
                # hold a Playwright page (and its closed tab) alive.
                event.page = None
            page_key = (event.page_url, event.page_title)
            if page_key != self._last_page:
                self._last_page = page_key
                self.page_changed.emit(event.page_url, event.page_title)
            self.registry.note_response(event)
        for event in events:
            outcomes = process_event(
                event, self.registry, self._fetch, self.quality, self.probe_height
            )
            for outcome in outcomes:
                self._report(outcome)
        for family in self.registry.synthesize_families():
            self.source_found.emit(family)
            self.message.emit(
                f"Найдена HLS-группа сегментов ({len(family.recorded)} файлов): {family.url}"
            )

    def _capture_youtube(self, context: BrowserContext) -> None:
        """Ask the inner-tube player API from the watch page (server-side ABR workaround).

        The web player serves media over SABR/UMP, so the response listener never
        sees a downloadable URL. The VISIONOS client still answers with classic
        signed URLs; the request is made by the page itself, so cookies and
        ``visitorData`` are present and the bot check is not triggered.
        """
        target: tuple[Any, str, str] | None = None
        for page in context.pages:
            try:
                page_url = page.url
            except Exception:
                continue
            video_id = video_id_from_url(page_url)
            if video_id and video_id != self._yt_last_id:
                target = (page, page_url, video_id)
                break
        if target is None:
            return
        now = time.monotonic()
        if now - self._yt_last_attempt < YOUTUBE_ATTEMPT_INTERVAL:
            return
        self._yt_last_attempt = now
        page, page_url, video_id = target
        try:
            raw = page.evaluate(
                PAGE_FETCH_SCRIPT,
                {
                    "key": API_KEY,
                    "clientName": CLIENT_NAME,
                    "clientVersion": CLIENT_VERSION,
                    "payloadTemplate": payload_template(video_id),
                    "visitor": "",
                },
            )
        except Exception as exc:
            if self._yt_failed_id != video_id:
                self._yt_failed_id = video_id
                self.message.emit(f"YouTube: {exc}")
            return
        if not raw:
            return
        player = parse_player(raw)
        if not player.ok:
            # The page may still be loading (no visitorData yet -> bot check):
            # retry silently, report the reason once per video.
            if self._yt_failed_id != video_id:
                self._yt_failed_id = video_id
                self.message.emit(f"YouTube: {reason_of(player)}")
            return
        heights = qualities(player)
        height = heights[0] if heights else None
        canonical = f"yt:{video_id}"
        existing = self.registry.get(canonical)
        if existing is not None:
            existing.payload = raw
            existing.height = height
            existing.choice = Choice(kind="mp4", url=page_url, height=height)
            self.message.emit(f"YouTube: поток обновлён — {existing.title or video_id}")
            self._yt_last_id = video_id
            self._yt_failed_id = None
            return
        ua = self._user_agent(page)
        headers = capture_headers({"user-agent": ua} if ua else {}, page_url)
        result = self.registry.add_custom(
            kind="youtube",
            url=page_url,
            normalized=canonical,
            title=player.title or video_id,
            page_url=page_url,
            headers=headers,
            height=height,
            duration=player.duration,
            payload=raw,
        )
        entry = result.entry
        entry.choice = Choice(kind="mp4", url=page_url, height=height)
        self._yt_last_id = video_id
        self._yt_failed_id = None
        if result.is_new:
            quality = ", ".join(f"{value}p" for value in heights) or "неизвестно"
            self.message.emit(f"Найден YouTube ({quality}): {entry.title}")
            self.source_found.emit(entry)

    def _user_agent(self, page) -> str:
        if self._cached_ua:
            return self._cached_ua
        try:
            self._cached_ua = str(page.evaluate("navigator.userAgent"))
        except Exception:
            return ""
        return self._cached_ua

    def _report(self, outcome: Outcome) -> None:
        if outcome.message:
            self.message.emit(outcome.message)
        if outcome.action == "show" and outcome.entry is not None:
            self.source_found.emit(outcome.entry)

    def _fetch(self, url: str, headers: dict[str, str]) -> str | None:
        """Re-issue the request with the captured headers and the current cookies.

        Runs in the pump loop, so ``context.cookies`` is safe here.
        """
        merged = capture_headers(headers)
        cookies: Sequence[Mapping[str, object]] = []
        if self._context is not None:
            try:
                cookies = self._context.cookies(url)
            except Exception:
                cookies = []
        merged = merge_cookies(merged, cookies)
        try:
            return fetch_text(url, merged)
        except FetchError as exc:
            self.message.emit(str(exc))
            return None


def cookies_for(sniffer: SnifferThread | None, url: str) -> str:
    """Cookie header for a download, empty when the sniffer is not running."""
    if sniffer is None:
        return ""
    return cookie_header(sniffer.request_cookies(url))


def browser_cookies(
    sniffer: SnifferThread | None, urls: Sequence[str]
) -> list[Mapping[str, object]]:
    """Cookies of the browser context for several URLs (page and CDN host).

    The download needs the cookies of both the page and the CDN: the page
    cookie carries the session, the CDN cookie the signature of the stream.
    """
    if sniffer is None:
        return []
    cookies: list[Mapping[str, object]] = []
    for url in urls:
        if not url:
            continue
        cookies.extend(sniffer.request_cookies(url))
    return cookies
