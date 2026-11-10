"""Finding a browser for Playwright (spec 7.2).

Order of attempts: installed Chrome → installed Edge → Chromium from Playwright.
Chromium is not shipped in the installer, so it is downloaded on demand by
``chromium_installer.py``. When the bundled ad blocker must be loaded, Chromium
is preferred: Chrome and Edge ignore ``--load-extension`` from the command line.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydownloader.browser.stealth import (
    DEFAULT_LOCALE,
    browser_version,
    chrome_user_agent,
    launch_args,
    stealth_kwargs,
)
from pydownloader.i18n import tr

BrowserKind = Literal["chrome", "msedge", "chromium"]

LABELS = {"chrome": "Chrome", "msedge": "Edge", "chromium": "Chromium (Playwright)"}
#: English reference of the key ``browser_codec_warning``: the warning shown to
#: the user is taken from the catalog, the constant is only its default text.
CHROMIUM_WARNING = (
    "Chromium from Playwright may not play H.264/AAC on some sites: "
    "the installed Chrome or Edge is a better choice"
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


def chromium_executable(browsers_dir: Path, legacy_dir: Path | None = None) -> Path | None:
    """Path of the Playwright Chromium downloaded earlier, ``None`` if absent.

    ``PLAYWRIGHT_BROWSERS_PATH`` lays files out as
    ``chromium-<revision>/chrome-win64/chrome.exe`` (``chrome-win`` and
    ``chrome.exe`` directly in older revisions). The folders are searched in
    order: the program folder first, then ``legacy_dir`` where an older version
    put the download, so a Chromium of a previous install is reused.
    """
    folders = [browsers_dir] if legacy_dir is None else [browsers_dir, legacy_dir]
    patterns = (
        "chromium-*/chrome-win64/chrome.exe",
        "chromium-*/chrome-win/chrome.exe",
        "chromium-*/chrome.exe",
        "chromium*/chrome.exe",
    )
    for pattern in patterns:
        for folder in folders:
            for candidate in sorted(folder.glob(pattern)):
                if candidate.is_file():
                    return candidate
    return None


def _chromium_choice(executable: Path) -> BrowserChoice:
    return BrowserChoice(
        kind="chromium", channel=None, executable=str(executable), label=LABELS["chromium"]
    )


def resolve_browser(
    browsers_dir: Path,
    candidates: list[tuple[BrowserKind, str]] | None = None,
    exists: Callable[[str], bool] = os.path.isfile,
    prefer_chromium: bool = False,
    legacy_dir: Path | None = None,
    name: str = "auto",
) -> BrowserChoice:
    """The browser to launch, from the name the user chose in the settings.

    ``auto`` is Chrome → Edge → the Chromium installed in ``browsers_dir``, the
    order of the spec. A chosen name is honoured: ``chromium`` is the browser
    that loads the ad blocker, ``chrome``/``msedge`` are the installed ones.
    When the chosen browser is not on the disk, the next one of the spec order
    is taken, so a choice does not stop the program.

    With ``prefer_chromium`` the bundled Chromium wins over installed browsers:
    it is the only one that loads the ad blocker from the command line.
    ``legacy_dir`` is searched for a Chromium downloaded by an older version.

    Raises :class:`NoBrowserError` when nothing is available, so the caller can
    offer the Chromium download (spec 7.2).
    """
    chromium = chromium_executable(browsers_dir, legacy_dir)
    installed = installed_browsers(candidates, exists)
    if name != "auto":
        chosen = [choice for choice in installed if choice.kind == name]
        if chosen:
            return chosen[0]
    # The browser the user named is not on the disk: launch the order of the spec,
    # so a choice does not stop the program.
    if chromium is not None and (name == "chromium" or prefer_chromium):
        return _chromium_choice(chromium)
    if installed:
        return installed[0]
    if chromium is not None:
        return _chromium_choice(chromium)
    raise NoBrowserError(tr("browser_no_browser"))


def auto_user_agent(choice: BrowserChoice) -> str:
    """User agent for the browser: the Chrome form for the bundled Chromium.

    Playwright Chromium reports ``Chromium`` in the string, which is the second
    thing a bot detector reads; the version of ``chrome.exe`` gives the major
    number, so the user agent says Chrome of the same version (spec 7.2).
    Installed Chrome and Edge send their own user agent, nothing is set here.
    """
    if not choice.is_bundled_chromium or not choice.executable:
        return ""
    version = browser_version(choice.executable)
    if not version:
        return ""
    return chrome_user_agent(version)


def launch_kwargs(
    choice: BrowserChoice,
    profile_dir: Path,
    extension: Path | None = None,
    anti_bot: bool = True,
    user_agent: str = "",
    locale: str = DEFAULT_LOCALE,
) -> dict[str, Any]:
    """Arguments of ``launch_persistent_context`` for the chosen browser.

    The profile is a separate directory (spec 7.2), so the user's own browser
    profile is not touched and there is no "profile is in use" conflict.

    ``extension`` is the unpacked folder of the ad blocker. Recent Chrome and
    Edge ignore ``--load-extension``, so the flags are passed to the bundled
    Chromium only; the caller keeps the extension out of that browser.

    ``anti_bot`` is the stealth of spec 7.2: the flags Playwright adds for a
    driver are dropped, the automation marker is turned off, the sandbox flag is
    taken out, and the locale of the interface is used, so the browser looks
    like the Chrome of a person. ``user_agent`` is the string the user chose;
    when it is empty the Chrome form of the same version is taken.
    """
    args = launch_args(
        ["--no-first-run", "--no-default-browser-check", "--start-maximized"],
        extension if extension is not None and choice.is_bundled_chromium else None,
        anti_bot,
    )
    agent = user_agent or auto_user_agent(choice)
    kwargs: dict[str, Any] = {
        "user_data_dir": str(profile_dir),
        "headless": False,
        "no_viewport": True,
        "args": args,
        **stealth_kwargs(anti_bot, locale),
    }
    # A user agent is a string a site reads, so it is sent even when the stealth
    # is off: the choice of the user is the point, not the flags of the launch.
    if agent:
        kwargs["user_agent"] = agent
    if choice.channel:
        kwargs["channel"] = choice.channel
    elif choice.executable:
        kwargs["executable_path"] = choice.executable
    return kwargs
