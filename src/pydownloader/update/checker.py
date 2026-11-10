"""Update check through GitHub Releases (spec 8.3).

The core is Qt-free: the network code returns the release data, the window
decides what to show. The check is cached, so the application asks the API no
more often than ``update_check_hours`` (spec 8.3 p.5), and a network error is
only a console warning.
"""

from __future__ import annotations

import hashlib
import subprocess
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from packaging.version import InvalidVersion, Version

from pydownloader.config.constants import releases_latest_url
from pydownloader.config.settings import Settings

#: Name pattern of the installer asset, and the checksum file next to it.
SETUP_PREFIX = "PyDownloader-Setup-"
SHA_SUFFIX = ".sha256"
INSTALLER_ARGS = ["/SILENT", "/CLOSEAPPLICATIONS"]
#: Windows flag: the installer runs detached, no console window is shown.
DETACHED_PROCESS = 0x00000008
API_TIMEOUT = 15.0
USER_AGENT = "PyDownloader"


class UpdateError(RuntimeError):
    """The release information cannot be read."""


@dataclass(frozen=True)
class Asset:
    name: str
    url: str
    size: int


@dataclass(frozen=True)
class Release:
    """One published release: version, notes and the installer files."""

    version: str
    tag: str
    body: str
    installer: Asset
    sha256_asset: Asset | None

    @property
    def has_installer(self) -> bool:
        return self.installer.name.endswith(".exe")


def parse_release(payload: Mapping[str, Any]) -> Release | None:
    """Read the API answer of ``releases/latest``.

    Returns ``None`` for a prerelease, a draft, a release without a tag, or a
    release with no installer asset, so the caller reports nothing.
    """
    if payload.get("prerelease") is True or payload.get("draft") is True:
        return None
    tag = str(payload.get("tag_name") or "")
    if not tag:
        return None
    assets = [item for item in payload.get("assets", []) if isinstance(item, Mapping)]
    installer = next((item for item in assets if str(item.get("name", "")).endswith(".exe")), None)
    if installer is None:
        return None
    sha = next(
        (item for item in assets if str(item.get("name", "")).endswith(SHA_SUFFIX)),
        None,
    )
    return Release(
        version=strip_v(tag),
        tag=tag,
        body=str(payload.get("body") or ""),
        installer=Asset(
            str(installer["name"]),
            str(installer["browser_download_url"]),
            int(installer.get("size", 0)),
        ),
        sha256_asset=Asset(str(sha["name"]), str(sha["browser_download_url"]), 0) if sha else None,
    )


def strip_v(tag: str) -> str:
    """``v1.2.3`` → ``1.2.3``."""
    return tag[1:] if tag.startswith("v") else tag


def parse_version(text: str) -> Version | None:
    """SemVer of the release, ``None`` when the string is not a version."""
    try:
        return Version(strip_v(text))
    except InvalidVersion:
        return None


def is_newer(current: str, latest: str) -> bool:
    """``True`` when the release version is above the running one."""
    mine = parse_version(current)
    theirs = parse_version(latest)
    if mine is None or theirs is None:
        return False
    return theirs > mine


def should_check(settings: Settings, now: float, last_check: float | None) -> bool:
    """Whether the API is asked again: auto check on, the cache is old (spec 8.3 p.5)."""
    if not settings.auto_update:
        return False
    if last_check is None:
        return True
    return now - last_check >= settings.update_check_hours * 3600


def parse_last_check(settings: Settings) -> float | None:
    """Timestamp of the previous check stored in the settings, ``None`` if never."""
    text = getattr(settings, "last_update_check", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def fetch_release(url: str | None = None, timeout: float = API_TIMEOUT) -> Release | None:
    """``GET`` the latest release; ``None`` when there is nothing to show.

    Raises :class:`UpdateError` on a network failure, so the caller writes a
    console warning and keeps running (spec 8.3 p.6).
    """
    target = url or releases_latest_url()
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            response = client.get(
                target, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
            )
    except httpx.HTTPError as exc:
        raise UpdateError(f"Не получен список релизов: {exc}") from exc
    if response.status_code == 403:
        raise UpdateError("GitHub API: ограничено число запросов (лимит на IP)")
    if response.status_code >= 400:
        raise UpdateError(f"GitHub API: HTTP {response.status_code}")
    return parse_release(response.json())


def sha256_of(path: Path) -> str:
    """SHA-256 of a file, read in one MB chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def parse_sha(text: str) -> str:
    """Hex digest from a ``.sha256`` file (``<hex> filename`` or plain hex)."""
    first = text.strip().split()[0] if text.strip() else ""
    return first.lower()


def fetch_expected_sha(url: str, timeout: float = API_TIMEOUT) -> str:
    """The expected digest from the release asset."""
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            response = client.get(url, headers={"User-Agent": USER_AGENT})
    except httpx.HTTPError as exc:
        raise UpdateError(f"Не получен файл SHA-256: {exc}") from exc
    if response.status_code >= 400:
        raise UpdateError(f"SHA-256: HTTP {response.status_code}")
    return parse_sha(response.text)


def verify(path: Path, expected: str) -> bool:
    """True when the downloaded installer matches the published digest."""
    return sha256_of(path) == expected.lower()


def download_installer(url: str, target: Path, on_chunk=None) -> Path:
    """Save the installer to ``target`` with a progress callback (spec 8.3 p.3.1)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, follow_redirects=True, timeout=API_TIMEOUT) as response:
        if response.status_code >= 400:
            raise UpdateError(f"Скачивание установщика: HTTP {response.status_code}")
        with target.open("wb") as handle:
            for chunk in response.iter_bytes(1024 * 1024):
                handle.write(chunk)
                if on_chunk is not None:
                    on_chunk(len(chunk))
    return target


def installer_command(path: Path) -> list[str]:
    """The installer is run silently with the applications closed (spec 8.3 p.3.4)."""
    return [str(path), *INSTALLER_ARGS]


def run_installer(path: Path) -> subprocess.Popen:
    """Start the installer as a detached process; the caller exits the program."""
    return subprocess.Popen(installer_command(path), creationflags=DETACHED_PROCESS)


def stamp(now: float | None = None) -> str:
    """Timestamp string for the settings cache."""
    return str(now if now is not None else time.time())
