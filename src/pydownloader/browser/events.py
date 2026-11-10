"""Events produced by the network sniffer.

The Playwright handlers only build this dataclass and put it into a queue, so
they return immediately (spec 4.4). Everything that needs a blocking call
(``page.title()``, ``context.cookies()``, reading the manifest body) happens
later in the pump loop of the sniffer thread.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from pydownloader.util.ranges import content_range_total


@dataclass
class ResponseEvent:
    """One intercepted HTTP response, reduced to what the filters need."""

    url: str
    page_url: str = ""
    page_title: str = ""
    status: int = 200
    content_type: str | None = None
    content_length: int | None = None
    content_range: str | None = None
    #: Headers of the browser request that produced the response: ``Referer``,
    #: ``Origin``, ``User-Agent``, ``Cookie`` are reused for the download (spec 6.1).
    request_headers: dict[str, str] = field(default_factory=dict)
    #: Page object of the page that made the request; used only inside the
    #: sniffer thread (``page.title()`` is a blocking call, so the title is
    #: resolved in the pump loop, not in the handler).
    page: Any = None
    #: Playwright ``Response`` of a manifest, read in the pump loop (the body the
    #: browser already downloaded is the most reliable copy: a signed CDN may
    #: reject a second request for the same path).
    response: Any = None
    #: Manifest body captured from the intercepted response, ``None`` when the
    #: response was not a manifest or the body could not be read.
    body: str | None = None

    def total_size(self) -> int | None:
        """Full file size: ``Content-Range`` total, otherwise ``Content-Length``."""
        if self.content_range:
            total = content_range_total(self.content_range)
            if total is not None:
                return total
        return self.content_length


@dataclass
class CookieRequest:
    """Asynchronous request for ``context.cookies(url)`` handled by the pump loop.

    ``context`` objects belong to the event loop of the sniffer thread, so the
    cookies can only be read there; the caller (a download worker) waits on
    ``event``.
    """

    url: str
    cookies: Sequence[Mapping[str, object]] = field(default_factory=list)
    event: threading.Event = field(default_factory=threading.Event)
