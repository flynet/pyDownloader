"""The browser extension shipped next to the program (uBlock).

A CRX file is a ZIP archive with a header. Chrome and Edge no longer load
extensions from the command line, so the extension is unpacked once and loaded
into the Chromium downloaded by Playwright (``--load-extension``). The folder is
cached by the hash of the CRX: a new file is unpacked again, the old one is kept
until the cache is cleaned.
"""

from __future__ import annotations

import hashlib
import io
import logging
import shutil
import tempfile
import zipfile
from pathlib import Path

from pydownloader.i18n import tr

logger = logging.getLogger("pydownloader.extensions")

#: Names searched next to the executable, in the order of preference.
EXTENSION_NAMES = ("uBlock.crx", "ublock.crx", "uBlockOrigin.crx", "uBlock-Origin.crx")
#: Header of every Chromium extension archive.
CRX_MAGIC = b"Cr24"


class ExtensionError(RuntimeError):
    """The CRX file is damaged or is not a Chromium extension."""


def find_crx(folder: Path) -> Path | None:
    """The ad blocker next to the program, ``None`` when it was not shipped."""
    if not folder.is_dir():
        return None
    files = {
        entry.name.lower(): entry
        for entry in folder.iterdir()
        if entry.is_file() and entry.suffix.lower() == ".crx"
    }
    for name in EXTENSION_NAMES:
        entry = files.get(name.lower())
        if entry is not None:
            return entry
    # Any uBlock-named archive (a version suffix, a different case).
    for key, entry in sorted(files.items()):
        if "ublock" in key:
            return entry
    return None


def _zip_start(data: bytes) -> int:
    """Offset of the ZIP payload after the CRX header."""
    if len(data) < 16 or data[:4] != CRX_MAGIC:
        raise ExtensionError(tr("ext_not_crx"))
    version = int.from_bytes(data[4:8], "little")
    if version == 2:
        # Cr24 v2: public key length, signature length, key, signature, ZIP.
        key_length = int.from_bytes(data[8:12], "little")
        signature_length = int.from_bytes(data[12:16], "little")
        start = 16 + key_length + signature_length
    elif version == 3:
        header_length = int.from_bytes(data[8:12], "little")
        start = 12 + header_length
    else:
        raise ExtensionError(tr("ext_unknown_version", value=version))
    if start >= len(data):
        raise ExtensionError(tr("ext_bad_header"))
    return start


def unpack_crx(crx: Path, target: Path) -> Path:
    """Extract the ZIP payload of ``crx`` into ``target`` and return the folder.

    The archive must contain ``manifest.json``; entries that would escape the
    target folder are rejected.
    """
    data = crx.read_bytes()
    start = _zip_start(data)
    target.mkdir(parents=True, exist_ok=True)
    root = target.resolve()
    try:
        with zipfile.ZipFile(io.BytesIO(data[start:])) as archive:
            for member in archive.infolist():
                destination = (target / member.filename).resolve()
                if not destination.is_relative_to(root):
                    raise ExtensionError(tr("ext_bad_path", path=member.filename))
            archive.extractall(target)
    except zipfile.BadZipFile as exc:
        raise ExtensionError(tr("ext_bad_zip")) from exc
    if not (target / "manifest.json").is_file():
        raise ExtensionError(tr("ext_no_manifest"))
    return target


def installed_extension(crx: Path, cache_dir: Path) -> Path:
    """Unpacked folder of the CRX, cached by the hash of the file.

    The same CRX is unpacked only once; a rebuilt archive gets a new folder, so
    a running browser is never surprised by files changing under it.
    """
    digest = hashlib.sha256(crx.read_bytes()).hexdigest()[:16]
    target = cache_dir / f"uBlock-{digest}"
    if (target / "manifest.json").is_file():
        return target
    cache_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="uBlock-", dir=cache_dir))
    try:
        unpack_crx(crx, staging)
        try:
            staging.rename(target)
        except OSError:
            # A parallel start unpacked the same CRX first: use its folder.
            if not (target / "manifest.json").is_file():
                raise
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    logger.info(tr("ext_unpacked", path=target))
    return target


def extension_dir(app_dir: Path, cache_dir: Path) -> Path | None:
    """Folder of the extension to load, ``None`` when it is not shipped or broken."""
    try:
        crx = find_crx(app_dir)
    except OSError as exc:
        logger.warning(tr("ext_dir_unreadable", path=app_dir, error=exc))
        return None
    if crx is None:
        return None
    try:
        return installed_extension(crx, cache_dir)
    except (OSError, ExtensionError) as exc:
        logger.warning(tr("ext_not_loaded", path=crx, error=exc))
        return None
