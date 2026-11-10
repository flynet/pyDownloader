"""Quality filter tests (spec 11: QualityFilter, 1080p threshold)."""

from __future__ import annotations

from pydownloader.dash.parser import parse_mpd
from pydownloader.hls.parser import parse_playlist
from pydownloader.manifest.quality import QualityFilter, heights_message
from tests.conftest import HLS_URL, MPD_URL

FILTER = QualityFilter()


def test_master_with_1080p_is_shown(read):
    playlist = parse_playlist(read("master.m3u8"), HLS_URL)
    decision = FILTER.decide_hls(playlist)
    assert decision.show
    assert decision.choice is not None
    assert decision.choice.kind == "hls-variant"
    assert decision.choice.url == "https://cdn.example.com/video/video/1080.m3u8?token=abc"
    assert decision.choice.height == 1080
    # The DEFAULT=YES audio track of the variant group is chosen.
    assert decision.choice.audio_language == "ru"
    assert decision.choice.audio_url == "https://cdn.example.com/video/audio/ru.m3u8"


def test_master_without_1080p_is_hidden(read):
    playlist = parse_playlist(read("no_1080.m3u8"), HLS_URL)
    decision = FILTER.decide_hls(playlist)
    assert not decision.show
    assert decision.choice is None
    assert decision.message == "Найден поток без 1080p: пропущен (доступно: 720p, 480p)"
    assert decision.available_heights == [720, 480]


def test_threshold_is_configurable(read):
    playlist = parse_playlist(read("no_1080.m3u8"), HLS_URL)
    decision = QualityFilter(target_height=720).decide_hls(playlist)
    assert decision.show
    assert decision.choice.url.endswith("720.m3u8")
    assert decision.choice.bandwidth == 3000000


def test_media_playlist_without_resolution_is_shown(read):
    playlist = parse_playlist(read("media.m3u8"), HLS_URL)
    decision = FILTER.decide_hls(playlist)
    assert decision.show
    assert decision.choice.kind == "hls-media"
    assert decision.choice.height is None
    assert decision.choice.url == HLS_URL


def test_dash_picks_best_1080p(read):
    mpd = parse_mpd(read("timeline.mpd"), MPD_URL)
    decision = FILTER.decide_dash(mpd)
    assert decision.show
    assert decision.choice.height == 1080
    assert decision.choice.video.id == "v1080"
    assert decision.choice.video.width == 1920
    # Audio is the highest bandwidth representation, language is kept for the UI.
    assert decision.choice.audio is not None
    assert decision.choice.audio.id == "a96"


def test_dash_without_1080p_is_hidden(read):
    mpd = parse_mpd(read("segmentlist.mpd"), MPD_URL)
    decision = QualityFilter(target_height=2160).decide_dash(mpd)
    assert not decision.show
    assert decision.message == "Найден поток без 2160p: пропущен (доступно: 1080p)"


def test_dash_threshold_720(read):
    mpd = parse_mpd(read("template.mpd"), MPD_URL)
    decision = QualityFilter(target_height=720).decide_dash(mpd)
    assert decision.show
    assert decision.choice.video.id == "v720"


def test_mp4_known_height_is_filtered():
    assert FILTER.decide_mp4("https://cdn.example.com/a.mp4", 1080).show
    assert FILTER.decide_mp4("https://cdn.example.com/a.mp4", 1080).choice.url.endswith("a.mp4")
    decision = FILTER.decide_mp4("https://cdn.example.com/a.mp4", 720)
    assert not decision.show
    assert "720p" in decision.message


def test_mp4_unknown_height_is_kept():
    decision = FILTER.decide_mp4("https://cdn.example.com/a.mp4", None)
    assert decision.show
    assert decision.choice.height is None


def test_message_format_when_resolution_is_unknown():
    assert (
        heights_message([], 1080) == "Найден поток без 1080p: пропущен (разрешение не определяется)"
    )
