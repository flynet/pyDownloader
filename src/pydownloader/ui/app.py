"""Application start: pick the folder, open the window and the browser (spec 3.1).

``main`` is the entry point of ``PyDownloader.exe`` and of ``python -m
pydownloader``. The order follows the spec: the folder dialog first (cancel
ends the program), then the window, then the browser in its own thread.
Chromium is downloaded on the first request (spec 7.2), its progress goes to
the console.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication, QMessageBox

from pydownloader._version import VERSION
from pydownloader.browser.chromium_installer import InstallResult, install_chromium
from pydownloader.browser.launcher import (
    BrowserChoice,
    NoBrowserError,
    resolve_browser,
)
from pydownloader.browser.sniffer import SnifferThread
from pydownloader.config.constants import APP_NAME
from pydownloader.config.paths import Paths, default_paths, download_dir_default
from pydownloader.config.settings import Settings, load_settings, save_settings
from pydownloader.download.worker import QueueWorker
from pydownloader.ffmpeg.locate import Ffmpeg, FfmpegNotFoundError, locate_ffmpeg
from pydownloader.ffmpeg.probe import probe_height
from pydownloader.manifest.quality import QualityFilter
from pydownloader.manifest.registry import SourceRegistry
from pydownloader.ui.main_window import MainWindow, pick_download_dir
from pydownloader.ui.theme import apply_theme
from pydownloader.update.ui import UpdateMonitor
from pydownloader.util.logging_setup import setup_logging

INSTALL_QUESTION = (
    "Chrome и Edge не найдены. Скачать Chromium от Playwright (около 170 МБ, один раз)?"
)


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
        return Path(sys.executable).parent
    return None


def make_worker(settings: Settings, ffmpeg: Ffmpeg, sniffer: SnifferThread | None) -> QueueWorker:
    return QueueWorker(sniffer, ffmpeg, settings.download_dir, parallel=settings.threads)


def make_sniffer(
    settings: Settings,
    paths: Paths,
    browser: BrowserChoice,
    ffmpeg: Ffmpeg,
) -> SnifferThread:
    registry = SourceRegistry(min_mp4_size=settings.min_mp4_size)
    quality = QualityFilter(target_height=settings.target_height)
    return SnifferThread(
        browser=browser,
        profile_dir=paths.profile_dir,
        registry=registry,
        quality=quality,
        probe_height=lambda url, headers: probe_height(url, ffmpeg, headers),
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
    setup_logging(paths.log_file, window.console.append_line)
    window.logger.info(f"PyDownloader {VERSION}, папка загрузок: {settings.download_dir}")
    window.logger.info(f"FFmpeg: {ffmpeg.path}")
    return window


def start_browser(window: MainWindow, settings: Settings, paths: Paths) -> None:
    """Launch the browser thread, downloading Chromium when it is the only option."""
    try:
        browser = resolve_browser(paths.browsers_dir)
    except NoBrowserError as exc:
        window.log_warning(str(exc))
        answer = QMessageBox.question(
            window,
            APP_NAME,
            INSTALL_QUESTION,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        installer = ChromiumInstallWorker(paths.browsers_dir, window)
        installer.line.connect(window.log_info)
        installer.finished_install.connect(
            lambda ok, message: _after_install(window, settings, paths, ok, message)
        )
        window.install_worker = installer
        installer.start()
        return
    launch_sniffer(window, settings, paths, browser)


def launch_sniffer(
    window: MainWindow, settings: Settings, paths: Paths, browser: BrowserChoice
) -> None:
    """Start the sniffer thread with the resolved browser (spec 7.2)."""
    if window.ffmpeg is None:
        return
    sniffer = make_sniffer(settings, paths, browser, window.ffmpeg)
    window.sniffer = sniffer
    window.attach_sniffer()
    sniffer.start()


def _after_install(
    window: MainWindow, settings: Settings, paths: Paths, ok: bool, message: str
) -> None:
    if not ok:
        window.log_error(message)
        return
    window.log_info(message)
    try:
        browser = resolve_browser(paths.browsers_dir)
    except NoBrowserError as exc:
        window.log_error(str(exc))
        return
    launch_sniffer(window, settings, paths, browser)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    app = QApplication(args)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    paths = default_paths()
    settings = load_settings(paths.settings_file)
    start = Path(settings.download_dir) if settings.download_dir else download_dir_default()
    chosen = pick_download_dir(start)
    if chosen is None:
        return 0
    settings.download_dir = str(chosen)
    paths = default_paths(settings.profile_in_downloads, chosen)
    save_settings(settings, paths.settings_file)
    window = create_window(app, settings, paths)
    apply_theme(app, settings.theme)
    start_browser(window, settings, paths)
    window.show()
    if window.updater is not None:
        window.updater.check_on_startup()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover - the entry point of the built program
    raise SystemExit(main())
