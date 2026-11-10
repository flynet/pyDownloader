"""Data model of an HLS playlist.

Everything is stored with absolute URLs already resolved against the manifest URL,
so a downloader does not need to know the playlist location.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydownloader.util.ranges import ByteRange

MediaKind = Literal["master", "media"]


@dataclass(frozen=True)
class Key:
    """``EXT-X-KEY`` entry. ``iv`` is an integer, ``None`` means "derive from the sequence"."""

    method: str
    uri: str | None = None
    iv: int | None = None
    key_format: str | None = None
    key_format_versions: str | None = None

    @property
    def is_plain(self) -> bool:
        return self.method.upper() == "NONE"

    @property
    def is_aes128(self) -> bool:
        return self.method.upper() == "AES-128"


@dataclass(frozen=True)
class InitSegment:
    """``EXT-X-MAP`` (fMP4 init segment), optionally a byte range inside a single file."""

    url: str
    byte_range: ByteRange | None = None


@dataclass(frozen=True)
class Segment:
    """One media segment with the key that applies to it."""

    url: str
    duration: float
    sequence: int
    index: int
    byte_range: ByteRange | None = None
    key: Key | None = None
    init: InitSegment | None = None


@dataclass(frozen=True)
class Media:
    """``EXT-X-MEDIA`` (alternate audio/subtitle track)."""

    type: str
    group_id: str
    url: str | None = None
    language: str | None = None
    name: str | None = None
    default: bool = False
    autoselect: bool = True
    forced: bool = False


@dataclass(frozen=True)
class Variant:
    """``EXT-X-STREAM-INF`` entry of a master playlist."""

    url: str
    bandwidth: int
    width: int | None = None
    height: int | None = None
    audio_group: str | None = None
    subtitles_group: str | None = None
    codecs: str | None = None


@dataclass
class Playlist:
    """Parsed playlist: master (with variants) or media (with segments)."""

    kind: MediaKind
    url: str
    variants: list[Variant] = field(default_factory=list)
    media: list[Media] = field(default_factory=list)
    segments: list[Segment] = field(default_factory=list)
    init: InitSegment | None = None
    key: Key | None = None
    has_endlist: bool = False
    target_duration: float | None = None
    media_sequence: int = 0

    @property
    def is_live(self) -> bool:
        """A media playlist without ``#EXT-X-ENDLIST`` is a live stream.

        A master playlist has no end-list marker, so for a master the answer is
        "unknown": the selected variant must be fetched first
        (:attr:`needs_live_probe`).
        """
        if self.kind == "media":
            return not self.has_endlist
        return False

    @property
    def needs_live_probe(self) -> bool:
        return self.kind == "master"

    def available_heights(self) -> list[int]:
        """Heights of all variants, sorted, for the "no 1080p" console message."""
        heights = [v.height for v in self.variants if v.height is not None]
        return sorted(set(heights), reverse=True)

    def audio_tracks(self, group_id: str | None) -> list[Media]:
        if group_id is None:
            return []
        return [m for m in self.media if m.type.upper() == "AUDIO" and m.group_id == group_id]
