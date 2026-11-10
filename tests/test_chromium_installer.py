"""Chromium download on demand (spec 7.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pydownloader.browser import chromium_installer
from pydownloader.browser.chromium_installer import (
    InstallResult,
    chromium_installed,
    driver_command,
    install_chromium,
    install_env,
)

LINES = [
    "Downloading to D:\\browsers\\chromium-1140",
    "Chromium 120.0.6093.0 added to the registry",
    "",
]


class FakeProcess:
    """Stand-in for ``subprocess.Popen``; the output lines are replayed."""

    def __init__(self, command, returncode=0, **kwargs):
        self.command = command
        self.kwargs = kwargs
        self.returncode = returncode
        self.stdout = iter(LINES)

    def wait(self) -> int:
        return self.returncode


@pytest.fixture
def fake_popen(monkeypatch):
    def factory(returncode: int = 0):
        captured = {}

        def make(command, **kwargs):
            captured["command"] = command
            captured["kwargs"] = kwargs
            return FakeProcess(command, returncode=returncode, **kwargs)

        monkeypatch.setattr(chromium_installer.subprocess, "Popen", make)
        return captured

    return factory


def test_env_uses_app_browsers_dir(tmp_path: Path):
    env = install_env(tmp_path / "browsers")
    assert env["PLAYWRIGHT_BROWSERS_PATH"] == str(tmp_path / "browsers")


def test_chromium_installed_check(tmp_path: Path):
    browsers = tmp_path / "browsers"
    browsers.mkdir()
    assert not chromium_installed(browsers)
    executable = browsers / "chromium-1140" / "chrome-win" / "chrome.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"MZ")
    assert chromium_installed(browsers)


def test_install_runs_playwright_driver(tmp_path, fake_popen):
    captured = fake_popen(returncode=0)
    collected: list[str] = []
    result = install_chromium(tmp_path / "browsers", collected.append)
    command = captured["command"]
    assert command[-2:] == ["install", "chromium"]
    assert captured["kwargs"]["env"]["PLAYWRIGHT_BROWSERS_PATH"] == str(tmp_path / "browsers")
    assert captured["kwargs"]["creationflags"] == 0
    assert collected == [LINES[0], LINES[1]]
    assert result.ok
    assert result.message == "Chromium установлен"


def test_install_failure_reports_tail(tmp_path, fake_popen):
    captured = fake_popen(returncode=1)
    collected: list[str] = []
    result = install_chromium(tmp_path / "browsers", collected.append)
    assert not result.ok
    assert "код 1" in result.message
    assert "registry" in result.message
    assert captured["command"][-1] == "chromium"


def test_driver_command_is_node_and_cli(monkeypatch):
    monkeypatch.setattr(
        chromium_installer,
        "compute_driver_executable",
        lambda: ("C:\\app\\node.exe", "C:\\app\\package\\cli.js"),
    )
    assert driver_command() == ["C:\\app\\node.exe", "C:\\app\\package\\cli.js"]


def test_install_result_is_frozen():
    assert InstallResult(ok=True, message="ok").ok
