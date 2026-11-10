"""Download plan of a YouTube source.

The VISIONOS player response gives classic signed URLs that answer a plain
``Range`` GET with ``206``. Each track is split into 8 MB ranges: the engine
downloads them in parallel, writes them as separate files, and the FFmpeg step
concatenates them in plan order before muxing. Chunking follows the segment
parallelism setting (at most six threads, spec 6.2 p.3).
"""

from __future__ import annotations

from pydownloader.download.plan import PlanItem, StreamId
from pydownloader.i18n import tr
from pydownloader.util.ranges import ByteRange
from pydownloader.youtube.player import Format, parse_player, pick_audio, pick_video, reason_of

#: Size of one parallel range request.
CHUNK = 8 * 1024 * 1024
NAME_WIDTH = 5


class YoutubeError(RuntimeError):
    """The player response cannot be downloaded (live, unavailable, no format)."""


def _extension(fmt: Format, stream: StreamId) -> str:
    if fmt.container == "webm":
        return ".webm"
    if stream == "audio":
        return ".m4a"
    return ".mp4"


def chunk_items(fmt: Format, stream: StreamId) -> list[PlanItem]:
    """Range chunks of one track, in playback order."""
    if fmt.url is None:
        return []
    ext = _extension(fmt, stream)
    total = fmt.content_length
    if total <= 0:
        return [PlanItem(url=fmt.url, name=f"{stream}-00000{ext}", stream=stream, order=0)]
    chunks = max(1, (total + CHUNK - 1) // CHUNK)
    items: list[PlanItem] = []
    for index in range(chunks):
        start = index * CHUNK
        end = min(total - 1, start + CHUNK - 1)
        items.append(
            PlanItem(
                url=fmt.url,
                name=f"{stream}-{index:0{NAME_WIDTH}d}{ext}",
                stream=stream,
                order=index,
                byte_range=ByteRange(start=start, length=end - start + 1),
            )
        )
    return items


def youtube_plan(payload: str, cap: int) -> list[PlanItem]:
    """Plan for a YouTube source: video chunks plus the best audio track."""
    player = parse_player(payload)
    if not player.ok:
        raise YoutubeError(tr("yt_plan_error", reason=reason_of(player)))
    if player.live:
        raise YoutubeError(tr("yt_plan_live"))
    video = pick_video(player, cap)
    if video is None:
        raise YoutubeError(tr("yt_plan_no_video"))
    items = chunk_items(video, "video")
    audio = pick_audio(player)
    if audio is not None:
        items.extend(chunk_items(audio, "audio"))
    return items
