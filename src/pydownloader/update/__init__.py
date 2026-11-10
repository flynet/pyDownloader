"""Self-update through GitHub Releases (spec 8)."""

from pydownloader.update.checker import (
    Asset,
    Release,
    UpdateError,
    download_installer,
    fetch_expected_sha,
    fetch_release,
    is_newer,
    parse_release,
    run_installer,
    should_check,
    verify,
)
from pydownloader.update.ui import UpdateMonitor

__all__ = [
    "Asset",
    "Release",
    "UpdateError",
    "UpdateMonitor",
    "download_installer",
    "fetch_expected_sha",
    "fetch_release",
    "is_newer",
    "parse_release",
    "run_installer",
    "should_check",
    "verify",
]
