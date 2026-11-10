"""Building the list of files to download for one source (spec 6.2).

A plan is a flat list of items: the init segment, every media segment, the
segments of the audio track, or one file for a progressive MP4. Each item
carries the name it gets inside ``.tmp/<id>/``, so the worker can resume:
an item whose file already exists with the expected size is not downloaded
again.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from pydownloader.dash.models import DashRepresentation
from pydownloader.hls.models import Key, Playlist
from pydownloader.util.ranges import ByteRange
from pydownloader.util.urls import SEGMENT_EXTENSIONS, last_segment, path_extension

StreamId = Literal["video", "audio", "file"]
#: Extension used when the URL has none, by stream kind.
DEFAULT_EXTENSIONS = {"video": ".ts", "audio": ".m4a", "file": ".mp4"}
NAME_WIDTH = 5


@dataclass(frozen=True)
class PlanItem:
    """One file to fetch. ``order`` keeps the muxing order inside a stream."""

    url: str
    name: str
    stream: StreamId
    order: int
    byte_range: ByteRange | None = None
    key: Key | None = None
    #: Media sequence number of the segment: the default AES-128 IV (spec 6.3).
    sequence: int = 0


def extension(url: str, stream: StreamId) -> str:
    """Extension of the target file: the extension of the URL, otherwise the default."""
    ext = path_extension(url)
    if ext and ext not in {".m3u8", ".mpd"}:
        return ext
    return DEFAULT_EXTENSIONS[stream]


def plan_hls(playlist: Playlist, stream: StreamId = "video") -> list[PlanItem]:
    """Init segment (``EXT-X-MAP``) plus every media segment of the playlist."""
    items: list[PlanItem] = []
    order = 0
    if playlist.init:
        items.append(
            PlanItem(
                url=playlist.init.url,
                name=f"{stream}-init{extension(playlist.init.url, stream)}",
                stream=stream,
                order=order,
                byte_range=playlist.init.byte_range,
            )
        )
        order += 1
    for segment in playlist.segments:
        items.append(
            PlanItem(
                url=segment.url,
                name=f"{stream}-{segment.index:0{NAME_WIDTH}d}{extension(segment.url, stream)}",
                stream=stream,
                order=order,
                byte_range=segment.byte_range,
                key=segment.key,
                sequence=segment.sequence,
            )
        )
        order += 1
    return items


def plan_dash(rep: DashRepresentation, stream: StreamId = "video") -> list[PlanItem]:
    """Init segment plus the segments of a representation, or the whole file."""
    if rep.progressive and rep.progressive_url:
        return [
            PlanItem(
                url=rep.progressive_url,
                name=f"{stream}-full{extension(rep.progressive_url, stream)}",
                stream=stream,
                order=0,
            )
        ]
    items: list[PlanItem] = []
    order = 0
    if rep.init:
        items.append(
            PlanItem(
                url=rep.init.url,
                name=f"{stream}-init{extension(rep.init.url, stream)}",
                stream=stream,
                order=order,
                byte_range=rep.init.byte_range,
            )
        )
        order += 1
    for segment in rep.segments:
        number = segment.number if segment.number is not None else order
        items.append(
            PlanItem(
                url=segment.url,
                name=f"{stream}-{number:0{NAME_WIDTH}d}{extension(segment.url, stream)}",
                stream=stream,
                order=order,
                byte_range=segment.byte_range,
            )
        )
        order += 1
    return items


def plan_family(recorded: Mapping[str, str], stream: StreamId = "video") -> list[PlanItem]:
    """Plan of a segment family: the recorded URLs in capture order, init first.

    A family has no playlist (hls.js fetched it in-page), so the exact URLs seen
    in browser traffic are the only source of truth. A recorded AES-128 key file
    is attached to every segment.
    """
    key_url = next((url for url in recorded.values() if path_extension(url) == ".key"), None)
    key = Key(method="AES-128", uri=key_url) if key_url else None
    files = [
        (last_segment(key), url)
        for key, url in recorded.items()
        if path_extension(url) in SEGMENT_EXTENSIONS
        or last_segment(key).lower().startswith("init")
    ]
    files.sort(key=lambda item: 0 if item[0].lower().startswith("init") else 1)
    items: list[PlanItem] = []
    media_index = 0
    for order, (name, url) in enumerate(files):
        ext = extension(url, stream)
        if name.lower().startswith("init"):
            items.append(PlanItem(url=url, name=f"{stream}-init{ext}", stream=stream, order=order))
        else:
            items.append(
                PlanItem(
                    url=url,
                    name=f"{stream}-{order:0{NAME_WIDTH}d}{ext}",
                    stream=stream,
                    order=order,
                    key=key,
                    sequence=media_index,
                )
            )
            media_index += 1
    return items


def plan_mp4(url: str) -> list[PlanItem]:
    """A direct MP4 is one file, fetched with a ``Range`` when it is supported."""
    return [
        PlanItem(
            url=url,
            name=f"file{extension(url, 'file')}",
            stream="file",
            order=0,
        )
    ]


def build_plan(
    video_playlist: Playlist | None = None,
    video_rep: DashRepresentation | None = None,
    audio_playlist: Playlist | None = None,
    audio_rep: DashRepresentation | None = None,
    mp4_url: str | None = None,
) -> list[PlanItem]:
    """Full plan of one download task: video, audio, or a single file."""
    if mp4_url:
        return plan_mp4(mp4_url)
    items: list[PlanItem] = []
    if video_playlist is not None:
        items.extend(plan_hls(video_playlist, "video"))
    if video_rep is not None:
        items.extend(plan_dash(video_rep, "video"))
    if audio_playlist is not None:
        items.extend(plan_hls(audio_playlist, "audio"))
    if audio_rep is not None:
        items.extend(plan_dash(audio_rep, "audio"))
    return items
