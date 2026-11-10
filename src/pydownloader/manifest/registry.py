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

from dataclasses import dataclass, field
from itertools import count
from urllib.parse import urlsplit

from pydownloader.manifest.detector import Candidate, SourceKind
from pydownloader.util.urls import base_dir_url, normalize_url

MAX_PATH_LIMIT = 260


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
        self._counter = count(1)

    def entries(self) -> list[SourceEntry]:
        """Registration order."""
        return list(self._entries.values())

    def get(self, normalized: str) -> SourceEntry | None:
        return self._entries.get(normalized)

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
        entry = self._entry(candidate, normalized)
        self._entries[normalized] = entry
        self._prefixes.add(_path_prefix(candidate.url))
        self._prefixes.add(base_dir_url(candidate.url))
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

    def remember_prefix(self, url: str) -> None:
        """Remember the directory of a manifest parsed from a playlist."""
        self._prefixes.add(_path_prefix(url))
        self._prefixes.add(base_dir_url(url))

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
