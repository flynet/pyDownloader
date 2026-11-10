"""The download engine: plan → files, with the rules of spec 6.2/6.3.

The core is Qt-free so it can be tested with a fake fetcher. It runs the items
of a plan in a pool of at most ``parallel`` threads (spec 6.2 p.3), retries a
failed item three times with an exponential pause, reuses a file that is
already on disk (resume), decrypts AES-128 segments and raises
:class:`CancelledError` when the user cancels the task.
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from pydownloader.dash.models import DashRepresentation
from pydownloader.download.aes import decrypt, key_bytes, segment_iv
from pydownloader.download.plan import PlanItem, build_plan
from pydownloader.hls.models import Playlist
from pydownloader.manifest.registry import SourceEntry
from pydownloader.util.ranges import ByteRange

#: Pause between the retries of a failed segment, in seconds (spec 6.2 p.6).
RETRY_PAUSES = (1.0, 2.0, 4.0)
#: Segments downloaded in parallel (spec 6.2 p.3).
MAX_PARALLEL = 6

CancelCheck = Callable[[], bool]
#: ``fetch(url, headers, byte_range)`` returns the bytes of one item.
FetchBytes = Callable[[str, dict[str, str], ByteRange | None], bytes]
Sleep = Callable[[float], None]


class CancelledError(RuntimeError):
    """The task was cancelled by the user."""


class DownloadError(RuntimeError):
    """A segment failed after all the retries."""


@dataclass
class Task:
    """One row of the queue: what to download and where the result goes."""

    id: str
    entry: SourceEntry
    tmp_dir: Path
    out_path: Path
    plan: list[PlanItem] = field(default_factory=list)

    @property
    def is_direct_mp4(self) -> bool:
        return any(item.stream == "file" for item in self.plan)


def plan_for_source(
    video_playlist: Playlist | None = None,
    video_rep: DashRepresentation | None = None,
    audio_playlist: Playlist | None = None,
    audio_rep: DashRepresentation | None = None,
    mp4_url: str | None = None,
) -> list[PlanItem]:
    """Plan of a parsed source: video segments, audio segments, or one file."""
    return build_plan(
        video_playlist=video_playlist,
        video_rep=video_rep,
        audio_playlist=audio_playlist,
        audio_rep=audio_rep,
        mp4_url=mp4_url,
    )


def download_plan(
    plan: Sequence[PlanItem],
    tmp_dir: Path,
    fetch: FetchBytes,
    headers: dict[str, str],
    should_stop: CancelCheck,
    parallel: int = MAX_PARALLEL,
    sleep: Sleep | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[Path]:
    """Download every item of the plan, returning the files in the plan order.

    A file that already exists with a non-zero size is reused (spec 6.2 p.5),
    so a task that was interrupted can be started again. A failed item is
    retried :data:`RETRY_PAUSES` times; after the last failure
    :class:`DownloadError` is raised.
    """
    if not plan:
        return []
    tmp_dir.mkdir(parents=True, exist_ok=True)
    keys: dict[str, bytes] = {}
    keys_lock = threading.Lock()
    progress_lock = threading.Lock()
    done = 0
    total = len(plan)
    results: dict[int, Path] = {}

    def worker(index: int, item: PlanItem) -> None:
        nonlocal done
        if should_stop():
            raise CancelledError("Задача отменена")
        target = tmp_dir / item.name
        if target.exists() and target.stat().st_size > 0:
            results[index] = target
        else:
            data = _fetch_with_retries(item, fetch, headers, should_stop, sleep)
            if item.key is not None and item.key.is_aes128:
                data = _decrypt_item(item, data, headers, fetch, keys, keys_lock)
            target.write_bytes(data)
            results[index] = target
        with progress_lock:
            done += 1
            if on_progress:
                on_progress(done, total)

    with ThreadPoolExecutor(max_workers=min(parallel, total)) as pool:
        futures = [pool.submit(worker, index, item) for index, item in enumerate(plan)]
        error: Exception | None = None
        for future in futures:
            try:
                future.result()
            except Exception as exc:
                error = exc
                break
        if error is not None:
            pool.shutdown(wait=False, cancel_futures=True)
            raise error
    if len(results) != total:
        raise DownloadError("Не все сегменты загружены")
    return [results[index] for index in range(total)]


def _fetch_with_retries(
    item: PlanItem,
    fetch: FetchBytes,
    headers: dict[str, str],
    should_stop: CancelCheck,
    sleep: Sleep | None,
) -> bytes:
    pauses = (0.0, *RETRY_PAUSES)
    last: Exception = DownloadError("Сегмент не скачан")
    for pause in pauses:
        if should_stop():
            raise CancelledError("Задача отменена")
        if pause and sleep:
            sleep(pause)
        try:
            return fetch(item.url, headers, item.byte_range)
        except Exception as exc:  # a segment failure is retried (spec 6.2 p.6)
            last = exc
    raise DownloadError(f"Сегмент не скачан после {len(pauses)} попыток: {item.url} ({last})")


def _decrypt_item(
    item: PlanItem,
    data: bytes,
    headers: dict[str, str],
    fetch: FetchBytes,
    keys: dict[str, bytes],
    keys_lock: threading.Lock,
) -> bytes:
    key = item.key
    if key is None or key.uri is None:
        raise DownloadError(f"Сегмент зашифрован, ключ не указан: {item.url}")
    with keys_lock:
        cached = keys.get(key.uri)
    if cached is None:
        cached = key_bytes(fetch(key.uri, headers, None))
        with keys_lock:
            keys[key.uri] = cached
    iv = segment_iv(key.iv, item.sequence)
    return decrypt(data, cached, iv)


def cleanup_tmp(tmp_dir: Path) -> None:
    """Delete the temporary directory of a cancelled task (spec 6.2 p.7)."""
    for file in sorted(tmp_dir.glob("*")):
        if file.is_dir():
            cleanup_tmp(file)
            with contextlib.suppress(OSError):
                file.rmdir()
        else:
            with contextlib.suppress(OSError):
                file.unlink()
    with contextlib.suppress(OSError):
        tmp_dir.rmdir()
