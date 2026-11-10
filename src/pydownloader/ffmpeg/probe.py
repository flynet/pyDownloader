"""Reading the resolution of a direct MP4 with FFmpeg (spec 5.1 p.3).

FFmpeg prints the stream line when it opens a file:
``Stream #0:0: Video: h264 (High) (High) ... 1920x1080, ...``. Only the header
of the file is read, so the probe works for a remote URL.
"""

from __future__ import annotations

import re
import subprocess

from pydownloader.ffmpeg.locate import Ffmpeg, ffmpeg_env

#: Windows flag: the FFmpeg console window stays hidden.
CREATE_NO_WINDOW = 0x00000000
PROBE_TIMEOUT = 25.0
_VIDEO_RE = re.compile(r"Video:.*?\s(\d{2,5})x(\d{2,5})", re.IGNORECASE)


def parse_height(text: str) -> int | None:
    """Height from the FFmpeg output, ``None`` when no video stream is found."""
    match = _VIDEO_RE.search(text)
    if not match:
        return None
    return int(match.group(2))


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
