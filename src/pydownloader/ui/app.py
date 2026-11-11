"""Application start: pick the folder, open the window and the browser (spec 3.1).

``main`` is the entry point of ``PyDownloader.exe`` and of ``python -m
pydownloader``. The folder dialog is shown on the first start (cancel ends the
program); later starts use the folder saved in the settings. Then the window is
opened and the browser starts in its own thread. Chromium is downloaded on the
first request (spec 7.2), its progress goes to the console.

The language comes from the settings and is applied right after they are read,
so every console line and every window text uses the chosen language (spec 8.1).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QProcess, QThread, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from pydownloader._version import VERSION
from pydownloader.browser.chromium_installer import InstallResult, install_chromium
from pydownloader.browser.extensions import extension_dir
from pydownloader.browser.launcher import (
    BrowserChoice,
    NoBrowserError,
    chromium_executable,
    resolve_browser,
)
from pydownloader.browser.sniffer import SnifferThread
from pydownloader.browser.stealth import locale_of
from pydownloader.config.constants import APP_NAME
from pydownloader.config.paths import (
    Paths,
    application_dir,
    default_paths,
    download_dir_default,
    icon_path,
)
from pydownloader.config.settings import Settings, load_settings, save_settings
from pydownloader.download.worker import QueueWorker
from pydownloader.ffmpeg.locate import Ffmpeg, FfmpegNotFoundError, locate_ffmpeg
from pydownloader.ffmpeg.probe import probe_media
from pydownloader.i18n import set_language, tr
from pydownloader.manifest.quality import QualityFilter
from pydownloader.manifest.registry import SourceRegistry
from pydownloader.ui.main_window import LogBridge, MainWindow, pick_download_dir
from pydownloader.ui.theme import apply_theme
from pydownloader.ui.tray import make_tray
from pydownloader.update.ui import UpdateMonitor
from pydownloader.util.logging_setup import setup_logging


class ChromiumInstallWorker(QThread):
    """``playwright install chromium`` with the progress lines in the console."""

    line = Signal(str)
    finished_install = Signal(bool, str)

    def __init__(self, browsers_dir, parent=None) -> None:
        super().__init__(parent)
        self.browsers_dir = browsers_dir

    def run(self) -> None:
        result: InstallResult = install_chromium(self.browsers_dir, self.line.emit)
        self.finished_install.emit(result.ok, result.message)


def app_root() -> Path | None:
    """Folder of the installed program (``{app}\\bin`` is inside it), ``None`` in a checkout."""
    if getattr(sys, "frozen", False):
        return application_dir()
    return None


def restart_command() -> tuple[str, list[str]]:
    """Command that starts the program again: the exe of the build, the module in a checkout."""
    if getattr(sys, "frozen", False):
        return sys.executable, []
    return sys.executable, ["-m", "pydownloader"]


def restart_application(app: QApplication) -> None:
    """Start a detached copy of the program and quit this one (spec 8.1).

    The new process keeps the current working directory, so it finds the same
    data folder of the installed program as the running one does.
    """
    exe, args = restart_command()
    QProcess.startDetached(exe, args)
    app.quit()


def make_worker(settings: Settings, ffmpeg: Ffmpeg, sniffer: SnifferThread | None) -> QueueWorker:
    return QueueWorker(
        sniffer,
        ffmpeg,
        settings.download_dir,
        parallel=settings.threads,
        target_height=settings.target_height,
        # An audio source is written as MP3 of the chosen bitrate (spec 5.2 p.4).
        mp3_bitrate=settings.mp3_bitrate,
    )


def make_sniffer(
    settings: Settings,
    paths: Paths,
    browser: BrowserChoice,
    ffmpeg: Ffmpeg,
    extension: Path | None = None,
    start_url: str = "",
) -> SnifferThread:
    registry = SourceRegistry(min_mp4_size=settings.min_mp4_size)
    quality = QualityFilter(
        target_height=settings.target_height,
        # «Audio only (MP3)» hides the video sources (spec 5.2 p.4).
        audio_only=settings.audio_only,
    )
    return SnifferThread(
        browser=browser,
        profile_dir=paths.profile_dir,
        registry=registry,
        quality=quality,
        start_url=start_url,
        probe_media=lambda url, headers: probe_media(url, ffmpeg, headers),
        extension_dir=extension,
        # The stealth of the launch is a setting, so a site that is unhappy with
        # it can be run without it (spec 7.2).
        anti_bot=settings.anti_bot,
        user_agent=settings.user_agent,
        locale=locale_of(settings.language),
    )


def create_window(app: QApplication, settings: Settings, paths: Paths) -> MainWindow:
    """Window with the worker, FFmpeg and the console handler wired."""
    try:
        ffmpeg = locate_ffmpeg(app_root())
    except FfmpegNotFoundError as exc:
        QMessageBox.warning(None, APP_NAME, str(exc))
        raise
    worker = make_worker(settings, ffmpeg, None)
    window = MainWindow(settings, paths, None, worker)
    window.ffmpeg = ffmpeg
    worker.start()  # the queue runs in its own thread (spec 4.4)
    window.updater = UpdateMonitor(window, settings)
    bridge = LogBridge(window)
    bridge.line.connect(window.console.append_line)
    window.log_bridge = bridge
    setup_logging(paths.log_file, bridge.line.emit)
    # The top panel button and the tray menu ask for the browser, the browser
    # thread itself is owned here (spec 4.3): the one button opens the window and
    # closes it, so the action is chosen by the state of the thread.
    window.browser_toggle_request.connect(lambda: toggle_browser(window, settings, paths))
    # «Go» of the address field: with the browser down, the thread starts on the page
    # of the link; the browser button of the window shows «Close browser» when the
    # thread is up (spec 4.2 p.4).
    window.browser_open_request.connect(
        lambda url: open_url_in_browser(window, settings, paths, url)
    )
    window.logger.info(tr("app_started", version=VERSION, dir=settings.download_dir))
    window.logger.info(tr("app_log_file", path=paths.log_file))
    window.logger.info(tr("app_data_dir", path=paths.data_dir))
    window.logger.info(tr("app_profile_dir", path=paths.profile_dir))
    window.logger.info(f"FFmpeg: {ffmpeg.path}")
    # The browser is opened by the button, so say where to look for it (spec 4.3).
    window.logger.info(tr("app_browser_hint"))
    return window


def start_browser(
    window: MainWindow, settings: Settings, paths: Paths, url: str = ""
) -> None:
    """Launch the browser thread, downloading Chromium when it is needed.

    The bundled ad blocker is loaded only by the Chromium downloaded by
    Playwright: Chrome and Edge ignore ``--load-extension``. When the extension
    is shipped but Chromium is missing, the user is offered the download first;
    declining falls back to Chrome/Edge without the blocker.

    The resolved browser and the blocker are kept on the window, so «Open
    browser» starts the same kind without asking again (spec 4.3).
    """
    extension = extension_dir(application_dir(), paths.data_dir / "extensions")
    if extension is not None and not settings.ad_blocker:
        # The blocker is switched off in the settings: nothing to load (spec 6.4).
        extension = None
        window.log_info(tr("app_blocker_disabled"))
    if extension is not None:
        window.log_info(tr("app_blocker_state", state=extension))
    want_chromium = settings.browser_name == "chromium"
    have_chromium = chromium_executable(paths.browsers_dir, paths.legacy_browsers_dir) is not None
    offered = False
    if (extension is not None or want_chromium) and not have_chromium:
        # The browser that can load the blocker is missing: ask for the download
        # first, so a decline falls back to Chrome/Edge without the blocker.
        offered = True
        if _ask_install(window, tr("app_chromium_offer_blocker")):
            _start_install(window, settings, paths)
            return
        extension = None
        window.log_warning(tr("app_blocker_not_loaded"))
    try:
        browser = resolve_browser(
            paths.browsers_dir,
            prefer_chromium=extension is not None,
            legacy_dir=paths.legacy_browsers_dir,
            name=settings.browser_name,
        )
    except NoBrowserError as exc:
        window.log_warning(str(exc))
        if not offered and _ask_install(window, tr("app_chromium_offer")):
            _start_install(window, settings, paths)
        return
    if extension is not None and not browser.is_bundled_chromium:
        window.log_warning(tr("app_blocker_not_loaded"))
        extension = None
    window.browser_choice = browser
    window.extension_dir = extension
    target = url if url else window.last_url
    if url:
        # The page of the field is the page the browser opens on, and «Open browser»
        # later opens the same site (spec 4.2 p.4).
        window.last_url = url
        window.log_info(tr("go_opened_browser", url=url))
    launch_sniffer(window, settings, paths, browser, extension, target)


def toggle_browser(window: MainWindow, settings: Settings, paths: Paths) -> None:
    """The one browser button: it opens the window, or closes it (spec 4.3).

    The button says what it will do, so the action is chosen by the state of the
    thread: «Open browser» restarts the browser of the last page, «Close browser»
    stops the thread and the downloads keep running. The launch is the part that
    can take a minute (the Chromium download, the offer dialog), so the button is
    disabled for its time.
    """
    if window.browser_running():
        close_browser(window)
        return
    window.set_browser_starting(True)
    try:
        open_browser(window, settings, paths)
    finally:
        window.set_browser_starting(False)


def open_url_in_browser(window: MainWindow, settings: Settings, paths: Paths, url: str) -> None:
    """«Go» with the browser down: the browser starts on the page of the field (spec 4.2 p.4).

    The launch is the slow part (the Chromium download, the offer dialog), so the
    browser button is disabled while it runs, as the same button does for the click of
    «Open browser», and the button changes to «Close browser» when the thread is up.
    """
    window.set_browser_starting(True)
    try:
        start_browser(window, settings, paths, url)
    finally:
        window.set_browser_starting(False)


def open_browser(window: MainWindow, settings: Settings, paths: Paths) -> None:
    """«Открыть браузер»: start the browser thread again on the last page.

    A thread that has finished is replaced by a new one: the Playwright objects
    of the closed browser belong to the event loop of the old thread, so they
    cannot be reused, and the profile of the user is read from the disk again.
    """
    sniffer = window.sniffer
    if sniffer is not None and sniffer.isRunning():
        window.log_info(tr("window_browser_open_already"))
        return
    if window.browser_choice is None:
        # Nothing was resolved yet (no browser found, Chromium being downloaded).
        start_browser(window, settings, paths)
        return
    launch_sniffer(
        window,
        settings,
        paths,
        window.browser_choice,
        window.extension_dir,
        window.last_url,
    )


def close_browser(window: MainWindow) -> None:
    """«Закрыть браузер»: stop the thread, the download keeps running (spec 4.3)."""
    sniffer = window.sniffer
    if sniffer is None or not sniffer.isRunning():
        window.log_info(tr("window_browser_not_running"))
        return
    sniffer.stop()
    window.log_info(tr("window_browser_stopping"))


def _ask_install(window: MainWindow, question: str) -> bool:
    answer = QMessageBox.question(
        window,
        APP_NAME,
        question,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes


def _start_install(window: MainWindow, settings: Settings, paths: Paths) -> None:
    installer = ChromiumInstallWorker(paths.browsers_dir, window)
    installer.line.connect(window.log_info)
    installer.finished_install.connect(
        lambda ok, message: _after_install(window, settings, paths, ok, message)
    )
    window.install_worker = installer
    installer.start()


def launch_sniffer(
    window: MainWindow,
    settings: Settings,
    paths: Paths,
    browser: BrowserChoice,
    extension: Path | None = None,
    start_url: str = "",
) -> None:
    """Start the sniffer thread with the resolved browser (spec 7.2)."""
    if window.ffmpeg is None:
        return
    sniffer = make_sniffer(settings, paths, browser, window.ffmpeg, extension, start_url)
    window.sniffer = sniffer
    window.attach_sniffer()
    sniffer.start()


def _after_install(
    window: MainWindow, settings: Settings, paths: Paths, ok: bool, message: str
) -> None:
    if not ok:
        window.log_error(message)
        # The download failed: use Chrome/Edge without the blocker when present.
        try:
            browser = resolve_browser(paths.browsers_dir, legacy_dir=paths.legacy_browsers_dir)
        except NoBrowserError:
            return
        launch_sniffer(window, settings, paths, browser)
        return
    window.log_info(message)
    start_browser(window, settings, paths)


def _is_temp(path: Path) -> bool:
    """Whether the folder is inside the system temp folder.

    The program never writes the videos there, so a settings file naming the temp
    folder is not the choice of the user. The test suite saves the settings of the
    windows it builds, and a window writes the file of ``%APPDATA%``, so the suite
    redirects the app data in ``conftest.py``; this guard is the safety net for a
    settings file that was left pointing at the temp folder of a test run.
    """
    temp = Path(tempfile.gettempdir())
    try:
        return path.is_relative_to(temp)
    except OSError:
        return False


def resolve_download_dir(settings: Settings) -> Path | None:
    """Folder for the videos: the saved one, or the dialog on the first start.

    The dialog appears only when the settings have no usable folder (the first
    run, a saved path on a removed drive, a path in the temp folder of a test
    run). Later starts take the saved path as is and create it when it was
    deleted. ``None`` means the user cancelled the first-start dialog.
    """
    saved = Path(settings.download_dir) if settings.download_dir else None
    if saved is not None and not _is_temp(saved):
        try:
            saved.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # the folder is gone (a removed drive, a file in the way): ask again
        else:
            return saved
    # No usable folder: the dialog starts where the user can pick the videos.
    start = download_dir_default()
    if saved is not None and not _is_temp(saved):
        if saved.is_dir():
            start = saved
        elif saved.parent.is_dir():
            start = saved.parent
    return pick_download_dir(start)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    app = QApplication(args)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    # The icon is shared by the title bar, the taskbar and the tray (spec 4.3).
    icon = icon_path()
    if icon is not None:
        app.setWindowIcon(QIcon(str(icon)))
    paths = default_paths()
    settings = load_settings(paths.settings_file)
    # The language is chosen once for the whole run, so it is set before any text.
    set_language(settings.language)
    chosen = resolve_download_dir(settings)
    if chosen is None:
        return 0
    settings.download_dir = str(chosen)
    paths = default_paths(settings.profile_in_downloads, chosen, application_dir())
    save_settings(settings, paths.settings_file)
    window = create_window(app, settings, paths)
    apply_theme(app, settings.theme)
    # The tray keeps the program alive when the window is hidden: Qt counts a
    # hidden window as closed, so quitting is done by the tray menu (spec 4.3).
    tray = make_tray(window, icon) if settings.tray_enabled else None
    if tray is not None:
        app.setQuitOnLastWindowClosed(False)
        # The first balloon points at the tray: the window is closed with «X» and
        # the program stays in the notification area, where «Exit» quits it (spec 4.3).
        window.hint_tray()
    # The browser is not launched here: the user opens it with the "Open browser"
    # button when he wants it (spec 4.3), and the sniffer runs only with it.
    window.show()
    if window.updater is not None:
        window.updater.check_on_startup()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover - the entry point of the built program
    raise SystemExit(main())
