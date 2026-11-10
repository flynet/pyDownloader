"""Parser of a YouTube player response (inner-tube ``/youtubei/v1/player`` answer).

Real-site facts (Nov 2026, verified by the Java harness):
  * the WEB player response carries no per-format URLs: YouTube serves media
    over server-side ABR (SABR/UMP), so the sniffer only sees ``POST
    /videoplayback`` and never a manifest;
  * the VISIONOS inner-tube client still returns classic signed URLs for every
    adaptive format, provided the request carries the page's ``visitorData``;
  * adaptive formats are video-only or audio-only, so both tracks are downloaded
    separately and muxed with FFmpeg (``-c copy``).

Signed URLs are kept in memory only and never logged.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

#: Player status values that mean "nothing can be downloaded".
REASONS = {
    "LOGIN_REQUIRED": "YouTube требует входа в аккаунт",
    "UNPLAYABLE": "видео недоступно для воспроизведения",
    "ERROR": "ошибка воспроизведения YouTube",
    "EMPTY": "пустой ответ плеера",
    "MALFORMED": "не удалось разобрать ответ плеера",
    "PARSE_ERROR": "не удалось разобрать ответ плеера",
}


@dataclass(frozen=True)
class Format:
    """One adaptive/progressive format from ``streamingData``."""

    itag: int
    mime_type: str
    url: str | None
    width: int = 0
    height: int = 0
    fps: int = 0
    bitrate: int = 0
    content_length: int = 0
    quality_label: str = ""
    audio_quality: str = ""
    audio_sample_rate: int = 0
    has_video: bool = False
    has_audio: bool = False
    cipher_only: bool = False

    @property
    def container(self) -> str:
        """Container family: ``mp4`` or ``webm`` (tracks must share it for ``-c copy``)."""
        mime = self.mime_type.lower()
        if "webm" in mime:
            return "webm"
        if "mp4" in mime:
            return "mp4"
        if "ogg" in mime:
            return "ogg"
        return "other"


@dataclass
class Player:
    """Parsed player response: what the download plan needs."""

    video_id: str = ""
    title: str = ""
    status: str = "UNKNOWN"
    live: bool = False
    duration: float = 0.0
    formats: list[Format] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "OK"


def _as_int(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _as_float(value: object) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def _as_dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _formats_from(items: object) -> list[Format]:
    if not isinstance(items, list):
        return []
    formats: list[Format] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        mime = str(item.get("mimeType") or "")
        url = item.get("url")
        has_video = mime.lower().startswith("video/")
        has_audio = mime.lower().startswith("audio/")
        formats.append(
            Format(
                itag=_as_int(item.get("itag")),
                mime_type=mime,
                url=url if isinstance(url, str) and url else None,
                width=_as_int(item.get("width")),
                height=_as_int(item.get("height")),
                fps=_as_int(item.get("fps")),
                bitrate=_as_int(item.get("bitrate")),
                content_length=_as_int(item.get("contentLength")),
                quality_label=str(item.get("qualityLabel") or ""),
                audio_quality=str(item.get("audioQuality") or ""),
                audio_sample_rate=_as_int(item.get("audioSampleRate")),
                has_video=has_video,
                has_audio=has_audio,
                cipher_only=not url and "signatureCipher" in item,
            )
        )
    return formats


def parse_player(text: str | None) -> Player:
    """Parse the raw JSON; never raises on malformed input."""
    if not text:
        return Player(status="EMPTY")
    try:
        root = json.loads(text)
    except (ValueError, TypeError):
        return Player(status="MALFORMED")
    if not isinstance(root, dict):
        return Player(status="MALFORMED")
    details = _as_dict(root.get("videoDetails"))
    play = _as_dict(root.get("playabilityStatus"))
    streaming = _as_dict(root.get("streamingData"))
    formats: list[Format] = []
    formats.extend(_formats_from(streaming.get("adaptiveFormats")))
    formats.extend(_formats_from(streaming.get("formats")))
    return Player(
        video_id=str(details.get("videoId") or ""),
        title=str(details.get("title") or ""),
        status=str(play.get("status") or "UNKNOWN"),
        live=bool(streaming.get("isLiveContent")),
        duration=_as_float(details.get("lengthSeconds")),
        formats=formats,
    )


def _better_video(candidate: Format, best: Format | None) -> bool:
    if best is None:
        return True
    if candidate.height != best.height:
        return candidate.height > best.height
    candidate_mp4 = candidate.container == "mp4"
    best_mp4 = best.container == "mp4"
    if candidate_mp4 != best_mp4:
        return candidate_mp4
    return candidate.bitrate > best.bitrate


def pick_video(player: Player, cap: int) -> Format | None:
    """Highest height not above ``cap``; when all are above it, the best available.

    Equal heights are broken by container (MP4 wins, so the result can be muxed
    into an MP4 container without re-encoding) and then by bitrate.
    """
    candidates = [
        fmt
        for fmt in player.formats
        if fmt.has_video and fmt.url is not None and fmt.height > 0
    ]
    if not candidates:
        return None
    best: Format | None = None
    for fmt in candidates:
        if cap > 0 and fmt.height > cap:
            continue
        if _better_video(fmt, best):
            best = fmt
    if best is None:
        for fmt in candidates:
            if _better_video(fmt, best):
                best = fmt
    return best


def pick_audio(player: Player) -> Format | None:
    """Highest-bitrate audio track; MP4 (m4a/aac) wins over WebM (opus)."""
    best: Format | None = None
    for fmt in player.formats:
        if not fmt.has_audio or fmt.has_video or fmt.url is None:
            continue
        if best is None:
            best = fmt
            continue
        fmt_mp4 = fmt.container == "mp4"
        best_mp4 = best.container == "mp4"
        if fmt_mp4 != best_mp4:
            if fmt_mp4:
                best = fmt
            continue
        if fmt.bitrate > best.bitrate:
            best = fmt
    return best


def qualities(player: Player) -> list[int]:
    """Distinct heights of usable video formats, descending."""
    heights = {
        fmt.height
        for fmt in player.formats
        if fmt.has_video and fmt.url is not None and fmt.height > 0
    }
    return sorted(heights, reverse=True)


def reason_of(player: Player) -> str:
    """Human-readable reason for a non-OK playability status."""
    return REASONS.get(player.status, f"YouTube: {player.status}")
