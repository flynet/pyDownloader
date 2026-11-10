"""Queue worker tests: sequential tasks, progress, cancel (spec 6.2 p.1)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from pydownloader.browser.events import ResponseEvent
from pydownloader.config.settings import DEFAULT_MP3_BITRATE, DEFAULT_TARGET_HEIGHT
from pydownloader.download import worker as worker_mod
from pydownloader.download.runner import build_task, task_root
from pydownloader.download.worker import QueueWorker
from pydownloader.ffmpeg.locate import Ffmpeg
from pydownloader.manifest.pipeline import process_event
from pydownloader.manifest.quality import QualityFilter
from pydownloader.manifest.registry import SourceEntry, SourceRegistry

DATA = Path(__file__).parent / "data"
MASTER = (DATA / "master.m3u8").read_text(encoding="utf-8")
MEDIA = (DATA / "media.m3u8").read_text(encoding="utf-8")
AUDIO_MASTER = (DATA / "audio_master.m3u8").read_text(encoding="utf-8")
AUDIO_MEDIA = (DATA / "audio_media.m3u8").read_text(encoding="utf-8")
HLS_URL = "https://cdn.example.com/video/master.m3u8"
VARIANT = "https://cdn.example.com/video/video/1080.m3u8?token=abc"
#: The master of SoundCloud has no ``RESOLUTION``, the highest bandwidth wins.
AUDIO_VARIANT = "https://cdn.example.com/video/audio-128.m3u8"
SEGMENTS = {
    "https://cdn.example.com/video/video/seg100.ts?token=abc": b"A",
    "https://cdn.example.com/video/video/seg101.ts?token=abc": b"B",
    "https://cdn.example.com/video/video/seg102.ts?token=abc": b"C",
}
AUDIO_SEGMENTS = {
    "https://cdn.example.com/video/init.mp4": b"I",
    "https://cdn.example.com/video/seg-0.m4a": b"S0",
    "https://cdn.example.com/video/seg-1.m4a": b"S1",
}
FFMPEG = Ffmpeg(path=Path("ffmpeg.exe"), label="test")


def entry(id: str = "s1") -> SourceEntry:
    return entry_from(MASTER, MEDIA, HLS_URL, VARIANT, "Клип", id)


def audio_entry(id: str = "s1") -> SourceEntry:
    """Registry entry of an audio master: the card is marked MP3, the target is ``.mp3``."""
    return entry_from(AUDIO_MASTER, AUDIO_MEDIA, HLS_URL, AUDIO_VARIANT, "Трек", id)


def entry_from(
    master: str, media: str, url: str, variant: str, title: str, id: str
) -> SourceEntry:
    """Registry entry built by the real pipeline, so the plan and the flags are the real ones."""
    registry = SourceRegistry(min_mp4_size=5 * 1024 * 1024)
    event = ResponseEvent(
        url=url,
        page_url="https://site.example/watch/42",
        page_title=title,
        content_type="application/vnd.apple.mpegurl",
        request_headers={"referer": "https://site.example/watch/42"},
    )
    process_event(
        event,
        registry,
        lambda u, headers: {url: master, variant: media}.get(u),
        QualityFilter(),
    )
    entry_obj = registry.entries()[0]
    entry_obj.id = id
    return entry_obj


@pytest.fixture
def http(monkeypatch):
    """The network is replaced: the manifests and the segments come from the fixtures."""

    def fetch_text(url, headers, timeout=20.0):
        return {HLS_URL: MASTER, VARIANT: MEDIA}.get(url)

    def fetch_bytes(url, headers, byte_range=None, timeout=60.0):
        if url not in SEGMENTS:
            raise RuntimeError(f"404 {url}")
        return SEGMENTS[url]

    monkeypatch.setattr(worker_mod, "fetch_text", fetch_text)
    monkeypatch.setattr(worker_mod, "fetch_bytes", fetch_bytes)

    def assemble(files, out_path, ffmpeg, work_dir, audio_files=(), mp3_bitrate=None, on_line=None):
        out_path.write_bytes(b"merged")
        return type("R", (), {"out_path": out_path, "log": "ok"})()

    monkeypatch.setattr("pydownloader.download.runner.assemble", assemble)


@pytest.fixture
def audio_http(monkeypatch):
    """The network of an audio master: the FFmpeg call records the bitrate (spec 5.2 p.4)."""

    def fetch_text(url, headers, timeout=20.0):
        return {HLS_URL: AUDIO_MASTER, AUDIO_VARIANT: AUDIO_MEDIA}.get(url)

    def fetch_bytes(url, headers, byte_range=None, timeout=60.0):
        if url not in AUDIO_SEGMENTS:
            raise RuntimeError(f"404 {url}")
        return AUDIO_SEGMENTS[url]

    seen: dict[str, object] = {}

    def assemble(files, out_path, ffmpeg, work_dir, audio_files=(), mp3_bitrate=None, on_line=None):
        seen["bitrate"] = mp3_bitrate
        seen["audio"] = [file.name for file in audio_files]
        out_path.write_bytes(b"ID3")
        return type("R", (), {"out_path": out_path, "log": "ok"})()

    monkeypatch.setattr(worker_mod, "fetch_text", fetch_text)
    monkeypatch.setattr(worker_mod, "fetch_bytes", fetch_bytes)
    monkeypatch.setattr("pydownloader.download.runner.assemble", assemble)
    return seen


def signals(worker: QueueWorker):
    """Collect the signals with a direct connection: the tests call ``run()`` directly."""
    from PySide6.QtCore import Qt

    collected = {"finished": [], "failed": [], "started": [], "progress": [], "log": []}
    worker.task_finished.connect(
        lambda tid, path: collected["finished"].append((tid, path)), Qt.DirectConnection
    )
    worker.task_failed.connect(
        lambda tid, message: collected["failed"].append((tid, message)), Qt.DirectConnection
    )
    worker.task_started.connect(
        lambda tid, name: collected["started"].append((tid, name)), Qt.DirectConnection
    )
    worker.progress.connect(
        lambda tid, done, total: collected["progress"].append((tid, done, total)),
        Qt.DirectConnection,
    )
    worker.log.connect(collected["log"].append, Qt.DirectConnection)
    return collected


def run_queue(worker: QueueWorker, collected: dict, expected: int, timeout: float = 20.0) -> None:
    """Run the real thread loop until ``expected`` tasks are reported, then stop it."""
    worker.start()
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if len(collected["finished"]) + len(collected["failed"]) >= expected:
                return
            time.sleep(0.02)
        raise AssertionError(f"очередь не завершилась: {collected}")
    finally:
        worker.stop()
        worker.wait(5000)


def test_an_audio_task_is_saved_as_an_mp3_file(qapp, tmp_path, audio_http):
    """The queue of a SoundCloud master writes ``.mp3`` with the chosen bitrate (spec 5.2 p.4)."""
    worker = QueueWorker(None, FFMPEG, str(tmp_path), parallel=2, mp3_bitrate=320)
    collected = signals(worker)
    task_id = worker.enqueue(audio_entry())
    run_queue(worker, collected, 1)
    out = Path(collected["finished"][0][1])
    assert out.suffix == ".mp3"
    assert out.read_bytes() == b"ID3"
    assert collected["started"][0] == (task_id, "Трек.mp3")
    # The FFmpeg call gets the bitrate of the settings, and the audio stream is the plan.
    assert audio_http["bitrate"] == 320
    assert list(audio_http["audio"]) == ["audio-init.mp4", "audio-00000.m4a", "audio-00001.m4a"]
    assert not task_root(tmp_path, audio_entry()).exists()


def test_the_worker_default_is_the_middle_bitrate(qapp, tmp_path):
    """A worker built by the settings of the program muxes an audio source at 192 kbit/s."""
    worker = QueueWorker(None, FFMPEG, str(tmp_path))
    audio_ctx = worker._context(build_task(audio_entry(), tmp_path))
    assert audio_ctx.mp3_bitrate == DEFAULT_MP3_BITRATE
    # A video source keeps the bitrate of the settings, its command stays ``-c copy``.
    video = QueueWorker(None, FFMPEG, str(tmp_path), mp3_bitrate=320)
    ctx = video._context(build_task(entry(), tmp_path))
    assert ctx.mp3_bitrate == 320
    assert ctx.target_height == DEFAULT_TARGET_HEIGHT


def test_one_task_is_downloaded(qapp, tmp_path, http):
    worker = QueueWorker(None, FFMPEG, str(tmp_path), parallel=2)
    collected = signals(worker)
    task_id = worker.enqueue(entry())
    run_queue(worker, collected, 1)
    out = Path(collected["finished"][0][1])
    assert collected["finished"][0][0] == task_id
    assert out.read_bytes() == b"merged"
    assert out.parent == tmp_path
    # The segments report progress 1..3 of 3.
    assert sorted(done for _, done, _ in collected["progress"]) == [1, 2, 3]
    assert not task_root(tmp_path, entry()).exists()


def test_worker_started_before_a_task_still_runs_it(qapp, tmp_path, http):
    """The thread waits on an empty queue instead of exiting (the old bug)."""
    worker = QueueWorker(None, FFMPEG, str(tmp_path), parallel=1)
    collected = signals(worker)
    worker.start()
    try:
        # The empty queue must not finish the thread: give it time to reach the wait.
        time.sleep(0.3)
        assert worker.isRunning()
        task_id = worker.enqueue(entry())
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline and not collected["finished"]:
            time.sleep(0.02)
    finally:
        worker.stop()
        worker.wait(5000)
    assert collected["finished"][0][0] == task_id


def test_tasks_run_one_after_another(qapp, tmp_path, http):
    """The queue is strictly sequential (spec 6.2 p.1): the files appear in the queue order."""
    worker = QueueWorker(None, FFMPEG, str(tmp_path), parallel=1)
    collected = signals(worker)
    first = worker.enqueue(entry("s1"))
    second = worker.enqueue(entry("s2"))
    run_queue(worker, collected, 2)
    names = sorted(name for _, name in collected["started"])
    assert names == ["Клип (1).mp4", "Клип.mp4"]
    ids = [tid for tid, _ in collected["finished"]]
    assert ids == [first, second]


def test_cancel_stops_the_current_task(qapp, tmp_path, monkeypatch):
    worker = QueueWorker(None, FFMPEG, str(tmp_path), parallel=1)
    collected = signals(worker)
    task_id = worker.enqueue(entry())
    calls = {"n": 0}

    def fetch_text(url, headers, timeout=20.0):
        return {HLS_URL: MASTER, VARIANT: MEDIA}.get(url)

    def fetch_bytes(url, headers, byte_range=None, timeout=60.0):
        calls["n"] += 1
        if calls["n"] == 1:
            # The user presses "Cancel" while the first segment fails.
            worker.cancel(task_id)
            raise RuntimeError("segment error")
        return SEGMENTS[url]

    def assemble(files, out_path, ffmpeg, work_dir, audio_files=(), mp3_bitrate=None, on_line=None):
        out_path.write_bytes(b"merged")
        return type("R", (), {"out_path": out_path, "log": "ok"})()

    monkeypatch.setattr(worker_mod, "fetch_text", fetch_text)
    monkeypatch.setattr(worker_mod, "fetch_bytes", fetch_bytes)
    monkeypatch.setattr("pydownloader.download.runner.assemble", assemble)
    run_queue(worker, collected, 1)
    assert collected["failed"] == [(task_id, "отменено")]
    assert not task_root(tmp_path, entry()).exists()
    assert any("Отменено" in line for line in collected["log"])
    # The cancelled task is not downloaded again: only one segment request was made.
    assert calls["n"] == 1


def test_failure_is_reported(qapp, tmp_path, monkeypatch):
    worker = QueueWorker(None, FFMPEG, str(tmp_path), parallel=1)
    collected = signals(worker)
    task_id = worker.enqueue(entry())

    def fetch_text(url, headers, timeout=20.0):
        return None

    monkeypatch.setattr(worker_mod, "fetch_text", fetch_text)
    run_queue(worker, collected, 1)
    assert collected["failed"] == [(task_id, "Не получен манифест: " + VARIANT)]
    assert any("Ошибка задачи" in line for line in collected["log"])


def test_pending_queue_order(qapp, tmp_path, http):
    worker = QueueWorker(None, FFMPEG, str(tmp_path), parallel=1)
    first = worker.enqueue(entry("s1"))
    second = worker.enqueue(entry("s2"))
    assert worker.pending() == [first, second]
    worker.cancel(second)
    assert worker.pending() == [first]


class FakeSniffer:
    """Only ``request_cookies`` is needed by the worker."""

    def request_cookies(self, url, timeout=10.0):
        if "site.example" in url:
            return [{"name": "session", "value": "s"}]
        return [{"name": "cdn", "value": "c"}]


def test_context_merges_page_and_cdn_cookies(qapp, tmp_path):
    entry_obj = entry()
    entry_obj.headers["Cookie"] = "captured=1"
    worker = QueueWorker(FakeSniffer(), FFMPEG, str(tmp_path))
    ctx = worker._context(build_task(entry_obj, tmp_path))
    cookie = ctx.headers["Cookie"]
    assert "captured=1" in cookie
    assert "session=s" in cookie
    assert "cdn=c" in cookie


def test_recorded_signed_url_is_preferred(qapp, tmp_path):
    entry_obj = entry()
    constructed = "https://cdn.example.com/video/video/seg100.ts?token=abc"
    signed = "https://cdn.example.com/video/video/seg100.ts?h=1&e=2"
    entry_obj.record(signed)
    worker = QueueWorker(None, FFMPEG, str(tmp_path))
    assert worker._recorded_url(entry_obj, constructed) == signed
