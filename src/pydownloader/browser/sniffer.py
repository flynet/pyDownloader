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
from collections.abc import Mapping, Sequence
from pathlib import Path

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
from pydownloader.manifest.quality import QualityFilter
from pydownloader.manifest.registry import SourceRegistry

#: Milliseconds of one pump step: the handlers fire while this call is running.
PUMP_MS = 200
#: How long a worker waits for cookies read in the sniffer thread.
COOKIES_TIMEOUT = 10.0


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
                context.close()
        except Exception as exc:
            self.failed.emit(f"Браузер: {exc}")
        self._context = None
        self.browser_closed.emit()

    def _on_response(self, response) -> None:
        """Handler of ``context.on("response")``: only enqueue, do nothing blocking."""
        try:
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
        """Process the queued events and cookie requests in the pump loop."""
        while True:
            try:
                item = self._events.get_nowait()
            except queue.Empty:
                return
            if isinstance(item, CookieRequest):
                item.cookies = context.cookies(item.url)
                item.event.set()
                continue
            event = item
            if event.page is not None:
                with contextlib.suppress(Exception):
                    event.page_title = event.page.title()
            page_key = (event.page_url, event.page_title)
            if page_key != self._last_page:
                self._last_page = page_key
                self.page_changed.emit(event.page_url, event.page_title)
            outcomes = process_event(
                event, self.registry, self._fetch, self.quality, self.probe_height
            )
            for outcome in outcomes:
                self._report(outcome)

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
