"""The main window: found videos on top, console below (spec 4.2).

The window owns the cards, the queue worker and the sniffer thread. All
updates from the threads arrive through Qt signals, so no widget is touched
from another thread. The window size and position are stored in the settings
and restored on the next start (spec 4.2 p.1).
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import cast

from PySide6.QtCore import QByteArray, QObject, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from pydownloader._version import VERSION
from pydownloader.browser.launcher import BrowserChoice
from pydownloader.browser.sniffer import SnifferThread
from pydownloader.config.paths import Paths, icon_path
from pydownloader.config.settings import Settings, save_settings
from pydownloader.download.worker import QueueWorker
from pydownloader.ffmpeg.locate import Ffmpeg
from pydownloader.i18n import tr
from pydownloader.manifest.registry import SourceEntry
from pydownloader.ui.card import SourceCard
from pydownloader.ui.console import ConsolePanel
from pydownloader.ui.settings_panel import SettingsDialog
from pydownloader.ui.theme import apply_theme
from pydownloader.ui.tray import TrayController, make_tray
from pydownloader.update.ui import UpdateMonitor

APP_TITLE = "PyDownloader"
MIN_WIDTH = 900
MIN_HEIGHT = 600
#: Split sizes of the two sections: about 40% for the cards, 60% for the console.
SPLIT_TOP = 400
SPLIT_BOTTOM = 600


class LogBridge(QObject):
    """Forwards log lines from the worker threads to the console in the GUI thread.

    The logging handler may be called from the sniffer or the download thread;
    emitting a signal keeps every widget change in the GUI thread (spec 4.4).
    """

    line = Signal(str)


class MainWindow(QMainWindow):
    """One window with the cards and the console."""

    #: «Открыть браузер» / «Закрыть браузер»: ``app.py`` owns the browser thread.
    browser_open_request = Signal()
    browser_close_request = Signal()

    def __init__(
        self,
        settings: Settings,
        paths: Paths,
        sniffer: SnifferThread | None,
        worker: QueueWorker | None,
        logger: logging.Logger | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.paths = paths
        self.sniffer = sniffer
        self.worker = worker
        self.logger = logger or logging.getLogger("pydownloader")
        self.cards: dict[str, SourceCard] = {}
        self.out_paths: dict[str, Path] = {}
        #: Chromium download thread, kept referenced so it is not garbage collected.
        self.install_worker: QThread | None = None
        #: FFmpeg binary used for the mux and for probing the resolution of MP4 files.
        self.ffmpeg: Ffmpeg | None = None
        #: Update check: created by ``app.py`` after the window, wired to the dialog.
        self.updater: UpdateMonitor | None = None
        #: Bridge of the log handler to the console, created with the window.
        self.log_bridge: LogBridge | None = None
        #: Browser of the last run: «Open browser» restarts the same kind and page.
        self.browser_choice: BrowserChoice | None = None
        self.extension_dir: Path | None = None
        self.last_url = ""
        #: Tray icon: created by ``app.py`` when the platform supports the tray.
        self.tray: TrayController | None = None
        #: Set by the tray «Выход» and the restart: the window really closes.
        self._quitting = False

        self.setObjectName("central")
        self.setWindowTitle(f"{APP_TITLE} {VERSION} — {settings.download_dir}")
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
        self.resize(MIN_WIDTH, MIN_HEIGHT)
        if settings.window_geometry:
            self.restoreGeometry(geometry_from_hex(settings.window_geometry))

        console = ConsolePanel(self)
        self.console = console

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._cards_section())
        splitter.addWidget(self._console_section(console))
        splitter.setSizes([SPLIT_TOP, SPLIT_BOTTOM])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setHandleWidth(6)
        self.splitter = splitter

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(splitter)
        self.setCentralWidget(central)

        self.status_label = QLabel(f"{VERSION} · {settings.download_dir}")
        self.update_label = QLabel("")
        self.statusBar().addWidget(self.status_label)
        self.statusBar().addPermanentWidget(self.update_label)

        self._connect()

    # --- widgets ---------------------------------------------------------

    def _cards_section(self) -> QWidget:
        container = QWidget()
        self.cards_layout = QVBoxLayout(container)
        self.cards_layout.setContentsMargins(8, 8, 8, 8)
        self.hint_label = QLabel(tr("window_empty"))
        self.hint_label.setObjectName("cardMeta")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cards_layout.addWidget(self.hint_label)
        self.cards_layout.addStretch(1)

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setWidget(container)
        self.scroll_area = area
        self.card_container = container
        self._sync_card_heights()

        header = QHBoxLayout()
        header.addWidget(QLabel(tr("window_found_videos")))
        header.addStretch(1)
        # The browser window can be closed by hand: the buttons reopen it and stop
        # the thread, so a download that is running does not need a restart (spec 4.3).
        self.open_browser_button = QPushButton(tr("window_open_browser"))
        self.open_browser_button.setToolTip(tr("window_open_browser_tip"))
        self.open_browser_button.clicked.connect(self.browser_open_request.emit)
        header.addWidget(self.open_browser_button)
        self.close_browser_button = QPushButton(tr("window_close_browser"))
        self.close_browser_button.setToolTip(tr("window_close_browser_tip"))
        self.close_browser_button.clicked.connect(self.browser_close_request.emit)
        header.addWidget(self.close_browser_button)
        self.clear_all_button = QPushButton(tr("window_clear_all"))
        self.clear_all_button.setToolTip(tr("window_clear_all_tip"))
        self.clear_all_button.clicked.connect(self.clear_all_cards)
        header.addWidget(self.clear_all_button)
        self.clear_downloaded_button = QPushButton(tr("window_clear_downloaded"))
        self.clear_downloaded_button.setToolTip(tr("window_clear_downloaded_tip"))
        self.clear_downloaded_button.clicked.connect(self.clear_downloaded_cards)
        header.addWidget(self.clear_downloaded_button)
        settings_button = QPushButton(tr("window_settings"))
        settings_button.clicked.connect(self.open_settings)
        header.addWidget(settings_button)

        wrapper = QWidget()
        outer = QVBoxLayout(wrapper)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(header)
        outer.addWidget(area, 1)
        return wrapper

    def _console_section(self, console: ConsolePanel) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)

        row = QHBoxLayout()
        clear = QPushButton(tr("window_clear"))
        clear.clicked.connect(console.clear_panel)
        folder = QPushButton(tr("window_open_download_folder"))
        folder.clicked.connect(self.open_download_folder)
        log = QPushButton(tr("window_open_log"))
        log.clicked.connect(self._open_log_file)
        row.addWidget(clear)
        row.addWidget(folder)
        row.addWidget(log)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(console, 1)
        return wrapper

    # --- wiring ----------------------------------------------------------

    def _connect(self) -> None:
        self.attach_sniffer()
        if self.worker is not None:
            self.worker.log.connect(self.log_info)
            self.worker.task_started.connect(self._task_started)
            self.worker.progress.connect(self._task_progress)
            self.worker.task_finished.connect(self._task_finished)
            self.worker.task_failed.connect(self._task_failed)

    def attach_sniffer(self) -> None:
        """Wire the sniffer signals; used when the thread is created after the window."""
        # The browser is not up yet: «Open browser» is the way to start it (spec 4.3).
        self.set_browser_running(False)
        if self.sniffer is None:
            return
        self.sniffer.source_found.connect(self.add_source)
        self.sniffer.message.connect(self.log_info)
        self.sniffer.failed.connect(self.log_error)
        self.sniffer.started.connect(lambda: self.set_browser_running(True))
        self.sniffer.page_changed.connect(self._page_changed)
        self.sniffer.browser_closed.connect(self._browser_closed)

    def browser_running(self) -> bool:
        """Whether the browser thread is up right now (the tray menu uses this)."""
        sniffer = self.sniffer
        return sniffer is not None and sniffer.isRunning()

    def set_browser_running(self, running: bool) -> None:
        """Enable «Open browser» only when the browser window is down (spec 4.3)."""
        self.open_browser_button.setEnabled(not running)
        self.close_browser_button.setEnabled(running)
        if self.tray is not None:
            self.tray.set_browser_running(running)

    def _page_changed(self, url: str, title: str) -> None:
        """Remember the page, so «Open browser» opens the site the user was on."""
        self.last_url = url

    def show_from_tray(self) -> None:
        """Double click on the tray icon: the window comes back to the front."""
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def check_updates_now(self) -> None:
        """The tray menu asks for a check with the same code as the settings dialog."""
        if self.updater is not None:
            self.updater.check_now()

    def quit_from_tray(self) -> None:
        """«Выход» in the tray menu: close the threads and quit (spec 4.3)."""
        self._quitting = True
        self.close()
        # With the tray the window is allowed to be the only one and hidden, so
        # quitting is asked for explicitly (Qt does not do it for a hidden window).
        app = QApplication.instance()
        if app is not None:
            app.quit()

    # --- console ---------------------------------------------------------

    def log_info(self, message: str) -> None:
        self.logger.info(message)

    def log_warning(self, message: str) -> None:
        self.logger.warning(message)

    def log_error(self, message: str) -> None:
        self.logger.error(message)

    def set_update_status(self, text: str) -> None:
        """Text of the status bar about the update check (spec 8)."""
        self.update_label.setText(text)

    def current_version(self) -> str:
        """Version of the running program, the value shown in the title."""
        return VERSION

    def exit_after_update(self) -> None:
        """The installer was launched: close the threads and quit the program (spec 8.3)."""
        self._quitting = True
        self.hide()
        worker = self.worker
        if worker is not None:
            worker.stop()
            worker.wait(5000)
        if self.sniffer is not None:
            self.sniffer.stop()
            self.sniffer.wait(5000)
        self._save_settings()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    # --- cards -----------------------------------------------------------

    def add_source(self, entry: SourceEntry) -> None:
        """A source passed the filters: add its card under the existing ones."""
        if entry.id in self.cards:
            return
        card = SourceCard(entry)
        card.download_clicked.connect(self._start_download)
        card.cancel_clicked.connect(self._cancel_download)
        card.open_file_clicked.connect(self._open_result_file)
        self.cards[entry.id] = card
        self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
        self.hint_label.hide()
        self._sync_card_heights()
        self.log_info(tr("window_shown", url=entry.url))

    def _start_download(self, entry_id: str) -> None:
        """«Скачать» puts the task in the queue (spec 4.1 p.6), the worker runs it."""
        card = self.cards.get(entry_id)
        if card is None or self.worker is None:
            return
        self.worker.enqueue(card.entry)
        card.set_state("queued")
        self.log_info(tr("window_queued", title=card.entry.title or card.entry.url))

    def _cancel_download(self, entry_id: str) -> None:
        if self.worker is not None:
            self.worker.cancel(entry_id)
        card = self.cards.get(entry_id)
        if card is not None:
            card.set_error(tr("card_cancelled"))
            self._sync_card_heights()

    def clear_all_cards(self) -> None:
        """«Очистить все»: remove every found video from the list.

        A running download is not cancelled: its card disappears, but the file
        is still written to the disk and the console keeps reporting it.
        """
        active = any(
            card.state in {"queued", "downloading"} for card in self.cards.values()
        )
        for card in list(self.cards.values()):
            self._remove_card(card)
        self.out_paths.clear()
        if active:
            self.log_warning(tr("window_active_kept"))
        self.log_info(tr("window_list_cleared"))

    def clear_downloaded_cards(self) -> None:
        """«Очистить скачанные»: remove only videos whose file is on the disk."""
        removed = 0
        for entry_id, card in list(self.cards.items()):
            path = self.out_paths.get(entry_id)
            if path is not None and path.is_file():
                self._remove_card(card)
                self.out_paths.pop(entry_id, None)
                removed += 1
        if removed:
            self.log_info(tr("window_removed_count", count=removed))
        else:
            self.log_info(tr("window_no_downloaded"))

    def _remove_card(self, card: SourceCard) -> None:
        self.cards.pop(card.entry.id, None)
        card.hide()
        self.cards_layout.removeWidget(card)
        card.setParent(None)
        card.deleteLater()
        self._update_hint()

    def _update_hint(self) -> None:
        self.hint_label.setVisible(not self.cards)
        self._sync_card_heights()

    def _sync_card_heights(self) -> None:
        """Keep the whole list of cards reachable when it does not fit.

        A resizable scroll area resizes its widget to the viewport, and the layout
        minimum of a widget that is not a top-level window is never propagated to
        it, so a long list of cards was squeezed and the part below the viewport
        could not be scrolled. The floor is written into the widget by hand from
        the floors of the cards: the scroll area shows a scrollbar, every card
        keeps its height, the buttons keep their text (spec 4.1 p.1).
        """
        cards = list(self.cards.values())
        visible = self.hint_label.isVisible()
        height = sum(card.minimumHeight() for card in cards)
        if visible:
            height += self.hint_label.sizeHint().height()
        items = len(cards) + (1 if visible else 0)
        if items > 1:
            height += self.cards_layout.spacing() * (items - 1)
        height += 16  # the top and bottom margin of cards_layout
        if self.card_container.minimumHeight() != height:
            self.card_container.setMinimumSize(0, height)

    def _task_started(self, entry_id: str, name: str) -> None:
        card = self.cards.get(entry_id)
        if card is not None:
            card.set_state("downloading")
            self._sync_card_heights()
            self.log_info(tr("window_download_started", title=name))

    def _task_progress(self, entry_id: str, done: int, total: int) -> None:
        card = self.cards.get(entry_id)
        if card is not None:
            card.set_progress(done, total)
            self._sync_card_heights()

    def _task_finished(self, entry_id: str, path: str) -> None:
        card = self.cards.get(entry_id)
        if card is not None:
            self.out_paths[entry_id] = Path(path)
            card.set_result(path)
            self._sync_card_heights()
        self.log_info(tr("window_finished", path=path))

    def _task_failed(self, entry_id: str, message: str) -> None:
        card = self.cards.get(entry_id)
        if card is not None:
            card.set_error(message)
            self._sync_card_heights()
        self.log_error(tr("window_task_failed", title=message))

    def _open_result_file(self, entry_id: str) -> None:
        """«Открыть файл»: play the downloaded video with the default player."""
        path = self.out_paths.get(entry_id)
        if path is None or not path.is_file():
            self.log_warning(tr("window_file_missing"))
            folder = path.parent if path is not None else Path(self.settings.download_dir)
            _show_in_explorer(folder)
            return
        if not _open_file(path):
            self.log_warning(tr("window_open_failed", error=path))

    def open_download_folder(self) -> None:
        _show_in_explorer(Path(self.settings.download_dir))

    def _open_log_file(self) -> None:
        if self.paths.log_file.exists():
            subprocess.Popen(["notepad", str(self.paths.log_file)])

    def _browser_closed(self) -> None:
        # The browser is closed by the user: the running download continues (spec 3.7).
        self.log_warning(tr("window_browser_closed"))
        # «Open browser» becomes the way to get the window back (spec 4.3).
        self.set_browser_running(False)

    # --- settings --------------------------------------------------------

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if self.updater is not None:
            dialog.check_requested.connect(self.updater.check_now)
        dialog.restart_requested.connect(self._restart_program)
        if dialog.exec():
            self.settings = dialog.settings
            self.setWindowTitle(f"{APP_TITLE} {VERSION} — {self.settings.download_dir}")
            self.status_label.setText(f"{VERSION} · {self.settings.download_dir}")
            if self.worker is not None:
                self.worker.download_dir = self.settings.download_dir
                self.worker.parallel = self.settings.threads
            app = QApplication.instance()
            if app is not None:
                apply_theme(cast(QApplication, app), self.settings.theme)
                self._apply_tray_state(cast(QApplication, app))
            self._save_settings()

    def _apply_tray_state(self, app: QApplication) -> None:
        """The tray is created the first time the setting is turned on (spec 4.3).

        Turning it off removes the icon: the window becomes a normal window, so
        Qt quits when it is closed, and «X» is no longer a way to hide.
        """
        if self.settings.tray_enabled:
            if self.tray is None:
                make_tray(self, icon_path())
                app.setQuitOnLastWindowClosed(False)
        elif self.tray is not None:
            self.tray.hide()
            self.tray = None
            app.setQuitOnLastWindowClosed(True)

    def _restart_program(self) -> None:
        """«Перезапустить» in the settings: the language is applied on the next start.

        ``app.py`` owns the restart, and it imports this module, so the helper is
        imported inside the method to avoid a cycle at import time.
        """
        from pydownloader.ui.app import restart_application

        self._quitting = True
        self._save_settings()
        self.close()
        app = QApplication.instance()
        if app is not None:
            restart_application(cast(QApplication, app))

    def _save_settings(self) -> None:
        self.settings.window_geometry = geometry_hex(self.saveGeometry())
        save_settings(self.settings, self.paths.settings_file)

    def persist_settings(self) -> None:
        """Write the settings from a slot: used by the update check cache (spec 8.3 p.5)."""
        save_settings(self.settings, self.paths.settings_file)

    # --- closing ---------------------------------------------------------

    def closeEvent(self, event) -> None:  # Qt naming
        if self._hide_to_tray():
            event.ignore()
            return
        worker = self.worker
        if worker is not None:
            pending = worker.pending()
            if pending:
                answer = QMessageBox.question(
                    self,
                    APP_TITLE,
                    tr("window_quit_question"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return
                for task_id in list(pending):
                    worker.cancel(task_id)
            worker.stop()
            worker.wait(5000)
        if self.sniffer is not None:
            self.sniffer.stop()
            self.sniffer.wait(5000)
        self._save_settings()

    def _hide_to_tray(self) -> bool:
        """«X» keeps the program in the tray: the threads stay alive (spec 4.3).

        A real exit (tray «Выход», restart, update install) is marked by
        ``_quitting``, so it runs the teardown of ``closeEvent``.
        """
        if self._quitting or self.tray is None:
            return False
        if not (self.settings.tray_enabled and self.settings.close_to_tray):
            return False
        self.hide()
        self.log_info(tr("window_hidden_to_tray"))
        if not self.settings.tray_hint_seen:
            # The first time the user has to learn that the program is still running.
            self.tray.notify(tr("tray_hint"))
            self.settings.tray_hint_seen = True
            self._save_settings()
        return True


def geometry_hex(data: QByteArray) -> str:
    """Saved window geometry as an ASCII hex string for the settings file."""
    return bytes(data.toHex().data()).decode("ascii")


def geometry_from_hex(text: str) -> QByteArray:
    """Geometry bytes read back from the settings string."""
    return QByteArray.fromHex(text.encode("ascii"))


def _show_in_explorer(folder: Path) -> None:
    """Open the folder in Explorer, creating it when it does not exist."""
    folder.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(["explorer", str(folder)])


def _open_file(path: Path) -> bool:
    """Open the video with the program associated with ``.mp4``."""
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def pick_download_dir(start: Path, parent: QWidget | None = None) -> Path | None:
    """The folder dialog of spec 3.1; ``None`` means the user cancelled the start."""
    path = QFileDialog.getExistingDirectory(parent, tr("window_download_folder_title"), str(start))
    return Path(path) if path else None
