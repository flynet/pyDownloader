"""The download worker: one sequential queue of tasks (spec 6.2 p.1, 4.4).

Only one video is downloaded at a time; the segments inside a task are
downloaded in parallel by the engine. The worker is a ``QThread``: it emits
Qt signals for the console and the progress of a card, and it never touches a
widget directly.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget

from pydownloader.browser.sniffer import SnifferThread, browser_cookies
from pydownloader.config.settings import DEFAULT_TARGET_HEIGHT
from pydownloader.download.engine import CancelledError, DownloadError, Task
from pydownloader.download.http import FetchError, fetch_bytes, fetch_text, merge_cookies
from pydownloader.download.runner import RunContext, build_task, output_path, run_task
from pydownloader.ffmpeg.locate import Ffmpeg, FfmpegNotFoundError
from pydownloader.manifest.registry import SourceEntry
from pydownloader.util.urls import path_extension

#: How long a segment waits for the sniffer to record its signed URL, in seconds.
RECORDED_POLL = 10.0
RECORDED_POLL_STEP = 0.25


class QueueWorker(QThread):
    """Runs the queue of download tasks, one task at a time."""

    log = Signal(str)
    progress = Signal(str, int, int)  # task id, segments done, segments total
    task_started = Signal(str, str)  # task id, file name
    task_finished = Signal(str, str)  # task id, path of the finished file
    task_failed = Signal(str, str)  # task id, message

    def __init__(
        self,
        sniffer: SnifferThread | None,
        ffmpeg: Ffmpeg,
        download_dir: str,
        parallel: int = 6,
        target_height: int = DEFAULT_TARGET_HEIGHT,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sniffer = sniffer
        self.ffmpeg = ffmpeg
        self.download_dir = download_dir
        self.parallel = parallel
        self.target_height = target_height
        self._queue: list[Task] = []
        self._cancelled: set[str] = set()
        self._lock = threading.Lock()
        self._stop = False
        self._current: Task | None = None

    def enqueue(self, entry: SourceEntry) -> str:
        """Add a source to the queue, returning the id of the task."""
        task = build_task(entry, self._root())
        with self._lock:
            self._queue.append(task)
        return task.id

    def cancel(self, task_id: str) -> None:
        """Cancel a task: the current one stops and its temp files are deleted."""
        with self._lock:
            self._cancelled.add(task_id)
            self._queue = [task for task in self._queue if task.id != task_id]

    def stop(self) -> None:
        """Ask the worker to finish (the window is closing)."""
        self._stop = True

    def pending(self) -> list[str]:
        """Ids of the queued tasks, in the order of the queue."""
        with self._lock:
            return [task.id for task in self._queue]

    def _root(self) -> Path:
        return Path(self.download_dir)

    def run(self) -> None:
        while not self._stop:
            with self._lock:
                if not self._queue:
                    return
                task = self._queue.pop(0)
                self._current = task
            self._run_one(task)

    def _run_one(self, task: Task) -> None:
        # The destination name is decided when the task starts, so a file created by
        # an earlier task in the queue does not get overwritten.
        task.out_path = output_path(self._root(), task.entry)
        ctx = self._context(task)
        self.task_started.emit(task.id, task.out_path.name)
        try:
            path = run_task(task, ctx)
            self.task_finished.emit(task.id, str(path))
        except CancelledError:
            self.log.emit(f"Отменено: {task.entry.title or task.entry.url}")
            self.task_failed.emit(task.id, "отменено")
        except (DownloadError, FetchError, FfmpegNotFoundError) as exc:
            self.log.emit(f"Ошибка задачи {task.entry.title or task.entry.url}: {exc}")
            self.task_failed.emit(task.id, str(exc))
        except Exception as exc:  # an unexpected failure must reach the console
            self.log.emit(f"Ошибка задачи {task.entry.title or task.entry.url}: {exc}")
            self.task_failed.emit(task.id, str(exc))

    def _context(self, task: Task) -> RunContext:
        entry = task.entry
        # The page cookie carries the session, the CDN cookie the stream signature.
        # Both are merged into the captured request cookies instead of replacing them.
        headers = dict(entry.headers)
        cookies = browser_cookies(self.sniffer, (entry.page_url, entry.url))
        if cookies:
            headers = merge_cookies(headers, cookies)
        return RunContext(
            headers=headers,
            fetch_text=lambda url, h: self._fetch_text(entry, url, h),
            fetch_bytes=lambda url, h, rng: self._fetch_bytes(entry, url, h, rng),
            ffmpeg=self.ffmpeg,
            should_stop=lambda: self._should_stop(task),
            log=self.log.emit,
            progress=lambda done, total: self.progress.emit(task.id, done, total),
            parallel=self.parallel,
            target_height=self.target_height,
        )

    def _should_stop(self, task: Task) -> bool:
        return self._stop or task.id in self._cancelled

    def _fetch_text(self, entry: SourceEntry, url: str, headers: dict) -> str | None:
        recorded = self._recorded_url(entry, url)
        if recorded is not None and recorded != url:
            try:
                return fetch_text(recorded, headers)
            except FetchError:
                pass  # the signed URL expired; try the constructed one below
        try:
            return fetch_text(url, headers)
        except FetchError as exc:
            self.log.emit(str(exc))
            return None

    def _fetch_bytes(self, entry: SourceEntry, url: str, headers: dict, byte_range) -> bytes:
        """Download one item, preferring the exact signed URL seen in browser traffic.

        A CDN that signs every path individually rejects a URL constructed from
        the playlist. When the signed URL is not recorded yet, the sniffer is
        polled for a few seconds; the engine retries the item after that.
        """
        recorded = self._recorded_url(entry, url)
        if recorded is not None and recorded != url:
            try:
                return fetch_bytes(recorded, headers, byte_range)
            except FetchError:
                pass  # the signed URL expired; fall back to the constructed one
        return fetch_bytes(url, headers, byte_range)

    def _recorded_url(self, entry: SourceEntry, url: str) -> str | None:
        found = entry.recorded_url(url)
        if found is not None:
            return found
        if not entry.recorded:
            return None
        # Only wait when the entry records files of the same kind: an audio track
        # of a signed CDN has its own directory (and its own family entry).
        ext = path_extension(url)
        if not any(path_extension(value) == ext for value in entry.recorded.values()):
            return None
        deadline = time.monotonic() + RECORDED_POLL
        while time.monotonic() < deadline:
            time.sleep(RECORDED_POLL_STEP)
            found = entry.recorded_url(url)
            if found is not None:
                return found
        return None


__all__ = ["QueueWorker", "Task"]
