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
from pydownloader.ffmpeg.probe import probe_height
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
    quality = QualityFilter(target_height=settings.target_height)
    return SnifferThread(
        browser=browser,
        profile_dir=paths.profile_dir,
        registry=registry,
        quality=quality,
        start_url=start_url,
        probe_height=lambda url, headers: probe_height(url, ffmpeg, headers),
        extension_dir=extension,
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
    # The top panel buttons and the tray menu ask for the browser, the browser
    # thread itself is owned here (spec 4.3).
    window.browser_open_request.connect(lambda: open_browser(window, settings, paths))
    window.browser_close_request.connect(lambda: close_browser(window))
    window.logger.info(tr("app_started", version=VERSION, dir=settings.download_dir))
    window.logger.info(tr("app_log_file", path=paths.log_file))
    window.logger.info(tr("app_data_dir", path=paths.data_dir))
    window.logger.info(tr("app_profile_dir", path=paths.profile_dir))
    window.logger.info(f"FFmpeg: {ffmpeg.path}")
    return window


def start_browser(window: MainWindow, settings: Settings, paths: Paths) -> None:
    """Launch the browser thread, downloading Chromium when it is needed.

    The bundled ad blocker is loaded only by the Chromium downloaded by
    Playwright: Chrome and Edge ignore ``--load-extension``. When the extension
    is shipped but Chromium is missing, the user is offered the download first;
    declining falls back to Chrome/Edge without the blocker.

    The resolved browser and the blocker are kept on the window, so «Open
    browser» starts the same kind without asking again (spec 4.3).
    """
    extension = extension_dir(application_dir(), paths.data_dir / "extensions")
    if extension is not None:
        window.log_info(tr("app_blocker_state", state=extension))
    offered = False
    if (
        extension is not None
        and chromium_executable(paths.browsers_dir, paths.legacy_browsers_dir) is None
    ):
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
    launch_sniffer(window, settings, paths, browser, extension, window.last_url)


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


def resolve_download_dir(settings: Settings) -> Path | None:
    """Folder for the videos: the saved one, or the dialog on the first start.

    The dialog appears only when the settings have no usable folder (the first
    run, or a saved path on a removed drive). Later starts take the saved path
    as is and create it when it was deleted. ``None`` means the user cancelled
    the first-start dialog.
    """
    if settings.download_dir:
        saved = Path(settings.download_dir)
        try:
            saved.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # the folder is gone (a removed drive, a file in the way): ask again
        else:
            return saved
    start = Path(settings.download_dir) if settings.download_dir else download_dir_default()
    if not start.is_dir():
        start = start.parent if start.parent.is_dir() else download_dir_default()
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
    start_browser(window, settings, paths)
    window.show()
    if window.updater is not None:
        window.updater.check_on_startup()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover - the entry point of the built program
    raise SystemExit(main())
