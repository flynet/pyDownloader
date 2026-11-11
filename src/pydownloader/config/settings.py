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
BrowserName = Literal["auto", "chrome", "msedge", "chromium"]
#: «Auto» first: Chrome → Edge → Chromium, the order of the spec (spec 7.2).
BROWSERS: tuple[BrowserName, ...] = ("auto", "chrome", "msedge", "chromium")

DEFAULT_THREADS = 6
DEFAULT_TARGET_HEIGHT = 1080
DEFAULT_MIN_MP4_SIZE = 1024 * 1024  # files under 1 MB are treated as not video
DEFAULT_UPDATE_CHECK_HOURS = 12
#: MP3 bitrate of an audio source, the middle choice of the settings (spec 5.2 p.4).
DEFAULT_MP3_BITRATE = 192
#: Bitrates the settings offer for an audio source, the values FFmpeg accepts.
MP3_BITRATES: tuple[int, ...] = (128, 192, 320)
#: Quality presets the settings offer: the heights of the quality dropdown (spec 5.2 p.3).
QUALITY_PRESETS: tuple[int, ...] = (1080, 720, 480)


@dataclass
class Settings:
    download_dir: str = ""
    threads: int = DEFAULT_THREADS
    auto_update: bool = True
    theme: ThemeName = "dark"
    #: Language of the interface and of the log lines, applied at startup (spec 8.1).
    language: Language = DEFAULT_LANGUAGE
    #: Browser to launch: «auto» is the order of the spec, a name is the choice
    #: of the user (spec 7.2).
    browser_name: BrowserName = "auto"
    #: User agent the browser sends, ``""`` takes the Chrome form of the version.
    user_agent: str = ""
    #: Stealth of the launch: the flags of a driver are dropped (spec 7.2).
    anti_bot: bool = True
    #: Load the bundled ad blocker when the browser is able to load it (spec 6.4).
    ad_blocker: bool = True
    target_height: int = DEFAULT_TARGET_HEIGHT
    min_mp4_size: int = DEFAULT_MIN_MP4_SIZE
    #: «Audio only (MP3)»: video sources are not shown, audio sources are saved
    #: as ``.mp3`` (spec 5.2 p.4).
    audio_only: bool = False
    #: Bitrate of the MP3 file an audio source is written with (spec 5.2 p.4).
    mp3_bitrate: int = DEFAULT_MP3_BITRATE
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
    #: The console panel starts hidden: the list of found videos gets the whole
    #: window (spec 4.2 p.5), «Show console» in the row of buttons opens it back.
    console_open: bool = False
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
    # A browser the settings name is not in the list (an edited file): launch the
    # order of the spec, which is the same as before the setting existed.
    if settings.browser_name not in BROWSERS:
        settings.browser_name = "auto"
    # An old settings file has no language at all, an edited one a value that is
    # not in the list: both fall back to the default language.
    if settings.language not in SUPPORTED_LANGUAGES:
        settings.language = DEFAULT_LANGUAGE
    settings.threads = max(1, min(32, int(settings.threads)))
    settings.target_height = max(0, int(settings.target_height))
    settings.min_mp4_size = max(0, int(settings.min_mp4_size))
    # FFmpeg accepts the bitrates the settings offer; an edited file with another
    # number falls back to the middle choice, so the MP3 command is always valid.
    if settings.mp3_bitrate not in MP3_BITRATES:
        settings.mp3_bitrate = DEFAULT_MP3_BITRATE
    return settings


def save_settings(settings: Settings, path: Path) -> None:
    """Write settings, creating the parent folder."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(settings), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
