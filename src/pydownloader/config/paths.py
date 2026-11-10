"""Where the installed application is allowed to write.

Everything the program produces lives in the program folder (``<app>``) so that
removing the installation removes the data: ``<app>/logs``,
``<app>/browsers`` (the Chromium downloaded by Playwright),
``<app>/extensions`` (the unpacked ad blocker) and ``<app>/profile`` (cookies,
sessions). Settings stay in ``%APPDATA%/PyDownloader`` — they survive a
reinstall. When the program folder is not writable (a ``Program Files`` install
without administrator rights), all of it falls back to
``%LOCALAPPDATA%/PyDownloader``. Chromium downloaded by an older version is
found in LocalAppData and reused, so nothing is downloaded twice.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pydownloader.config.constants import APP_NAME

logger = logging.getLogger("pydownloader.paths")


def _app_data_root() -> Path:
    base = os.environ.get("APPDATA")
    return Path(base) / APP_NAME if base else Path.home() / "AppData" / "Roaming" / APP_NAME


def _local_app_data_root() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / APP_NAME if base else Path.home() / "AppData" / "Local" / APP_NAME


def application_dir() -> Path:
    """Folder of the program: next to ``PyDownloader.exe`` or the checkout root.

    In a frozen build this is the folder the user installed the program into
    (``{app}``); in a source checkout it is the repository root, so running
    ``run.bat`` behaves exactly like the installed application.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Paths:
    settings_file: Path
    log_dir: Path
    log_file: Path
    data_dir: Path
    browsers_dir: Path
    profile_dir: Path
    #: Where an older version downloaded Chromium (``%LOCALAPPDATA%``), reused if found.
    legacy_browsers_dir: Path | None = None


def _writable(folder: Path) -> bool:
    """Whether a file can be created in ``folder`` (the profile lives there)."""
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=folder, prefix=".write-test-", delete=True):
            pass
    except OSError:
        return False
    return True


def _data_root(app_dir: Path | None, local: Path) -> Path:
    """Folder for the data the program writes: the program folder when writable.

    Logs, the downloaded Chromium and the unpacked ad blocker live there, so
    deleting the installation deletes them with it.
    """
    if app_dir is None:
        return local
    if not _writable(app_dir):
        logger.warning(
            "Папка программы %s недоступна для записи, данные остаются в %s",
            app_dir,
            local,
        )
        return local
    return app_dir


def _migrate_profile(old: Path, new: Path) -> bool:
    """Move the profile of an older version next to the program.

    The profile used to live in ``%LOCALAPPDATA%``; moving it once keeps the
    sessions the user already has. ``False`` means the old folder stays in use
    (it is locked, or the disk refused the move).
    """
    if new.exists() and not new.is_dir():
        logger.warning("Путь профиля занят файлом: %s", new)
        return False
    if not old.is_dir() or new.exists():
        return True
    try:
        shutil.move(str(old), str(new))
    except OSError as exc:
        logger.warning("Не удалось перенести профиль %s в %s: %s", old, new, exc)
        return False
    logger.info("Профиль браузера перенесён: %s -> %s", old, new)
    return True


def _profile_dir(
    local: Path,
    profile_in_downloads: bool,
    downloads_dir: Path | None,
    app_dir: Path | None,
) -> Path:
    fallback = local / "profile"
    if profile_in_downloads and downloads_dir is not None:
        return downloads_dir / ".profile"
    if app_dir is None:
        return fallback
    if not _writable(app_dir):
        logger.warning(
            "Папка программы %s недоступна для записи, профиль остаётся в %s",
            app_dir,
            fallback,
        )
        return fallback
    target = app_dir / "profile"
    if not _migrate_profile(fallback, target):
        return fallback
    return target


def default_paths(
    profile_in_downloads: bool = False,
    downloads_dir: Path | None = None,
    app_dir: Path | None = None,
) -> Paths:
    """Build the standard layout.

    Logs, Chromium and the unpacked ad blocker go to the program folder
    (``app_dir``) when it is writable, to LocalAppData otherwise.
    ``profile_in_downloads`` moves the browser profile into ``<downloads>/.profile``
    (the alternative offered in the settings); otherwise the profile is kept in
    ``<app_dir>/profile`` and in LocalAppData as the last resort.
    """
    local = _local_app_data_root()
    root = _data_root(app_dir, local)
    return Paths(
        settings_file=_app_data_root() / "settings.json",
        log_dir=root / "logs",
        log_file=root / "logs" / "app.log",
        data_dir=root,
        browsers_dir=root / "browsers",
        profile_dir=_profile_dir(
            local, profile_in_downloads, downloads_dir, root if app_dir is not None else None
        ),
        legacy_browsers_dir=local / "browsers",
    )


def download_dir_default() -> Path:
    """Default folder for the videos: the user's ``Downloads``."""
    return Path.home() / "Downloads"


def task_tmp_dir(downloads_dir: Path, task_id: str) -> Path:
    """Temporary folder of one task: ``<downloads>/.tmp/<task id>``."""
    return downloads_dir / ".tmp" / task_id
