"""Queue worker tests: sequential tasks, progress, cancel (spec 6.2 p.1)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from pydownloader.browser.events import ResponseEvent
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
HLS_URL = "https://cdn.example.com/video/master.m3u8"
VARIANT = "https://cdn.example.com/video/video/1080.m3u8?token=abc"
SEGMENTS = {
    "https://cdn.example.com/video/video/seg100.ts?token=abc": b"A",
    "https://cdn.example.com/video/video/seg101.ts?token=abc": b"B",
    "https://cdn.example.com/video/video/seg102.ts?token=abc": b"C",
}
FFMPEG = Ffmpeg(path=Path("ffmpeg.exe"), label="test")


def entry(id: str = "s1") -> SourceEntry:
    registry = SourceRegistry(min_mp4_size=5 * 1024 * 1024)
    event = ResponseEvent(
        url=HLS_URL,
        page_url="https://site.example/watch/42",
        page_title="Клип",
        content_type="application/vnd.apple.mpegurl",
        request_headers={"referer": "https://site.example/watch/42"},
    )
    process_event(
        event,
        registry,
        lambda url, headers: {HLS_URL: MASTER, VARIANT: MEDIA}.get(url),
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

    def assemble(files, out_path, ffmpeg, work_dir, audio_files=(), on_line=None):
        out_path.write_bytes(b"merged")
        return type("R", (), {"out_path": out_path, "log": "ok"})()

    monkeypatch.setattr("pydownloader.download.runner.assemble", assemble)


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

    def assemble(files, out_path, ffmpeg, work_dir, audio_files=(), on_line=None):
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
