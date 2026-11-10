"""Unpacking the bundled CRX and caching the folder (uBlock)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from pydownloader.browser.extensions import (
    ExtensionError,
    extension_dir,
    find_crx,
    installed_extension,
    unpack_crx,
)

MANIFEST = b'{"manifest_version": 3, "name": "uBlock", "version": "1.0"}'


def crx_bytes(files: dict[str, bytes] | None = None, version: int = 3) -> bytes:
    """A minimal CRX around a real ZIP payload."""
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        for name, data in (files or {"manifest.json": MANIFEST}).items():
            archive.writestr(name, data)
    if version == 2:
        key = b"public key"
        signature = b"signature"
        return (
            b"Cr24"
            + (2).to_bytes(4, "little")
            + len(key).to_bytes(4, "little")
            + len(signature).to_bytes(4, "little")
            + key
            + signature
            + payload.getvalue()
        )
    header = b"\x00\x00\x00\x00"
    return (
        b"Cr24"
        + (3).to_bytes(4, "little")
        + len(header).to_bytes(4, "little")
        + header
        + payload.getvalue()
    )


def write_crx(folder: Path, data: bytes, name: str = "uBlock.crx") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(data)
    return path


def test_find_crx_prefers_ublock(tmp_path: Path):
    write_crx(tmp_path, crx_bytes(), "uBlock.crx")
    write_crx(tmp_path, crx_bytes(), "other.crx")
    assert find_crx(tmp_path).name == "uBlock.crx"


def test_find_crx_matches_any_ublock_name(tmp_path: Path):
    write_crx(tmp_path, crx_bytes(), "uBlock-Origin-1.2.3.crx")
    assert find_crx(tmp_path).name == "uBlock-Origin-1.2.3.crx"


def test_find_crx_none_when_not_shipped(tmp_path: Path):
    assert find_crx(tmp_path) is None
    assert find_crx(tmp_path / "missing") is None
    write_crx(tmp_path, crx_bytes(), "something.crx")
    assert find_crx(tmp_path) is None


def test_unpack_crx3(tmp_path: Path):
    crx = write_crx(tmp_path / "app", crx_bytes())
    target = unpack_crx(crx, tmp_path / "unpacked")
    assert (target / "manifest.json").read_bytes() == MANIFEST


def test_unpack_crx2(tmp_path: Path):
    crx = write_crx(tmp_path / "app", crx_bytes(version=2))
    target = unpack_crx(crx, tmp_path / "unpacked")
    assert (target / "manifest.json").is_file()


def test_unpack_rejects_a_file_that_is_not_crx(tmp_path: Path):
    broken = tmp_path / "broken.crx"
    broken.write_bytes(b"not a crx at all")
    with pytest.raises(ExtensionError):
        unpack_crx(broken, tmp_path / "unpacked")


def test_unpack_rejects_a_bad_zip(tmp_path: Path):
    broken = tmp_path / "broken.crx"
    broken.write_bytes(b"Cr24" + (3).to_bytes(4, "little") + (0).to_bytes(4, "little") + b"junk")
    with pytest.raises(ExtensionError):
        unpack_crx(broken, tmp_path / "unpacked")


def test_unpack_rejects_an_archive_without_manifest(tmp_path: Path):
    crx = write_crx(tmp_path / "app", crx_bytes({"readme.txt": b"hi"}))
    with pytest.raises(ExtensionError):
        unpack_crx(crx, tmp_path / "unpacked")


def test_unpack_rejects_path_traversal(tmp_path: Path):
    crx = write_crx(
        tmp_path / "app",
        crx_bytes({"manifest.json": MANIFEST, "../evil.txt": b"oops"}),
    )
    target = tmp_path / "unpacked"
    with pytest.raises(ExtensionError):
        unpack_crx(crx, target)
    assert not (tmp_path / "evil.txt").exists()


def test_unpack_accepts_nested_files(tmp_path: Path):
    crx = write_crx(
        tmp_path / "app",
        crx_bytes({"manifest.json": MANIFEST, "js/background.js": b"//"}),
    )
    target = unpack_crx(crx, tmp_path / "unpacked")
    assert (target / "js" / "background.js").read_bytes() == b"//"


def test_installed_extension_is_cached_by_hash(tmp_path: Path):
    crx = write_crx(tmp_path / "app", crx_bytes())
    cache = tmp_path / "cache"
    first = installed_extension(crx, cache)
    (first / "marker.txt").write_text("keep", encoding="utf-8")
    second = installed_extension(crx, cache)
    assert second == first
    assert (second / "marker.txt").is_file()


def test_a_new_crx_gets_a_new_folder(tmp_path: Path):
    crx = write_crx(tmp_path / "app", crx_bytes())
    cache = tmp_path / "cache"
    first = installed_extension(crx, cache)
    crx.write_bytes(crx_bytes({"manifest.json": MANIFEST, "new.js": b"//"}))
    second = installed_extension(crx, cache)
    assert second != first
    assert (second / "new.js").is_file()


def test_extension_dir_returns_none_when_absent(tmp_path: Path):
    assert extension_dir(tmp_path / "app", tmp_path / "cache") is None


def test_extension_dir_unpacks_the_shipped_file(tmp_path: Path):
    write_crx(tmp_path / "app", crx_bytes())
    folder = extension_dir(tmp_path / "app", tmp_path / "cache")
    assert folder is not None
    assert (folder / "manifest.json").is_file()


def test_extension_dir_survives_a_broken_file(tmp_path: Path):
    write_crx(tmp_path / "app", b"broken")
    assert extension_dir(tmp_path / "app", tmp_path / "cache") is None
