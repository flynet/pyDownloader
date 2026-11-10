"""Browser discovery and launch arguments (spec 7.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

import pydownloader.browser.launcher as launcher_mod
from pydownloader.browser.launcher import (
    CHROMIUM_WARNING,
    BrowserChoice,
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


def test_chromium_of_an_older_install_is_found_in_the_legacy_folder(tmp_path: Path):
    legacy = tmp_path / "local"
    old = legacy / "chromium-1248" / "chrome-win64" / "chrome.exe"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"MZ")
    primary = tmp_path / "app-browsers"
    assert chromium_executable(primary, legacy) == old
    # Both present: the folder of the current install wins, nothing is redownloaded.
    new = primary / "chromium-1254" / "chrome-win64" / "chrome.exe"
    new.parent.mkdir(parents=True)
    new.write_bytes(b"MZ")
    assert chromium_executable(primary, legacy) == new


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


def test_bundled_chromium_is_found_in_the_new_layout(tmp_path: Path):
    executable = tmp_path / "chromium-1248" / "chrome-win64" / "chrome.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"MZ")
    choice = resolve_browser(
        tmp_path, [("chrome", str(tmp_path / "none.exe"))], exists=lambda path: False
    )
    assert choice.kind == "chromium"
    assert choice.executable == str(executable)


def test_prefer_chromium_wins_over_installed_chrome(tmp_path: Path):
    executable = tmp_path / "chromium-1248" / "chrome-win64" / "chrome.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"MZ")
    choice = resolve_browser(
        tmp_path, [("chrome", CHROME)], exists=lambda path: path == CHROME, prefer_chromium=True
    )
    assert choice.kind == "chromium"
    assert choice.is_bundled_chromium


def test_prefer_chromium_falls_back_to_chrome(tmp_path: Path):
    choice = resolve_browser(
        tmp_path, [("chrome", CHROME)], exists=lambda path: path == CHROME, prefer_chromium=True
    )
    assert choice.channel == "chrome"


def test_extension_flags_are_passed_to_bundled_chromium(tmp_path: Path):
    executable = tmp_path / "chromium-1248" / "chrome-win64" / "chrome.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"MZ")
    choice = resolve_browser(
        tmp_path, [("chrome", str(tmp_path / "none.exe"))], exists=lambda path: False
    )
    extension = tmp_path / "uBlock"
    kwargs = launch_kwargs(choice, tmp_path / "profile", extension)
    assert f"--load-extension={extension}" in kwargs["args"]
    assert f"--disable-extensions-except={extension}" in kwargs["args"]


def test_extension_flags_are_not_passed_to_chrome(tmp_path: Path):
    choice = resolve_browser(tmp_path, [("chrome", CHROME)], exists=lambda path: path == CHROME)
    kwargs = launch_kwargs(choice, tmp_path / "profile", tmp_path / "uBlock")
    assert not any("load-extension" in arg for arg in kwargs["args"])


def make_chrome(tmp_path: Path) -> BrowserChoice:
    return resolve_browser(tmp_path, [("chrome", CHROME)], exists=lambda path: path == CHROME)


def make_chromium(tmp_path: Path) -> BrowserChoice:
    executable = tmp_path / "chromium-1248" / "chrome-win64" / "chrome.exe"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_bytes(b"MZ")
    return resolve_browser(
        tmp_path, [("chrome", str(tmp_path / "none.exe"))], exists=lambda path: False
    )


def test_the_stealth_flags_of_a_driver_are_in_the_launch(tmp_path: Path):
    kwargs = launch_kwargs(make_chrome(tmp_path), tmp_path / "profile")
    assert "--disable-blink-features=AutomationControlled" in kwargs["args"]
    assert kwargs["chromium_sandbox"] is True
    # --disable-extensions is the flag Chrome uses to ignore the ad blocker.
    assert "--disable-extensions" in kwargs["ignore_default_args"]
    assert kwargs["locale"] == "en-US"


def test_stealth_off_keeps_the_defaults_of_playwright(tmp_path: Path):
    kwargs = launch_kwargs(make_chrome(tmp_path), tmp_path / "profile", None, anti_bot=False)
    assert not any("AutomationControlled" in arg for arg in kwargs["args"])
    assert "ignore_default_args" not in kwargs


def test_bundled_chromium_sends_the_chrome_user_agent(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        launcher_mod, "browser_version", lambda executable: "Chromium 156.0.3304.0"
    )
    kwargs = launch_kwargs(make_chromium(tmp_path), tmp_path / "profile")
    assert "Chrome/156.0.0.0" in kwargs["user_agent"]
    assert "Chromium" not in kwargs["user_agent"]


def test_installed_chrome_keeps_the_user_agent_of_its_own_version(tmp_path: Path):
    # Chrome sends the string of its install; nothing is overridden (spec 7.2).
    assert "user_agent" not in launch_kwargs(make_chrome(tmp_path), tmp_path / "profile")


def test_the_user_agent_of_the_settings_is_sent(tmp_path: Path):
    kwargs = launch_kwargs(
        make_chrome(tmp_path), tmp_path / "profile", None, True, "My player 1.0"
    )
    assert kwargs["user_agent"] == "My player 1.0"


def test_a_browser_of_the_choice_is_used(tmp_path: Path):
    choice = resolve_browser(
        tmp_path,
        [("chrome", CHROME), ("msedge", EDGE)],
        exists=lambda path: path in (CHROME, EDGE),
        name="msedge",
    )
    assert choice.kind == "msedge"


def test_chromium_of_the_choice_wins_over_installed_chrome(tmp_path: Path):
    chromium = tmp_path / "chromium-1248" / "chrome-win64" / "chrome.exe"
    chromium.parent.mkdir(parents=True)
    chromium.write_bytes(b"MZ")
    choice = resolve_browser(
        tmp_path, [("chrome", CHROME)], exists=lambda path: path == CHROME, name="chromium"
    )
    assert choice.kind == "chromium"


def test_a_choice_that_is_not_installed_falls_back_to_the_spec_order(tmp_path: Path):
    # The user asked for Edge, it is not on the disk: Chrome is launched, so a
    # choice in the settings cannot stop the program.
    choice = resolve_browser(
        tmp_path, [("chrome", CHROME)], exists=lambda path: path == CHROME, name="msedge"
    )
    assert choice.kind == "chrome"


def test_no_browser_at_all_raises(tmp_path: Path):
    with pytest.raises(NoBrowserError):
        resolve_browser(
            tmp_path, [("chrome", CHROME)], exists=lambda path: False, name="msedge"
        )
