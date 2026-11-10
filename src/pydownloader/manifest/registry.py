"""Registry of found sources: duplicate detection, MP4 ``Range`` merging, fragment skipping.

Spec 5.1/5.2 p.4:
  * duplicates are removed by a normalized URL (volatile query tokens are dropped);
  * the browser asks for the same MP4 file many times with ``Range`` requests,
    so requests with the same normalized URL are merged into one entry, the full
    size comes from ``Content-Range`` (``bytes 0-1/12345678``) or ``Content-Length``;
  * ``.m4s``/``.mp4`` fragments belonging to an already registered manifest do not
    appear in the list.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from itertools import count
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from pydownloader.download.http import capture_headers
from pydownloader.manifest.detector import Candidate, SourceKind
from pydownloader.manifest.quality import Choice
from pydownloader.util.urls import (
    SEGMENT_EXTENSIONS,
    base_dir_url,
    dir_prefix,
    last_segment,
    normalize_url,
    path_extension,
    path_of,
)

if TYPE_CHECKING:
    from pydownloader.browser.events import ResponseEvent

logger = logging.getLogger("pydownloader.registry")

MAX_PATH_LIMIT = 260
#: Segment GETs from one directory that synthesize an HLS row when no playlist was seen.
FAMILY_MIN_SEGMENTS = 3


@dataclass
class SourceEntry:
    """One row of the upper section (a card in the UI, M7)."""

    id: str
    kind: SourceKind
    url: str
    normalized: str
    title: str = ""
    page_url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    size: int | None = None
    height: int | None = None
    duration: float | None = None
    range_requests: int = 1
    skipped: bool = False
    #: Selected video/audio track, filled by the pipeline after the manifest is parsed.
    choice: Choice | None = None
    #: Signed URLs seen in browser traffic: path -> URL, in capture order.
    #: A CDN that signs every path individually (phncdn) rejects constructed URLs,
    #: so the downloader prefers these exact URLs.
    recorded: dict[str, str] = field(default_factory=dict)
    #: ``True`` for an HLS row synthesized from segment GETs (playlist fetched in-page).
    family: bool = False
    #: Raw player response of a YouTube source, consumed by the download plan.
    payload: str = ""

    def record(self, url: str) -> None:
        """Remember the exact URL of a file, keyed by its path (capture order kept).

        The path, not the file name, is the key: adaptive streaming fetches the
        same segment names from the 720p and 1080p directories, and a name-only
        key would mix the resolutions.
        """
        key = path_of(url)
        if key:
            self.recorded[key] = url
            logger.debug("Записан URL %s -> %s", key, url)

    def recorded_url(self, url: str) -> str | None:
        """Exact signed URL for a constructed one, ``None`` when nothing was recorded."""
        found = self.recorded.get(path_of(url))
        if found:
            return found
        if url in self.recorded.values():
            return url
        # A constructed URL may differ in path encoding: accept a unique recorded
        # file with the same name, but never guess between two directories.
        name = last_segment(url)
        matches = [value for key, value in self.recorded.items() if last_segment(key) == name]
        return matches[0] if len(matches) == 1 else None

    def display_size(self) -> str:
        if self.size is None:
            return ""
        mb = self.size / (1024 * 1024)
        return f"{mb:.1f} MB"

    def display_quality(self) -> str:
        return f"{self.height}p" if self.height else "неизвестно"


@dataclass
class AddResult:
    entry: SourceEntry
    is_new: bool
    merged: bool = False
    reason: str = ""


def _path_prefix(url: str) -> str:
    """Directory prefix of a URL, used to recognize segments of a manifest."""
    parts = urlsplit(url)
    path = parts.path
    trimmed = path.rsplit("/", 1)[0] if "/" in path else ""
    return f"{parts.scheme}://{parts.netloc}{trimmed}/"


class SourceRegistry:
    """All sources found by the sniffer, with the filters of spec 5.1 applied."""

    def __init__(self, min_mp4_size: int = 1024 * 1024) -> None:
        self.min_mp4_size = min_mp4_size
        self._entries: dict[str, SourceEntry] = {}
        self._prefixes: set[str] = set()
        #: Directory -> entry owning the files below it (signed URL recording).
        self._owners: dict[str, SourceEntry] = {}
        #: Directory -> file name -> URL of segment GETs seen before any playlist.
        self._family: dict[str, dict[str, str]] = {}
        self._family_meta: dict[str, ResponseEvent] = {}
        self._counter = count(1)

    def entries(self) -> list[SourceEntry]:
        """Registration order."""
        return list(self._entries.values())

    def get(self, normalized: str) -> SourceEntry | None:
        return self._entries.get(normalized)

    def remove(self, normalized: str) -> None:
        """Drop an entry that was registered before the filters rejected it."""
        entry = self._entries.pop(normalized, None)
        if entry is None:
            return
        for directory, owner in list(self._owners.items()):
            if owner is entry:
                del self._owners[directory]

    def is_fragment_of_known(self, url: str) -> bool:
        """A segment of an already registered manifest (``.m4s``/``.mp4`` under its directory)."""
        prefix = _path_prefix(url)
        return prefix in self._prefixes

    def add_manifest(self, candidate: Candidate) -> AddResult:
        """Register an HLS/DASH manifest and remember its directory prefix."""
        normalized = normalize_url(candidate.url)
        existing = self._entries.get(normalized)
        if existing:
            return AddResult(entry=existing, is_new=False)
        if candidate.kind == "hls":
            # A playlist in a directory already owned by a stream (the media
            # playlist next to the master, an audio track) is a part of it, not
            # a second row: its URL is recorded for the downloader instead.
            owner = self._owners.get(_path_prefix(candidate.url))
            if owner is not None:
                owner.record(candidate.url)
                logger.debug(
                    "Плейлист %s принадлежит уже найденному потоку %s",
                    candidate.url,
                    owner.url,
                )
                return AddResult(
                    entry=owner, is_new=False, reason="плейлист уже найденного потока"
                )
        entry = self._entry(candidate, normalized)
        self._entries[normalized] = entry
        self._prefixes.add(_path_prefix(candidate.url))
        self._prefixes.add(base_dir_url(candidate.url))
        self._owners[_path_prefix(candidate.url)] = entry
        self.adopt_pending(candidate.url, entry)
        logger.debug("Новый манифест %s: %s", candidate.kind, candidate.url)
        return AddResult(entry=entry, is_new=True)

    def add_mp4(self, candidate: Candidate) -> AddResult:
        """Register a direct MP4, merging repeated ``Range`` requests of the same file.

        Returns ``is_new=False`` when the request is a duplicate, ``merged=True``
        when it is a new ``Range`` of an already known file.
        """
        normalized = normalize_url(candidate.url)
        existing = self._entries.get(normalized)
        size = candidate.content_length
        if existing:
            if size is not None and existing.size is not None:
                existing.size = max(existing.size, size)
            elif size is not None:
                existing.size = size
            existing.range_requests += 1
            return AddResult(entry=existing, is_new=False, merged=True)
        if self.is_fragment_of_known(candidate.url):
            return AddResult(
                entry=SourceEntry(id="", kind="mp4", url=candidate.url, normalized=normalized),
                is_new=False,
                reason="фрагмент уже найденного манифеста",
            )
        if size is not None and size < self.min_mp4_size:
            return AddResult(
                entry=SourceEntry(id="", kind="mp4", url=candidate.url, normalized=normalized),
                is_new=False,
                reason="файл меньше порога, не видео",
            )
        entry = self._entry(candidate, normalized)
        entry.size = size
        self._entries[normalized] = entry
        return AddResult(entry=entry, is_new=True)

    def add(self, candidate: Candidate) -> AddResult:
        """Register any candidate, dispatching on its kind."""
        if candidate.kind == "mp4":
            return self.add_mp4(candidate)
        return self.add_manifest(candidate)

    def remember_prefix(self, url: str, entry: SourceEntry | None = None) -> None:
        """Remember the directory of a manifest parsed from a playlist."""
        prefix = _path_prefix(url)
        self._prefixes.add(prefix)
        self._prefixes.add(base_dir_url(url))
        if entry is not None:
            self._owners[prefix] = entry
            self.adopt_pending(url, entry)

    def adopt_pending(self, url: str, entry: SourceEntry) -> None:
        """Attach the URLs seen before the entry was registered to its recorded map."""
        for directory in {dir_prefix(url), _path_prefix(url)}:
            pending = self._family.pop(directory, None)
            if not pending:
                continue
            for value in pending.values():
                entry.record(value)
            self._family_meta.pop(directory, None)

    def owner_for(self, url: str) -> SourceEntry | None:
        """Entry owning the directory of a URL, searching the parent directories."""
        parts = urlsplit(url)
        path = parts.path
        while "/" in path:
            path = path.rsplit("/", 1)[0]
            owner = self._owners.get(f"{parts.scheme}://{parts.netloc}{path}/")
            if owner is not None:
                return owner
        return None

    def add_custom(
        self,
        *,
        kind: SourceKind,
        url: str,
        normalized: str,
        title: str = "",
        page_url: str = "",
        headers: dict[str, str] | None = None,
        height: int | None = None,
        duration: float | None = None,
        payload: str = "",
        family: bool = False,
    ) -> AddResult:
        """Register an entry built outside the classifier (YouTube, segment family)."""
        existing = self._entries.get(normalized)
        if existing is not None:
            return AddResult(entry=existing, is_new=False)
        entry = SourceEntry(
            id=f"s{next(self._counter)}",
            kind=kind,
            url=url,
            normalized=normalized,
            title=title,
            page_url=page_url,
            headers=dict(headers or {}),
            height=height,
            duration=duration,
            payload=payload,
            family=family,
        )
        self._entries[normalized] = entry
        return AddResult(entry=entry, is_new=True)

    def note_response(self, event: ResponseEvent) -> None:
        """Record the exact URL of every manifest/segment/key request in browser traffic.

        Only recording happens here: an entry can be synthesized later by
        :meth:`synthesize_families`, once the manifest events of the same burst
        have been processed (otherwise a playlist and its segments would produce
        two rows for one stream).
        """
        if event.status >= 400 or not event.url:
            return
        url = event.url
        ext = path_extension(url)
        name = last_segment(url)
        if not (
            ext in SEGMENT_EXTENSIONS
            or ext in {".key", ".m3u8", ".mpd"}
            or (ext == ".mp4" and name.lower().startswith("init"))
        ):
            return
        owner = self.owner_for(url)
        if owner is not None:
            owner.record(url)
            return
        # No entry owns this directory yet: keep the URL until a playlist appears
        # (adopted by the entry) or until enough segments synthesize a family.
        directory = _path_prefix(url)
        self._family.setdefault(directory, {})[name] = url
        self._family_meta.setdefault(directory, event)
        logger.debug("Сегмент до манифеста (%s): %s", directory, url)

    def synthesize_families(self) -> list[SourceEntry]:
        """Turn directories with enough segment GETs into HLS entries.

        hls.js fetches the playlist in-page, so Playwright sees only the segment
        requests. Three segments from one directory are enough to know that a
        stream exists; the recorded URLs are the download plan (init first).
        """
        created: list[SourceEntry] = []
        for directory, seen in list(self._family.items()):
            media = [url for url in seen.values() if path_extension(url) in SEGMENT_EXTENSIONS]
            if len(media) < FAMILY_MIN_SEGMENTS:
                continue
            owner = self.owner_for(media[0])
            if owner is not None:
                for url in seen.values():
                    owner.record(url)
                self._family.pop(directory, None)
                self._family_meta.pop(directory, None)
                continue
            event = self._family_meta.get(directory)
            if event is None:
                continue
            last = media[-1]
            query = urlsplit(last).query
            master = f"{directory}index-v1-a1.m3u8" + (f"?{query}" if query else "")
            headers = capture_headers(event.request_headers, event.page_url)
            result = self.add_custom(
                kind="hls",
                url=master,
                normalized=normalize_url(master),
                title=event.page_title,
                page_url=event.page_url,
                headers=headers,
                family=True,
            )
            entry = result.entry
            if result.is_new:
                for url in seen.values():
                    entry.record(url)
                created.append(entry)
            self._owners[directory] = entry
            self._prefixes.add(directory)
            self._family.pop(directory, None)
            self._family_meta.pop(directory, None)
        return created

    def _entry(self, candidate: Candidate, normalized: str) -> SourceEntry:
        return SourceEntry(
            id=f"s{next(self._counter)}",
            kind=candidate.kind,
            url=candidate.url,
            normalized=normalized,
            title=candidate.page_title,
            page_url=candidate.page_url,
            headers=dict(candidate.headers),
            size=candidate.content_length,
        )
