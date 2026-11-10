"""Assembling the downloaded files with FFmpeg (spec 6.4).

Segments are concatenated as a raw byte stream: an MPEG-TS stream and a
fragmented MP4 stream are both readable by FFmpeg when the files are
appended one after another, with the init segment first. Then FFmpeg remuxes
the stream into ``.mp4`` with ``-c copy``, so the video is not re-encoded.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydownloader.ffmpeg.locate import Ffmpeg, ffmpeg_env

#: Windows flag: the FFmpeg console window stays hidden.
CREATE_NO_WINDOW = 0x00000000
TS_EXTENSIONS = {".ts", ".ifs"}
#: Bitstream filter needed when AAC in MPEG-TS is put into MP4 (spec 6.4).
AAC_BSF = ["-bsf:a", "aac_adtstoasc"]
MUXING_QUEUE = ["-max_muxing_queue_size", "2048"]

logger = logging.getLogger("pydownloader.ffmpeg")


class FfmpegError(RuntimeError):
    """FFmpeg finished with a non-zero exit code."""


@dataclass
class MuxResult:
    out_path: Path
    log: str


def is_ts(files: Sequence[Path]) -> bool:
    """All files are MPEG-TS segments (the AAC bitstream filter is then needed)."""
    return all(file.suffix.lower() in TS_EXTENSIONS for file in files)


def merge_streams(files: Sequence[Path], target: Path) -> None:
    """Append every file to one stream file, in the order of the plan."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as out:
        for file in files:
            with file.open("rb") as src:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)


def remux_command(
    ffmpeg: Ffmpeg,
    video_stream: Path,
    out_path: Path,
    audio_stream: Path | None = None,
    ts: bool = False,
) -> list[str]:
    """FFmpeg command: copy the streams, no re-encode (spec 6.4).

    ``audio_stream`` is added as the second input, so the audio of an HLS
    ``EXT-X-MEDIA`` track is muxed with the video.
    """
    cmd = [str(ffmpeg.path), "-hide_banner", "-loglevel", "warning", "-y"]
    cmd += ["-i", str(video_stream)]
    if audio_stream is not None:
        cmd += ["-i", str(audio_stream)]
    if audio_stream is not None:
        cmd += ["-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "copy", "-shortest"]
    else:
        cmd += ["-c", "copy"]
    if ts:
        cmd += AAC_BSF
    cmd += MUXING_QUEUE
    cmd += ["-f", "mp4", str(out_path)]
    return cmd


def run_ffmpeg(command: Sequence[str], on_line: Callable[[str], None] | None = None) -> str:
    """Run FFmpeg, collect its output, raise :class:`FfmpegError` on failure."""
    logger.debug("FFmpeg: %s", subprocess.list2cmdline(list(command)))
    process = subprocess.run(
        list(command),
        env=ffmpeg_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_NO_WINDOW,
    )
    output = process.stdout or ""
    if on_line:
        for line in output.splitlines():
            if line.strip():
                on_line(line)
    if process.returncode != 0:
        tail = " ".join(output.splitlines()[-3:]) if output else "нет вывода"
        logger.error("FFmpeg код %s: %s", process.returncode, tail)
        raise FfmpegError(f"FFmpeg завершился с кодом {process.returncode}: {tail}")
    logger.debug("FFmpeg готов, вывод: %d строк", len(output.splitlines()))
    return output


def copy_single(src: Path, out_path: Path) -> MuxResult:
    """A direct MP4 is copied to the destination, FFmpeg is not needed (spec 6.4 p.4)."""
    out_path.write_bytes(src.read_bytes())
    return MuxResult(out_path=out_path, log="прямой MP4")


def assemble(
    files: Sequence[Path],
    out_path: Path,
    ffmpeg: Ffmpeg,
    work_dir: Path,
    audio_files: Sequence[Path] = (),
    on_line: Callable[[str], None] | None = None,
) -> MuxResult:
    """Merge the segments into one stream and remux it into ``out_path``."""
    video_stream = work_dir / "video.stream"
    merge_streams(files, video_stream)
    audio_stream: Path | None = None
    if audio_files:
        audio_stream = work_dir / "audio.stream"
        merge_streams(audio_files, audio_stream)
    ts = is_ts(files) or is_ts(audio_files)
    command = remux_command(ffmpeg, video_stream, out_path, audio_stream, ts)
    log = run_ffmpeg(command, on_line)
    return MuxResult(out_path=out_path, log=log)
