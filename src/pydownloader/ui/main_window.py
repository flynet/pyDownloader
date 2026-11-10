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

from PySide6.QtCore import QByteArray, QObject, Qt, QThread, Signal
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
from pydownloader.browser.sniffer import SnifferThread
from pydownloader.config.paths import Paths
from pydownloader.config.settings import Settings, save_settings
from pydownloader.download.worker import QueueWorker
from pydownloader.ffmpeg.locate import Ffmpeg
from pydownloader.manifest.registry import SourceEntry
from pydownloader.ui.card import SourceCard
from pydownloader.ui.console import ConsolePanel
from pydownloader.ui.settings_panel import SettingsDialog
from pydownloader.ui.theme import apply_theme
from pydownloader.update.ui import UpdateMonitor

APP_TITLE = "PyDownloader"
MIN_WIDTH = 900
MIN_HEIGHT = 600
#: Split sizes of the two sections: about 40% for the cards, 60% for the console.
SPLIT_TOP = 400
SPLIT_BOTTOM = 600
HINT = "Видео пока не найдены. Откройте сайт в браузере и запустите видео."

CLEAR_BUTTON = "Очистить"
OPEN_FOLDER_BUTTON = "Открыть папку загрузки"
OPEN_LOG_BUTTON = "Открыть лог-файл"
SETTINGS_BUTTON = "⚙ Настройки"
CLOSE_CONFIRM = "Идёт загрузка. Отменить загрузку и выйти?"


class LogBridge(QObject):
    """Forwards log lines from the worker threads to the console in the GUI thread.

    The logging handler may be called from the sniffer or the download thread;
    emitting a signal keeps every widget change in the GUI thread (spec 4.4).
    """

    line = Signal(str)


class MainWindow(QMainWindow):
    """One window with the cards and the console."""

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
        self.hint_label = QLabel(HINT)
        self.hint_label.setObjectName("cardMeta")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cards_layout.addWidget(self.hint_label)
        self.cards_layout.addStretch(1)

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setWidget(container)
        self.scroll_area = area

        header = QHBoxLayout()
        header.addWidget(QLabel("Найденные видео"))
        header.addStretch(1)
        settings_button = QPushButton(SETTINGS_BUTTON)
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
        clear = QPushButton(CLEAR_BUTTON)
        clear.clicked.connect(console.clear_panel)
        folder = QPushButton(OPEN_FOLDER_BUTTON)
        folder.clicked.connect(self._open_download_folder)
        log = QPushButton(OPEN_LOG_BUTTON)
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
        if self.sniffer is None:
            return
        self.sniffer.source_found.connect(self.add_source)
        self.sniffer.message.connect(self.log_info)
        self.sniffer.failed.connect(self.log_error)
        self.sniffer.browser_closed.connect(self._browser_closed)

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
        card.open_folder_clicked.connect(self._open_result_folder)
        self.cards[entry.id] = card
        self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
        self.hint_label.hide()
        self.log_info(f"Показано в списке: {entry.url}")

    def _start_download(self, entry_id: str) -> None:
        """«Скачать» puts the task in the queue (spec 4.1 p.6), the worker runs it."""
        card = self.cards.get(entry_id)
        if card is None or self.worker is None:
            return
        self.worker.enqueue(card.entry)
        card.set_state("queued")
        self.log_info(f"В очереди: {card.entry.title or card.entry.url}")

    def _cancel_download(self, entry_id: str) -> None:
        if self.worker is not None:
            self.worker.cancel(entry_id)
        card = self.cards.get(entry_id)
        if card is not None:
            card.set_error("отменено")

    def _task_started(self, entry_id: str, name: str) -> None:
        card = self.cards.get(entry_id)
        if card is not None:
            card.set_state("downloading")
            self.log_info(f"Начата загрузка: {name}")

    def _task_progress(self, entry_id: str, done: int, total: int) -> None:
        card = self.cards.get(entry_id)
        if card is not None:
            card.set_progress(done, total)

    def _task_finished(self, entry_id: str, path: str) -> None:
        card = self.cards.get(entry_id)
        self.out_paths[entry_id] = Path(path)
        if card is not None:
            card.set_result(path)
        self.log_info(f"Готово: {path}")

    def _task_failed(self, entry_id: str, message: str) -> None:
        card = self.cards.get(entry_id)
        if card is not None:
            card.set_error(message)
        self.log_error(f"Задача не выполнена: {message}")

    def _open_result_folder(self, entry_id: str) -> None:
        path = self.out_paths.get(entry_id)
        folder = path.parent if path else Path(self.settings.download_dir)
        _show_in_explorer(folder)

    def _open_download_folder(self) -> None:
        _show_in_explorer(Path(self.settings.download_dir))

    def _open_log_file(self) -> None:
        if self.paths.log_file.exists():
            subprocess.Popen(["notepad", str(self.paths.log_file)])

    def _browser_closed(self) -> None:
        # The browser is closed by the user: the running download continues (spec 3.7).
        self.log_warning("Браузер закрыт")

    # --- settings --------------------------------------------------------

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if self.updater is not None:
            dialog.check_requested.connect(self.updater.check_now)
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
            self._save_settings()

    def _save_settings(self) -> None:
        self.settings.window_geometry = geometry_hex(self.saveGeometry())
        save_settings(self.settings, self.paths.settings_file)

    def persist_settings(self) -> None:
        """Write the settings from a slot: used by the update check cache (spec 8.3 p.5)."""
        save_settings(self.settings, self.paths.settings_file)

    # --- closing ---------------------------------------------------------

    def closeEvent(self, event) -> None:  # Qt naming
        worker = self.worker
        if worker is not None:
            pending = worker.pending()
            if pending:
                answer = QMessageBox.question(
                    self,
                    APP_TITLE,
                    CLOSE_CONFIRM,
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


def pick_download_dir(start: Path, parent: QWidget | None = None) -> Path | None:
    """The folder dialog of spec 3.1; ``None`` means the user cancelled the start."""
    path = QFileDialog.getExistingDirectory(parent, "Папка для загрузок", str(start))
    return Path(path) if path else None
