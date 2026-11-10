"""Plans of the sample sources: names, order, init segments (spec 6.2)."""

from __future__ import annotations

from pydownloader.dash.parser import parse_mpd
from pydownloader.download.plan import build_plan, extension, plan_dash, plan_hls, plan_mp4
from pydownloader.hls.parser import parse_playlist
from tests.conftest import HLS_URL, MPD_URL


def names(items):
    return [item.name for item in items]


def test_hls_ts_segments(read):
    playlist = parse_playlist(read("media.m3u8"), HLS_URL)
    items = plan_hls(playlist)
    assert names(items) == ["video-00000.ts", "video-00001.ts", "video-00002.ts"]
    assert [item.sequence for item in items] == [100, 101, 102]
    assert [item.order for item in items] == [0, 1, 2]
    assert items[0].url == "https://cdn.example.com/video/seg100.ts"


def test_hls_fmp4_has_init_first(read):
    playlist = parse_playlist(read("fmp4.m3u8"), HLS_URL)
    items = plan_hls(playlist)
    assert names(items) == ["video-init.mp4", "video-00000.m4s", "video-00001.m4s"]
    assert items[0].url == "https://cdn.example.com/video/init.mp4"
    assert items[1].order == 1


def test_hls_audio_stream_names(read):
    playlist = parse_playlist(read("fmp4.m3u8"), HLS_URL)
    # The extension of the URL is kept, so the init file of an audio track is .mp4.
    assert names(plan_hls(playlist, "audio"))[0] == "audio-init.mp4"


def test_hls_audio_playlist(read):
    playlist = parse_playlist(read("media.m3u8"), HLS_URL)
    items = plan_hls(playlist, "audio")
    assert names(items) == ["audio-00000.ts", "audio-00001.ts", "audio-00002.ts"]


def test_dash_template_plan(read):
    mpd = parse_mpd(read("template.mpd"), MPD_URL)
    period = mpd.periods[0]
    video = period.videos()[0]
    items = plan_dash(video)
    assert names(items) == [
        "video-init.m4s",
        "video-00001.m4s",
        "video-00002.m4s",
        "video-00003.m4s",
        "video-00004.m4s",
        "video-00005.m4s",
    ]
    assert items[1].url == "https://cdn.example.com/dash/video/video-00001.m4s"


def test_dash_audio_plan(read):
    mpd = parse_mpd(read("template.mpd"), MPD_URL)
    audio = mpd.periods[0].audios()[0]
    items = plan_dash(audio, "audio")
    assert names(items) == [
        "audio-init.m4s",
        "audio-00001.m4s",
        "audio-00002.m4s",
        "audio-00003.m4s",
        "audio-00004.m4s",
        "audio-00005.m4s",
    ]


def test_progressive_is_one_file(read):
    mpd = parse_mpd(read("segmentbase.mpd"), MPD_URL)
    video = mpd.periods[0].videos()[0]
    items = plan_dash(video)
    assert len(items) == 1
    assert items[0].name == "video-full.mp4"
    assert items[0].url == "https://cdn.example.com/dash/file.mp4"


def test_direct_mp4_is_one_file():
    items = plan_mp4("https://cdn.example.com/movie.mp4?t=1")
    assert names(items) == ["file.mp4"]
    assert items[0].stream == "file"


def test_extension_defaults():
    assert extension("https://cdn.example.com/seg", "video") == ".ts"
    assert extension("https://cdn.example.com/seg?a=1", "audio") == ".m4a"
    assert extension("https://cdn.example.com/x.m3u8", "video") == ".ts"
    assert extension("https://cdn.example.com/x.ts", "video") == ".ts"


def test_build_plan_combines_video_and_audio(read):
    playlist = parse_playlist(read("fmp4.m3u8"), HLS_URL)
    audio = parse_playlist(read("media.m3u8"), HLS_URL)
    items = build_plan(video_playlist=playlist, audio_playlist=audio)
    assert names(items) == [
        "video-init.mp4",
        "video-00000.m4s",
        "video-00001.m4s",
        "audio-00000.ts",
        "audio-00001.ts",
        "audio-00002.ts",
    ]


def test_build_plan_mp4_wins():
    assert names(build_plan(mp4_url="https://cdn.example.com/a.mp4")) == ["file.mp4"]
