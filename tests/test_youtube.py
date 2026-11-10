"""YouTube: player response parsing, format picking and the chunked plan."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pydownloader.download.runner import RunContext, build_task, make_plan, run_task
from pydownloader.ffmpeg.locate import Ffmpeg
from pydownloader.ffmpeg.mux import MuxResult
from pydownloader.manifest.quality import Choice
from pydownloader.manifest.registry import SourceEntry
from pydownloader.youtube.api import payload_template, video_id_from_url
from pydownloader.youtube.downloader import CHUNK, YoutubeError, youtube_plan
from pydownloader.youtube.player import (
    parse_player,
    pick_audio,
    pick_video,
    qualities,
    reason_of,
)

VIDEO_ID = "uKo4emYptFw"
PLAYER = {
    "playabilityStatus": {"status": "OK"},
    "videoDetails": {"videoId": VIDEO_ID, "title": "Тестовый клип", "lengthSeconds": "212"},
    "streamingData": {
        "adaptiveFormats": [
            {
                "itag": 137,
                "mimeType": "video/mp4; codecs=avc1",
                "url": "https://rr.example/v?itag=137",
                "width": 1920,
                "height": 1080,
                "bitrate": "4000000",
                "contentLength": str(2 * CHUNK + 100),
            },
            {
                "itag": 248,
                "mimeType": "video/webm; codecs=vp9",
                "url": "https://rr.example/v?itag=248",
                "width": 1920,
                "height": 1080,
                "bitrate": "5000000",
                "contentLength": "1000",
            },
            {
                "itag": 140,
                "mimeType": "audio/mp4; codecs=mp4a",
                "url": "https://rr.example/a?itag=140",
                "bitrate": "128000",
                "contentLength": "5000000",
            },
            {
                "itag": 251,
                "mimeType": "audio/webm; codecs=opus",
                "url": "https://rr.example/a?itag=251",
                "bitrate": "160000",
                "contentLength": "5000000",
            },
        ]
    },
}


def player_text(data: dict = PLAYER) -> str:
    return json.dumps(data)


def test_parse_player():
    player = parse_player(player_text())
    assert player.ok
    assert player.video_id == VIDEO_ID
    assert player.title == "Тестовый клип"
    assert player.duration == 212
    assert len(player.formats) == 4


def test_parse_player_never_raises_on_bad_input():
    assert parse_player("not json").status == "MALFORMED"
    assert parse_player("").status == "EMPTY"
    assert reason_of(parse_player("")) == "пустой ответ плеера"


def test_pick_video_prefers_mp4_at_the_same_height():
    player = parse_player(player_text())
    video = pick_video(player, 1080)
    assert video is not None
    assert video.itag == 137
    assert video.height == 1080


def test_pick_video_below_every_height_falls_back_to_the_best():
    player = parse_player(player_text())
    video = pick_video(player, 720)
    assert video is not None
    assert video.height == 1080


def test_pick_audio_prefers_mp4_over_a_higher_webm_bitrate():
    player = parse_player(player_text())
    audio = pick_audio(player)
    assert audio is not None
    assert audio.itag == 140


def test_qualities_and_plan():
    player = parse_player(player_text())
    assert qualities(player) == [1080]
    plan = youtube_plan(player_text(), 1080)
    video = [item for item in plan if item.stream == "video"]
    audio = [item for item in plan if item.stream == "audio"]
    assert len(video) == 3
    assert len(audio) == 1
    assert video[0].byte_range is not None
    assert video[0].byte_range.start == 0
    assert video[0].byte_range.length == CHUNK
    assert video[-1].byte_range is not None
    assert video[-1].byte_range.end == 2 * CHUNK + 99
    assert video[0].url == "https://rr.example/v?itag=137"
    assert audio[0].url == "https://rr.example/a?itag=140"
    assert plan[0].name == "video-00000.mp4"
    assert audio[0].name == "audio-00000.m4a"


def test_live_stream_is_rejected():
    data = json.loads(player_text())
    data["streamingData"]["isLiveContent"] = True
    with pytest.raises(YoutubeError, match="Live"):
        youtube_plan(json.dumps(data), 1080)


def test_unplayable_video_is_rejected():
    data = json.loads(player_text())
    data["playabilityStatus"] = {"status": "LOGIN_REQUIRED"}
    with pytest.raises(YoutubeError, match="входа"):
        youtube_plan(json.dumps(data), 1080)


def test_video_id_from_url():
    assert video_id_from_url("https://www.youtube.com/watch?v=" + VIDEO_ID) == VIDEO_ID
    assert video_id_from_url("https://youtu.be/" + VIDEO_ID) == VIDEO_ID
    assert video_id_from_url("https://www.youtube.com/shorts/" + VIDEO_ID) == VIDEO_ID
    assert video_id_from_url("https://www.youtube.com/") is None
    assert video_id_from_url("https://example.com/watch?v=" + VIDEO_ID) is None


def test_payload_template_has_the_visionos_client_and_visitor_slot():
    payload = payload_template(VIDEO_ID)
    assert VIDEO_ID in payload
    assert '"clientName":"VISIONOS"' in payload
    assert '"visitorData":"__VISITOR__"' in payload


def youtube_entry() -> SourceEntry:
    entry = SourceEntry(
        id="s1",
        kind="youtube",
        url="https://www.youtube.com/watch?v=" + VIDEO_ID,
        normalized="yt:" + VIDEO_ID,
        title="Тестовый клип",
        payload=player_text(),
        height=1080,
    )
    entry.choice = Choice(kind="mp4", url=entry.url, height=1080)
    return entry


def youtube_context() -> RunContext:
    return RunContext(
        headers={},
        fetch_text=lambda url, headers: None,
        fetch_bytes=lambda url, headers, byte_range: b"x",
        ffmpeg=Ffmpeg(path=Path("ffmpeg.exe"), label="test"),
        should_stop=lambda: False,
        log=lambda message: None,
        progress=lambda done, total: None,
        target_height=1080,
    )


def test_youtube_runner_builds_the_plan():
    plan = make_plan(youtube_entry(), youtube_context())
    assert [item.stream for item in plan] == ["video", "video", "video", "audio"]


def test_youtube_task_is_muxed(tmp_path, monkeypatch):
    seen: dict[str, list[str]] = {}

    def assemble(files, out_path, ffmpeg, work_dir, audio_files=(), mp3_bitrate=None, on_line=None):
        seen["video"] = [path.name for path in files]
        seen["audio"] = [path.name for path in audio_files]
        out_path.write_bytes(b"merged")
        return MuxResult(out_path=out_path, log="ok")

    monkeypatch.setattr("pydownloader.download.runner.assemble", assemble)
    entry = youtube_entry()
    out = run_task(build_task(entry, tmp_path), youtube_context())
    assert out.read_bytes() == b"merged"
    assert seen["video"] == ["video-00000.mp4", "video-00001.mp4", "video-00002.mp4"]
    assert seen["audio"] == ["audio-00000.m4a"]
