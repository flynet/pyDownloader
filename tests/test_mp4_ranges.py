"""Direct MP4 tests: classification, Range merging, fragment skipping (spec 5.1)."""

from __future__ import annotations

from pydownloader.manifest.detector import Candidate, classify
from pydownloader.manifest.registry import SourceRegistry
from pydownloader.util.ranges import ByteRange, content_range_total, merge_ranges
from pydownloader.util.urls import normalize_url, origin_of, path_extension

MIN_SIZE = 5 * 1024 * 1024
PAGE = "https://site.example/watch/42"


def mp4(url: str, size: int | None = None, content_type: str = "video/mp4") -> Candidate:
    return classify(
        url,
        content_type=content_type,
        page_url=PAGE,
        page_title="Страница",
        headers={"Referer": PAGE},
        content_length=size,
        min_mp4_size=MIN_SIZE,
    )


def test_classify_manifest_by_extension_and_content_type():
    by_ext = classify(
        "https://cdn.example.com/a/index.m3u8?token=x", content_type=None, page_url=PAGE
    )
    assert by_ext is not None and by_ext.kind == "hls"
    by_type = classify(
        "https://cdn.example.com/a/playlist", content_type="application/x-mpegurl", page_url=PAGE
    )
    assert by_type is not None and by_type.kind == "hls"
    dash = classify("https://cdn.example.com/a/stream.mpd", content_type=None, page_url=PAGE)
    assert dash is not None and dash.kind == "dash"
    dash_type = classify(
        "https://cdn.example.com/a/stream", content_type="application/dash+xml", page_url=PAGE
    )
    assert dash_type is not None and dash_type.kind == "dash"


def test_classify_mp4_by_content_type_and_extension():
    by_type = mp4("https://cdn.example.com/file", 12_000_000)
    assert by_type is not None and by_type.kind == "mp4"
    by_ext = mp4(
        "https://cdn.example.com/file.mp4?token=1",
        12_000_000,
        content_type="application/octet-stream",
    )
    assert by_ext is not None and by_ext.kind == "mp4"
    # Extension is read from the path, before the query string.
    assert path_extension("https://cdn.example.com/file.mp4?x=.m3u8") == ".mp4"


def test_an_audio_file_is_a_candidate_marked_audio():
    """SoundCloud sends an MP3: the source is kept and marked audio, target ``.mp3``."""
    by_type = mp4("https://cdn.example.com/track", 6_000_000, content_type="audio/mpeg")
    assert by_type is not None and by_type.kind == "mp4" and by_type.audio
    by_ext = mp4(
        "https://cdn.example.com/track.mp3?token=1",
        6_000_000,
        content_type="application/octet-stream",
    )
    assert by_ext is not None and by_ext.audio
    # The extension is read before the query, so the MP3 is found under a token.
    # A video file is not audio, its target stays .mp4.
    video = mp4("https://cdn.example.com/file.mp4", 12_000_000)
    assert video is not None and not video.audio


def test_a_small_audio_file_is_dropped_by_the_threshold():
    """A preview sound in the page is under the threshold, like a small MP4 (spec 5.1 p.3)."""
    assert mp4("https://cdn.example.com/preview.mp3", 200_000) is None


def test_small_files_are_dropped():
    assert mp4("https://cdn.example.com/small.mp4", 200_000) is None
    assert mp4("https://cdn.example.com/small.mp4", None) is not None


def test_segments_are_never_candidates():
    assert mp4("https://cdn.example.com/seg-1.m4s", 6_000_000) is None
    assert mp4("https://cdn.example.com/seg-1.ts", 6_000_000, content_type="video/mp4") is None
    assert mp4("https://cdn.example.com/init.mp4", 6_000_000, content_type="video/mp4") is not None


def test_normalize_url_drops_volatile_tokens():
    a = "https://cdn.example.com/a/b.mp4?token=AAA&sig=BBB&quality=1080#frag"
    b = "https://cdn.example.com/a/b.mp4?token=ZZZ&quality=1080"
    assert normalize_url(a) == normalize_url(b)
    assert "quality=1080" in normalize_url(a)
    assert normalize_url("https://cdn.example.com/a.mp4?sig=x") == "https://cdn.example.com/a.mp4"


def test_content_range_total():
    assert content_range_total("bytes 0-1/12345678") == 12345678
    assert content_range_total("bytes */12345678") == 12345678
    assert content_range_total("bytes 0-99/200") == 200
    assert content_range_total("") is None


def test_origin_of_page():
    assert origin_of("https://site.example/watch/42") == "https://site.example"


def test_registry_merges_range_requests_of_one_file():
    registry = SourceRegistry(min_mp4_size=MIN_SIZE)
    first = mp4(
        "https://cdn.example.com/movie.mp4?token=A", content_range_total("bytes 0-1/12345678")
    )
    result = registry.add_mp4(first)
    assert result.is_new
    assert result.entry.size == 12345678
    second = mp4(
        "https://cdn.example.com/movie.mp4?token=B", content_range_total("bytes 0-1/12345678")
    )
    merged = registry.add_mp4(second)
    assert not merged.is_new
    assert merged.merged
    assert merged.entry.id == result.entry.id
    assert merged.entry.range_requests == 2
    # The same normalized URL is one entry, so the list has exactly one card.
    assert len(registry.entries()) == 1


def test_registry_deduplicates_manifests():
    registry = SourceRegistry(min_mp4_size=MIN_SIZE)
    first = classify("https://cdn.example.com/a/master.m3u8?token=A", page_url=PAGE)
    second = classify("https://cdn.example.com/a/master.m3u8?token=B", page_url=PAGE)
    assert registry.add(first).is_new
    result = registry.add(second)
    assert not result.is_new
    assert registry.get(result.entry.normalized) is result.entry
    assert len(registry.entries()) == 1


def test_fragments_of_a_known_manifest_are_skipped():
    registry = SourceRegistry(min_mp4_size=MIN_SIZE)
    registry.add_manifest(classify("https://cdn.example.com/v/master.m3u8", page_url=PAGE))
    fragment = mp4("https://cdn.example.com/v/seg-1.mp4", 6_000_000)
    result = registry.add_mp4(fragment)
    assert not result.is_new
    assert "фрагмент" in result.reason
    assert len(registry.entries()) == 1
    # A file from another directory is a separate source.
    other = mp4("https://cdn.example.com/other/movie.mp4", 6_000_000)
    assert registry.add_mp4(other).is_new
    assert len(registry.entries()) == 2


def test_merge_ranges_sorts_and_joins():
    merged = merge_ranges(
        [ByteRange(150, 50), ByteRange(0, 100), ByteRange(100, 100), ByteRange(300, 10)]
    )
    assert [(r.start, r.length) for r in merged] == [(0, 200), (300, 10)]
