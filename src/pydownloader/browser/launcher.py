"""Finding a browser for Playwright (spec 7.2).

Order of attempts: installed Chrome → installed Edge → Chromium from Playwright.
Chromium is not shipped in the installer, so it is downloaded on demand by
``chromium_installer.py``.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

BrowserKind = Literal["chrome", "msedge", "chromium"]

LABELS = {"chrome": "Chrome", "msedge": "Edge", "chromium": "Chromium (Playwright)"}
CHROMIUM_WARNING = (
    "Chromium от Playwright может не проигрывать H.264/AAC на части сайтов: "
    "лучше использовать установленный Chrome или Edge"
)

#: Standard install locations of Chrome and Edge, including the per-user installs
#: created on machines without administrator rights.
PROGRAM_FILES = r"C:\Program Files"
PROGRAM_FILES_X86 = r"C:\Program Files (x86)"


class NoBrowserError(RuntimeError):
    """Neither Chrome, Edge nor Playwright Chromium is available."""


@dataclass(frozen=True)
class BrowserChoice:
    """The browser to launch. ``channel`` is the Playwright channel name."""

    kind: BrowserKind
    channel: str | None
    executable: str | None
    label: str

    @property
    def is_bundled_chromium(self) -> bool:
        return self.kind == "chromium"


def local_appdata() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) if base else Path.home() / "AppData" / "Local"


def browser_candidate_paths() -> list[tuple[BrowserKind, str]]:
    """Paths to check, in the order of the spec (Chrome first, then Edge)."""
    local = local_appdata()
    return [
        ("chrome", rf"{PROGRAM_FILES}\Google\Chrome\Application\chrome.exe"),
        ("chrome", rf"{PROGRAM_FILES_X86}\Google\Chrome\Application\chrome.exe"),
        ("chrome", str(local / "Google" / "Chrome" / "Application" / "chrome.exe")),
        ("msedge", rf"{PROGRAM_FILES_X86}\Microsoft\Edge\Application\msedge.exe"),
        ("msedge", rf"{PROGRAM_FILES}\Microsoft\Edge\Application\msedge.exe"),
        ("msedge", str(local / "Microsoft" / "Edge" / "Application" / "msedge.exe")),
    ]


def installed_browsers(
    candidates: list[tuple[BrowserKind, str]] | None = None,
    exists: Callable[[str], bool] = os.path.isfile,
) -> list[BrowserChoice]:
    """Installed Chrome/Edge, in the order of ``candidates`` (one entry per kind)."""
    paths = candidates if candidates is not None else browser_candidate_paths()
    found: list[BrowserChoice] = []
    for kind, path in paths:
        if exists(path) and all(choice.kind != kind for choice in found):
            found.append(
                BrowserChoice(kind=kind, channel=kind, executable=path, label=LABELS[kind])
            )
    return found


def chromium_executable(browsers_dir: Path) -> Path | None:
    """Path of the Playwright Chromium downloaded earlier, ``None`` if absent.

    ``PLAYWRIGHT_BROWSERS_PATH`` lays files out as
    ``chromium-<revision>/chrome-win/chrome.exe`` (and ``chrome.exe`` directly
    in older revisions).
    """
    if not browsers_dir.is_dir():
        return None
    patterns = ("chromium-*/chrome-win/chrome.exe", "chromium-*/chrome.exe", "chromium*/chrome.exe")
    for pattern in patterns:
        for candidate in sorted(browsers_dir.glob(pattern)):
            if candidate.is_file():
                return candidate
    return None


def resolve_browser(
    browsers_dir: Path,
    candidates: list[tuple[BrowserKind, str]] | None = None,
    exists: Callable[[str], bool] = os.path.isfile,
) -> BrowserChoice:
    """Chrome → Edge → the Chromium installed in ``browsers_dir``.

    Raises :class:`NoBrowserError` when nothing is available, so the caller can
    offer the Chromium download (spec 7.2).
    """
    installed = installed_browsers(candidates, exists)
    if installed:
        return installed[0]
    chromium = chromium_executable(browsers_dir)
    if chromium is not None:
        return BrowserChoice(
            kind="chromium", channel=None, executable=str(chromium), label=LABELS["chromium"]
        )
    raise NoBrowserError(
        "Не найдены Chrome и Edge, Chromium от Playwright не установлен. "
        "Установите Chrome или Edge, либо разрешите скачать Chromium."
    )


def launch_kwargs(choice: BrowserChoice, profile_dir: Path) -> dict[str, Any]:
    """Arguments of ``launch_persistent_context`` for the chosen browser.

    The profile is a separate directory (spec 7.2), so the user's own browser
    profile is not touched and there is no "profile is in use" conflict.
    """
    args = ["--no-first-run", "--no-default-browser-check", "--start-maximized"]
    kwargs: dict[str, Any] = {
        "user_data_dir": str(profile_dir),
        "headless": False,
        "no_viewport": True,
        "args": args,
    }
    if choice.channel:
        kwargs["channel"] = choice.channel
    elif choice.executable:
        kwargs["executable_path"] = choice.executable
    return kwargs
