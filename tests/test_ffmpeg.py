"""FFmpeg location and command building (spec 6.4/7.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pydownloader.ffmpeg.locate import (
    NOT_FOUND,
    Ffmpeg,
    FfmpegNotFoundError,
    candidate_paths,
    locate_ffmpeg,
)
from pydownloader.ffmpeg.mux import (
    assemble,
    is_ts,
    merge_streams,
    mp3_command,
    remux_command,
    stream_format,
    to_mp3,
)
from pydownloader.ffmpeg.probe import headers_option, parse_height, parse_media
from pydownloader.i18n import tr

FFMPEG_TEXT = """ffmpeg version 6.0
Input #0, mov,mp4, from 'file.mp4':
  Duration: 00:00:30.00, bitrate: 4000 kb/s
  Stream #0:0(eng): Video: h264 (High) (avc1 / 0x0000001a), yuv420p, 1920x1080 [sqa], 3999 kb/s
  Stream #0:1(eng): Audio: aac (LC) (mp4a / 0x00000020), 48000 Hz, stereo, fltp, 128 kb/s
"""


def test_ffmpeg_console_window_is_hidden():
    """``CREATE_NO_WINDOW`` is the Windows flag 0x08000000, not zero.

    A zero flag runs FFmpeg in a console window, so the program flashes a
    terminal for every probe of a stream (spec 6.4).
    """
    from pydownloader.browser.chromium_installer import CREATE_NO_WINDOW as installer_flag
    from pydownloader.ffmpeg.mux import CREATE_NO_WINDOW as mux_flag
    from pydownloader.ffmpeg.probe import CREATE_NO_WINDOW as probe_flag

    assert mux_flag == 0x08000000
    assert probe_flag == 0x08000000
    assert installer_flag == 0x08000000


def test_bundled_bin_is_first(tmp_path: Path):
    root = tmp_path / "app"
    (root / "bin").mkdir(parents=True)
    binary = root / "bin" / "ffmpeg.exe"
    binary.write_bytes(b"MZ")
    found = locate_ffmpeg(
        root,
        exists=lambda path: path == binary,
        which=lambda name: str(tmp_path / "system" / "ffmpeg.exe"),
    )
    assert found.label == "bundled"
    assert found.path == binary
    order = [label for label, _ in candidate_paths(root, which=lambda name: None)]
    assert order == ["bundled"]


def test_path_binary_is_second(tmp_path: Path):
    system = tmp_path / "system" / "ffmpeg.exe"
    found = locate_ffmpeg(None, exists=lambda path: path == system, which=lambda name: str(system))
    assert found.label == "PATH"
    assert found.name == "ffmpeg.exe"


def test_missing_ffmpeg_reports_the_message(tmp_path: Path):
    with pytest.raises(FfmpegNotFoundError, match=NOT_FOUND):
        locate_ffmpeg(tmp_path, exists=lambda path: False, which=lambda name: None)


def test_remux_video_only():
    cmd = remux_command(
        Ffmpeg(path=Path("ffmpeg.exe"), label="bundled"), Path("video.stream"), Path("out.mp4")
    )
    assert cmd[0] == "ffmpeg.exe"
    assert "-c" in cmd and cmd[cmd.index("-c") + 1] == "copy"
    assert "-bsf:a" not in cmd
    assert cmd[-3:] == ["-f", "mp4", "out.mp4"]
    assert "-i" in cmd and cmd[cmd.index("-i") + 1] == "video.stream"


def test_remux_ts_needs_the_aac_filter():
    cmd = remux_command(
        Ffmpeg(path=Path("ffmpeg.exe"), label="bundled"),
        Path("video.stream"),
        Path("out.mp4"),
        ts=True,
    )
    assert cmd[cmd.index("-bsf:a") + 1] == "aac_adtstoasc"


def test_remux_with_audio_maps_both_streams():
    cmd = remux_command(
        Ffmpeg(path=Path("ffmpeg.exe"), label="bundled"),
        Path("video.stream"),
        Path("out.mp4"),
        Path("audio.stream"),
    )
    assert cmd[cmd.index("-map") + 1] == "0:v:0"
    assert cmd.count("-i") == 2
    assert "-c:v" in cmd and "-c:a" in cmd
    assert "-shortest" in cmd
    assert "-y" in cmd and "-hide_banner" in cmd


def test_mp3_command_re_encodes_with_the_chosen_bitrate():
    cmd = mp3_command(
        Ffmpeg(path=Path("ffmpeg.exe"), label="bundled"),
        Path("audio.stream"),
        Path("out.mp3"),
        192,
    )
    assert "-vn" in cmd
    assert cmd[cmd.index("-c:a") + 1] == "libmp3lame"
    assert cmd[cmd.index("-b:a") + 1] == "192k"
    assert "-c" not in cmd
    assert cmd[-3:] == ["-f", "mp3", "out.mp3"]


def test_mp3_command_names_the_input_format_of_the_stream():
    """A merged stream of fragments is told to FFmpeg: the file has no header.

    The AAC bitstream filter is not used for MP3: the audio is decoded, not
    copied, and a filter that does not fit the stream fails the task with
    "Invalid argument" and an empty output file.
    """
    cmd = mp3_command(
        Ffmpeg(path=Path("ffmpeg.exe"), label="bundled"),
        Path("audio.stream"),
        Path("out.mp3"),
        128,
        "mpegts",
    )
    fmt = cmd.index("-f")
    assert cmd[fmt + 1] == "mpegts"
    assert fmt < cmd.index("-i")
    assert cmd[cmd.index("-i") + 1] == "audio.stream"
    assert "-bsf:a" not in cmd


def test_mp3_command_of_fmp4_fragments_is_told_as_mp4():
    cmd = mp3_command(
        Ffmpeg(path=Path("ffmpeg.exe"), label="bundled"),
        Path("audio.stream"),
        Path("out.mp3"),
        192,
        "mp4",
    )
    fmt = cmd.index("-f")
    assert cmd[fmt + 1] == "mp4"
    assert fmt < cmd.index("-i")
    assert "-bsf:a" not in cmd


def test_stream_format_of_the_segment_kind(tmp_path: Path):
    assert stream_format([tmp_path / "a.m4s", tmp_path / "b.m4s"]) == "mp4"
    assert stream_format([tmp_path / "a.ts", tmp_path / "b.ts"]) == "mpegts"
    assert stream_format([tmp_path / "a.aac"]) == "aac"
    assert stream_format([tmp_path / "a.mp3", tmp_path / "b.mp3"]) == "mp3"


def test_stream_format_of_mixed_and_empty_kinds(tmp_path: Path):
    """Mixed segments are left to the FFmpeg probe, an empty list is no format."""
    assert stream_format([tmp_path / "a.ts", tmp_path / "b.m4s"]) is None
    assert stream_format([tmp_path / "a.bin"]) is None
    assert stream_format([]) is None


def test_empty_list_is_not_ts(tmp_path: Path):
    """An audio source has no video files: ``all()`` of an empty list is true.

    The empty video list used to mean TS, so the AAC filter was applied to the
    audio stream and FFmpeg exited with -22 and an empty MP3 file.
    """
    assert not is_ts([])
    assert is_ts([tmp_path / "a.ts"])
    assert not is_ts([tmp_path / "a.m4s"])


def test_an_mp3_file_is_copied_without_re_encode(tmp_path: Path):
    """A direct MP3 download is already the target format, FFmpeg is not run."""
    src = tmp_path / "track.mp3"
    src.write_bytes(b"ID3audio")
    out = tmp_path / "out.mp3"
    result = to_mp3(src, out, Ffmpeg(path=Path("ffmpeg.exe"), label="bundled"), 192)
    assert out.read_bytes() == b"ID3audio"
    assert result.out_path == out
    assert result.log == tr("ffmpeg_direct_mp3")


def test_assemble_of_audio_only_segments_writes_mp3(tmp_path: Path, monkeypatch):
    """A source of fMP4 audio fragments is merged and encoded to MP3.

    The command gets the format of the merged stream, no AAC bitstream filter
    (the audio is decoded, not copied), and the bitrate of the settings.
    """
    init = tmp_path / "audio-init.m4s"
    first = tmp_path / "audio-00000.m4s"
    init.write_bytes(b"init")
    first.write_bytes(b"seg")
    commands: list[list[str]] = []

    def fake_run(command, on_line=None):
        commands.append(list(command))
        Path(command[-1]).write_bytes(b"mp3data")
        return "encoded"

    monkeypatch.setattr("pydownloader.ffmpeg.mux.run_ffmpeg", fake_run)
    result = assemble(
        [],
        tmp_path / "out.mp3",
        Ffmpeg(path=Path("ffmpeg.exe"), label="bundled"),
        tmp_path,
        [init, first],
        192,
    )
    merged = (tmp_path / "audio.stream").read_bytes()
    assert merged == b"initseg"
    command = commands[0]
    fmt = command.index("-f")
    assert command[fmt + 1] == "mp4"
    assert fmt < command.index("-i")
    assert "-bsf:a" not in command
    assert command[command.index("-b:a") + 1] == "192k"
    assert command[-3:] == ["-f", "mp3", str(tmp_path / "out.mp3")]
    assert result.out_path == tmp_path / "out.mp3"


def test_assemble_audio_of_ts_segments_is_told_as_mpegts(tmp_path: Path, monkeypatch):
    init = tmp_path / "audio-init.ts"
    init.write_bytes(b"init")
    commands: list[list[str]] = []

    def fake_run(command, on_line=None):
        commands.append(list(command))
        Path(command[-1]).write_bytes(b"mp3data")
        return "encoded"

    monkeypatch.setattr("pydownloader.ffmpeg.mux.run_ffmpeg", fake_run)
    assemble(
        [],
        tmp_path / "out.mp3",
        Ffmpeg(path=Path("ffmpeg.exe"), label="bundled"),
        tmp_path,
        [init],
        128,
    )
    command = commands[0]
    fmt = command.index("-f")
    assert command[fmt + 1] == "mpegts"
    assert fmt < command.index("-i")


def test_merge_streams_concatenates_in_order(tmp_path: Path):
    a = tmp_path / "a.ts"
    b = tmp_path / "b.ts"
    a.write_bytes(b"AAA")
    b.write_bytes(b"BB")
    target = tmp_path / "sub" / "video.stream"
    merge_streams([a, b], target)
    assert target.read_bytes() == b"AAABB"


def test_merge_streams_of_init_then_segments(tmp_path: Path):
    files = []
    for name, body in (("init.mp4", b"init"), ("video-00000.m4s", b"seg")):
        path = tmp_path / name
        path.write_bytes(body)
        files.append(path)
    target = tmp_path / "video.stream"
    merge_streams(files, target)
    assert target.read_bytes() == b"initseg"


def test_parse_height_from_stream_line():
    assert parse_height(FFMPEG_TEXT) == 1080
    assert parse_height("Stream #0:0: Video: hevc, 3840x2160, 25 fps") == 2160
    assert parse_height("Stream #0:1: Audio: aac, 48000 Hz") is None
    assert parse_height("") is None


def test_a_file_with_video_and_audio_is_a_video_file():
    info = parse_media(FFMPEG_TEXT)
    assert info.height == 1080
    assert info.has_video
    assert info.has_audio
    assert info.audio_bitrate == 128


def test_an_audio_only_stream_is_an_audio_source():
    """The probe of a SoundCloud playlist: audio with no video is an MP3 target."""
    info = parse_media("Stream #0:0: Audio: mp3, 44100 Hz, stereo, fltp, 64 kb/s")
    assert info.has_audio
    assert not info.has_video
    assert info.height is None
    assert info.audio_bitrate == 64


def test_a_probe_that_read_nothing_is_not_audio():
    """FFmpeg failed to open the file: the source keeps its classification."""
    info = parse_media("Input #0, mov,mp4, from 'a.mp4':\n")
    assert not info.has_audio
    assert not info.has_video


def test_headers_option_is_crlf_separated():
    text = headers_option({"Referer": "https://site.example/a", "User-Agent": "UA"})
    assert text == "Referer: https://site.example/a\r\nUser-Agent: UA\r\n"
    assert headers_option({"Empty": ""}) == ""


def test_missing_packaged_binary_is_not_an_error(monkeypatch):
    """The frozen build drops imageio-ffmpeg's binary: the lookup returns None."""
    import sys
    import types

    from pydownloader.ffmpeg.locate import imageio_ffmpeg_path

    fake = types.ModuleType("imageio_ffmpeg")

    def boom():
        raise RuntimeError("no ffmpeg exe")

    fake.get_ffmpeg_exe = boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", fake)
    assert imageio_ffmpeg_path() is None
