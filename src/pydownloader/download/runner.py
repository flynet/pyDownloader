"""Running one download task (spec 6.2), Qt-free so it is testable.

The task is: parse the manifest of the source, build the plan, download the
segments in parallel, run FFmpeg, move the result to the destination folder
and delete the temporary directory. Cancellation stops the download and
removes the temporary files.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pydownloader.dash.models import DashRepresentation
from pydownloader.dash.parser import ManifestParseError, parse_mpd
from pydownloader.download.engine import (
    MAX_PARALLEL,
    CancelledError,
    DownloadError,
    FetchBytes,
    Sleep,
    Task,
    cleanup_tmp,
    download_plan,
)
from pydownloader.download.plan import build_plan, plan_mp4
from pydownloader.ffmpeg.locate import Ffmpeg
from pydownloader.ffmpeg.mux import assemble, copy_single
from pydownloader.hls.parser import PlaylistParseError, parse_playlist
from pydownloader.manifest.quality import Choice
from pydownloader.manifest.registry import SourceEntry
from pydownloader.util.filenames import unique_path

FetchText = Callable[[str, dict[str, str]], str | None]
Progress = Callable[[int, int], None]
Log = Callable[[str], None]

#: The directory of segments inside the download folder (spec 6.2 p.2).
TMP_DIR_NAME = ".tmp"


@dataclass
class RunContext:
    """Callbacks the worker injects: network, FFmpeg, cancellation, console."""

    headers: dict[str, str]
    fetch_text: FetchText
    fetch_bytes: FetchBytes
    ffmpeg: Ffmpeg
    should_stop: Callable[[], bool]
    log: Log
    progress: Progress
    parallel: int = MAX_PARALLEL
    sleep: Sleep | None = None


def task_root(root: Path, entry: SourceEntry) -> Path:
    """Directory of the segments: ``<downloads>/.tmp/<id>/`` (spec 6.2 p.2)."""
    return root / TMP_DIR_NAME / entry.id


def output_path(root: Path, entry: SourceEntry, suffix: str = ".mp4") -> Path:
    """Destination file name: the page title, sanitized, with a unique suffix."""
    return unique_path(root, entry.title or entry.page_url, suffix)


def build_task(
    entry: SourceEntry,
    root: Path,
    suffix: str = ".mp4",
) -> Task:
    """Task with the temporary and destination paths of the source."""
    return Task(
        id=entry.id,
        entry=entry,
        tmp_dir=task_root(root, entry),
        out_path=output_path(root, entry, suffix),
        plan=[],
    )


def make_plan(entry: SourceEntry, ctx: RunContext) -> list:
    """Plan of a source: the manifest body is fetched with the browser headers."""
    choice = entry.choice
    if choice is None:
        raise DownloadError(f"Источник не разобран: {entry.url}")
    if entry.kind == "mp4":
        return plan_mp4(entry.url)
    if entry.kind == "dash":
        return _dash_plan(entry, choice, ctx)
    return _hls_plan(entry, choice, ctx)


def _hls_plan(entry: SourceEntry, choice: Choice, ctx: RunContext) -> list:
    text = ctx.fetch_text(choice.url, ctx.headers)
    if text is None:
        raise DownloadError(f"Не получен манифест: {choice.url}")
    try:
        playlist = parse_playlist(text, choice.url)
    except PlaylistParseError as exc:
        raise DownloadError(f"Манифест не разобран: {exc}") from exc
    if playlist.kind == "master":
        raise DownloadError("Манифест не разобран: выбран мастер-плейлист")
    audio = None
    if choice.audio_url:
        audio_text = ctx.fetch_text(choice.audio_url, ctx.headers)
        if audio_text is not None:
            try:
                audio = parse_playlist(audio_text, choice.audio_url)
            except PlaylistParseError:
                ctx.log(f"Аудио-дорожка не получена: {choice.audio_url}")
    return build_plan(video_playlist=playlist, audio_playlist=audio)


def _dash_plan(entry: SourceEntry, choice: Choice, ctx: RunContext) -> list:
    text = ctx.fetch_text(entry.url, ctx.headers)
    if text is None:
        raise DownloadError(f"Не получен манифест: {entry.url}")
    try:
        # The body is re-parsed: the plan uses the representations chosen by the filters,
        # and a broken manifest must fail the task here, not in the middle of the download.
        parse_mpd(text, entry.url)
    except ManifestParseError as exc:
        raise DownloadError(f"Манифест не разобран: {exc}") from exc
    video: DashRepresentation | None = choice.video
    audio: DashRepresentation | None = choice.audio
    if video is None:
        raise DownloadError("В манифесте нет видеоролика")
    return build_plan(video_rep=video, audio_rep=audio)


def run_task(task: Task, ctx: RunContext) -> Path:
    """Download one task and return the path of the finished file.

    Raises :class:`CancelledError` when the user cancels,
    :class:`DownloadError` when a segment fails, and the FFmpeg/parse
    errors of the modules used.
    """
    if ctx.should_stop():
        raise CancelledError("Задача отменена")
    task.plan = make_plan(task.entry, ctx)
    if not task.plan:
        raise DownloadError("Нечего скачивать")
    try:
        files = download_plan(
            task.plan,
            task.tmp_dir,
            ctx.fetch_bytes,
            ctx.headers,
            ctx.should_stop,
            parallel=ctx.parallel,
            sleep=ctx.sleep,
            on_progress=ctx.progress,
        )
    except CancelledError:
        # A cancelled task leaves no temp files (spec 6.2 p.7).
        cleanup_tmp(task.tmp_dir)
        raise
    if ctx.should_stop():
        cleanup_tmp(task.tmp_dir)
        raise CancelledError("Задача отменена")
    streams = [path for path in files if path.stem != "file"]
    single = [path for path in files if path.stem == "file"]
    if single:
        result = copy_single(single[0], task.out_path)
        cleanup_tmp(task.tmp_dir)
        return result.out_path
    audio_files = [path for path in streams if path.name.startswith("audio-")]
    video_files = [path for path in streams if not path.name.startswith("audio-")]
    result = assemble(video_files, task.out_path, ctx.ffmpeg, task.tmp_dir, audio_files, ctx.log)
    cleanup_tmp(task.tmp_dir)
    return result.out_path
