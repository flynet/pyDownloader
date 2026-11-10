"""Browser discovery and launch arguments (spec 7.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pydownloader.browser.launcher import (
    CHROMIUM_WARNING,
    NoBrowserError,
    chromium_executable,
    installed_browsers,
    launch_kwargs,
    resolve_browser,
)

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_X86 = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CANDIDATES = [("chrome", CHROME), ("chrome", CHROME_X86), ("msedge", EDGE)]


def make_files(tmp_path: Path, names: list[str]) -> list[tuple[str, str]]:
    """Fake executables on disk, as (kind, path) candidates."""
    created = []
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"MZ")
        created.append((name, str(path)))
    return created


def test_chrome_is_preferred_over_edge(tmp_path: Path):
    files = make_files(tmp_path, ["chrome.exe", "msedge.exe"])
    candidates = [("chrome", files[0][1]), ("msedge", files[1][1])]
    found = installed_browsers(candidates)
    assert [choice.kind for choice in found] == ["chrome", "msedge"]
    assert resolve_browser(tmp_path, candidates).kind == "chrome"
    assert resolve_browser(tmp_path, candidates).channel == "chrome"


def test_only_edge_is_used(tmp_path: Path):
    files = make_files(tmp_path, ["msedge.exe"])
    candidates = [("chrome", str(tmp_path / "missing.exe")), ("msedge", files[0][1])]
    assert [choice.kind for choice in installed_browsers(candidates)] == ["msedge"]
    choice = resolve_browser(tmp_path, candidates)
    assert choice.kind == "msedge"
    assert choice.label == "Edge"


def test_two_chrome_paths_give_one_choice(tmp_path: Path):
    files = make_files(tmp_path, ["chrome.exe"])
    candidates = [("chrome", files[0][1]), ("chrome", files[0][1])]
    assert len(installed_browsers(candidates)) == 1


def test_chromium_of_playwright_is_the_last_option(tmp_path: Path):
    executable = tmp_path / "chromium-1140" / "chrome-win" / "chrome.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"MZ")
    choice = resolve_browser(tmp_path, [(("chrome"), str(tmp_path / "none.exe"))])
    assert choice.kind == "chromium"
    assert choice.channel is None
    assert choice.executable == str(executable)
    assert choice.is_bundled_chromium
    assert chromium_executable(tmp_path) == executable


def test_no_browser_raises(tmp_path: Path):
    with pytest.raises(NoBrowserError):
        resolve_browser(tmp_path, [("chrome", str(tmp_path / "none.exe"))])


def test_chromium_warning_is_shown_for_bundled_chromium():
    assert "H.264" in CHROMIUM_WARNING


def test_launch_kwargs_for_channel_browser(tmp_path: Path):
    choice = resolve_browser(tmp_path, [("chrome", CHROME)], exists=lambda path: path == CHROME)
    kwargs = launch_kwargs(choice, tmp_path / "profile")
    assert kwargs["channel"] == "chrome"
    assert "executable_path" not in kwargs
    assert kwargs["headless"] is False
    assert kwargs["no_viewport"] is True
    assert kwargs["user_data_dir"] == str(tmp_path / "profile")
    assert "--no-first-run" in kwargs["args"]
    assert "--no-default-browser-check" in kwargs["args"]


def test_launch_kwargs_for_bundled_chromium(tmp_path: Path):
    executable = tmp_path / "chromium-1140" / "chrome.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"MZ")
    choice = resolve_browser(
        tmp_path, [("chrome", str(tmp_path / "none.exe"))], exists=lambda path: False
    )
    kwargs = launch_kwargs(choice, tmp_path / "profile")
    assert "channel" not in kwargs
    assert kwargs["executable_path"] == str(executable)
