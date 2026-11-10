"""Which intercepted request is a video candidate (spec 5.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydownloader.i18n import tr
from pydownloader.util.urls import (
    AUDIO_CONTENT_TYPES,
    AUDIO_EXTENSIONS,
    MP4_CONTENT_TYPE,
    is_audio_content_type,
    is_manifest_url,
    normalize_content_type,
    origin_of,
    path_extension,
)

SourceKind = Literal["hls", "dash", "mp4", "youtube"]
FRAGMENT_EXTENSIONS = {".m4s", ".m4v", ".m4a", ".ac3", ".ec3", ".ts", ".ifs", ".srt", ".vtt"}
#: Extensions of a media file that is not a manifest and not a segment.
MEDIA_EXTENSIONS = {".mp4", *AUDIO_EXTENSIONS}
#: Content types of a direct media file: video MP4 and the audio types (spec 5.2 p.4).
MEDIA_CONTENT_TYPES = {MP4_CONTENT_TYPE, *AUDIO_CONTENT_TYPES}


@dataclass(frozen=True)
class Candidate:
    """A request that passed the classification filters.

    ``headers`` carries the ``Referer``/``Origin``/``User-Agent`` of the intercepted
    request; the downloader uses them plus cookies from the browser context.
    """

    url: str
    kind: SourceKind
    page_url: str = ""
    page_title: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    content_length: int | None = None
    content_type: str | None = None
    #: ``True`` for a direct audio file: the source is saved as ``.mp3`` (spec 5.2 p.4).
    audio: bool = False


def is_media_file(ext: str, content_type: str | None) -> bool:
    """``True`` for a direct media file: an MP4 video or an audio file."""
    normalized = normalize_content_type(content_type)
    return normalized in MEDIA_CONTENT_TYPES or ext in MEDIA_EXTENSIONS


def build_headers(page_url: str, user_agent: str | None = None) -> dict[str, str]:
    """Headers copied from the browser request: ``Referer``, ``Origin``, ``User-Agent``."""
    headers: dict[str, str] = {}
    if page_url:
        headers["Referer"] = page_url
        headers["Origin"] = origin_of(page_url)
    if user_agent:
        headers["User-Agent"] = user_agent
    return headers


def media_size_skip(
    url: str,
    content_type: str | None,
    content_length: int | None,
    min_mp4_size: int,
) -> str | None:
    """Reason to log when a media file is below the size threshold (spec 5.1).

    A direct MP4 video and a direct audio file are both media files: the audio of
    SoundCloud is a small MP3, and the same threshold keeps the icons and the
    preview sounds out of the list.

    Returns ``None`` when the request is not a media file or the size is unknown,
    so the caller reports the skip in the console.
    """
    ext = path_extension(url)
    if ext in FRAGMENT_EXTENSIONS or not url:
        return None
    if not is_media_file(ext, content_type):
        return None
    if content_length is not None and content_length < min_mp4_size:
        return tr("mf_reason_small_file")
    return None


def classify(
    url: str,
    content_type: str | None = None,
    page_url: str = "",
    page_title: str = "",
    headers: dict[str, str] | None = None,
    content_length: int | None = None,
    min_mp4_size: int = 1024 * 1024,
) -> Candidate | None:
    """Return a candidate for a request, ``None`` if it is not a video source.

    Rules (spec 5.1, 5.2 p.4):
      * a candidate is HLS/DASH when the URL contains ``.m3u8``/``.mpd`` **or**
        the content type is one of the four manifest types;
      * a candidate is a direct media file when the content type is
        ``video/mp4``/an audio type **or** the path ends with ``.mp4``/``.mp3``
        (before the query); an audio file is marked ``audio``, so the download
        saves it as ``.mp3``;
      * segments (``.m4s`` and friends) are never candidates, they belong to a manifest;
      * media files under ``min_mp4_size`` are dropped as not media (size checked
        when it is known).
    """
    if not url:
        return None
    ext = path_extension(url)
    if ext in FRAGMENT_EXTENSIONS:
        return None

    normalized_type = normalize_content_type(content_type)
    manifest_type = normalized_type in {
        "application/vnd.apple.mpegurl",
        "application/x-mpegurl",
        "audio/mpegurl",
        "application/dash+xml",
    }
    manifest_ext = ext in {".m3u8", ".mpd"}

    if manifest_type or manifest_ext:
        kind: SourceKind = (
            "dash" if ext == ".mpd" or normalized_type == "application/dash+xml" else "hls"
        )
        return Candidate(
            url=url,
            kind=kind,
            page_url=page_url,
            page_title=page_title,
            headers=dict(headers or {}),
            content_length=content_length,
            content_type=content_type,
        )

    if media_size_skip(url, content_type, content_length, min_mp4_size):
        return None
    if not is_media_file(ext, normalized_type):
        return None
    audio = is_audio_content_type(content_type) or ext in AUDIO_EXTENSIONS
    return Candidate(
        url=url,
        kind="mp4",
        page_url=page_url,
        page_title=page_title,
        headers=dict(headers or {}),
        content_length=content_length,
        content_type=content_type,
        audio=audio,
    )


def is_known_manifest_url(url: str) -> bool:
    """Helper for the sniffer: the URL is a manifest by extension."""
    return is_manifest_url(url)
