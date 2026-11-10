"""User settings stored in ``%APPDATA%/PyDownloader/settings.json``."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

ThemeName = Literal["system", "light", "dark"]
THEMES: tuple[ThemeName, ...] = ("system", "light", "dark")

DEFAULT_THREADS = 6
DEFAULT_TARGET_HEIGHT = 1080
DEFAULT_MIN_MP4_SIZE = 1024 * 1024  # files under 1 MB are treated as not video
DEFAULT_UPDATE_CHECK_HOURS = 12


@dataclass
class Settings:
    download_dir: str = ""
    threads: int = DEFAULT_THREADS
    auto_update: bool = True
    theme: ThemeName = "system"
    target_height: int = DEFAULT_TARGET_HEIGHT
    min_mp4_size: int = DEFAULT_MIN_MP4_SIZE
    profile_in_downloads: bool = False
    update_check_hours: int = DEFAULT_UPDATE_CHECK_HOURS
    skipped_version: str = ""
    #: Timestamp of the last successful API check, cached for ``update_check_hours``.
    last_update_check: str = ""
    window_geometry: str = ""


def load_settings(path: Path) -> Settings:
    """Read settings; a missing or damaged file falls back to the defaults."""
    settings = Settings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return settings
    for key, value in raw.items():
        if not hasattr(settings, key):
            continue
        default = getattr(settings, key)
        if type(value) is type(default):
            setattr(settings, key, value)
    if settings.theme not in THEMES:
        settings.theme = "system"
    settings.threads = max(1, min(32, int(settings.threads)))
    settings.target_height = max(0, int(settings.target_height))
    settings.min_mp4_size = max(0, int(settings.min_mp4_size))
    return settings


def save_settings(settings: Settings, path: Path) -> None:
    """Write settings, creating the parent folder."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(settings), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
