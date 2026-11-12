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
from pydownloader.i18n import tr

#: Name pattern of the installer asset, and the checksum file next to it.
SETUP_PREFIX = "PyDownloader-Setup-"
SHA_SUFFIX = ".sha256"
INSTALLER_ARGS = ["/SILENT", "/SUPPRESSMSGBOXES", "/CLOSEAPPLICATIONS", "/NORESTART"]
#: Windows flag: the installer runs detached, no console window is shown.
DETACHED_PROCESS = 0x00000008
API_TIMEOUT = 15.0
#: The window of a read of the installer. A release of GitHub comes over a slow
#: link today: the 15 s of the API check stopped the 110 MB file in the middle,
#: and the code behind it reported nothing, so the program hung with the bar of
#: the progress moving and the update never arrived (spec 8.3 p.3.1).
INSTALLER_READ_TIMEOUT = 90.0
INSTALLER_TIMEOUT = httpx.Timeout(
    connect=API_TIMEOUT, read=INSTALLER_READ_TIMEOUT, write=30.0, pool=API_TIMEOUT
)
#: How many times a broken connection of the installer is tried again, each time
#: from the byte the file reached (the ``Range`` of HTTP), not from the start.
DOWNLOAD_ATTEMPTS = 3
USER_AGENT = "PyDownloader"


class UpdateError(RuntimeError):
    """The release information cannot be read; the message is a catalog key."""


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
    console warning and keeps running (spec 8.3 p.6). The text of the error is
    a key of the ``update`` group, so the warning follows the language.
    """
    target = url or releases_latest_url()
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            response = client.get(
                target, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
            )
    except httpx.HTTPError as exc:
        raise UpdateError(tr("up_release_list_failed", error=exc)) from exc
    if response.status_code == 404:
        # A repository without published releases answers 404: nothing to show.
        return None
    if response.status_code == 403:
        raise UpdateError(tr("up_rate_limited"))
    if response.status_code >= 400:
        raise UpdateError(tr("up_api_http", status=response.status_code))
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
        raise UpdateError(tr("up_sha_file_failed", error=exc)) from exc
    if response.status_code >= 400:
        raise UpdateError(tr("up_sha_http", status=response.status_code))
    return parse_sha(response.text)


def verify(path: Path, expected: str) -> bool:
    """True when the downloaded installer matches the published digest."""
    return sha256_of(path) == expected.lower()


def _final_size(headers: Mapping[str, str], done: int, length: int) -> int:
    """The whole size of the installer the server promises.

    A normal answer says the size in ``Content-Length``. A part of the file
    (``206``) says only what is left, and writes the whole size in
    ``Content-Range``, so the bar of the progress needs that number to show the
    bytes that are already on disk against the full file (spec 8.3 p.3.1).
    """
    span = headers.get("content-range", "")
    if "/" in span:
        tail = span.rsplit("/", 1)[1]
        if tail.isdigit():
            return int(tail)
    return done + length


def download_installer(url: str, target: Path, on_chunk=None) -> Path:
    """Save the installer to ``target``; the callback gets the bytes written (spec 8.3 p.3.1).

    ``on_chunk(written, total)`` is called after every megabyte lands, so the
    window shows the real progress of the file. A connection that breaks is
    tried again from the byte the file reached, and not from the start: a slow
    GitHub gives a 110 MB installer in pieces, and a restart from zero on such a
    link never finishes. Every network failure is turned into
    :class:`UpdateError`, so the console names the reason instead of leaving the
    program to hang with a moving bar and no word about the update.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    last: Exception | None = None
    for _attempt in range(DOWNLOAD_ATTEMPTS):
        done = target.stat().st_size if target.exists() else 0
        headers = {"User-Agent": USER_AGENT}
        if done:
            headers["Range"] = f"bytes={done}-"
        try:
            with httpx.stream(
                "GET", url, follow_redirects=True, timeout=INSTALLER_TIMEOUT, headers=headers
            ) as response:
                if response.status_code >= 400:
                    raise UpdateError(tr("up_installer_http", status=response.status_code))
                if response.status_code == 416:
                    # The server has no bytes after the ones the file already has:
                    # the installer is whole.
                    return target
                length = int(response.headers.get("content-length", 0) or 0)
                final = _final_size(response.headers, done, length)
                written = done
                with target.open("ab") as handle:
                    for chunk in response.iter_bytes(1024 * 1024):
                        handle.write(chunk)
                        written += len(chunk)
                        if on_chunk is not None:
                            on_chunk(written, final)
                if final and written >= final:
                    # The file is whole: the next request would ask for bytes the
                    # server does not have.
                    return target
        except UpdateError:
            # A reason the user must hear (HTTP 404, a cancel of the download):
            # trying the same address again answers the same way.
            raise
        except httpx.HTTPError as exc:
            last = exc
            continue
    if not target.exists() or target.stat().st_size == 0:
        raise UpdateError(tr("up_installer_failed", error=last or "empty answer"))
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
