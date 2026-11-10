"""Which intercepted request is a video candidate (spec 5.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydownloader.util.urls import (
    MP4_CONTENT_TYPE,
    is_manifest_url,
    normalize_content_type,
    origin_of,
    path_extension,
)

SourceKind = Literal["hls", "dash", "mp4"]
FRAGMENT_EXTENSIONS = {".m4s", ".m4v", ".m4a", ".ac3", ".ec3", ".ts", ".ifs", ".srt", ".vtt"}


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


def build_headers(page_url: str, user_agent: str | None = None) -> dict[str, str]:
    """Headers copied from the browser request: ``Referer``, ``Origin``, ``User-Agent``."""
    headers: dict[str, str] = {}
    if page_url:
        headers["Referer"] = page_url
        headers["Origin"] = origin_of(page_url)
    if user_agent:
        headers["User-Agent"] = user_agent
    return headers


def mp4_size_skip(
    url: str,
    content_type: str | None,
    content_length: int | None,
    min_mp4_size: int,
) -> str | None:
    """Reason to log when the request is an MP4 below the size threshold (spec 5.1).

    Returns ``None`` when the request is not an MP4 or the size is unknown,
    so the caller reports the skip in the console.
    """
    ext = path_extension(url)
    if ext in FRAGMENT_EXTENSIONS or not url:
        return None
    if not (normalize_content_type(content_type) == MP4_CONTENT_TYPE or ext == ".mp4"):
        return None
    if content_length is not None and content_length < min_mp4_size:
        return "файл меньше порога, не видео"
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

    Rules (spec 5.1):
      * a candidate is HLS/DASH when the URL contains ``.m3u8``/``.mpd`` **or**
        the content type is one of the four manifest types;
      * a candidate is a direct MP4 when the content type is ``video/mp4``
        **or** the path ends with ``.mp4`` (before the query);
      * segments (``.m4s`` and friends) are never candidates, they belong to a manifest;
      * MP4 files under ``min_mp4_size`` are dropped as not video (size checked
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

    if mp4_size_skip(url, content_type, content_length, min_mp4_size):
        return None
    if not (normalized_type == MP4_CONTENT_TYPE or ext == ".mp4"):
        return None
    return Candidate(
        url=url,
        kind="mp4",
        page_url=page_url,
        page_title=page_title,
        headers=dict(headers or {}),
        content_length=content_length,
        content_type=content_type,
    )


def is_known_manifest_url(url: str) -> bool:
    """Helper for the sniffer: the URL is a manifest by extension."""
    return is_manifest_url(url)
