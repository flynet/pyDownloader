"""The still of a video on its card (spec 4.1).

The page of the video paints a preview of it: the ``og:image`` of the markup, the
picture of a tweet card, the ``poster`` of the player. The sniffer reads the
address of that picture in the thread that owns the page and puts it on the
entry; this module reads the bytes for the card.

The window is never blocked: Qt's network manager fetches the picture in the
event loop, and the card is added only after the answer has arrived and has been
decoded, so the list never shows a card with an empty frame. A picture that did
not arrive in time is skipped: the card is added without it, because a found
source is never lost to a preview.
"""

from __future__ import annotations

import base64
import weakref
from urllib.parse import unquote_to_bytes, urljoin

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from pydownloader.manifest.registry import SourceEntry

#: How long the window waits for a still before the card is added without it.
THUMBNAIL_TIMEOUT_MS = 8000
#: The largest picture the window reads: a page may point at a full-size photo.
THUMBNAIL_MAX_BYTES = 8 * 1024 * 1024
#: What the request says about the picture it expects. AVIF is left out on
#: purpose: Qt of this build has no AVIF plugin, and a host that sees it in the
#: header answers with AVIF instead of JPEG or WebP (phncdn does), so the bytes
#: arrive and the frame stays empty (spec 4.1).
THUMBNAIL_ACCEPT = "image/webp,image/png,image/jpeg,image/gif,image/*;q=0.8,*/*;q=0.5"
#: The headers of the page that the request for its picture repeats. The rest of
#: the captured headers describe a media request (``Accept``, ``Sec-Fetch-*``),
#: not an image, so they are not sent: an image host may reject them.
THUMBNAIL_HEADERS = (
    "user-agent",
    "cookie",
    "accept-language",
    "origin",
    "referer",
)


def preview_url(entry: SourceEntry) -> str:
    """Address of the still of a video, ``""`` for an audio source or a page without one.

    A page may write the picture as a relative address or without a scheme; it is
    resolved against the page, so the card always asks for an absolute one. A
    player may also hand the frame over as a ``data:image/...`` URL: the picture
    is already in the address, it is decoded instead of fetched. An audio source
    has no still: its card is just the name of what is downloaded.
    """
    if entry.is_audio or not entry.thumbnail:
        return ""
    if entry.thumbnail.startswith("data:image/"):
        return entry.thumbnail
    url = urljoin(entry.page_url or entry.url, entry.thumbnail)
    return url if url.startswith(("http://", "https://")) else ""


def _raw(text: str) -> bytes:
    """A header value as bytes: Qt sends them as they are, so nothing is guessed."""
    return text.encode("latin-1", "ignore")


class ThumbnailLoader(QObject):
    """Reads the still of a video without blocking the window (spec 4.1).

    One signal per request: the key of the card that asked for the picture and the
    decoded image, ``None`` when the picture did not arrive or is not an image.
    The caller adds its card either way, so a broken preview never hides a source.
    """

    loaded = Signal(str, object)

    def __init__(
        self, parent: QObject | None = None, timeout_ms: int = THUMBNAIL_TIMEOUT_MS
    ) -> None:
        super().__init__(parent)
        self.timeout_ms = timeout_ms
        self._manager = QNetworkAccessManager(self)
        self._replies: dict[str, QNetworkReply] = {}
        self._timers: dict[str, QTimer] = {}

    def load(
        self,
        key: str,
        url: str,
        referer: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        """Ask for a still for ``key``: the answer comes through :attr:`loaded`.

        The request repeats the ``Referer``, the ``User-Agent``, the language and
        the cookies of the page, so a CDN that checks where the picture is shown
        from answers the same way it answers the browser. A ``data:image/...``
        URL is decoded here: the frame was already painted by the player, there
        is nothing to fetch.
        """
        self.cancel(key)
        # Qt keeps the callbacks on the objects the loader owns: the reply and the
        # timer. A lambda that holds ``self`` closes the circle, and the collector
        # then frees the loader inside the event loop, in the middle of a reply,
        # which ends the process with an abort. A weak reference keeps the circle
        # open: the loader is freed when its owner drops it, and the callback of
        # a loader that is gone is not called (spec 4.1).
        guard = weakref.ref(self)

        def on_timeout(key: str) -> None:
            target = guard()
            if target is not None:
                target._timed_out(key)

        def on_finished(own: QNetworkReply, key: str) -> None:
            target = guard()
            if target is not None:
                target._finished(key, own)

        def on_progress(own: QNetworkReply, received: int) -> None:
            target = guard()
            if target is not None:
                target._guard(own, received)

        def on_decode(key: str, source: str) -> None:
            target = guard()
            if target is not None:
                target._decode_data_url(key, source)

        if url.startswith("data:image/"):
            QTimer.singleShot(0, lambda key=key, source=url: on_decode(key, source))
            return
        request = QNetworkRequest(QUrl(url))
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
        )
        request.setRawHeader(b"Accept", THUMBNAIL_ACCEPT.encode("ascii"))
        request.setTransferTimeout(self.timeout_ms)
        if referer:
            encoded = QUrl(referer)
            request.setRawHeader(
                b"Referer",
                _raw(encoded.toString(QUrl.ComponentFormattingOption.FullyEncoded)),
            )
        for name, value in (headers or {}).items():
            if not value or name.lower() not in THUMBNAIL_HEADERS:
                continue
            header = name.encode("latin-1", "ignore")
            request.setRawHeader(header, _raw(value))
        reply = self._manager.get(request)
        self._replies[key] = reply
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda key=key: on_timeout(key))
        timer.start(self.timeout_ms)
        self._timers[key] = timer
        reply.finished.connect(lambda reply=reply, key=key: on_finished(reply, key))
        reply.downloadProgress.connect(
            lambda received, total, reply=reply: on_progress(reply, received)
        )

    def cancel(self, key: str) -> None:
        """Forget the request of ``key``: its answer is not wanted any more."""
        timer = self._timers.pop(key, None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()
        reply = self._replies.pop(key, None)
        if reply is not None:
            reply.abort()
            reply.deleteLater()

    def cancel_all(self) -> None:
        for key in list(self._replies):
            self.cancel(key)

    def _guard(self, reply: QNetworkReply, received: int) -> None:
        """Stop a picture that is larger than the window reads (a full-size photo)."""
        if received > THUMBNAIL_MAX_BYTES:
            reply.abort()

    def _decode_data_url(self, key: str, url: str) -> None:
        """Decode a frame the player handed over as a ``data:image/...`` URL.

        The picture is already painted by the page, so there is no request: the
        bytes of the address are decoded and the card is built as with a fetched
        still. A broken address is the same as an absent picture (spec 4.1).
        """
        pixmap: QPixmap | None = None
        try:
            header, _, payload = url.partition(",")
            if ";base64" in header.lower():
                data = base64.b64decode(payload)
            else:
                data = unquote_to_bytes(payload)
            if 0 < len(data) <= THUMBNAIL_MAX_BYTES:
                image = QPixmap()
                if image.loadFromData(data):
                    pixmap = image
        except ValueError:
            pixmap = None
        self.loaded.emit(key, pixmap)

    def _timed_out(self, key: str) -> None:
        """The picture did not arrive in time: the card is added without it (spec 4.1)."""
        self._timers.pop(key, None)
        reply = self._replies.pop(key, None)
        if reply is not None:
            reply.abort()
            reply.deleteLater()
        self.loaded.emit(key, None)

    def _finished(self, key: str, reply: QNetworkReply) -> None:
        if self._replies.get(key) is not reply:
            # Cancelled or replaced while it was on its way: nobody waits for it.
            reply.deleteLater()
            return
        del self._replies[key]
        timer = self._timers.pop(key, None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()
        pixmap: QPixmap | None = None
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = bytes(reply.readAll().data())
            if data:
                image = QPixmap()
                if image.loadFromData(data):
                    pixmap = image
        reply.deleteLater()
        self.loaded.emit(key, pixmap)


__all__ = [
    "THUMBNAIL_MAX_BYTES",
    "THUMBNAIL_TIMEOUT_MS",
    "ThumbnailLoader",
    "preview_url",
]
