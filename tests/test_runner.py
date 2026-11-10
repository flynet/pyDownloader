"""Runner tests: one task from the manifest to the file (spec 6.2), no FFmpeg."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from pydownloader.browser.events import ResponseEvent
from pydownloader.download import runner
from pydownloader.download.engine import CancelledError, DownloadError
from pydownloader.download.runner import (
    RunContext,
    build_task,
    make_plan,
    output_path,
    run_task,
    task_root,
)
from pydownloader.ffmpeg.locate import Ffmpeg
from pydownloader.ffmpeg.mux import MuxResult
from pydownloader.manifest.pipeline import process_event
from pydownloader.manifest.quality import Choice, QualityFilter
from pydownloader.manifest.registry import SourceEntry, SourceRegistry
from tests.conftest import HLS_URL, MPD_URL

DATA = Path(__file__).parent / "data"
FFMPEG = Ffmpeg(path=Path("ffmpeg.exe"), label="test")
ROOT = Path("D:/downloads")
VARIANT_1080 = "https://cdn.example.com/video/video/1080.m3u8?token=abc"
AUDIO_URL = "https://cdn.example.com/video/audio/ru.m3u8"
MASTER = (DATA / "master.m3u8").read_text(encoding="utf-8")
MEDIA = (DATA / "media.m3u8").read_text(encoding="utf-8")
FMP4 = (DATA / "fmp4.m3u8").read_text(encoding="utf-8")
MPD = (DATA / "template.mpd").read_text(encoding="utf-8")
SEGMENTS = {
    "https://cdn.example.com/video/video/seg100.ts": b"A",
    "https://cdn.example.com/video/video/seg101.ts": b"B",
    "https://cdn.example.com/video/video/seg102.ts": b"C",
}
TEXTS = {HLS_URL: MASTER, VARIANT_1080: MEDIA}


def entry_for(texts: dict[str, str], url: str, kind: str) -> SourceEntry:
    """Registry entry built by the real pipeline, so the plan is the real one."""
    registry = SourceRegistry(min_mp4_size=5 * 1024 * 1024)
    event = ResponseEvent(
        url=url,
        page_url="https://site.example/watch/42",
        page_title="Мой клип",
        content_type="application/vnd.apple.mpegurl" if kind == "hls" else "application/dash+xml",
        request_headers={"referer": "https://site.example/watch/42"},
    )
    process_event(event, registry, lambda target, headers: texts.get(target), QualityFilter())
    return registry.entries()[0]


def make_context(
    texts: dict[str, str],
    bodies: dict[str, bytes],
    stopped: list[bool] | None = None,
    calls: list[str] | None = None,
) -> RunContext:
    used = calls if calls is not None else []
    stop = stopped if stopped is not None else [False]

    def fetch_text(url: str, headers: dict) -> str | None:
        used.append(url)
        return texts.get(url)

    def fetch_bytes(url: str, headers: dict, byte_range) -> bytes:
        used.append(url)
        if url not in bodies:
            raise RuntimeError(f"404 {url}")
        return bodies[url]

    return RunContext(
        headers={"Referer": "https://site.example/watch/42"},
        fetch_text=fetch_text,
        fetch_bytes=fetch_bytes,
        ffmpeg=FFMPEG,
        should_stop=lambda: stop[0],
        log=lambda message: None,
        progress=lambda done, total: None,
        parallel=2,
        sleep=None,
    )


class FakeMux:
    """FFmpeg is replaced: the merged stream file is written as the output."""

    def __init__(self) -> None:
        self.video: list[Path] = []
        self.audio: list[Path] = []

    def __call__(self, files, out_path, ffmpeg, work_dir, audio_files=(), on_line=None):
        self.video = list(files)
        self.audio = list(audio_files)
        out_path.write_bytes(b"merged")
        return MuxResult(out_path=out_path, log="ok")


@pytest.fixture
def mux(monkeypatch):
    fake = FakeMux()
    monkeypatch.setattr(runner, "assemble", fake)
    return fake


def test_hls_task_produces_the_file(tmp_path, mux):
    texts = TEXTS
    entry = entry_for(texts, HLS_URL, "hls")
    task = build_task(entry, tmp_path)
    out = run_task(task, make_context(texts, SEGMENTS))
    assert out.exists()
    assert out.read_bytes() == b"merged"
    assert [f.name for f in mux.video] == ["video-00000.ts", "video-00001.ts", "video-00002.ts"]
    assert not task.tmp_dir.exists()
    assert out.parent == tmp_path
    assert out.suffix == ".mp4"
    assert "Мой клип" in out.name


def test_audio_track_is_muxed_with_video(tmp_path, mux):
    texts = {**TEXTS, AUDIO_URL: FMP4}
    bodies = dict(SEGMENTS)
    bodies.update(
        {
            "https://cdn.example.com/video/audio/init.mp4": b"I",
            "https://cdn.example.com/video/audio/seg-1.m4s": b"S1",
            "https://cdn.example.com/video/audio/seg-2.m4s": b"S2",
        }
    )
    entry = entry_for(texts, HLS_URL, "hls")
    task = build_task(entry, tmp_path)
    run_task(task, make_context(texts, bodies))
    assert mux.audio[0].name == "audio-init.mp4"
    assert len(mux.audio) == 3
    assert len(mux.video) == 3


def test_dash_task(tmp_path, mux):
    texts = {MPD_URL: MPD}
    bodies = {"https://cdn.example.com/dash/init-video.m4s": b"I"}
    for number in range(1, 6):
        bodies[f"https://cdn.example.com/dash/video/video-{number:05d}.m4s"] = b"S"
        bodies[f"https://cdn.example.com/dash/audio/audio-{number}.m4s"] = b"A"
    bodies["https://cdn.example.com/dash/init-audio.m4s"] = b"AI"
    entry = entry_for(texts, MPD_URL, "dash")
    task = build_task(entry, tmp_path)
    out = run_task(task, make_context(texts, bodies))
    assert out.read_bytes() == b"merged"
    assert mux.video[0].name == "video-init.m4s"
    assert len(mux.video) == 6
    assert len(mux.audio) == 6


def test_direct_mp4_is_copied_without_ffmpeg(tmp_path, mux):
    url = "https://cdn.example.com/movie.mp4"
    entry = SourceEntry(
        id="s1", kind="mp4", url=url, normalized=url, title="Фильм", size=12_000_000, height=1080
    )
    entry.choice = Choice(kind="mp4", url=url, height=1080)
    task = build_task(entry, tmp_path)
    calls: list[str] = []
    ctx = make_context({}, {url: b"MP4-DATA"}, calls=calls)
    out = run_task(task, ctx)
    assert out.read_bytes() == b"MP4-DATA"
    assert mux.video == []
    assert calls == [url]
    assert not task.tmp_dir.exists()


def test_cancel_stops_the_task(tmp_path, mux):
    texts = TEXTS
    stop = [False]
    calls: list[str] = []
    entry = entry_for(texts, HLS_URL, "hls")
    task = build_task(entry, tmp_path)
    ctx = make_context(texts, SEGMENTS, stopped=stop, calls=calls)

    def fetch_bytes(url: str, headers: dict, byte_range) -> bytes:
        calls.append(url)
        stop[0] = True
        return SEGMENTS[url]

    ctx.fetch_bytes = fetch_bytes
    ctx.parallel = 1
    with pytest.raises(CancelledError):
        run_task(task, ctx)
    # The temp files of a cancelled task are deleted (spec 6.2 p.7).
    assert not task.tmp_dir.exists()
    # Only the first segment was fetched, the rest of the plan was cancelled.
    segments = [url for url in calls if url.endswith(".ts")]
    assert segments == ["https://cdn.example.com/video/video/seg100.ts"]


def test_missing_manifest_is_an_error(tmp_path, mux):
    entry = entry_for(TEXTS, HLS_URL, "hls")
    task = build_task(entry, tmp_path)
    with pytest.raises(DownloadError, match="Не получен манифест"):
        run_task(task, make_context({}, {}))


def test_task_paths(tmp_path):
    entry = entry_for(TEXTS, HLS_URL, "hls")
    task = build_task(entry, ROOT)
    assert task.tmp_dir == ROOT / ".tmp" / entry.id
    out = output_path(tmp_path, entry)
    assert out.name.startswith("Мой клип")


def test_plan_rejects_a_master_playlist(tmp_path):
    entry = entry_for(TEXTS, HLS_URL, "hls")
    entry.choice = dataclasses.replace(entry.choice, url=HLS_URL)  # an abnormal state
    with pytest.raises(DownloadError, match="мастер-плейлист"):
        make_plan(entry, make_context(TEXTS, {}))


def test_name_conflicts_get_a_suffix(tmp_path):
    entry = entry_for(TEXTS, HLS_URL, "hls")
    first = output_path(tmp_path, entry)
    first.write_bytes(b"x")
    second = output_path(tmp_path, entry)
    assert second.name.endswith(" (1).mp4")
    assert first != second


def test_playlists_are_parsed_for_the_plan():
    entry = entry_for(TEXTS, HLS_URL, "hls")
    plan = make_plan(entry, make_context(TEXTS, {}))
    assert [item.name for item in plan] == ["video-00000.ts", "video-00001.ts", "video-00002.ts"]
    assert task_root(Path("D:/x"), entry).name == entry.id
