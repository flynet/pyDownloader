"""Where the installed application is allowed to write.

The program lives in ``Program Files`` and never writes into its own folder.
Settings go to ``%APPDATA%/PyDownloader``; logs, the browser profile and the
downloaded Chromium go to ``%LOCALAPPDATA%/PyDownloader``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from pydownloader.config.constants import APP_NAME


def _app_data_root() -> Path:
    base = os.environ.get("APPDATA")
    return Path(base) / APP_NAME if base else Path.home() / "AppData" / "Roaming" / APP_NAME


def _local_app_data_root() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / APP_NAME if base else Path.home() / "AppData" / "Local" / APP_NAME


@dataclass(frozen=True)
class Paths:
    settings_file: Path
    log_dir: Path
    log_file: Path
    data_dir: Path
    browsers_dir: Path
    profile_dir: Path


def default_paths(profile_in_downloads: bool = False, downloads_dir: Path | None = None) -> Paths:
    """Build the standard layout.

    ``profile_in_downloads`` moves the browser profile into ``<downloads>/.profile``
    (the alternative offered in the settings, the default is LocalAppData).
    """
    local = _local_app_data_root()
    if profile_in_downloads and downloads_dir is not None:
        profile = downloads_dir / ".profile"
    else:
        profile = local / "profile"
    return Paths(
        settings_file=_app_data_root() / "settings.json",
        log_dir=local / "logs",
        log_file=local / "logs" / "app.log",
        data_dir=local,
        browsers_dir=local / "browsers",
        profile_dir=profile,
    )


def task_tmp_dir(downloads_dir: Path, task_id: str) -> Path:
    """Temporary folder of one task: ``<downloads>/.tmp/<task id>``."""
    return downloads_dir / ".tmp" / task_id
