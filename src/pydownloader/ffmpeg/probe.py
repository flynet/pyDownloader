"""Reading the streams of a media file with FFmpeg (spec 5.1 p.3, 5.2 p.4).

FFmpeg prints the stream lines when it opens a file:
``Stream #0:0: Video: h264 (High) (High) ... 1920x1080, ...`` and
``Stream #0:1: Audio: aac (LC), 48000 Hz, stereo, 128 kb/s``. Only the header
of the file is read, so the probe works for a remote URL, and the same probe
opens an HLS playlist: the ``.m3u8`` is read by the HLS demuxer, and the stream
lines tell whether the stream has video at all (an audio-only stream of
SoundCloud is saved as ``.mp3``, spec 5.2 p.4).
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

from pydownloader.ffmpeg.locate import Ffmpeg, ffmpeg_env

#: Windows flag: the FFmpeg console window stays hidden (``CREATE_NO_WINDOW``).
#: A zero flag shows the console of every probe, and the program probes a stream
#: on each request the page makes, so the windows flash on the screen.
CREATE_NO_WINDOW = 0x08000000
PROBE_TIMEOUT = 25.0
_VIDEO_RE = re.compile(r"Video:.*?\s(\d{2,5})x(\d{2,5})", re.IGNORECASE)
#: The audio stream line of FFmpeg, the sign that a source is an audio file.
_AUDIO_RE = re.compile(r"Audio:", re.IGNORECASE)
#: Presence of a video stream, printed without a resolution for a codec probe.
_HAS_VIDEO_RE = re.compile(r"Video:", re.IGNORECASE)
#: ``kb/s`` of the audio line, the bitrate FFmpeg reports for the stream.
_AUDIO_BITRATE_RE = re.compile(r"Audio:.*?(\d+)\s*kb/s", re.IGNORECASE)


@dataclass(frozen=True)
class MediaInfo:
    """What FFmpeg saw in the file: the height of the video, the streams present."""

    height: int | None = None
    has_video: bool = False
    has_audio: bool = False
    #: Bitrate of the audio in kb/s, ``None`` when FFmpeg did not print it.
    audio_bitrate: int | None = None


def parse_height(text: str) -> int | None:
    """Height from the FFmpeg output, ``None`` when no video stream is found."""
    match = _VIDEO_RE.search(text)
    if not match:
        return None
    return int(match.group(2))


def parse_media(text: str) -> MediaInfo:
    """Height, streams and audio bitrate from the FFmpeg output.

    An output with no stream line means FFmpeg could not open the file: both
    flags stay ``False``, so the caller keeps the source as it was classified
    and does not call it audio on a probe that read nothing.
    """
    video = _VIDEO_RE.search(text)
    audio_bitrate = _AUDIO_BITRATE_RE.search(text)
    return MediaInfo(
        height=int(video.group(2)) if video else None,
        has_video=bool(_HAS_VIDEO_RE.search(text)),
        has_audio=bool(_AUDIO_RE.search(text)),
        audio_bitrate=int(audio_bitrate.group(1)) if audio_bitrate else None,
    )


def headers_option(headers: dict[str, str]) -> str:
    """The ``-headers`` value of FFmpeg: ``Key: Value`` lines separated by CRLF."""
    return "".join(f"{key}: {value}\r\n" for key, value in headers.items() if value)


def probe_lines(url: str, ffmpeg: Ffmpeg, headers: dict[str, str] | None = None) -> str:
    """Run FFmpeg on a URL and return its output.

    FFmpeg exits with a non-zero code when no output file is asked for, so the
    exit code is ignored here: only the printed stream information matters.
    """
    command = [str(ffmpeg.path), "-hide_banner", "-loglevel", "info"]
    header_text = headers_option(headers or {})
    if header_text:
        command += ["-headers", header_text]
    command += ["-i", url]
    try:
        process = subprocess.run(
            command,
            env=ffmpeg_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=PROBE_TIMEOUT,
            creationflags=CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return ""
    return process.stderr or ""


def probe_height(url: str, ffmpeg: Ffmpeg, headers: dict[str, str] | None = None) -> int | None:
    """Resolution of a direct MP4, ``None`` when FFmpeg cannot read the file."""
    return parse_height(probe_lines(url, ffmpeg, headers))


def probe_media(url: str, ffmpeg: Ffmpeg, headers: dict[str, str] | None = None) -> MediaInfo:
    """Streams of a file, an MP4 fragment or an HLS playlist (spec 5.2 p.4).

    FFmpeg opens ``.m3u8`` with its HLS demuxer, so the probe of a playlist says
    whether the stream carries video: a stream with audio only is a SoundCloud
    track, and it is saved as ``.mp3``. The headers of the browser request are
    passed, because a signed CDN rejects a probe without the ``Referer``.
    """
    return parse_media(probe_lines(url, ffmpeg, headers))
