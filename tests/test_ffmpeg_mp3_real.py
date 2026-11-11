"""Real FFmpeg: an audio-only HLS stream becomes a valid MP3 (spec 6.4, 5.2 p.4).

The test runs the binary the application runs (``bin/ffmpeg.exe`` of the build,
``ffmpeg`` on PATH, the ``imageio-ffmpeg`` binary of a source checkout). It is
skipped when no binary is available, so CI without FFmpeg does not fail. The
mocked tests of ``test_ffmpeg.py`` check the command lines; this file checks that
the commands produce a playable file, which is the part that broke on SoundCloud
(the AAC bitstream filter on an MP3 stream ends with "Invalid argument" and an
empty output file, spec 6.4 p.3).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from pydownloader.ffmpeg.locate import Ffmpeg, locate_ffmpeg
from pydownloader.ffmpeg.mux import assemble
from pydownloader.ffmpeg.probe import probe_lines, probe_media

MIN_AUDIO_SECONDS = 3.0
_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", re.IGNORECASE)


def seconds_of(text: str) -> float:
    """Seconds of the ``Duration:`` line FFmpeg prints for a file."""
    match = _DURATION_RE.search(text)
    if not match:
        return 0.0
    return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))


@pytest.fixture(scope="module")
def ffmpeg() -> Ffmpeg:
    """The FFmpeg binary of the environment, skipped when there is none."""
    try:
        return locate_ffmpeg(None)
    except Exception as exc:  # the reason is shown as the skip reason
        pytest.skip(f"no FFmpeg binary: {exc}")


def run_ffmpeg(ffmpeg: Ffmpeg, args: list[str], cwd: Path) -> None:
    """FFmpeg in the working directory, the console window stays hidden."""
    process = subprocess.run(
        [str(ffmpeg.path), "-hide_banner", "-loglevel", "warning", "-y", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd),
        creationflags=0x08000000,
    )
    if process.returncode != 0:
        pytest.fail((process.stderr or "").strip())


def make_audio_hls(ffmpeg: Ffmpeg, work: Path, kind: str) -> list[Path]:
    """Write an audio-only HLS of four seconds, return the files of the stream.

    ``kind`` is ``fmp4`` (fragmented MP4 with a separate ``init.mp4``) or
    ``mpegts``. The init segment is first, as the plan of an HLS puts it.
    """
    suffix = ".m4s" if kind == "fmp4" else ".ts"
    run_ffmpeg(
        ffmpeg,
        [
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=4",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-f",
            "hls",
            "-hls_segment_type",
            kind,
            "-hls_list_size",
            "0",
            "-hls_segment_filename",
            f"seg%03d{suffix}",
            "test.m3u8",
        ],
        work,
    )
    segments = sorted(work.glob(f"seg*{suffix}"))
    init = work / "init.mp4"
    return ([init] if init.exists() else []) + segments


def check_mp3(ffmpeg: Ffmpeg, out: Path, segments: list[Path]) -> None:
    """The merged stream is assembled to MP3, and the file is audio without video."""
    assert segments, "the test HLS has no segments"
    result = assemble([], out, ffmpeg, out.parent, segments, 192)
    assert result.out_path == out
    assert out.stat().st_size > 1000, "FFmpeg wrote an empty MP3"
    lines = probe_lines(str(out), ffmpeg)
    info = probe_media(str(out), ffmpeg)
    assert info.has_audio, "the MP3 has no audio stream"
    assert not info.has_video, "the MP3 has a video stream"
    assert seconds_of(lines) >= MIN_AUDIO_SECONDS, f"the MP3 is {seconds_of(lines)} s long"


def test_audio_hls_of_fmp4_fragments_is_a_valid_mp3(ffmpeg: Ffmpeg, tmp_path: Path):
    segments = make_audio_hls(ffmpeg, tmp_path, "fmp4")
    check_mp3(ffmpeg, tmp_path / "out.mp3", segments)


def test_audio_hls_of_ts_segments_is_a_valid_mp3(ffmpeg: Ffmpeg, tmp_path: Path):
    segments = make_audio_hls(ffmpeg, tmp_path, "mpegts")
    check_mp3(ffmpeg, tmp_path / "out.mp3", segments)


def test_a_direct_mp3_file_of_the_download_is_the_output(ffmpeg: Ffmpeg, tmp_path: Path):
    """A direct ``.mp3`` download is copied to the destination as it is (spec 5.2 p.4)."""
    segments = make_audio_hls(ffmpeg, tmp_path, "fmp4")
    source = tmp_path / "track.mp3"
    check_mp3(ffmpeg, source, segments)
    out = tmp_path / "copy.mp3"
    out.write_bytes(source.read_bytes())
    info = probe_media(str(out), ffmpeg)
    assert info.has_audio and not info.has_video
