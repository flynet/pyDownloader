"""DASH parser tests (spec 11: SegmentTemplate, SegmentTimeline, BaseURL)."""

from __future__ import annotations

import pytest

from pydownloader.dash.parser import ManifestParseError, parse_mpd
from pydownloader.dash.segments import build_segments, expand_template
from tests.conftest import MPD_URL


def test_number_template_with_padding(read):
    mpd = parse_mpd(read("template.mpd"), MPD_URL)
    assert mpd.mpd_type == "static"
    assert not mpd.is_live
    videos = mpd.periods[0].videos()
    assert [v.id for v in videos] == ["v1080", "v720"]
    v1080 = videos[0]
    assert (v1080.width, v1080.height, v1080.bandwidth) == (1920, 1080, 6000000)
    assert v1080.init is not None
    assert v1080.init.url == "https://cdn.example.com/dash/init-video.m4s"
    # mediaPresentationDuration=PT30S, duration=6s -> 5 segments, $Number%05d$ padded.
    assert len(v1080.segments) == 5
    assert v1080.segments[0].url == "https://cdn.example.com/dash/video/video-00001.m4s"
    assert v1080.segments[-1].url == "https://cdn.example.com/dash/video/video-00005.m4s"
    assert v1080.segments[0].number == 1
    assert v1080.segments[-1].start == pytest.approx(24.0)
    audio = mpd.periods[0].audios()[0]
    assert audio.language == "ru"
    assert audio.segments[0].url == "https://cdn.example.com/dash/audio/audio-1.m4s"


def test_segment_timeline_repeats(read):
    mpd = parse_mpd(read("timeline.mpd"), MPD_URL)
    video = mpd.periods[0].videos()[0]
    # <S t="0" d="180000" r="2"/> + <S t="540000" d="90000"/> at timescale 90000.
    urls = [s.url for s in video.segments]
    assert urls == [
        "https://cdn.example.com/dash/video/0.m4s",
        "https://cdn.example.com/dash/video/180000.m4s",
        "https://cdn.example.com/dash/video/360000.m4s",
        "https://cdn.example.com/dash/video/540000.m4s",
    ]
    assert [round(s.duration, 3) for s in video.segments] == [2.0, 2.0, 2.0, 1.0]
    assert [round(s.start, 3) for s in video.segments] == [0.0, 2.0, 4.0, 6.0]
    audio = mpd.periods[0].audios()[0]
    assert len(audio.segments) == 3
    assert audio.language == "en"


def test_multiple_periods(read):
    mpd = parse_mpd(read("timeline.mpd"), MPD_URL)
    assert len(mpd.periods) == 2
    second = mpd.periods[1]
    assert second.start == 6.0
    assert second.videos() == []
    audio = second.audios()[0]
    assert audio.language == "ru"
    assert audio.segments[0].url == "https://cdn.example.com/dash/audio2/288000.m4s"


def test_baseurl_chain_and_segment_list(read):
    mpd = parse_mpd(read("segmentlist.mpd"), MPD_URL)
    video = mpd.periods[0].videos()[0]
    # MPD BaseURL + Period BaseURL are concatenated (DASH BaseURL rule).
    assert video.init is not None
    assert video.init.url == "https://cdn.example.com/api/segment/init.m4s"
    urls = [s.url for s in video.segments]
    assert urls == [
        "https://cdn.example.com/api/segment/seg1.m4s",
        "https://cdn.example.com/api/segment/seg2.m4s",
        "https://cdn.example.com/api/segment/seg3.m4s",
    ]
    ranges = [s.byte_range for s in video.segments]
    assert ranges[1] is not None
    assert (ranges[1].start, ranges[1].length) == (0, 50000)
    assert ranges[0] is None


def test_segment_base_is_progressive(read):
    mpd = parse_mpd(read("segmentbase.mpd"), MPD_URL)
    video = mpd.periods[0].videos()[0]
    assert video.progressive
    assert video.progressive_url == "https://cdn.example.com/dash/file.mp4"
    assert video.segments == []
    assert video.height == 1080


def test_dynamic_manifest_is_live(read):
    mpd = parse_mpd(read("dynamic.mpd"), MPD_URL)
    assert mpd.is_live


def test_adaptation_set_without_representations(read):
    text = (
        '<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static" mediaPresentationDuration="PT6S">'
        '<Period start="PT0S"><AdaptationSet contentType="audio" mimeType="audio/mp4">'
        '<SegmentTemplate timescale="1000" media="a-$Number$.m4s" startNumber="1" duration="6000">'
        '<Initialization sourceURL="init.m4s"/></SegmentTemplate>'
        '<Representation id="a" bandwidth="64000"/></AdaptationSet></Period></MPD>'
    )
    mpd = parse_mpd(text, MPD_URL)
    stream = mpd.periods[0].audios()[0]
    assert stream.content_type == "audio"
    assert len(stream.segments) == 1


def test_expand_template_tokens():
    assert (
        expand_template(
            "$RepresentationID$/seg-$Number%04d$-$Time$.m4s",
            number=7,
            time=42,
            representation_id="v1",
        )
        == "v1/seg-0007-42.m4s"
    )
    assert expand_template("seg$$plain$Number$.m4s", number=3) == "seg$plain3.m4s"


def test_build_segments_without_duration_or_end_number():
    assert build_segments("seg$Number$.m4s", start_number=1) == []


def test_init_template_expands_representation_id():
    """DASH-IF live profile: the init URL also carries $RepresentationID$."""
    text = (
        '<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static" '
        'mediaPresentationDuration="PT8S"><Period>'
        '<AdaptationSet contentType="video" mimeType="video/mp4">'
        '<SegmentTemplate duration="120" timescale="30" startNumber="1" '
        'media="$RepresentationID$/$RepresentationID$_$Number$.m4v" '
        'initialization="$RepresentationID$/$RepresentationID$_0.m4v"/>'
        '<Representation id="bbb_1080" codecs="avc1.640028" width="1920" height="1080" '
        'bandwidth="9914554"/></AdaptationSet></Period></MPD>'
    )
    mpd = parse_mpd(text, MPD_URL)
    video = mpd.periods[0].videos()[0]
    assert video.init is not None
    assert video.init.url == "https://cdn.example.com/dash/bbb_1080/bbb_1080_0.m4v"
    assert video.segments[0].url == "https://cdn.example.com/dash/bbb_1080/bbb_1080_1.m4v"


def test_invalid_xml(read):
    with pytest.raises(ManifestParseError):
        parse_mpd("<not-xml", MPD_URL)
    with pytest.raises(ManifestParseError):
        parse_mpd("", MPD_URL)
