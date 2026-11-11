"""The main window: found videos on top, console below (spec 4.2).

The window owns the cards, the queue worker and the sniffer thread. All
updates from the threads arrive through Qt signals, so no widget is touched
from another thread. The window size and position are stored in the settings
and restored on the next start (spec 4.2 p.1).
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
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
    QLineEdit,
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
from pydownloader.config.settings import Settings, ThemeName, save_settings
from pydownloader.download.worker import QueueWorker
from pydownloader.ffmpeg.locate import Ffmpeg
from pydownloader.i18n import tr
from pydownloader.manifest.registry import SourceEntry
from pydownloader.ui.button_icons import (
    attach,
    browser_icon,
    chevron_icon,
    clear_all_icon,
    clear_downloaded_icon,
    console_icon,
    cross_icon,
    folder_icon,
    gear_icon,
    go_icon,
    icon_color,
    log_icon,
)
from pydownloader.ui.card import SourceCard, format_duration
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
#: Split sizes with the console hidden: the list of cards takes the whole window,
#: the console section is not on the screen and the handle of the splitter is 0 px,
#: so there is no divider between the two (spec 4.2 p.5).
SPLIT_CARDS_ONLY = 1000
SPLIT_CONSOLE_MIN = 12
#: The width of the handle of the splitter while the console panel is shown.
CONSOLE_HANDLE = 6

#: The tooltip of the tray is rewritten at most once a second: the progress signal
#: of the queue comes for every segment, and a tooltip of Windows is a heavy call.
TOOLTIP_MS = 1000

#: The balloon and the sound report the end of a batch of downloads, so a batch is
#: at least two files: one download is not a batch, and the user hears nothing after
#: every file of a batch (spec 4.2 p.7).
MIN_BATCH = 2


@dataclass
class RunInfo:
    """One task that is downloading: the name, the size, the percent, the start."""

    name: str
    size: int | None
    percent: int
    started: float


def tray_speed_line(info: RunInfo, now: float) -> str:
    """The tooltip line of a running task: name, percent, speed, time left (spec 4.2 p.7).

    The queue reports the segments, not the bytes, so the speed is the size of the
    source divided by the time since the start: a tooltip of the tray, not a
    measurement, and a source with no size shows the percent only.
    """
    if info.size is None:
        return tr("tray_tooltip_line_plain", name=info.name, percent=info.percent)
    elapsed = max(now - info.started, 0.1)
    downloaded = info.size * info.percent / 100
    speed = downloaded / elapsed / (1024 * 1024)
    if speed <= 0:
        return tr("tray_tooltip_line_plain", name=info.name, percent=info.percent)
    left = (info.size - downloaded) / (speed * 1024 * 1024)
    return tr(
        "tray_tooltip_line",
        name=info.name,
        percent=info.percent,
        speed=round(speed, 1),
        left=format_duration(left),
    )


class LogBridge(QObject):
    """Forwards log lines from the worker threads to the console in the GUI thread.

    The logging handler may be called from the sniffer or the download thread;
    emitting a signal keeps every widget change in the GUI thread (spec 4.4).
    """

    line = Signal(str)


class MainWindow(QMainWindow):
    """One window with the cards and the console."""

    #: The one button of the browser window asks ``app.py`` for the action: the
    #: thread is owned there, the window only reports the state of the button (spec 4.3).
    browser_toggle_request = Signal()
    #: «Go» with the browser down: ``app.py`` starts the thread on the address of the
    #: field, so the browser window comes up on the page of the link (spec 4.2 p.4).
    browser_open_request = Signal(str)

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
        #: The color of the icons: the buttons of the accent are white, the buttons
        #: of the panel and the tray menu take the text color of the theme (spec 4.3).
        self._accent = icon_color("accent", settings.theme)
        self._panel = icon_color("panel", settings.theme)
        #: The marks of the second row: white on the red of «Clear all», the dark of
        #: the theme on the yellow of «Clear downloaded» (spec 4.1 p.1).
        self._warn = icon_color("warn", settings.theme)
        self._danger = icon_color("danger", settings.theme)
        self.cards: dict[str, SourceCard] = {}
        self.out_paths: dict[str, Path] = {}
        #: The tasks that are downloading, for the tooltip of the tray (spec 4.2 p.7).
        self._runs: dict[str, RunInfo] = {}
        #: The moment the tooltip of the tray may be written again.
        self._tooltip_due = 0.0
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
        #: The browser thread is being resolved and launched: the one browser button
        #: is not clickable while it runs, so a second press cannot start a second thread.
        self._browser_starting = False

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
        splitter.setHandleWidth(CONSOLE_HANDLE)
        self.splitter = splitter
        #: The console panel is hidden: the list of cards fills the window (spec 4.2 p.5).
        self._console_hidden = not settings.console_open
        self._count_done = 0
        #: The sound of the finished downloads (spec 4.2 p.7); a test replaces it.
        self.play_sound: Callable[[], None] = play_notification
        if self._console_hidden:
            self._hide_console()
        else:
            # The window opens with the panel on the screen, so the button in the top
            # row says «Hide console» from the first frame (spec 4.2 p.5).
            self._sync_console_button()

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

        # The program starts with the browser closed, so the console has nothing to
        # show: the window says what to press (spec 4.3), and the hidden panel says
        # which button opens it back (spec 4.2 p.5).
        self.log_info(tr("app_browser_hint"))
        if self._console_hidden:
            self.log_info(tr("app_console_hint"))

    # --- widgets ---------------------------------------------------------

    def _cards_section(self) -> QWidget:
        container = QWidget()
        #: The wall behind the cards is painted by the rule of the theme, not by the
        #: palette: a plain QWidget takes the color of the palette, and that color is
        #: not the theme, so the list of cards stayed dark in the light theme.
        container.setObjectName("cardArea")
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
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
        # One button for the browser window: the same button shows the window and
        # takes it away, so its text, tip and icon follow the thread (spec 4.3).
        self.browser_button = QPushButton(tr("window_open_browser"))
        self.browser_button.setToolTip(tr("window_open_browser_tip"))
        attach(self.browser_button, browser_icon(self._accent, True))
        self.browser_button.clicked.connect(self.browser_toggle_request.emit)
        header.addWidget(self.browser_button)
        # «Show console» / «Hide console» is one button of the top row: the panel is
        # on the screen only when the user asks for it, so the toggle is where the
        # other commands of the window are (spec 4.2 p.5).
        self.console_button = QPushButton(tr("console_show"))
        self.console_button.setToolTip(tr("console_show_tip"))
        attach(self.console_button, console_icon(self._accent))
        self.console_button.clicked.connect(self.toggle_console)
        header.addWidget(self.console_button)
        # The downloads folder is opened from the top row: the row of the console is
        # on the screen only with the panel, and the folder is needed without it.
        self.folder_button = QPushButton(tr("window_open_download_folder"))
        attach(self.folder_button, folder_icon(self._accent))
        self.folder_button.clicked.connect(self.open_download_folder)
        header.addWidget(self.folder_button)
        self.settings_button = QPushButton(tr("window_settings"))
        # The gear is drawn: the glyph of the font shows a box on Windows (spec 4.3 p.2).
        attach(self.settings_button, gear_icon(self._accent))
        self.settings_button.clicked.connect(self.open_settings)
        header.addWidget(self.settings_button)
        # The four commands of the window are in the upper-left corner. «Clear
        # downloaded» (yellow) and «Clear all» (red) are in the right end of the same
        # row: the color tells which of the two is the softer action, the yellow takes
        # only the cards whose file is on the disk, the red takes the whole list
        # (spec 4.1 p.1).
        header.addStretch(1)
        self.clear_downloaded_button = QPushButton(tr("window_clear_downloaded"))
        self.clear_downloaded_button.setObjectName("clearDownloaded")
        self.clear_downloaded_button.setToolTip(tr("window_clear_downloaded_tip"))
        attach(self.clear_downloaded_button, clear_downloaded_icon(self._warn))
        self.clear_downloaded_button.clicked.connect(self.clear_downloaded_cards)
        header.addWidget(self.clear_downloaded_button)
        self.clear_all_button = QPushButton(tr("window_clear_all"))
        self.clear_all_button.setObjectName("clearAll")
        self.clear_all_button.setToolTip(tr("window_clear_all_tip"))
        attach(self.clear_all_button, clear_all_icon(self._danger))
        self.clear_all_button.clicked.connect(self.clear_all_cards)
        header.addWidget(self.clear_all_button)

        url_row = QHBoxLayout()
        # The address of the video is pasted in the window itself, so the user starts
        # a download without opening the browser and typing the address in it: «Go»
        # opens the browser on that page, and the browser starts when it is down
        # (spec 4.2 p.4).
        self.url_input = QLineEdit()
        placeholder = tr("window_url_placeholder")
        self.url_input.setPlaceholderText(placeholder)
        # A link longer than the field is read in the tooltip.
        self.url_input.setToolTip(placeholder)
        self.url_input.textChanged.connect(self.url_input.setToolTip)
        self.url_input.setClearButtonEnabled(True)
        self.url_input.returnPressed.connect(self.open_url)
        self.go_button = QPushButton(tr("window_go"))
        self.go_button.setToolTip(tr("window_go_tip"))
        attach(self.go_button, go_icon(self._accent))
        self.go_button.clicked.connect(self.open_url)
        url_row.addWidget(self.url_input, 1)
        url_row.addWidget(self.go_button)

        wrapper = QWidget()
        outer = QVBoxLayout(wrapper)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(header)
        outer.addLayout(url_row)
        outer.addWidget(area, 1)
        return wrapper

    def _console_section(self, console: ConsolePanel) -> QWidget:
        """The panel of the console: the row of its buttons and the text.

        The whole section is on the screen only while the console is shown: hidden,
        there is no row and no divider of the splitter, the list of cards fills the
        window (spec 4.2 p.5).
        """
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)

        row = QHBoxLayout()
        # «Clear» clears the text of the console, «Open log file» opens the full
        # diary of the run: both belong to the panel, so they appear with it. The
        # commands of the window (console, folder) are in the top row.
        self.console_clear = QPushButton(tr("window_clear"))
        attach(self.console_clear, cross_icon(self._accent))
        self.console_clear.clicked.connect(console.clear_panel)
        self.log_button = QPushButton(tr("window_open_log"))
        attach(self.log_button, log_icon(self._accent))
        self.log_button.clicked.connect(self._open_log_file)
        row.addWidget(self.console_clear)
        row.addWidget(self.log_button)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(console, 1)
        self.console_section = wrapper
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
        """The browser button is the toggle: its text and icon follow the thread (spec 4.3).

        One button does both jobs, so the state of the window is written on it:
        «Open browser» with the arrow when the window is down, «Close browser» with
        the cross when it runs. The button is clickable in both states, only the
        launch of the browser keeps it disabled (spec 4.3 p.2).
        """
        key = "window_close_browser" if running else "window_open_browser"
        self.browser_button.setText(tr(key))
        self.browser_button.setToolTip(tr(f"{key}_tip"))
        # The icon is the action the button does: open and close are one window with
        # a different mark, so the button is recognized as the same button.
        attach(self.browser_button, browser_icon(self._accent, not running))
        self.browser_button.setEnabled(not self._browser_starting)
        if self.tray is not None:
            self.tray.set_browser_running(running)

    def set_browser_starting(self, starting: bool) -> None:
        """The launch of the browser is running: the button waits for it (spec 4.3 p.2).

        Resolving the browser, reading the settings and the offer to download
        Chromium are on the click, and a second click of the same button during the
        launch would start a second thread of Playwright, so the button is disabled
        for the time of the launch and gets its own tip.
        """
        self._browser_starting = starting
        self.browser_button.setEnabled(not starting)
        if starting:
            self.browser_button.setToolTip(tr("window_browser_starting"))
        else:
            self.set_browser_running(self.browser_running())

    def open_url(self) -> None:
        """«Go»: the address of the field goes to the browser (spec 4.2 p.4).

        The link is read from the field of the window, so a download starts without
        opening the browser and typing the address inside it: with the browser down
        the thread is launched on the page of the field (the browser button of the
        window changes to «Close browser» when the thread is up), with the browser up
        the pump loop of the thread opens the page, and the same response listener
        finds the manifests of the new site.
        """
        url = self.url_input.text().strip()
        if not url:
            self.log_info(tr("go_url_missing"))
            return
        if not url.startswith(("http://", "https://")):
            # A domain pasted without the protocol is a page address as well.
            url = "https://" + url
        if self._browser_starting:
            # The launch is running: a second request would start a second thread.
            self.log_info(tr("window_browser_starting"))
            return
        sniffer = self.sniffer
        if sniffer is not None and sniffer.isRunning():
            if self.last_url and self.last_url.lower() == url.lower():
                # The page of the field is the page of the browser: do not reload it.
                self.log_info(tr("go_same_page"))
                return
            sniffer.go(url)
            self.last_url = url
            self.log_info(tr("go_page_opened", url=url))
            return
        self.browser_open_request.emit(url)

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

    def toggle_console(self) -> None:
        """«Show console» / «Hide console»: the list of cards gets the whole window."""
        if self._console_hidden:
            self.show_console()
        else:
            self._hide_console()

    def show_console(self) -> None:
        """The console panel comes back with the room it had before (spec 4.2 p.5).

        The section of the console is the row of its buttons and the text, so the
        row and the panel appear together, and the handle of the splitter gets its
        width back: with the panel on the screen the divider is the line between the
        two sections.
        """
        self._console_hidden = False
        self.console_section.setVisible(True)
        self.splitter.setHandleWidth(CONSOLE_HANDLE)
        self.splitter.setSizes([SPLIT_TOP, SPLIT_BOTTOM])
        self._sync_console_button()
        self.settings.console_open = True
        self._save_settings()
        self.log_info(tr("console_shown"))

    def _hide_console(self) -> None:
        """The console section goes away: the list of cards is the whole window.

        The row of the console and the panel are one section, so hidden the window
        has no divider at all: the handle of the splitter is 0 px. The top row keeps
        the button of the console, and the state is stored, so the window opens the
        next time the way the user left it (spec 4.2 p.5).
        """
        self._console_hidden = True
        self.console_section.setVisible(False)
        self.splitter.setHandleWidth(0)
        self.splitter.setSizes([SPLIT_CARDS_ONLY, 0])
        self._sync_console_button()
        self.settings.console_open = False
        self._save_settings()

    def _sync_console_button(self) -> None:
        """The button in the top row says what the console will do (spec 4.2 p.5).

        The window opens with the panel the user left, so the state is written on the
        button at the start and after every toggle: «Show console» with the terminal
        when the panel is not on the screen, «Hide console» with the chevron when it
        is.
        """
        key = "console_show" if self._console_hidden else "console_hide"
        self.console_button.setText(tr(key))
        self.console_button.setToolTip(tr(f"{key}_tip"))
        # The terminal is the panel that is not on the screen, the chevron points to
        # the panel that goes away: the mark is the action of the button.
        icon = chevron_icon(self._accent, False)
        if self._console_hidden:
            icon = console_icon(self._accent)
        attach(self.console_button, icon)

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
        card = SourceCard(entry, theme=self.settings.theme)
        card.download_clicked.connect(self._start_download)
        card.cancel_clicked.connect(self._cancel_download)
        card.open_file_clicked.connect(self._open_result_file)
        card.remove_clicked.connect(self._remove_entry)
        self.cards[entry.id] = card
        self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
        # The card is created after the window is shown, so it has to be shown by
        # hand: a widget added to a layout of a visible window stays hidden until
        # the event loop activates the layout (spec 4.1 p.1).
        card.show()
        self.hint_label.hide()
        self._sync_card_heights()
        self.log_info(tr("window_shown", url=entry.url))

    def _start_download(self, entry_id: str) -> None:
        """«Скачать» puts the task in the queue (spec 4.1 p.6), the worker runs it."""
        card = self.cards.get(entry_id)
        if card is None or self.worker is None:
            return
        if self._queue_drained():
            # A queue that was empty is a new batch: the balloon reports the end of
            # a batch, so its counter starts from 0 (spec 4.2 p.7).
            self._count_done = 0
        self.worker.enqueue(card.entry)
        card.set_state("queued")
        self.log_info(tr("window_queued", title=card.entry.title or card.entry.url))
        if self.tray is not None:
            # The tray is the place the user looks at when the window is minimized:
            # the green arrow says that the program is downloading (spec 4.2 p.7).
            self.tray.set_download_active(True)

    def _cancel_download(self, entry_id: str) -> None:
        if self.worker is not None:
            self.worker.cancel(entry_id)
        card = self.cards.get(entry_id)
        if card is not None:
            card.set_error(tr("card_cancelled"))
            self._sync_card_heights()
        self._runs.pop(entry_id, None)
        self._push_tray_tooltip(True)
        if self._queue_drained():
            # A cancelled task is not a finished download: the icon goes quiet, the
            # balloon stays away (spec 4.2 p.7).
            self._idle_tray()

    def _queue_drained(self) -> bool:
        """Whether the queue is empty now: the last task of the worker is done."""
        return self.worker is None or not self.worker.pending()

    def _idle_tray(self) -> None:
        """The queue is empty: the arrow of the tray goes back to white (spec 4.2 p.7).

        The state of the icon only, no balloon and no sound. The queue can be empty
        for reasons that are not a finished batch: the user took a card out of the
        list, a task was cancelled, one download ended. None of them is the report
        the user asks for, so the icon is set quiet and the balloon stays away.
        """
        if self.tray is not None:
            self.tray.set_download_active(False)
        self._push_tray_tooltip(True)

    def _report_queue_done(self) -> None:
        """A batch of downloads is over: the balloon and the sound (spec 4.2 p.7).

        The queue is empty and every task of the batch is finished, so the report
        is sent once for the whole batch, not after every file. A batch is at least
        `MIN_BATCH` files: a single download gives no balloon and no sound, and
        removing a card or cancelling a task is not a finished download at all. The
        counter is reset, so the next batch is counted from the start and a single
        download after a batch stays quiet.
        """
        self._idle_tray()
        if self._count_done < MIN_BATCH:
            return
        if self.tray is not None:
            self.tray.notify(tr("tray_download", n=self._count_done))
        self.play_sound()
        self.log_info(tr("window_all_done", n=self._count_done))
        self._count_done = 0

    def _push_tray_tooltip(self, force: bool = False) -> None:
        """The tooltip of the tray icon: the files that are downloading (spec 4.2 p.7).

        The progress of the queue comes for every segment and writing the tooltip of
        Windows is a heavy call, so the text is rewritten at most once a second.
        The start and the end of a task are written at once, ``force`` is the way.
        """
        if self.tray is None:
            return
        now = time.monotonic()
        if not force and now < self._tooltip_due:
            return
        self._tooltip_due = now + TOOLTIP_MS / 1000
        lines = [(info.name, tray_speed_line(info, now)) for info in self._runs.values()]
        pending = self.worker.pending() if self.worker is not None else []
        queued = max(len(pending) - len(self._runs), 0)
        if queued:
            lines.append(("", tr("tray_tooltip_queued", n=queued)))
        self.tray.set_progress_lines(lines)

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

    def _remove_entry(self, entry_id: str) -> None:
        """«✕» on a card: take this one entry out of the list (spec 4.1 p.1).

        A queued or running task is cancelled first: the person asked for this
        card to disappear, so its download stops and the card goes with it. A
        finished file stays on the disk, only the card is taken out of the list.
        """
        card = self.cards.get(entry_id)
        if card is None:
            return
        name = card.entry.title or card.entry.url
        if self.worker is not None and card.state in {"queued", "downloading"}:
            self.worker.cancel(entry_id)
            self.log_info(tr("window_card_removed_cancelled", title=name))
        else:
            self.log_info(tr("window_card_removed", title=name))
        self.out_paths.pop(entry_id, None)
        self._runs.pop(entry_id, None)
        self._push_tray_tooltip(True)
        self._remove_card(card)
        if self._queue_drained():
            # Removing a card is not a finished download: nothing was downloaded in
            # this batch, so the icon goes quiet and the balloon stays away.
            self._idle_tray()

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
            # The tray tooltip follows the running task: the name, the percent, the
            # speed, the time left (spec 4.2 p.7).
            self._runs[entry_id] = RunInfo(name, card.entry.size, 0, time.monotonic())
            self._push_tray_tooltip(True)

    def _task_progress(self, entry_id: str, done: int, total: int) -> None:
        card = self.cards.get(entry_id)
        if card is not None:
            card.set_progress(done, total)
            self._sync_card_heights()
        info = self._runs.get(entry_id)
        if info is not None:
            info.percent = done * 100 // total if total else 0
            self._push_tray_tooltip()

    def _task_finished(self, entry_id: str, path: str) -> None:
        card = self.cards.get(entry_id)
        if card is not None:
            self.out_paths[entry_id] = Path(path)
            card.set_result(path)
            self._sync_card_heights()
        self._count_done += 1
        self._runs.pop(entry_id, None)
        self._push_tray_tooltip(True)
        self.log_info(tr("window_finished", path=path))
        if self._queue_drained():
            self._report_queue_done()

    def _task_failed(self, entry_id: str, message: str) -> None:
        card = self.cards.get(entry_id)
        if card is not None:
            card.set_error(message)
            self._sync_card_heights()
        self._runs.pop(entry_id, None)
        self._push_tray_tooltip(True)
        self.log_error(tr("window_task_failed", title=message))
        if self._queue_drained():
            # A failed task is not a finished download: the batch did not end with
            # every file on the disk, so the icon goes quiet without a balloon.
            self._idle_tray()

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

    def _recolor_icons(self, theme: ThemeName) -> None:
        """The colors of the painted marks follow the theme, without a restart.

        The marks are painted once, when the button is built, so a theme chosen in the
        settings leaves the buttons and the cards the colors of the old theme: every
        mark is drawn again with the colors of the theme the user picked, the badge of
        every card is repainted, and the bar of a card takes the bar of the new theme
        (spec 4.3 p.2, p.3).
        """
        self._accent = icon_color("accent", theme)
        self._panel = icon_color("panel", theme)
        self._warn = icon_color("warn", theme)
        self._danger = icon_color("danger", theme)
        attach(self.browser_button, browser_icon(self._accent, not self.browser_running()))
        attach(self.console_button, console_icon(self._accent))
        attach(self.folder_button, folder_icon(self._accent))
        attach(self.settings_button, gear_icon(self._accent))
        attach(self.clear_downloaded_button, clear_downloaded_icon(self._warn))
        attach(self.clear_all_button, clear_all_icon(self._danger))
        attach(self.go_button, go_icon(self._accent))
        attach(self.console_clear, cross_icon(self._accent))
        attach(self.log_button, log_icon(self._accent))
        for card in self.cards.values():
            card.set_theme(theme)
        if self.tray is not None:
            self.tray.set_theme(theme)

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
            # The theme is applied without a restart: the marks that are painted once
            # are drawn again with the colors of the new theme (spec 4.3 p.2).
            self._recolor_icons(self.settings.theme)
            # The console row of the settings decides what the window shows (spec 4.2 p.5),
            # so the panel is brought to the state the user chose.
            if self.settings.console_open == self._console_hidden:
                self.toggle_console()
            self._save_settings()

    def _apply_tray_state(self, app: QApplication) -> None:
        """The tray is created the first time the setting is turned on (spec 4.3).

        Turning it off removes the icon: the window becomes a normal window, so
        Qt quits when it is closed. «X» is a normal close, and the tray menu is
        the place the program is quit from.
        """
        if self.settings.tray_enabled:
            if self.tray is None:
                make_tray(self, icon_path())
                app.setQuitOnLastWindowClosed(False)
                self.hint_tray()
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
        # «X» hides the window to the tray, the downloads and the browser stay alive
        # (spec 4.3 p.4). A real exit (tray «Exit», restart, update install) is
        # marked by ``_quitting``, so the teardown below runs for it.
        if self._hide_to_tray():
            event.ignore()
            return
        self._quitting = True
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

    def hint_tray(self) -> None:
        """The balloon of the first start: the program lives in the tray (spec 4.3).

        Shown once, the flag is stored, so the hint is not repeated on the next
        run. The tray is where the window is brought back and where the program
        is quit, so the first start has to point at it.
        """
        if self.tray is None or self.settings.tray_hint_seen:
            return
        self.tray.notify(tr("tray_hint"))
        self.log_info(tr("window_in_tray"))
        self.settings.tray_hint_seen = True
        self._save_settings()

    def _hide_to_tray(self) -> bool:
        """«X» keeps the program in the tray: the threads stay alive (spec 4.3).

        A real exit (tray «Exit», restart, update install) is marked by
        ``_quitting``, so it runs the teardown of ``closeEvent``.
        """
        if self._quitting or self.tray is None:
            return False
        if not (self.settings.tray_enabled and self.settings.close_to_tray):
            return False
        self.hide()
        self.log_info(tr("window_hidden_to_tray"))
        self._hint_tray_once()
        return True

    def _hint_tray_once(self) -> None:
        """The balloon of the first hide, shown once (spec 4.3)."""
        if self.tray is None or self.settings.tray_hint_seen:
            return
        self.tray.notify(tr("tray_hint"))
        self.settings.tray_hint_seen = True
        self._save_settings()


def geometry_hex(data: QByteArray) -> str:
    """Saved window geometry as an ASCII hex string for the settings file."""
    return bytes(data.toHex().data()).decode("ascii")


def geometry_from_hex(text: str) -> QByteArray:
    """Geometry bytes read back from the settings string."""
    return QByteArray.fromHex(text.encode("ascii"))


def play_notification() -> None:
    """The system sound of the finished downloads (spec 4.2 p.7).

    The sound of Windows is used, so the program needs no sound file of its own.
    A platform without ``winsound`` (Linux, the CI of the tests) plays nothing:
    there the balloon of the tray is the report the user sees as well.
    """
    if sys.platform != "win32":
        return
    import winsound

    winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)


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
