"""Startup: the download folder is asked once and then taken from the settings."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pydownloader.browser.launcher import BrowserChoice
from pydownloader.config.paths import Paths
from pydownloader.config.settings import Settings
from pydownloader.ffmpeg.locate import Ffmpeg
from pydownloader.ui import app as app_mod


def test_saved_folder_is_used_without_a_dialog(tmp_path, monkeypatch):
    saved = tmp_path / "Мои видео"
    settings = Settings(download_dir=str(saved))
    asked: list[object] = []
    monkeypatch.setattr(app_mod, "pick_download_dir", lambda start: asked.append(start))

    assert app_mod.resolve_download_dir(settings) == saved
    # The folder is created when it was deleted: no dialog on a normal start.
    assert saved.is_dir()
    assert asked == []


def test_first_start_asks_for_the_folder(tmp_path, monkeypatch):
    settings = Settings()  # no folder saved yet
    monkeypatch.setattr(app_mod, "pick_download_dir", lambda start: tmp_path)

    assert app_mod.resolve_download_dir(settings) == tmp_path


def test_cancelled_first_start_stops_the_program(monkeypatch):
    monkeypatch.setattr(app_mod, "pick_download_dir", lambda start: None)
    assert app_mod.resolve_download_dir(Settings()) is None


def test_unusable_saved_folder_asks_again(tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("not a folder", encoding="utf-8")
    settings = Settings(download_dir=str(blocker / "sub"))
    chosen = tmp_path / "new"
    monkeypatch.setattr(app_mod, "pick_download_dir", lambda start: chosen)

    assert app_mod.resolve_download_dir(settings) == chosen


def make_paths(tmp_path: Path) -> Paths:
    return Paths(
        settings_file=tmp_path / "settings.json",
        log_dir=tmp_path / "logs",
        log_file=tmp_path / "logs" / "app.log",
        data_dir=tmp_path / "data",
        browsers_dir=tmp_path / "browsers",
        profile_dir=tmp_path / "profile",
    )


def make_window() -> SimpleNamespace:
    messages: list[str] = []
    return SimpleNamespace(
        messages=messages,
        log_info=messages.append,
        log_warning=messages.append,
        ffmpeg=Ffmpeg(Path("ffmpeg.exe"), "FFmpeg"),
    )


def record_launch(launched: list[object]):
    """Stand-in for ``launch_sniffer`` that remembers the extension argument."""

    def launch(window, settings, paths, browser, extension=None):
        launched.append(extension)

    return launch


CHROMIUM = BrowserChoice(kind="chromium", channel=None, executable="chrome.exe", label="Chromium")
CHROME = BrowserChoice(kind="chrome", channel="chrome", executable="chrome.exe", label="Chrome")


def test_make_sniffer_gets_the_extension(tmp_path: Path):
    extension = tmp_path / "uBlock"
    sniffer = app_mod.make_sniffer(
        Settings(download_dir=str(tmp_path)),
        make_paths(tmp_path),
        CHROMIUM,
        Ffmpeg(Path("ffmpeg.exe"), "FFmpeg"),
        extension,
    )
    assert sniffer.extension_dir == extension


def test_extension_without_chromium_offers_the_download(tmp_path: Path, monkeypatch):
    window = make_window()
    started: list[str] = []
    monkeypatch.setattr(app_mod, "extension_dir", lambda app, cache: tmp_path / "uBlock")
    monkeypatch.setattr(app_mod, "chromium_executable", lambda folder: None)
    monkeypatch.setattr(app_mod, "_ask_install", lambda window, question: True)
    monkeypatch.setattr(app_mod, "_start_install", lambda *args: started.append("install"))

    app_mod.start_browser(window, Settings(), make_paths(tmp_path))
    assert started == ["install"]


def test_declining_the_extension_falls_back_to_chrome(tmp_path: Path, monkeypatch):
    window = make_window()
    launched: list[object] = []
    monkeypatch.setattr(app_mod, "extension_dir", lambda app, cache: tmp_path / "uBlock")
    monkeypatch.setattr(app_mod, "chromium_executable", lambda folder: None)
    monkeypatch.setattr(app_mod, "_ask_install", lambda window, question: False)
    monkeypatch.setattr(
        app_mod, "resolve_browser", lambda browsers_dir, prefer_chromium=False: CHROME
    )
    monkeypatch.setattr(app_mod, "launch_sniffer", record_launch(launched))

    app_mod.start_browser(window, Settings(), make_paths(tmp_path))
    assert launched == [None]
    assert any("Блокировщик" in message for message in window.messages)


def test_extension_is_passed_to_the_bundled_chromium(tmp_path: Path, monkeypatch):
    window = make_window()
    extension = tmp_path / "uBlock"
    launched: list[object] = []
    monkeypatch.setattr(app_mod, "extension_dir", lambda app, cache: extension)
    monkeypatch.setattr(app_mod, "chromium_executable", lambda folder: Path("chrome.exe"))
    monkeypatch.setattr(
        app_mod, "resolve_browser", lambda browsers_dir, prefer_chromium=False: CHROMIUM
    )
    monkeypatch.setattr(app_mod, "launch_sniffer", record_launch(launched))

    app_mod.start_browser(window, Settings(), make_paths(tmp_path))
    assert launched == [extension]
