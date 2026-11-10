"""Downloading Playwright Chromium on demand (spec 7.2).

Chromium is not shipped in the installer. When neither Chrome nor Edge is
installed, the app asks the user and runs the Playwright driver with
``PLAYWRIGHT_BROWSERS_PATH=<папка программы>/browsers`` (LocalAppData when the
program folder is not writable), so the download is removed together with the
installation. A Chromium of an older version is found in LocalAppData and
reused. The same driver is used in the frozen app, because
``collect_all("playwright")`` puts ``node.exe`` and ``package/cli.js`` into the
build.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from playwright._impl._driver import compute_driver_executable

from pydownloader.browser.launcher import chromium_executable

#: Windows flag so the console window of the installer process stays hidden.
CREATE_NO_WINDOW = 0x00000000
INSTALL_ARGS = ("install", "chromium")


@dataclass(frozen=True)
class InstallResult:
    ok: bool
    message: str


def driver_command() -> list[str]:
    """Command of the Playwright driver: ``node.exe`` + ``cli.js``, Python module as fallback."""
    try:
        node, cli = compute_driver_executable()
        return [str(node), str(cli)]
    except Exception:  # pragma: no cover - the package is always present in a build
        return [sys.executable, "-m", "playwright"]


def install_env(browsers_dir: Path) -> dict[str, str]:
    """Environment with the browsers path of the application."""
    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_dir)
    return env


def chromium_installed(browsers_dir: Path, legacy_dir: Path | None = None) -> bool:
    """Whether Chromium was downloaded to ``browsers_dir`` (or by an older version)."""
    return chromium_executable(browsers_dir, legacy_dir) is not None


def install_chromium(browsers_dir: Path, on_line: Callable[[str], None]) -> InstallResult:
    """Run ``playwright install chromium``, writing every progress line to the console.

    The caller runs this in a worker thread; ``on_line`` is the console callback.
    """
    command = driver_command() + list(INSTALL_ARGS)
    process = subprocess.Popen(
        command,
        env=install_env(browsers_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_NO_WINDOW,
    )
    lines: list[str] = []
    assert process.stdout is not None
    for raw in process.stdout:
        line = raw.strip()
        if line:
            lines.append(line)
            on_line(line)
    code = process.wait()
    if code == 0:
        return InstallResult(ok=True, message="Chromium установлен")
    tail = "; ".join(lines[-3:]) if lines else "нет вывода"
    return InstallResult(ok=False, message=f"Chromium не установлен (код {code}): {tail}")
