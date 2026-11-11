"""Startup: the download folder is asked once and then taken from the settings."""

from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path

from pydownloader.browser.launcher import BrowserChoice
from pydownloader.config.paths import Paths, download_dir_default
from pydownloader.config.settings import Settings, load_settings, save_settings
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


def test_a_temp_folder_in_the_settings_is_asked_again(tmp_path, monkeypatch):
    """The temp folder of a test run is not the choice of the user (spec 3.1).

    A window writes the settings of the user, so the suite redirects the app data
    in ``conftest.py``; the guard is for a settings file that was left pointing at
    ``%TEMP%`` after such a run. The program does not create that folder and asks
    for a real one, starting the dialog at the downloads of the user.
    """
    temp = Path(tempfile.gettempdir()) / "tmpvideos"
    settings = Settings(download_dir=str(temp))
    asked: list[object] = []
    monkeypatch.setattr(app_mod, "pick_download_dir", lambda start: asked.append(start) or tmp_path)

    assert app_mod.resolve_download_dir(settings) == tmp_path
    # The temp folder is not created, and the dialog starts at the downloads.
    assert not temp.exists()
    assert asked == [download_dir_default()]


def test_the_startup_write_keeps_the_settings_of_the_user(tmp_path: Path):
    """A start writes the settings back: it changes the folder it resolved, nothing else.

    The theme, the language and the state of the console panel are the settings of
    the user, so the file a start leaves must be the file it read, not the defaults
    (spec 7.4).
    """
    paths = make_paths(tmp_path)
    saved = tmp_path / "videos"
    save_settings(
        Settings(download_dir=str(saved), theme="dark", console_open=False, language="ru"),
        paths.settings_file,
    )
    settings = load_settings(paths.settings_file)
    settings.download_dir = str(saved)
    save_settings(settings, paths.settings_file)

    back = load_settings(paths.settings_file)
    assert back.theme == "dark"
    assert back.console_open is False
    assert back.language == "ru"
    assert back.download_dir == str(saved)


def make_paths(tmp_path: Path) -> Paths:
    return Paths(
        settings_file=tmp_path / "settings.json",
        log_dir=tmp_path / "logs",
        log_file=tmp_path / "logs" / "app.log",
        data_dir=tmp_path / "data",
        browsers_dir=tmp_path / "browsers",
        profile_dir=tmp_path / "profile",
    )


class FakeWindow:
    """Stand-in of the window for the browser actions (spec 4.3).

    It keeps the console lines the app writes, the resolved browser, the last page
    and the state of the browser button, so the toggle can be checked without Qt.
    """

    def __init__(self) -> None:
        self.messages: list[str] = []
        self.ffmpeg = Ffmpeg(Path("ffmpeg.exe"), "FFmpeg")
        # «Open browser» reuses what the first start resolved (spec 4.3).
        self.browser_choice = None
        self.extension_dir = None
        self.last_url = ""
        self.sniffer = None
        #: The state the button is set to during a launch: True, then False.
        self.starting: list[bool] = []

    def log_info(self, message: str) -> None:
        self.messages.append(message)

    def log_warning(self, message: str) -> None:
        self.messages.append(message)

    def browser_running(self) -> bool:
        return self.sniffer is not None and self.sniffer.isRunning()

    def set_browser_starting(self, starting: bool) -> None:
        self.starting.append(starting)


def make_window() -> FakeWindow:
    return FakeWindow()


def record_launch(launched: list[object]):
    """Stand-in for ``launch_sniffer`` that remembers the extension argument."""

    def launch(window, settings, paths, browser, extension=None, start_url=""):
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
    monkeypatch.setattr(app_mod, "chromium_executable", lambda folder, legacy=None: None)
    monkeypatch.setattr(app_mod, "_ask_install", lambda window, question: True)
    monkeypatch.setattr(app_mod, "_start_install", lambda *args: started.append("install"))

    app_mod.start_browser(window, Settings(), make_paths(tmp_path))
    assert started == ["install"]


def test_declining_the_extension_falls_back_to_chrome(tmp_path: Path, monkeypatch):
    window = make_window()
    launched: list[object] = []
    monkeypatch.setattr(app_mod, "extension_dir", lambda app, cache: tmp_path / "uBlock")
    monkeypatch.setattr(app_mod, "chromium_executable", lambda folder, legacy=None: None)
    monkeypatch.setattr(app_mod, "_ask_install", lambda window, question: False)
    monkeypatch.setattr(
        app_mod,
        "resolve_browser",
        lambda browsers_dir, prefer_chromium=False, legacy_dir=None, name="auto": CHROME,
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
    monkeypatch.setattr(
        app_mod, "chromium_executable", lambda folder, legacy=None: Path("chrome.exe")
    )
    monkeypatch.setattr(
        app_mod,
        "resolve_browser",
        lambda browsers_dir, prefer_chromium=False, legacy_dir=None, name="auto": CHROMIUM,
    )
    monkeypatch.setattr(app_mod, "launch_sniffer", record_launch(launched))

    app_mod.start_browser(window, Settings(), make_paths(tmp_path))
    assert launched == [extension]


def test_chromium_of_an_older_version_is_used_without_a_new_download(
    tmp_path: Path, monkeypatch
):
    window = make_window()
    extension = tmp_path / "uBlock"
    legacy = tmp_path / "local-browsers"
    executable = legacy / "chromium-1248" / "chrome-win64" / "chrome.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"MZ")
    started: list[str] = []
    launched: list[object] = []
    monkeypatch.setattr(app_mod, "extension_dir", lambda app, cache: extension)
    monkeypatch.setattr(app_mod, "_ask_install", lambda window, question: started.append("install"))
    monkeypatch.setattr(
        app_mod,
        "launch_sniffer",
        lambda window, settings, paths, browser, ext=None, start_url="": launched.append(
            (browser, ext)
        ),
    )

    paths = replace(make_paths(tmp_path), legacy_browsers_dir=legacy)
    app_mod.start_browser(window, Settings(), paths)

    assert started == []
    assert launched[0][0].kind == "chromium"
    assert launched[0][1] == extension


class FakeSniffer:
    """Stand-in for the browser thread: the buttons ask it to start and stop."""

    def __init__(self, running: bool, open_now: bool) -> None:
        self._running = running
        self._open = open_now
        self.stops = 0

    def isRunning(self) -> bool:
        return self._running

    def is_browser_open(self) -> bool:
        return self._open

    def stop(self) -> None:
        self.stops += 1
        self._running = False


def test_close_browser_stops_the_thread(tmp_path: Path, monkeypatch):
    window = make_window()
    sniffer = FakeSniffer(running=True, open_now=True)
    window.sniffer = sniffer

    app_mod.close_browser(window)
    assert sniffer.stops == 1
    assert any("Закрываю" in message for message in window.messages)


def test_close_browser_without_a_thread_is_a_plain_message(tmp_path: Path, monkeypatch):
    window = make_window()
    window.sniffer = None

    app_mod.close_browser(window)
    assert any("не запущен" in message for message in window.messages)


def test_open_browser_reuses_the_resolved_browser_on_the_last_page(
    tmp_path: Path, monkeypatch
):
    window = make_window()
    window.browser_choice = CHROME
    window.extension_dir = tmp_path / "uBlock"
    window.last_url = "https://example.com/player"
    # A thread that finished cannot be reused: its Playwright objects are bound
    # to the event loop of the old thread, so a new one is launched.
    window.sniffer = FakeSniffer(running=False, open_now=False)
    launched: list[object] = []
    monkeypatch.setattr(
        app_mod,
        "launch_sniffer",
        lambda window, settings, paths, browser, ext=None, start_url="": launched.append(
            (browser, ext, start_url)
        ),
    )

    app_mod.open_browser(window, Settings(), make_paths(tmp_path))

    assert launched == [(CHROME, tmp_path / "uBlock", "https://example.com/player")]


def test_the_address_of_the_field_starts_the_browser_on_that_page(tmp_path: Path, monkeypatch):
    """«Go» with the browser down launches the thread on the page of the field.

    The address pasted in the window is the page the browser opens on, and it is
    remembered as the last page, so «Open browser» after a restart opens the same
    site (spec 4.2 p.4).
    """
    window = make_window()
    launched: list[tuple[object, str]] = []

    def launch(window, settings, paths, browser, ext=None, start_url=""):
        launched.append((ext, start_url))

    monkeypatch.setattr(app_mod, "extension_dir", lambda app, cache: None)
    monkeypatch.setattr(
        app_mod,
        "resolve_browser",
        lambda browsers_dir, prefer_chromium=False, legacy_dir=None, name="auto": CHROME,
    )
    monkeypatch.setattr(app_mod, "launch_sniffer", launch)

    app_mod.open_url_in_browser(
        window, Settings(), make_paths(tmp_path), "https://site.example/watch"
    )

    assert launched == [(None, "https://site.example/watch")]
    assert window.last_url == "https://site.example/watch"
    # The browser button is disabled for the launch, and the page is written in the log.
    assert window.starting == [True, False]
    assert any("site.example" in message for message in window.messages)


def test_open_browser_does_not_start_a_second_thread(tmp_path: Path, monkeypatch):
    window = make_window()
    window.browser_choice = CHROME
    window.sniffer = FakeSniffer(running=True, open_now=True)
    launched: list[object] = []
    monkeypatch.setattr(
        app_mod,
        "launch_sniffer",
        lambda window, settings, paths, browser, ext=None, start_url="": launched.append(browser),
    )

    app_mod.open_browser(window, Settings(), make_paths(tmp_path))

    assert launched == []
    assert any("уже открыт" in message for message in window.messages)


def test_open_browser_without_a_resolved_browser_starts_the_first_one(
    tmp_path: Path, monkeypatch
):
    window = make_window()
    started: list[str] = []
    monkeypatch.setattr(app_mod, "chromium_executable", lambda folder, legacy=None: None)
    monkeypatch.setattr(app_mod, "extension_dir", lambda app, cache: None)
    monkeypatch.setattr(app_mod, "_ask_install", lambda window, question: False)
    monkeypatch.setattr(app_mod, "resolve_browser", lambda *args, **kwargs: CHROME)
    monkeypatch.setattr(app_mod, "launch_sniffer", lambda *args, **kwargs: started.append("launch"))

    app_mod.open_browser(window, Settings(), make_paths(tmp_path))

    assert started == ["launch"]


def test_toggle_of_the_browser_button_closes_the_running_window(tmp_path: Path, monkeypatch):
    window = make_window()
    sniffer = FakeSniffer(running=True, open_now=True)
    window.sniffer = sniffer
    launched: list[object] = []
    monkeypatch.setattr(app_mod, "launch_sniffer", record_launch(launched))

    app_mod.toggle_browser(window, Settings(), make_paths(tmp_path))

    # «Close browser» stops the thread and does not touch the button of the launch,
    # so the state of the button stays as fast as the close (spec 4.3).
    assert sniffer.stops == 1
    assert launched == []
    assert window.starting == []


def test_toggle_opens_the_browser_and_the_button_waits_for_the_launch(tmp_path: Path, monkeypatch):
    window = make_window()
    monkeypatch.setattr(app_mod, "chromium_executable", lambda folder, legacy=None: None)
    monkeypatch.setattr(app_mod, "extension_dir", lambda app, cache: None)
    monkeypatch.setattr(app_mod, "resolve_browser", lambda *args, **kwargs: CHROME)
    launched: list[object] = []
    monkeypatch.setattr(app_mod, "launch_sniffer", record_launch(launched))

    app_mod.toggle_browser(window, Settings(), make_paths(tmp_path))

    # The button is disabled for the launch: the Chromium download and the offer
    # dialog are on the same click, so a second press cannot start a second thread
    # of Playwright (spec 4.3 p.2).
    assert launched == [None]
    assert window.starting == [True, False]


def test_startup_leaves_the_browser_closed(tmp_path: Path, qapp, qtbot, monkeypatch):
    """The program starts without a browser: the user opens it with the button (spec 4.3).

    The startup path is the window itself, so the test runs :func:`create_window`
    and looks at what the window owns: no thread, no resolved browser, and the
    console telling where to start the browser.
    """
    monkeypatch.setattr(app_mod, "locate_ffmpeg", lambda root: Ffmpeg(Path("ffmpeg.exe"), "FFmpeg"))
    settings = Settings(download_dir=str(tmp_path))
    window = app_mod.create_window(qapp, settings, make_paths(tmp_path))
    qtbot.addWidget(window)

    assert window.sniffer is None
    assert window.browser_choice is None
    # The console names the button, so an empty window is not a mystery.
    assert "Открыть браузер" in window.console.toPlainText()
