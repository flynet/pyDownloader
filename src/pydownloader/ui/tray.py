"""Tray icon: the program lives in the Windows notification area (spec 4.3).

«X» in the title bar hides the window to the tray, the downloads keep running,
and the tray menu keeps the program reachable: show the window, open and close
the browser, show the console, check for an update, open the download folder,
exit. «Exit» is the only way to quit when the window is hidden (spec 4.3 p.4),
so it runs the same teardown as a close that is not a hide.

The icon is drawn by the program, not taken from the file, because its colour
marks the state: a green arrow points down while a download is running, a blue
one when the queue is empty (spec 4.2 p.7). Windows draws the tray icon in the
notification area, so the arrow cannot be moved there: the animation is the
arrow jumping between the up and the down drawing, which is the same motion.
The balloon of the finished downloads uses the same ``showMessage`` as the hint
of the tray.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from pydownloader._version import VERSION
from pydownloader.config.constants import APP_NAME
from pydownloader.i18n import tr

if TYPE_CHECKING:
    from pydownloader.ui.main_window import MainWindow

#: Balloon of the first minimize: how long it stays on the screen, in ms.
HINT_MS = 4000
#: Side of the tray icon, the size the notification area draws.
TRAY_SIZE = 32
#: Blue of the program icon: the tray is idle when nothing is downloaded.
IDLE_COLOR = QColor(84, 120, 209)
#: Green arrow: the tray shows that a download is running in the background.
ACTIVE_COLOR = QColor(46, 164, 79)
#: Period of the jumping arrow while a download runs, in ms.
BOUNCE_MS = 500
#: Reasons of ``QSystemTrayIcon.activated`` that open the window back.
OPEN_TRIGGER = QSystemTrayIcon.ActivationReason.Trigger
OPEN_DOUBLE = QSystemTrayIcon.ActivationReason.DoubleClick
OPEN_REASONS = (OPEN_TRIGGER, OPEN_DOUBLE)


def arrow_icon(color: QColor, down: bool, size: int = TRAY_SIZE) -> QIcon:
    """Round icon of ``color`` with a white arrow: the state of the downloads.

    The arrow points down while a download runs, up when the queue is empty, so
    the icon of the tray changes with the state of the program.
    """
    pm = QPixmap(size, size)
    pm.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawEllipse(1, 1, size - 2, size - 2)
    pen = QPen(QColor(255, 255, 255), max(2, size // 10))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    middle = size // 2
    far = size * 3 // 4 - 1
    near = size // 4
    half = size // 6
    head = size // 4
    if down:
        painter.drawLine(middle, near, middle, far)
        painter.drawLine(middle, far, middle - half, far - head)
        painter.drawLine(middle, far, middle + half, far - head)
    else:
        painter.drawLine(middle, far, middle, near)
        painter.drawLine(middle, near, middle - half, near + head)
        painter.drawLine(middle, near, middle + half, near + head)
    painter.end()
    return QIcon(pm)


def blue_icon() -> QIcon:
    """Idle tray icon: the blue arrow of the program, nothing is downloading."""
    return arrow_icon(IDLE_COLOR, down=True)


def green_icon() -> QIcon:
    """Green arrow of a running download, the first frame of the animation."""
    return arrow_icon(ACTIVE_COLOR, down=True)


def green_up_icon() -> QIcon:
    """Green arrow pointing up: the frame the animation alternates with."""
    return arrow_icon(ACTIVE_COLOR, down=False)


class Bounce(QObject):
    """Animation of the tray icon while a download runs: the arrow jumps (spec 4.2 p.7).

    Windows draws the icon in the notification area, so it cannot be moved
    there: the arrow flips between the down and the up drawing every
    ``BOUNCE_MS``, which reads as the icon jumping up and down.
    """

    def __init__(self, tray: QSystemTrayIcon) -> None:
        super().__init__(tray)
        self.tray = tray
        self.timer = QTimer(self)
        self.timer.setInterval(BOUNCE_MS)
        self.phase = 0
        self.timer.timeout.connect(self._frame)

    def start(self) -> None:
        self.timer.start()

    def stop(self) -> None:
        self.timer.stop()

    def _frame(self) -> None:
        self.phase += 1
        self.tray.setIcon(green_up_icon() if self.phase % 2 else green_icon())


class TrayController(QSystemTrayIcon):
    """Icon of the program in the tray, with the menu of the main window."""

    def __init__(self, window: MainWindow, icon: Path | None) -> None:
        """The tray icon is drawn for the state, ``icon`` is the file of the window.

        ``icon`` is the PNG of the program in the title bar and the taskbar; the
        tray has to show the state of the queue, so the arrow is painted here and
        the file is not used.
        """
        super().__init__(blue_icon(), window)
        self._window = window
        self.setToolTip(f"{APP_NAME} {VERSION}")
        menu = QMenu()
        self.show_action = menu.addAction(tr("tray_show"))
        self.open_action = menu.addAction(tr("tray_open_browser"))
        self.close_action = menu.addAction(tr("tray_close_browser"))
        self.console_action = menu.addAction(tr("window_open_console"))
        self.check_action = menu.addAction(tr("tray_check_updates"))
        self.folder_action = menu.addAction(tr("tray_open_folder"))
        self.quit_action = menu.addAction(tr("tray_quit"))
        self.show_action.triggered.connect(window.show_from_tray)
        self.open_action.triggered.connect(window.browser_open_request.emit)
        self.close_action.triggered.connect(window.browser_close_request.emit)
        self.console_action.triggered.connect(window.toggle_console)
        self.check_action.triggered.connect(window.check_updates_now)
        self.folder_action.triggered.connect(window.open_download_folder)
        self.quit_action.triggered.connect(window.quit_from_tray)
        self.setContextMenu(menu)
        self.activated.connect(self._open_window)
        #: The last balloon, so a test can read what the tray reported.
        self.last_note = ""
        #: The jumping arrow of a running download.
        self.bounce = Bounce(self)
        # The menu items of the browser follow the thread, so the first state is
        # taken from the window that owns it (spec 4.3).
        self.set_browser_running(window.browser_running())
        self._active = False

    def set_download_active(self, active: bool) -> None:
        """The icon is a green arrow with a jumping animation while a download runs.

        The tray is the place the user sees when the window is minimized, so
        the colour is the state of the queue: green while the worker has tasks
        (spec 4.2 p.7), blue when every download is done.
        """
        if active == self._active:
            return
        self._active = active
        if active:
            self.setIcon(green_icon())
            self.bounce.start()
        else:
            self.bounce.stop()
            self.setIcon(blue_icon())

    def download_state(self) -> bool:
        """Whether the tray shows the green arrow."""
        return self._active

    def notify(self, text: str) -> None:
        """A balloon next to the tray icon: the hint of the first minimize."""
        self.last_note = text
        self.showMessage(APP_NAME, text, QSystemTrayIcon.MessageIcon.Information, HINT_MS)

    def set_browser_running(self, running: bool) -> None:
        """The browser items follow the state of the browser window (spec 4.3)."""
        self.open_action.setEnabled(not running)
        self.close_action.setEnabled(running)

    def _open_window(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in OPEN_REASONS:
            self._window.show_from_tray()


def make_tray(window: MainWindow, icon: Path | None) -> TrayController | None:
    """The tray icon of the window, ``None`` when the platform has no tray.

    ``supportsMessages`` is the Qt flag of the notification area: on a platform
    without it (a window manager with no tray, the offscreen test platform) the
    icon is never shown, so the window must not rely on the tray.
    """
    tray = TrayController(window, icon)
    if not tray.supportsMessages():
        return None
    window.tray = tray
    tray.show()
    return tray


__all__ = [
    "ACTIVE_COLOR",
    "BOUNCE_MS",
    "HINT_MS",
    "IDLE_COLOR",
    "OPEN_DOUBLE",
    "OPEN_REASONS",
    "OPEN_TRIGGER",
    "TRAY_SIZE",
    "Bounce",
    "TrayController",
    "arrow_icon",
    "blue_icon",
    "green_icon",
    "green_up_icon",
    "make_tray",
]
