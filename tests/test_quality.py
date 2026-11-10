"""Quality filter tests (spec 11: QualityFilter, 1080p threshold)."""

from __future__ import annotations

from pydownloader.dash.parser import parse_mpd
from pydownloader.hls.parser import parse_playlist
from pydownloader.i18n import tr
from pydownloader.manifest.quality import (
    QualityFilter,
    heights_message,
    is_audio_codec,
    is_audio_variants,
)
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


def test_a_codec_list_of_audio_only_is_audio():
    assert is_audio_codec("mp4a.40.2")
    assert is_audio_codec("opus,flac")
    # A list with a video codec is a video variant.
    assert not is_audio_codec("avc1.64001f,mp4a.40.2")
    assert not is_audio_codec(None)


def test_a_video_master_is_not_an_audio_source(read):
    playlist = parse_playlist(read("master.m3u8"), HLS_URL)
    assert not is_audio_variants(playlist.variants)


def test_audio_master_shows_the_best_audio_variant(read):
    """SoundCloud master: variants with no RESOLUTION, the highest bandwidth wins."""
    playlist = parse_playlist(read("audio_master.m3u8"), HLS_URL)
    assert is_audio_variants(playlist.variants)
    decision = FILTER.decide_hls(playlist, audio=True)
    assert decision.show
    assert decision.choice.kind == "hls-variant"
    assert decision.choice.audio_only
    assert decision.choice.height is None
    assert decision.choice.url.endswith("audio-128.m3u8")
    assert decision.choice.bandwidth == 134400


def test_an_audio_media_playlist_is_shown_whatever_the_height_is(read):
    """A single media playlist of an audio track has no resolution, it is shown."""
    playlist = parse_playlist(read("audio_media.m3u8"), HLS_URL)
    decision = QualityFilter(target_height=1080, audio_only=True).decide_hls(playlist, audio=True)
    assert decision.show
    assert decision.choice.kind == "hls-media"
    assert decision.choice.audio_only


def test_audio_only_mode_skips_the_video_sources(read):
    """«Audio only (MP3)»: HLS, DASH and direct MP4 video are not shown (spec 5.2 p.4)."""
    audio = QualityFilter(audio_only=True)
    hls = audio.decide_hls(parse_playlist(read("master.m3u8"), HLS_URL))
    assert not hls.show
    assert hls.message == tr("mf_quality_video_skipped")
    dash = audio.decide_dash(parse_mpd(read("template.mpd"), MPD_URL))
    assert not dash.show
    mp4 = audio.decide_mp4("https://cdn.example.com/a.mp4", 1080)
    assert not mp4.show
    # The audio sources stay in the list.
    direct = audio.decide_mp4("https://cdn.example.com/track.mp3", None, audio=True)
    assert direct.show
    assert direct.choice.audio_only


def test_dash_audio_manifest_is_a_shown_audio_source(read):
    mpd = parse_mpd(read("audio_mpd.mpd"), MPD_URL)
    decision = FILTER.decide_dash(mpd, audio=True)
    assert decision.show
    assert decision.choice.kind == "dash-audio"
    assert decision.choice.audio_only
    assert decision.choice.bandwidth == 192000
    assert decision.choice.audio is not None
    assert decision.choice.audio.id == "a192"


def test_a_dash_manifest_without_audio_is_reported_as_skipped(read):
    """A stream with no audio track cannot be saved as MP3: the console says why."""
    mpd = parse_mpd(read("video_only.mpd"), MPD_URL)
    decision = FILTER.decide_dash(mpd, audio=True)
    assert not decision.show
    assert decision.message == tr("mf_quality_no_audio")
