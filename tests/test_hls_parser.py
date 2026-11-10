"""HLS parser tests (spec 11: master, media, AES-128, fMP4, byterange, relative URLs)."""

from __future__ import annotations

import pytest

from pydownloader.hls.models import Playlist
from pydownloader.hls.parser import PlaylistParseError, parse_attributes, parse_playlist
from tests.conftest import HLS_URL


def test_master_variants(read):
    playlist = parse_playlist(read("master.m3u8"), HLS_URL)
    assert playlist.kind == "master"
    assert len(playlist.variants) == 3
    top = playlist.variants[0]
    assert (top.width, top.height) == (1920, 1080)
    assert top.bandwidth == 6000000
    assert top.audio_group == "aud"
    # Relative link of the variant is resolved, the query token is preserved.
    assert top.url == "https://cdn.example.com/video/video/1080.m3u8?token=abc"
    assert playlist.variants[1].height == 720
    assert playlist.variants[2].height == 480


def test_master_media_tracks(read):
    playlist = parse_playlist(read("master.m3u8"), HLS_URL)
    assert [m.language for m in playlist.media] == ["ru", "en"]
    ru = playlist.media[0]
    assert ru.type == "AUDIO" and ru.group_id == "aud" and ru.default
    assert ru.url == "https://cdn.example.com/video/audio/ru.m3u8"
    assert not playlist.media[1].default


def test_master_needs_live_probe(read):
    playlist = parse_playlist(read("master.m3u8"), HLS_URL)
    assert playlist.needs_live_probe
    assert playlist.available_heights() == [1080, 720, 480]


def test_media_segments(read):
    playlist = parse_playlist(read("media.m3u8"), HLS_URL)
    assert playlist.kind == "media"
    assert playlist.target_duration == 10
    assert playlist.has_endlist
    assert not playlist.is_live
    sequences = [s.sequence for s in playlist.segments]
    assert sequences == [100, 101, 102]
    assert [s.duration for s in playlist.segments] == [10.0, 10.0, 9.5]
    assert playlist.segments[0].url == "https://cdn.example.com/video/seg100.ts"
    assert playlist.segments[-1].url == "https://cdn.example.com/video/seg102.ts"


def test_live_playlist_is_skipped(read):
    playlist = parse_playlist(read("live.m3u8"), HLS_URL)
    assert playlist.is_live
    assert not playlist.has_endlist


def test_aes128_key(read):
    playlist = parse_playlist(read("aes.m3u8"), HLS_URL)
    first = playlist.segments[0]
    assert first.key is not None
    assert first.key.method == "AES-128"
    assert first.key.uri == "https://keys.example.com/key.bin"
    assert first.key.iv == 0x00123456789ABCDEF0
    # The second key line replaces the key for the following segments, the IV
    # is absent and must be derived from the media sequence number.
    third = playlist.segments[2]
    assert third.key is not None
    assert third.key.uri == "https://cdn.example.com/video/key2.bin"
    assert third.key.iv is None
    assert third.sequence == 2


def test_fmp4_init_segment(read):
    playlist = parse_playlist(read("fmp4.m3u8"), HLS_URL)
    assert playlist.init is not None
    assert playlist.init.url == "https://cdn.example.com/video/init.mp4"
    assert playlist.init.byte_range is None
    assert all(s.init == playlist.init for s in playlist.segments)


def test_byterange_absolute_and_continuation(read):
    playlist = parse_playlist(read("byterange.m3u8"), HLS_URL)
    init = playlist.init
    assert init is not None and (init.byte_range.start, init.byte_range.length) == (0, 1024)
    ranges = [(s.byte_range.start, s.byte_range.length) for s in playlist.segments]
    # 1024+100000 = 101024 is the byte after the first range, the plain length continues from it.
    assert ranges == [(1024, 100000), (101024, 120000), (320000, 80000)]
    # All segments point to the same file, only offsets differ.
    assert {s.url for s in playlist.segments} == {"https://cdn.example.com/video/single.mp4"}


def test_relative_urls_resolved_from_manifest_url():
    text = "#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXTINF:6.0,\n../other/seg.ts\n#EXT-X-ENDLIST\n"
    playlist = parse_playlist(text, "https://cdn.example.com/a/b/media.m3u8")
    assert playlist.segments[0].url == "https://cdn.example.com/a/other/seg.ts"


def test_parse_attributes_with_commas_in_quotes():
    attrs = parse_attributes('TYPE=AUDIO,GROUP-ID="a,b",NAME="Low, mid",DEFAULT=YES')
    assert attrs["GROUP-ID"] == "a,b"
    assert attrs["NAME"] == "Low, mid"
    assert attrs["DEFAULT"] == "YES"


def test_empty_and_non_hls_text():
    with pytest.raises(PlaylistParseError):
        parse_playlist("", HLS_URL)
    with pytest.raises(PlaylistParseError):
        parse_playlist("<?xml version='1.0'?><MPD/>", HLS_URL)


def test_playlist_defaults(read):
    playlist = parse_playlist(read("master.m3u8"), HLS_URL)
    assert isinstance(playlist, Playlist)
    assert playlist.segments == []
    assert playlist.key is None
