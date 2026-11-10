"""Engine tests: parallel downloads, resume, retries, cancel, AES (spec 6.2/6.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pydownloader.download.engine import (
    RETRY_PAUSES,
    CancelledError,
    DownloadError,
    cleanup_tmp,
    download_plan,
)
from pydownloader.download.plan import PlanItem
from pydownloader.hls.models import Key

TMP = ".tmp/s1"


def item(name: str, url: str, order: int, key: Key | None = None, sequence: int = 0) -> PlanItem:
    return PlanItem(url=url, name=name, stream="video", order=order, key=key, sequence=sequence)


def make_fetch(bodies: dict[str, bytes], calls: list[str] | None = None):
    used = calls if calls is not None else []

    def fetch(url: str, headers: dict, byte_range) -> bytes:
        used.append(url)
        if url not in bodies:
            raise RuntimeError(f"404 {url}")
        return bodies[url]

    return fetch


def test_downloads_every_item(tmp_path: Path):
    plan = [
        item("video-00000.ts", "https://a/1.ts", 0),
        item("video-00001.ts", "https://a/2.ts", 1),
    ]
    fetch = make_fetch({"https://a/1.ts": b"AA", "https://a/2.ts": b"BB"})
    files = download_plan(plan, tmp_path / TMP, fetch, {}, lambda: False)
    assert [f.name for f in files] == ["video-00000.ts", "video-00001.ts"]
    assert files[0].read_bytes() == b"AA"
    assert files[1].read_bytes() == b"BB"


def test_progress_is_reported(tmp_path: Path):
    plan = [item(f"video-0000{i}.ts", f"https://a/{i}.ts", i) for i in range(3)]
    fetch = make_fetch({f"https://a/{i}.ts": b"x" for i in range(3)})
    seen: list[tuple[int, int]] = []
    download_plan(
        plan,
        tmp_path / TMP,
        fetch,
        {},
        lambda: False,
        parallel=1,
        on_progress=lambda done, total: seen.append((done, total)),
    )
    assert sorted(seen) == [(1, 3), (2, 3), (3, 3)]


def test_existing_segment_is_not_downloaded_again(tmp_path: Path):
    """Resume (spec 6.2 p.5): a file already on disk is kept as it is."""
    tmp = tmp_path / TMP
    tmp.mkdir(parents=True)
    (tmp / "video-00000.ts").write_bytes(b"done")
    plan = [
        item("video-00000.ts", "https://a/1.ts", 0),
        item("video-00001.ts", "https://a/2.ts", 1),
    ]
    calls: list[str] = []
    fetch = make_fetch({"https://a/1.ts": b"new", "https://a/2.ts": b"BB"}, calls)
    files = download_plan(plan, tmp, fetch, {}, lambda: False, parallel=1)
    assert calls == ["https://a/2.ts"]
    assert files[0].read_bytes() == b"done"


def test_empty_file_is_downloaded(tmp_path: Path):
    tmp = tmp_path / TMP
    tmp.mkdir(parents=True)
    (tmp / "video-00000.ts").write_bytes(b"")
    fetch = make_fetch({"https://a/1.ts": b"data"})
    files = download_plan(
        [item("video-00000.ts", "https://a/1.ts", 0)], tmp, fetch, {}, lambda: False, parallel=1
    )
    assert files[0].read_bytes() == b"data"


def test_retries_then_succeeds(tmp_path: Path):
    attempts = {"n": 0}

    def fetch(url: str, headers: dict, byte_range) -> bytes:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("connection reset")
        return b"ok"

    sleeps: list[float] = []
    files = download_plan(
        [item("video-00000.ts", "https://a/1.ts", 0)],
        tmp_path / TMP,
        fetch,
        {},
        lambda: False,
        parallel=1,
        sleep=sleeps.append,
    )
    assert files[0].read_bytes() == b"ok"
    # Two pauses are applied before the third attempt.
    assert sleeps == list(RETRY_PAUSES[:2])


def test_retries_are_exponential(tmp_path: Path):
    def fetch(url: str, headers: dict, byte_range) -> bytes:
        raise RuntimeError("always fails")

    sleeps: list[float] = []
    with pytest.raises(DownloadError, match="попыток"):
        download_plan(
            [item("video-00000.ts", "https://a/1.ts", 0)],
            tmp_path / TMP,
            fetch,
            {},
            lambda: False,
            parallel=1,
            sleep=sleeps.append,
        )
    assert sleeps == list(RETRY_PAUSES)


def test_cancel_stops_before_download(tmp_path: Path):
    calls: list[str] = []
    fetch = make_fetch({"https://a/1.ts": b"x"}, calls)
    with pytest.raises(CancelledError):
        download_plan(
            [item("video-00000.ts", "https://a/1.ts", 0)],
            tmp_path / TMP,
            fetch,
            {},
            lambda: True,
            parallel=1,
        )
    assert calls == []


def test_aes_segment_is_decrypted(tmp_path: Path):
    key = Key(method="AES-128", uri="https://a/key.bin", iv=None)
    plain = b"segment payload"
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.padding import PKCS7

    iv = (100).to_bytes(16, "big")
    key_bytes = bytes(range(16))
    pad = PKCS7(128).padder()
    padded = pad.update(plain) + pad.finalize()
    enc = Cipher(algorithms.AES(key_bytes), modes.CBC(iv)).encryptor()
    body = enc.update(padded) + enc.finalize()
    bodies = {"https://a/1.ts": body, "https://a/key.bin": key_bytes}
    calls: list[str] = []
    fetch = make_fetch(bodies, calls)
    plan = [item("video-00000.ts", "https://a/1.ts", 0, key=key, sequence=100)]
    files = download_plan(plan, tmp_path / TMP, fetch, {}, lambda: False, parallel=1)
    assert files[0].read_bytes() == plain
    # The key is fetched once, before the segment is written.
    assert calls.count("https://a/key.bin") == 1


def test_key_of_bad_size_is_an_error(tmp_path: Path):
    key = Key(method="AES-128", uri="https://a/key.bin")
    fetch = make_fetch({"https://a/1.ts": b"x" * 16, "https://a/key.bin": b"<html>"})
    with pytest.raises(ValueError, match="16"):
        download_plan(
            [item("video-00000.ts", "https://a/1.ts", 0, key=key, sequence=1)],
            tmp_path / TMP,
            fetch,
            {},
            lambda: False,
            parallel=1,
        )


def test_parallelism_is_limited(tmp_path: Path):
    import threading

    active = {"max": 0, "now": 0}
    lock = threading.Lock()

    def fetch(url: str, headers: dict, byte_range) -> bytes:
        with lock:
            active["now"] += 1
            active["max"] = max(active["max"], active["now"])
        import time

        time.sleep(0.01)
        with lock:
            active["now"] -= 1
        return b"x"

    plan = [item(f"video-{i:05d}.ts", f"https://a/{i}.ts", i) for i in range(12)]
    download_plan(plan, tmp_path / TMP, fetch, {}, lambda: False, parallel=6)
    assert active["max"] <= 6
    assert active["max"] > 1


def test_cleanup_removes_tmp(tmp_path: Path):
    tmp = tmp_path / ".tmp/s1"
    (tmp / "sub").mkdir(parents=True)
    (tmp / "a.ts").write_bytes(b"x")
    (tmp / "sub" / "b.ts").write_bytes(b"y")
    cleanup_tmp(tmp)
    assert not tmp.exists()


def test_empty_plan_returns_no_files(tmp_path: Path):
    assert download_plan([], tmp_path, lambda *a: b"", {}, lambda: False) == []
