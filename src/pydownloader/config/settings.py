"""User settings stored in ``%APPDATA%/PyDownloader/settings.json``."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from pydownloader.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, Language

ThemeName = Literal["dark", "light", "system"]
#: Dark first: it is the default, the system theme is the fallback choice.
THEMES: tuple[ThemeName, ...] = ("dark", "light", "system")

DEFAULT_THREADS = 6
DEFAULT_TARGET_HEIGHT = 1080
DEFAULT_MIN_MP4_SIZE = 1024 * 1024  # files under 1 MB are treated as not video
DEFAULT_UPDATE_CHECK_HOURS = 12


@dataclass
class Settings:
    download_dir: str = ""
    threads: int = DEFAULT_THREADS
    auto_update: bool = True
    theme: ThemeName = "dark"
    #: Language of the interface and of the log lines, applied at startup (spec 8.1).
    language: Language = DEFAULT_LANGUAGE
    target_height: int = DEFAULT_TARGET_HEIGHT
    min_mp4_size: int = DEFAULT_MIN_MP4_SIZE
    profile_in_downloads: bool = False
    #: Tray icon of the program (spec 4.3): the window is hidden, the menu is used.
    tray_enabled: bool = True
    #: «X» in the title bar hides the window to the tray instead of quitting.
    close_to_tray: bool = True
    #: The balloon that explains the tray is shown once (spec 4.3).
    tray_hint_seen: bool = False
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
        settings.theme = "dark"
    # An old settings file has no language at all, an edited one a value that is
    # not in the list: both fall back to the default language.
    if settings.language not in SUPPORTED_LANGUAGES:
        settings.language = DEFAULT_LANGUAGE
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
