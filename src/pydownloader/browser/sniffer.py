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
import logging
import queue
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from playwright.sync_api import BrowserContext, sync_playwright
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget

from pydownloader.browser.events import CookieRequest, NavigateRequest, ResponseEvent
from pydownloader.browser.launcher import BrowserChoice, launch_kwargs
from pydownloader.browser.stealth import DEFAULT_LOCALE, stealth_script
from pydownloader.download.http import (
    FetchError,
    capture_headers,
    cookie_header,
    fetch_text,
    merge_cookies,
)
from pydownloader.i18n import tr
from pydownloader.manifest.pipeline import Outcome, ProbeMedia, process_event
from pydownloader.manifest.quality import Choice, QualityFilter
from pydownloader.manifest.registry import SourceEntry, SourceRegistry
from pydownloader.util.urls import is_manifest_url, normalize_content_type
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
#: Content types that mark a manifest even when the URL has no ``.m3u8``/``.mpd``.
MANIFEST_TYPES = {
    "application/vnd.apple.mpegurl",
    "application/x-mpegurl",
    "audio/mpegurl",
    "application/dash+xml",
}

#: Script that reads the still of the video the page itself paints: the
#: ``og:image`` of the page, the picture of the tweet card, the ``poster`` of the
#: player or the frame the player shows right now. The card of a video shows
#: exactly what the person saw in the browser, so the program never guesses an
#: address of a preview (spec 4.1).
THUMBNAIL_SCRIPT = """
() => {
    const pick = (selector) => {
        const element = document.querySelector(selector);
        if (!element) return '';
        return element.content || element.href || element.src || '';
    };
    const metas = [
        'meta[property="og:image"]',
        'meta[property="og:image:url"]',
        'meta[property="og:image:secure_url"]',
        'meta[name="og:image"]',
        'meta[name="twitter:image"]',
        'meta[name="twitter:image:src"]',
        'meta[property="twitter:image"]',
        'meta[itemprop="thumbnailUrl"]',
        'meta[name="thumbnail"]',
        'link[rel="image_src"]',
    ];
    for (const selector of metas) {
        const found = pick(selector);
        if (found) return found;
    }
    // Structured data of the page: the thumbnail the site tells the search
    // engines about, often the only copy of the still in the markup.
    for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
        try {
            const data = JSON.parse(script.textContent);
            const nodes = Array.isArray(data) ? data.slice() : [data];
            while (nodes.length) {
                const node = nodes.shift();
                if (!node || typeof node !== 'object') continue;
                const thumb = node.thumbnailUrl;
                if (typeof thumb === 'string' && thumb) return thumb;
                if (Array.isArray(thumb) && typeof thumb[0] === 'string') return thumb[0];
                // Video objects name the still `thumbnail` or `image`, sometimes as
                // an object with the address inside.
                for (const name of ['thumbnail', 'image']) {
                    const value = node[name];
                    if (typeof value === 'string' && value) return value;
                    if (Array.isArray(value) && typeof value[0] === 'string') return value[0];
                    if (value && typeof value === 'object') {
                        if (typeof value.url === 'string' && value.url) return value.url;
                        if (typeof value.contentUrl === 'string' && value.contentUrl) {
                            return value.contentUrl;
                        }
                    }
                }
                if (Array.isArray(node['@graph'])) nodes.push(...node['@graph']);
            }
        } catch (error) {}
    }
    // A player that paints its poster as an image (Dailymotion, many custom
    // players): the mark of the picture is in its class, id or alt text. The
    // largest picture wins, so an icon of the player is not taken for a still.
    let posterImage = '';
    let posterArea = 0;
    const posters = document.querySelectorAll(
        'img[class*="poster" i], img[id*="poster" i], img[class*="still" i],' +
        'img[class*="preview" i], img[class*="cover" i], img[alt*="poster" i]'
    );
    for (const element of [...posters].slice(0, 40)) {
        const src = element.currentSrc || element.src || '';
        const area = element.naturalWidth * element.naturalHeight;
        const real = element.naturalWidth >= 120 && element.naturalHeight >= 60;
        if (src && real && area > posterArea) {
            posterImage = src;
            posterArea = area;
        }
    }
    if (posterImage) return posterImage;
    // The player paints its poster as a background of a div (Video.js, JW
    // Player, Plyr, custom skins): the picture is read from the computed style.
    for (const selector of ['.vjs-poster', '.jw-preview', '.plyr__poster',
                            '[class*="poster"]', '[id*="poster"]']) {
        const element = document.querySelector(selector);
        if (!element) continue;
        const image = window.getComputedStyle(element).backgroundImage || '';
        const match = /url\\(["']?(.*?)["']?\\)/.exec(image);
        if (match && match[1]) return match[1];
    }
    const video = document.querySelector('video');
    if (video) {
        if (video.poster) return video.poster;
        if (video.dataset && video.dataset.poster) return video.dataset.poster;
        // The frame on the screen right now: a video of another origin may not be
        // drawn to a canvas, the try/catch keeps such a page quiet.
        try {
            if (video.videoWidth > 0 && video.videoHeight > 0 && video.readyState >= 2) {
                const canvas = document.createElement('canvas');
                canvas.width = 320;
                canvas.height = Math.round(320 * video.videoHeight / video.videoWidth);
                canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
                const frame = canvas.toDataURL('image/jpeg', 0.8);
                if (frame && frame.length > 128) return frame;
            }
        } catch (error) {}
    }
    return '';
}
"""

#: How many responses of one page may ask for its still, and how often: the
#: metadata of a page appears after the markup is parsed, and some players paint
#: their poster only when the video starts, so the page is asked again over its
#: life instead of once (spec 4.1).
THUMBNAIL_ATTEMPTS = 30
THUMBNAIL_RETRY_SECONDS = 1.0
#: How many frames of a page are searched: a player often lives in an iframe.
THUMBNAIL_FRAMES = 8


def youtube_thumbnail(video_id: str) -> str:
    """Cover of a YouTube video: the 320x180 still the site itself shows (spec 4.1)."""
    return f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"


logger = logging.getLogger("pydownloader.sniffer")


class SnifferThread(QThread):
    """Intercepts browser traffic and publishes the sources that passed the filters."""

    source_found = Signal(object)  # SourceEntry
    message = Signal(str)
    page_changed = Signal(str, str)  # url, title
    started = Signal()  # the browser window is up: the UI enables «Close browser»
    browser_closed = Signal()
    failed = Signal(str)

    def __init__(
        self,
        browser: BrowserChoice,
        profile_dir: Path,
        registry: SourceRegistry,
        quality: QualityFilter,
        start_url: str = "",
        probe_media: ProbeMedia | None = None,
        extension_dir: Path | None = None,
        anti_bot: bool = True,
        user_agent: str = "",
        locale: str = DEFAULT_LOCALE,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.browser = browser
        self.profile_dir = profile_dir
        self.extension_dir = extension_dir
        self.registry = registry
        self.quality = quality
        self.start_url = start_url
        self.probe_media = probe_media
        #: Stealth of the launch (spec 7.2): the flags of a driver are dropped.
        self.anti_bot = anti_bot
        #: User agent the user chose, ``""`` means the Chrome form of the browser.
        self.user_agent = user_agent
        #: ``Accept-Language`` of the browser, the language of the interface.
        self.locale = locale
        self._events: queue.Queue[ResponseEvent | CookieRequest | NavigateRequest] = queue.Queue()
        self._stop = False
        self._context: BrowserContext | None = None
        self._last_page: tuple[str, str] | None = None
        self._yt_last_id: str | None = None
        self._yt_failed_id: str | None = None
        self._yt_last_attempt = 0.0
        self._cached_ua = ""
        #: Page address -> address of the still the page painted (spec 4.1): the
        #: card takes it from here when the source of that page is reported.
        self._thumbnails: dict[str, str] = {}
        #: Page address -> how many responses asked for its still already.
        self._thumb_attempts: dict[str, int] = {}
        #: Page address -> when its still was read last: a burst of responses of
        #: one page asks its DOM once, not once per response.
        self._thumb_last: dict[str, float] = {}
        #: Page the browser is on: «Open browser» opens this address again.
        self.last_url = start_url

    def stop(self) -> None:
        """Ask the loop to finish; the browser is closed at the end of ``run``."""
        self._stop = True

    def is_browser_open(self) -> bool:
        """Whether the browser window is up: the top panel buttons use this."""
        return self._context is not None and not self._stop

    def go(self, url: str) -> None:
        """Ask the pump loop to open ``url`` in the browser window (spec 4.2 p.4).

        The page object of Playwright belongs to the event loop of this thread, so the
        GUI thread only puts the address in the queue: the pump loop opens the page
        there, and the responses of the new page are read by the same listener that
        reads any other page of the browser.
        """
        self._events.put(NavigateRequest(url=url))

    def _navigate(self, context: BrowserContext, url: str) -> None:
        """Open the address in the browser window, in the loop that owns the page."""
        pages = context.pages
        page = pages[0] if pages else context.new_page()
        with contextlib.suppress(Exception):
            page.goto(url)
        # The page of the browser is remembered, so «Open browser» opens this address.
        self.last_url = url
        title = ""
        with contextlib.suppress(Exception):
            title = page.title()
        self._last_page = (url, title)
        logger.info(tr("browser_page", url=url, title=title))
        self.page_changed.emit(url, title)

    def _log_page_state(self, page: Any) -> None:
        """What a bot detector reads on its first check, written for analysis.

        ``navigator.webdriver`` is the marker Playwright leaves, the user agent
        tells whether the browser reports Chrome, the list of languages tells
        whether the locale of the user is set (spec 7.2).
        """
        try:
            ua = page.evaluate("navigator.userAgent")
            driver = page.evaluate("!!navigator.webdriver")
            languages = page.evaluate("navigator.languages.join(',')")
        except Exception as exc:
            logger.debug(tr("browser_state_failed", error=exc))
            return
        logger.info(
            tr("browser_page_state", ua=ua, driver=driver, languages=languages)
        )

    def _log_extensions(self, context: BrowserContext) -> None:
        """The ad blocker: Chrome and Edge ignore ``--load-extension`` (spec 6.4).

        The service workers of the context are the visible sign of an extension
        that was loaded, so they are logged; an empty list means the blocker is
        not running in this browser.
        """
        urls = ", ".join(worker.url for worker in context.service_workers)
        logger.info(tr("browser_ext_state", state=urls or tr("browser_none")))

    def request_cookies(
        self, url: str, timeout: float = COOKIES_TIMEOUT
    ) -> Sequence[Mapping[str, object]]:
        """Cookies of the browser context for a URL (spec 6.1).

        Playwright objects are bound to the event loop of this thread, so the
        call is executed here by the pump loop; a download worker waits for it.
        With the browser closed (the user closed the window) there is nothing to
        read: return at once, so the download of the captured headers is not
        stalled by a 10 s timeout for every segment.
        """
        if self._context is None:
            return []
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
                kwargs = launch_kwargs(
                    self.browser,
                    self.profile_dir,
                    self.extension_dir,
                    self.anti_bot,
                    self.user_agent,
                    self.locale,
                )
                # The flags are the answer to a "JavaScript is disabled" report,
                # so the launch is written in the log as it was sent (spec 7.2).
                logger.info(tr("browser_launch_args", args=" ".join(kwargs["args"])))
                logger.info(
                    tr(
                        "browser_stealth",
                        stealth=tr("browser_on") if self.anti_bot else tr("browser_off"),
                        locale=self.locale,
                        ua=kwargs.get("user_agent") or tr("browser_auto_ua"),
                    )
                )
                context = playwright.chromium.launch_persistent_context(**kwargs)
                self._context = context
                if self.anti_bot:
                    # The init script runs before every page of the context, so a
                    # detector reads navigator on a browser that already looks human.
                    context.add_init_script(
                        stealth_script(str(kwargs.get("user_agent", "")), self.locale)
                    )
                context.on("response", self._on_response)
                logger.info(
                    tr(
                        "browser_started",
                        browser=self.browser.label,
                        profile=self.profile_dir,
                        extension=self.extension_dir or tr("browser_none"),
                    )
                )
                self.message.emit(tr("browser_started_line", browser=self.browser.label))
                if self.extension_dir is not None:
                    self.message.emit(tr("ext_connected"))
                if self.browser.is_bundled_chromium:
                    self.message.emit(tr("browser_codec_warning"))
                pages = context.pages
                page = pages[0] if pages else context.new_page()
                self._log_page_state(page)
                if self.start_url:
                    page.goto(self.start_url)
                    self._log_page_state(page)
                self._log_extensions(context)
                self.started.emit()
                while not self._stop:
                    pages = context.pages
                    if not pages:
                        self.message.emit(tr("browser_closed_by_user"))
                        break
                    page = pages[0]
                    try:
                        if page.is_closed():
                            self.message.emit(tr("browser_closed_by_user"))
                            break
                        self.last_url = page.url
                        page.wait_for_timeout(PUMP_MS)
                    except Exception as exc:  # a page was closed or crashed
                        if page.is_closed():
                            self.message.emit(tr("browser_closed_by_user"))
                            break
                        text = tr("browser_page_unavailable", error=exc)
                        logger.debug(text)
                        self.message.emit(text)
                        continue
                    self._drain(context)
                    self._capture_youtube(context)
                context.close()
        except Exception as exc:
            self.failed.emit(tr("browser_failed", error=exc))
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
            content_type = response_headers.get("content-type")
            event = ResponseEvent(
                url=response.url,
                page_url=page.url,
                status=response.status,
                content_type=content_type,
                content_length=int(length) if length and length.isdigit() else None,
                content_range=response_headers.get("content-range"),
                request_headers=headers,
                page=page,
            )
            # A manifest body is read in the pump loop: the copy the browser
            # already has is the most reliable one (a signed CDN rejects a
            # second request for the same path).
            if event.status < 400 and (
                normalize_content_type(content_type) in MANIFEST_TYPES
                or is_manifest_url(event.url)
            ):
                event.response = response
            self._events.put(event)
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
        pages: dict[str, Any] = {}
        while True:
            try:
                item = self._events.get_nowait()
            except queue.Empty:
                break
            if isinstance(item, CookieRequest):
                item.cookies = context.cookies(item.url)
                logger.debug(tr("browser_cookies", url=item.url, count=len(item.cookies)))
                item.event.set()
                continue
            if isinstance(item, NavigateRequest):
                self._navigate(context, item.url)
                continue
            events.append(item)
        for event in events:
            placeholder = tr("browser_placeholder")
            logger.debug(
                tr(
                    "browser_response",
                    status=event.status,
                    type=event.content_type or placeholder,
                    length=event.content_length
                    if event.content_length is not None
                    else placeholder,
                    url=event.url,
                )
            )
            if event.response is not None:
                if event.status < 400:
                    with contextlib.suppress(Exception):
                        event.body = event.response.text()
                event.response = None
            if event.page is not None:
                with contextlib.suppress(Exception):
                    event.page_title = event.page.title()
                # The still of the page is read here, in the thread that owns the
                # page: the card of the video shows it (spec 4.1).
                self._thumbnail_of(event.page, event.page_url)
                # The page is kept until the entries of this burst are reported: a
                # player may paint its poster a moment later, and the headers of
                # the request for the picture are read from the context here, in
                # the thread that owns it. A closed tab is not kept alive.
                pages.setdefault(event.page_url, event.page)
            page_key = (event.page_url, event.page_title)
            if page_key != self._last_page:
                self._last_page = page_key
                self.last_url = event.page_url
                logger.debug(tr("browser_page", url=event.page_url, title=event.page_title))
                self.page_changed.emit(event.page_url, event.page_title)
            self.registry.note_response(event)
        for event in events:
            outcomes = process_event(
                event,
                self.registry,
                self._fetch,
                self.quality,
                self.probe_media,
                body=event.body,
            )
            for outcome in outcomes:
                page = None
                if outcome.entry is not None:
                    page = pages.get(outcome.entry.page_url)
                self._report(outcome, page)
        # The burst is read: a page of a closed tab must not be kept by an entry.
        for event in events:
            event.page = None
        for family in self.registry.synthesize_families():
            logger.info(
                tr("browser_family", url=family.url, count=len(family.recorded))
            )
            self._attach_thumbnail(family, pages.get(family.page_url))
            self.source_found.emit(family)
            self.message.emit(
                tr("browser_hls_group", count=len(family.recorded), url=family.url)
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
            if not existing.thumbnail:
                existing.thumbnail = youtube_thumbnail(video_id)
            self._attach_thumbnail(existing, page)
            self.message.emit(tr("browser_youtube_updated", title=existing.title or video_id))
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
            # The player of the watch page serves the video over SABR/UMP, so the
            # DOM of the page has no still to read: the cover of the video is the
            # one YouTube itself uses, and it is known from the id (spec 4.1).
            thumbnail=youtube_thumbnail(video_id),
        )
        entry = result.entry
        entry.choice = Choice(kind="mp4", url=page_url, height=height)
        self._attach_thumbnail(entry, page)
        self._yt_last_id = video_id
        self._yt_failed_id = None
        if result.is_new:
            quality = ", ".join(f"{value}p" for value in heights) or tr("browser_quality_none")
            self.message.emit(tr("browser_youtube_found", quality=quality, title=entry.title))
            self.source_found.emit(entry)

    def _user_agent(self, page) -> str:
        if self._cached_ua:
            return self._cached_ua
        try:
            self._cached_ua = str(page.evaluate("navigator.userAgent"))
        except Exception:
            return ""
        return self._cached_ua

    def _thumbnail_of(self, page: Any, page_url: str, force: bool = False) -> str:
        """Address of the still the page painted for its video, ``""`` when none.

        The page already fetched the picture it shows in the player, so the read
        is a lookup in its DOM, not a guess of an address: ``og:image`` first,
        then the structured data of the page, the card of the tweet, the
        ``poster`` of the player and the frame it shows right now. A player often
        lives in an iframe, so every frame of the page is asked, up to
        :data:`THUMBNAIL_FRAMES`.

        A page is asked on a few responses, not on every one: the metadata
        appears after the markup is parsed, so a page that has no still yet is
        asked again a second later. ``force`` skips that pause when the entry of
        the page is about to be shown: the last chance to find the picture is the
        moment the card is built. A page that answered is remembered (spec 4.1).
        """
        found = self._thumbnails.get(page_url, "")
        if found and not force:
            return found
        attempts = self._thumb_attempts.get(page_url, 0)
        if attempts >= THUMBNAIL_ATTEMPTS:
            return found
        now = time.monotonic()
        if not force and now - self._thumb_last.get(page_url, 0.0) < THUMBNAIL_RETRY_SECONDS:
            return found
        self._thumb_attempts[page_url] = attempts + 1
        self._thumb_last[page_url] = now
        try:
            frames = list(getattr(page, "frames", None) or [page])[:THUMBNAIL_FRAMES]
        except Exception:
            frames = [page]
        for frame in frames:
            try:
                raw = frame.evaluate(THUMBNAIL_SCRIPT)
            except Exception:
                # A frame of another origin, a frame that is gone, a page of an
                # older browser: the next frame still may have the picture.
                continue
            if not raw:
                continue
            url = self._resolve_still(str(raw).strip(), page_url)
            if url:
                self._thumbnails[page_url] = url
                return url
        return found

    @staticmethod
    def _resolve_still(raw: str, page_url: str) -> str:
        """An absolute address of a still: a relative one is resolved, a data URL kept.

        Some players paint the frame into a canvas and hand the picture over as a
        ``data:image/...`` URL: there is nothing to fetch, the bytes are already
        in the address (spec 4.1).
        """
        if raw.startswith("data:image/"):
            return raw
        url = urljoin(page_url or "", raw)
        return url if url.startswith(("http://", "https://")) else ""

    def _attach_thumbnail(self, entry: SourceEntry, page: Any = None) -> None:
        """Give the entry the still of its page before the card is built.

        At the moment the entry is reported the page gets one last look: a player
        that paints its poster on play has had no still on the first responses.
        The headers of the request for the picture are captured here too, so the
        image host receives the ``Referer``, the ``User-Agent`` and the cookies
        the browser would have sent (spec 4.1).
        """
        if not entry.thumbnail:
            if page is not None:
                entry.thumbnail = self._thumbnail_of(page, entry.page_url, force=True)
            else:
                entry.thumbnail = self._thumbnails.get(entry.page_url, "")
        if not entry.thumbnail or entry.thumbnail.startswith("data:"):
            return
        if entry.thumbnail_headers:
            return
        # The picture is an image of the page, not the media request: the request
        # for it repeats the user agent and the language of the browser, and the
        # referer of the page itself, so a hotlink check sees the page (spec 4.1).
        source = {
            key: value
            for key, value in entry.headers.items()
            if key.lower() in ("user-agent", "accept-language")
        }
        headers = capture_headers(source, entry.page_url)
        cookies: Sequence[Mapping[str, object]] = []
        if self._context is not None:
            try:
                cookies = self._context.cookies(entry.thumbnail)
            except Exception:
                cookies = []
        entry.thumbnail_headers = merge_cookies(headers, cookies)

    def _report(self, outcome: Outcome, page: Any = None) -> None:
        if outcome.message:
            self.message.emit(outcome.message)
        if outcome.action == "show" and outcome.entry is not None:
            self._attach_thumbnail(outcome.entry, page)
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
        cookie_names = sorted(
            part.split("=", 1)[0].strip()
            for part in merged.get("Cookie", "").split(";")
            if "=" in part
        )
        logger.debug(
            tr("browser_manifest_request", url=url, cookies=", ".join(cookie_names) or "-")
        )
        try:
            return fetch_text(url, merged)
        except FetchError as exc:
            logger.debug(tr("browser_manifest_failed", url=url, error=exc))
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
