"""Data model of an MPEG-DASH manifest (``.mpd``).

All URLs are absolute and already resolved against the manifest URL and the
``BaseURL`` chain, so a downloader does not need to re-read the XML.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydownloader.util.ranges import ByteRange

ContentType = Literal["video", "audio", "text"]
MPDType = Literal["static", "dynamic"]


@dataclass(frozen=True)
class DashInit:
    """Init segment (``SegmentTemplate/Initialization`` or ``SegmentBase/Initialization``)."""

    url: str
    byte_range: ByteRange | None = None


@dataclass(frozen=True)
class DashSegment:
    """One DASH segment: ``number`` for ``$Number$``, ``start`` in seconds."""

    url: str
    duration: float
    number: int | None = None
    start: float | None = None
    byte_range: ByteRange | None = None


@dataclass
class DashRepresentation:
    """A single ``Representation`` with its resolved segment list.

    ``progressive`` means the stream is one file without a segment list
    (``SegmentBase``), so it is downloaded as a plain MP4.
    """

    id: str
    content_type: ContentType
    mime_type: str = ""
    codecs: str | None = None
    width: int | None = None
    height: int | None = None
    bandwidth: int = 0
    language: str | None = None
    init: DashInit | None = None
    segments: list[DashSegment] = field(default_factory=list)
    progressive: bool = False
    progressive_url: str | None = None
    #: ``ContentProtection`` entries as ``(schemeIdUri, value)``.
    content_protection: list[tuple[str, str]] = field(default_factory=list)

    def is_video(self) -> bool:
        return self.content_type == "video"

    def is_audio(self) -> bool:
        return self.content_type == "audio"


@dataclass
class DashPeriod:
    id: str = ""
    start: float | None = None
    representations: list[DashRepresentation] = field(default_factory=list)

    def videos(self) -> list[DashRepresentation]:
        return [r for r in self.representations if r.is_video()]

    def audios(self) -> list[DashRepresentation]:
        return [r for r in self.representations if r.is_audio()]


@dataclass
class DashManifest:
    url: str
    mpd_type: MPDType = "static"
    periods: list[DashPeriod] = field(default_factory=list)
    #: ``MPD@mediaPresentationDuration`` in seconds, ``None`` if the attribute is absent.
    media_presentation_duration: float | None = None

    @property
    def is_live(self) -> bool:
        return self.mpd_type == "dynamic"

    def has_video(self) -> bool:
        """``True`` when one representation of any Period is a video (spec 5.2 p.4)."""
        return any(bool(p.videos()) for p in self.periods)

    def has_audio(self) -> bool:
        """``True`` when one representation of any Period is audio."""
        return any(bool(p.audios()) for p in self.periods)

    def available_heights(self) -> list[int]:
        heights = [r.height for p in self.periods for r in p.videos() if r.height is not None]
        return sorted(set(heights), reverse=True)

    def content_protection(self) -> list[tuple[str, str]]:
        """All ``ContentProtection`` entries found in every representation."""
        found: list[tuple[str, str]] = []
        for period in self.periods:
            for rep in period.representations:
                found.extend(rep.content_protection)
        return found
