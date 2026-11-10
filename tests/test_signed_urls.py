"""Signed URLs: query inheritance, recorded URLs, segment families (spec 6.1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pydownloader.browser.events import ResponseEvent
from pydownloader.download.engine import DownloadError
from pydownloader.download.plan import plan_family
from pydownloader.download.runner import RunContext, make_plan
from pydownloader.ffmpeg.locate import Ffmpeg
from pydownloader.manifest.detector import Candidate
from pydownloader.manifest.registry import SourceEntry, SourceRegistry
from pydownloader.util.urls import resolve_url

FFMPEG = Ffmpeg(path=Path("ffmpeg.exe"), label="test")
PLAYLIST = "https://cdn.example.com/v/index-v1-a1.m3u8?h=9"


def segment_event(url: str, title: str = "Клип") -> ResponseEvent:
    return ResponseEvent(
        url=url,
        page_url="https://site.example/watch/42",
        page_title=title,
        content_type="video/mp4",
        request_headers={"referer": "https://site.example/watch/42"},
    )


def test_relative_reference_inherits_manifest_query():
    resolved = resolve_url("https://cdn.example.com/v/index.m3u8?h=1&e=2", "seg-1.m4s")
    assert resolved == "https://cdn.example.com/v/seg-1.m4s?h=1&e=2"


def test_absolute_reference_keeps_its_own_query():
    target = "https://cdn2.example.com/v/seg.ts?x=2"
    assert resolve_url("https://cdn.example.com/v/index.m3u8?h=1", target) == target


def test_reference_with_query_wins():
    resolved = resolve_url("https://cdn.example.com/v/index.m3u8?h=1", "seg.ts?x=2")
    assert resolved == "https://cdn.example.com/v/seg.ts?x=2"


def test_entry_recorded_url_by_file_name():
    entry = SourceEntry(id="s1", kind="hls", url="u", normalized="u")
    entry.record("https://cdn.example.com/v/seg-1.m4s?h=7&e=8")
    assert (
        entry.recorded_url("https://cdn.example.com/v/seg-1.m4s")
        == "https://cdn.example.com/v/seg-1.m4s?h=7&e=8"
    )
    assert entry.recorded_url("https://cdn.example.com/v/other.m4s") is None


def test_segments_are_recorded_into_their_manifest_entry():
    registry = SourceRegistry()
    registry.add_manifest(Candidate(url="https://cdn.example.com/v/master.m3u8?h=1", kind="hls"))
    registry.note_response(segment_event("https://cdn.example.com/v/seg-1.m4s?h=2"))
    entry = registry.entries()[0]
    assert entry.recorded["/v/seg-1.m4s"] == "https://cdn.example.com/v/seg-1.m4s?h=2"


def test_same_file_name_in_two_variant_directories_does_not_collide():
    entry = SourceEntry(id="s1", kind="hls", url="u", normalized="u")
    entry.record("https://cdn.example.com/v/720/seg-1.m4s?h=1")
    entry.record("https://cdn.example.com/v/1080/seg-1.m4s?h=2")
    assert (
        entry.recorded_url("https://cdn.example.com/v/1080/seg-1.m4s")
        == "https://cdn.example.com/v/1080/seg-1.m4s?h=2"
    )
    assert (
        entry.recorded_url("https://cdn.example.com/v/720/seg-1.m4s")
        == "https://cdn.example.com/v/720/seg-1.m4s?h=1"
    )
    # An unknown directory is not guessed when the name is ambiguous.
    assert entry.recorded_url("https://cdn.example.com/v/480/seg-1.m4s") is None


def test_url_seen_before_the_manifest_is_adopted():
    registry = SourceRegistry()
    variant = "https://cdn.example.com/v/1080/v.m3u8?h=9"
    registry.note_response(segment_event(variant))
    registry.add_manifest(Candidate(url="https://cdn.example.com/v/master.m3u8?h=1", kind="hls"))
    entry = registry.entries()[0]
    registry.adopt_pending(variant, entry)
    assert entry.recorded_url(variant) == variant


def test_family_is_synthesized_after_three_segments():
    registry = SourceRegistry()
    for index in range(1, 3):
        registry.note_response(
            segment_event(f"https://cdn.example.com/v/seg-{index}.m4s?h={index}")
        )
    assert registry.synthesize_families() == []

    registry.note_response(segment_event("https://cdn.example.com/v/seg-3.m4s?h=3"))
    created = registry.synthesize_families()
    assert len(created) == 1
    entry = created[0]
    assert entry.family is True
    assert entry.kind == "hls"
    assert entry.title == "Клип"
    assert list(entry.recorded) == ["/v/seg-1.m4s", "/v/seg-2.m4s", "/v/seg-3.m4s"]
    assert entry.recorded["/v/seg-2.m4s"].endswith("h=2")
    # The synthesized row is registered once and owns its directory afterwards.
    assert registry.entries() == [entry]
    registry.note_response(segment_event("https://cdn.example.com/v/seg-4.m4s?h=4"))
    assert registry.synthesize_families() == []
    assert entry.recorded["/v/seg-4.m4s"].endswith("h=4")


def test_family_is_not_created_when_a_manifest_owns_the_directory():
    registry = SourceRegistry()
    registry.add_manifest(Candidate(url="https://cdn.example.com/v/master.m3u8", kind="hls"))
    for index in range(1, 4):
        registry.note_response(segment_event(f"https://cdn.example.com/v/seg-{index}.m4s"))
    assert registry.synthesize_families() == []
    assert len(registry.entries()) == 1


def test_plan_family_puts_the_init_segment_first():
    recorded = {
        "seg-1.m4s": "https://cdn.example.com/v/seg-1.m4s",
        "init.mp4": "https://cdn.example.com/v/init.mp4",
        "seg-2.m4s": "https://cdn.example.com/v/seg-2.m4s",
    }
    plan = plan_family(recorded)
    assert [item.name for item in plan] == ["video-init.mp4", "video-00001.m4s", "video-00002.m4s"]
    assert [item.url for item in plan] == [
        "https://cdn.example.com/v/init.mp4",
        "https://cdn.example.com/v/seg-1.m4s",
        "https://cdn.example.com/v/seg-2.m4s",
    ]


def family_entry(recorded: dict[str, str]) -> SourceEntry:
    entry = SourceEntry(
        id="s1",
        kind="hls",
        url="https://cdn.example.com/v/index-v1-a1.m3u8",
        normalized="family",
        family=True,
    )
    for url in recorded.values():
        entry.record(url)
    return entry


def make_context(texts: dict[str, str], calls: list[str] | None = None) -> RunContext:
    used = calls if calls is not None else []

    def fetch_text(url: str, headers: dict) -> str | None:
        used.append(url)
        return texts.get(url)

    return RunContext(
        headers={},
        fetch_text=fetch_text,
        fetch_bytes=lambda url, headers, byte_range: b"",
        ffmpeg=FFMPEG,
        should_stop=lambda: False,
        log=lambda message: None,
        progress=lambda done, total: None,
    )


def test_family_plan_prefers_the_recorded_playlist(read):
    recorded = {
        "seg-1.m4s": "https://cdn.example.com/v/seg-1.m4s?h=1",
        "seg-2.m4s": "https://cdn.example.com/v/seg-2.m4s?h=2",
        "seg-3.m4s": "https://cdn.example.com/v/seg-3.m4s?h=3",
        "index-v1-a1.m3u8": PLAYLIST,
    }
    plan = make_plan(family_entry(recorded), make_context({PLAYLIST: read("fmp4.m3u8")}))
    # The playlist has the complete list (two segments, not three) and its own
    # signature is inherited by the relative references.
    assert [item.url for item in plan] == [
        "https://cdn.example.com/v/init.mp4?h=9",
        "https://cdn.example.com/v/seg-1.m4s?h=9",
        "https://cdn.example.com/v/seg-2.m4s?h=9",
    ]


def test_family_plan_without_a_playlist_uses_the_recorded_urls():
    recorded = {
        "init.mp4": "https://cdn.example.com/v/init.mp4?h=1",
        "seg-1.m4s": "https://cdn.example.com/v/seg-1.m4s?h=2",
        "seg-2.m4s": "https://cdn.example.com/v/seg-2.m4s?h=3",
    }
    calls: list[str] = []
    plan = make_plan(family_entry(recorded), make_context({}, calls))
    # No guessed playlist is requested: a per-path signature would reject it.
    assert calls == []
    assert [item.url for item in plan] == list(recorded.values())


def test_family_plan_rejects_a_recorded_live_playlist(read):
    recorded = {"index-v1-a1.m3u8": PLAYLIST}
    with pytest.raises(DownloadError, match="Live"):
        make_plan(family_entry(recorded), make_context({PLAYLIST: read("live.m3u8")}))
