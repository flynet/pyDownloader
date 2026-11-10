"""The download worker: one sequential queue of tasks (spec 6.2 p.1, 4.4).

Only one video is downloaded at a time; the segments inside a task are
downloaded in parallel by the engine. The worker is a ``QThread``: it emits
Qt signals for the console and the progress of a card, and it never touches a
widget directly.
"""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget

from pydownloader.browser.sniffer import SnifferThread, cookies_for
from pydownloader.download.engine import CancelledError, DownloadError, Task
from pydownloader.download.http import FetchError, fetch_bytes, fetch_text
from pydownloader.download.runner import RunContext, build_task, output_path, run_task
from pydownloader.ffmpeg.locate import Ffmpeg, FfmpegNotFoundError
from pydownloader.manifest.registry import SourceEntry


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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sniffer = sniffer
        self.ffmpeg = ffmpeg
        self.download_dir = download_dir
        self.parallel = parallel
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
        headers = dict(task.entry.headers)
        cookies = cookies_for(self.sniffer, task.entry.url)
        if cookies:
            headers["Cookie"] = cookies
        return RunContext(
            headers=headers,
            fetch_text=lambda url, h: self._fetch_text(url, h),
            fetch_bytes=lambda url, h, rng: self._fetch_bytes(url, h, rng),
            ffmpeg=self.ffmpeg,
            should_stop=lambda: self._should_stop(task),
            log=self.log.emit,
            progress=lambda done, total: self.progress.emit(task.id, done, total),
            parallel=self.parallel,
        )

    def _should_stop(self, task: Task) -> bool:
        return self._stop or task.id in self._cancelled

    def _fetch_text(self, url: str, headers: dict) -> str | None:
        try:
            return fetch_text(url, headers)
        except FetchError as exc:
            self.log.emit(str(exc))
            return None

    def _fetch_bytes(self, url: str, headers: dict, byte_range) -> bytes:
        # The engine retries the segment, so the first failure is not fatal.
        return fetch_bytes(url, headers, byte_range)


__all__ = ["QueueWorker", "Task"]
