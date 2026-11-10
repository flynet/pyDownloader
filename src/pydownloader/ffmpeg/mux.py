"""Assembling the downloaded files with FFmpeg (spec 6.4, 5.2 p.4).

Segments are concatenated as a raw byte stream: an MPEG-TS stream and a
fragmented MP4 stream are both readable by FFmpeg when the files are
appended one after another, with the init segment first. Then FFmpeg remuxes
the stream into ``.mp4`` with ``-c copy``, so the video is not re-encoded.
An audio-only source is decoded once with ``libmp3lame`` and written as
``.mp3`` with the bitrate of the settings.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydownloader.ffmpeg.locate import Ffmpeg, ffmpeg_env
from pydownloader.i18n import tr

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


def mp3_command(
    ffmpeg: Ffmpeg,
    audio_source: Path,
    out_path: Path,
    bitrate: int,
    ts: bool = False,
) -> list[str]:
    """FFmpeg command for an audio file: MP3 of the chosen bitrate (spec 5.2 p.4).

    An audio-only stream has no video, so ``-vn`` drops any video track the
    container may carry, and the audio is re-encoded with ``libmp3lame``: the
    codecs of an HLS audio track (AAC, Opus) cannot be put into an MP3 container
    as they are, so the stream is decoded once (spec 6.4 p.3).
    """
    cmd = [str(ffmpeg.path), "-hide_banner", "-loglevel", "warning", "-y"]
    cmd += ["-i", str(audio_source)]
    cmd += ["-vn", "-c:a", "libmp3lame", "-b:a", f"{bitrate}k"]
    if ts:
        cmd += AAC_BSF
    cmd += MUXING_QUEUE
    cmd += ["-f", "mp3", str(out_path)]
    return cmd


def to_mp3(src: Path, out_path: Path, ffmpeg: Ffmpeg, bitrate: int) -> MuxResult:
    """A direct audio file to MP3; an MP3 file is copied, no re-encode (spec 5.2 p.4).

    A direct MP4 with an audio stream (the m4a track of SoundCloud) is decoded
    once with ``libmp3lame``; a file that is already MP3 is copied as it is.
    """
    if src.suffix.lower() == ".mp3":
        out_path.write_bytes(src.read_bytes())
        return MuxResult(out_path=out_path, log=tr("ffmpeg_direct_mp3"))
    log = run_ffmpeg(mp3_command(ffmpeg, src, out_path, bitrate))
    return MuxResult(out_path=out_path, log=log)


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
        tail = " ".join(output.splitlines()[-3:]) if output else tr("ffmpeg_no_output")
        logger.error(tr("ffmpeg_exit_log", code=process.returncode, tail=tail))
        raise FfmpegError(tr("ffmpeg_failed", code=process.returncode, tail=tail))
    logger.debug(tr("ffmpeg_done_output", lines=len(output.splitlines())))
    return output


def copy_single(src: Path, out_path: Path) -> MuxResult:
    """A direct MP4 is copied to the destination, FFmpeg is not needed (spec 6.4 p.4)."""
    out_path.write_bytes(src.read_bytes())
    return MuxResult(out_path=out_path, log=tr("ffmpeg_direct_mp4"))


def assemble(
    files: Sequence[Path],
    out_path: Path,
    ffmpeg: Ffmpeg,
    work_dir: Path,
    audio_files: Sequence[Path] = (),
    mp3_bitrate: int | None = None,
    on_line: Callable[[str], None] | None = None,
) -> MuxResult:
    """Merge the segments into one stream and remux it into ``out_path``.

    ``mp3_bitrate`` is the MP3 target of an audio source (spec 5.2 p.4): the
    stream is decoded once and written as MP3, so the audio of a stream with no
    video becomes an ``.mp3`` file. Without it the streams are copied as they are.
    """
    if mp3_bitrate is not None:
        mp3_stream = work_dir / "audio.stream"
        merge_streams(list(files) + list(audio_files), mp3_stream)
        ts = is_ts(files) or is_ts(audio_files)
        command = mp3_command(ffmpeg, mp3_stream, out_path, mp3_bitrate, ts)
        log = run_ffmpeg(command, on_line)
        return MuxResult(out_path=out_path, log=log)
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
