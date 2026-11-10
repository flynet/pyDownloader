"""Running one download task (spec 6.2), Qt-free so it is testable.

The task is: parse the manifest of the source, build the plan, download the
segments in parallel, run FFmpeg, move the result to the destination folder
and delete the temporary directory. Cancellation stops the download and
removes the temporary files.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pydownloader.config.settings import DEFAULT_TARGET_HEIGHT
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
from pydownloader.download.plan import build_plan, plan_family, plan_hls, plan_mp4
from pydownloader.ffmpeg.locate import Ffmpeg
from pydownloader.ffmpeg.mux import assemble, copy_single
from pydownloader.hls.models import Playlist
from pydownloader.hls.parser import PlaylistParseError, parse_playlist
from pydownloader.i18n import tr
from pydownloader.manifest.drm import detect_dash, detect_hls
from pydownloader.manifest.quality import Choice, best_variant
from pydownloader.manifest.registry import SourceEntry
from pydownloader.util.filenames import unique_path
from pydownloader.util.urls import path_extension
from pydownloader.youtube.downloader import YoutubeError, youtube_plan

FetchText = Callable[[str, dict[str, str]], str | None]
Progress = Callable[[int, int], None]
Log = Callable[[str], None]

#: The directory of segments inside the download folder (spec 6.2 p.2).
TMP_DIR_NAME = ".tmp"

logger = logging.getLogger("pydownloader.runner")


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
    #: Quality cap for sources without a manifest (YouTube adaptive formats).
    target_height: int = DEFAULT_TARGET_HEIGHT


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
    # A segment family has no playlist unless the browser's one was recorded.
    if entry.family:
        return _family_plan(entry, ctx)
    if entry.kind == "youtube":
        try:
            return youtube_plan(entry.payload, ctx.target_height)
        except YoutubeError as exc:
            raise DownloadError(str(exc)) from exc
    choice = entry.choice
    if choice is None:
        raise DownloadError(tr("dl_source_not_parsed", url=entry.url))
    if entry.kind == "mp4":
        return plan_mp4(entry.url)
    if entry.kind == "dash":
        return _dash_plan(entry, choice, ctx)
    return _hls_plan(entry, choice, ctx)


def _family_plan(entry: SourceEntry, ctx: RunContext) -> list:
    """Plan of a synthesized family (no playlist was parsed by the pipeline).

    When the browser's playlist was recorded, it is the better source: it has the
    real segment order, the media sequence used for the AES-128 IV and every
    segment, including the ones the browser did not play. Otherwise the recorded
    segment URLs are the plan, in capture order with the init segment first.
    """
    playlist_url = next(
        (url for url in entry.recorded.values() if path_extension(url) == ".m3u8"),
        None,
    )
    if playlist_url is not None:
        text = ctx.fetch_text(playlist_url, ctx.headers)
        if text is not None:
            try:
                playlist = parse_playlist(text, playlist_url)
            except PlaylistParseError as exc:
                ctx.log(tr("dl_family_playlist_not_parsed", error=exc))
            else:
                if playlist.kind == "media":
                    if playlist.is_live:
                        raise DownloadError(tr("dl_live_skipped"))
                    verdict = detect_hls(playlist)
                    if verdict.is_drm:
                        raise DownloadError(
                            tr("dl_drm_detected", message=verdict.message, system=verdict.system)
                        )
                    if playlist.segments:
                        return plan_hls(playlist)
    return plan_family(entry.recorded)


def _hls_plan(entry: SourceEntry, choice: Choice, ctx: RunContext) -> list:
    playlist = _media_playlist(entry, choice.url, ctx)
    if playlist is None:
        # The chosen quality is not signed for this client: take the best
        # variant the browser really fetched (a lower quality is still a video).
        fallback = _recorded_variant(entry, choice, ctx)
        if fallback is not None:
            choice, playlist = fallback
    if playlist is None:
        raise DownloadError(tr("dl_manifest_not_fetched", url=choice.url))
    audio: Playlist | None = None
    if choice.audio_url:
        audio = _media_playlist(entry, choice.audio_url, ctx)
        if audio is None:
            ctx.log(tr("dl_audio_not_fetched", url=choice.audio_url))
    return build_plan(video_playlist=playlist, audio_playlist=audio)


def _recorded_variant(
    entry: SourceEntry, choice: Choice, ctx: RunContext
) -> tuple[Choice, Playlist] | None:
    """Best master variant whose exact URL the browser requested.

    phncdn signs every path: the URL of a quality the player did not request is
    rejected (HTTP 410), while the requested one is recorded from the traffic.
    """
    candidates = [variant for variant in entry.variants if variant.url != choice.url]
    candidates.sort(key=lambda variant: (variant.height or 0, variant.bandwidth or 0), reverse=True)
    for variant in candidates:
        recorded = entry.recorded_url(variant.url)
        if recorded is None:
            continue
        playlist = _media_playlist(entry, recorded, ctx)
        if playlist is None:
            continue
        logger.info(
            tr(
                "dl_variant_fallback",
                height=choice.height,
                fallback=variant.height,
                url=recorded,
            )
        )
        ctx.log(tr("dl_variant_fallback_short", height=choice.height, fallback=variant.height))
        return variant, playlist
    return None


def _media_playlist(
    entry: SourceEntry, url: str, ctx: RunContext, depth: int = 2
) -> Playlist | None:
    """Media playlist of a variant, descending into a nested master (phncdn).

    The live and DRM checks happen here as well: the pipeline may have shown a
    master whose variant URL it could not fetch (a per-path signature), so the
    download is the last place where these filters can be applied.
    """
    text = ctx.fetch_text(url, ctx.headers)
    if text is None:
        return None
    # The body may come from another recorded URL (a signed playlist of the same
    # stream), so its relative links must be resolved against that URL.
    base = entry.effective_url(url)
    try:
        playlist = parse_playlist(text, base)
    except PlaylistParseError as exc:
        raise DownloadError(tr("dl_manifest_not_parsed", error=exc)) from exc
    if playlist.kind == "media":
        if playlist.is_live:
            raise DownloadError(tr("dl_live_skipped"))
        verdict = detect_hls(playlist)
        if verdict.is_drm:
            raise DownloadError(
                tr("dl_drm_detected", message=verdict.message, system=verdict.system)
            )
        return playlist
    if depth <= 0:
        raise DownloadError(tr("dl_nested_master_deep"))
    variant = best_variant(playlist.variants, ctx.target_height)
    if variant is None:
        variants = sorted(
            playlist.variants,
            key=lambda item: (item.height or 0, item.bandwidth),
            reverse=True,
        )
        if not variants:
            raise DownloadError(tr("dl_no_variants"))
        variant = variants[0]
    next_url = entry.recorded_url(variant.url) or variant.url
    logger.debug(tr("dl_nested_master", url=url, target=next_url))
    return _media_playlist(entry, next_url, ctx, depth - 1)


def _dash_plan(entry: SourceEntry, choice: Choice, ctx: RunContext) -> list:
    text = ctx.fetch_text(entry.url, ctx.headers)
    if text is None:
        raise DownloadError(tr("dl_manifest_not_fetched", url=entry.url))
    try:
        # The body is re-parsed: the plan uses the representations chosen by the filters,
        # and a broken manifest must fail the task here, not in the middle of the download.
        mpd = parse_mpd(text, entry.effective_url(entry.url))
    except ManifestParseError as exc:
        raise DownloadError(tr("dl_manifest_not_parsed", error=exc)) from exc
    if mpd.is_live:
        raise DownloadError(tr("dl_live_skipped"))
    verdict = detect_dash(mpd)
    if verdict.is_drm:
        raise DownloadError(tr("dl_drm_detected", message=verdict.message, system=verdict.system))
    video: DashRepresentation | None = choice.video
    audio: DashRepresentation | None = choice.audio
    if video is None:
        raise DownloadError(tr("dl_no_video_track"))
    return build_plan(video_rep=video, audio_rep=audio)


def run_task(task: Task, ctx: RunContext) -> Path:
    """Download one task and return the path of the finished file.

    Raises :class:`CancelledError` when the user cancels,
    :class:`DownloadError` when a segment fails, and the FFmpeg/parse
    errors of the modules used.
    """
    if ctx.should_stop():
        raise CancelledError(tr("dl_task_cancelled"))
    task.plan = make_plan(task.entry, ctx)
    if not task.plan:
        raise DownloadError(tr("dl_nothing_to_download"))
    logger.debug(
        tr(
            "dl_plan_of_task",
            id=task.id,
            count=len(task.plan),
            streams=", ".join(sorted({item.stream for item in task.plan})),
        )
    )
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
        raise CancelledError(tr("dl_task_cancelled"))
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
