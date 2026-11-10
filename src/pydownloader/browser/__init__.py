"""Managed browser: launch, network sniffing, Chromium download on demand."""

from pydownloader.browser.chromium_installer import InstallResult, install_chromium
from pydownloader.browser.events import CookieRequest, ResponseEvent
from pydownloader.browser.launcher import (
    CHROMIUM_WARNING,
    BrowserChoice,
    NoBrowserError,
    launch_kwargs,
    resolve_browser,
)

__all__ = [
    "CHROMIUM_WARNING",
    "BrowserChoice",
    "CookieRequest",
    "InstallResult",
    "NoBrowserError",
    "ResponseEvent",
    "install_chromium",
    "launch_kwargs",
    "resolve_browser",
]
