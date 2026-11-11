"""Tray icon: the program lives in the Windows notification area (spec 4.3).

«X» in the title bar hides the window to the tray, the downloads keep running,
and the tray menu keeps the program reachable: show the window, open and close
the browser, show the console, check for an update, open the download folder,
exit. «Exit» is the only way to quit when the window is hidden (spec 4.3 p.4),
so it runs the same teardown as a close that is not a hide.

The icon is the icon of the program (spec 7.3): the dark square with the arrow
pointing down. Only the colour of the arrow marks the state, white when the
queue is empty, green while a download runs (spec 4.2 p.7). Windows draws the
icon in its own grid, so the arrow cannot be moved there: the animation of a
running download is the arrow drawn in the shifted frames of a timer, which
reads as the arrow jumping up and down.

The tooltip of the icon is the list of the files that are downloading, with the
percent, the speed and the time left (spec 4.2 p.7): the window writes it on the
progress of the queue, so a person who works with the window hidden sees the
queue without opening the program. The balloon of the finished downloads uses the
same ``showMessage`` as the hint of the tray.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from pydownloader._version import VERSION
from pydownloader.config.constants import APP_NAME
from pydownloader.config.settings import ThemeName
from pydownloader.i18n import tr
from pydownloader.ui.app_icon import GREEN, WHITE, tray_icon
from pydownloader.ui.button_icons import (
    browser_icon,
    console_icon,
    exit_icon,
    folder_icon,
    icon_color,
    retry_icon,
    window_icon,
)

if TYPE_CHECKING:
    from pydownloader.ui.main_window import MainWindow

#: Balloon of the first minimize: how long it stays on the screen, in ms.
HINT_MS = 4000
#: The arrow of the icon when nothing is downloaded: the icon of the program.
IDLE_COLOR = WHITE
#: The green arrow of a running download (spec 4.2 p.7).
ACTIVE_COLOR = GREEN
#: Period of the jumping arrow while a download runs, in ms.
BOUNCE_MS = 500
#: The shifts of the arrow for the frames of the jump: base, up, base, down.
BOUNCE_SHIFTS = (0, -2, 0, 2)
#: Reasons of ``QSystemTrayIcon.activated`` that open the window back.
OPEN_TRIGGER = QSystemTrayIcon.ActivationReason.Trigger
OPEN_DOUBLE = QSystemTrayIcon.ActivationReason.DoubleClick
OPEN_REASONS = (OPEN_TRIGGER, OPEN_DOUBLE)
#: The tooltip the tray shows when no download runs.
BASE_TOOLTIP = f"{APP_NAME} {VERSION}"


def idle_icon() -> QIcon:
    """The tray icon of the program: the same icon as the desktop, white arrow."""
    return tray_icon(WHITE)


def frame_icon(shift: int) -> QIcon:
    """The icon of a running download: the green arrow drawn in the shifted frame."""
    return tray_icon(GREEN, shift)


class Bounce(QObject):
    """Animation of the tray icon while a download runs: the arrow jumps (spec 4.2 p.7).

    Windows draws the icon in the grid of the notification area, so it cannot be
    moved there: the green arrow is drawn with the shift of the next frame every
    ``BOUNCE_MS``, which reads as the arrow jumping up and down over the line of
    the tray.
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
        self.tray.setIcon(frame_icon(BOUNCE_SHIFTS[self.phase % len(BOUNCE_SHIFTS)]))


class TrayController(QSystemTrayIcon):
    """Icon of the program in the tray, with the menu of the main window."""

    def __init__(self, window: MainWindow, icon: Path | None) -> None:
        """The tray is the icon of the program, ``icon`` is the file of the window.

        ``icon`` is the PNG of the program in the title bar and the taskbar; the
        tray paints the same picture with the colour of the arrow, so the file is
        not used (spec 7.3, 4.2 p.7).
        """
        super().__init__(idle_icon(), window)
        self._window = window
        self.setToolTip(BASE_TOOLTIP)
        # The marks of the menu are painted in the text color of the theme: the menu
        # of the tray is drawn by Qt with the QSS of the panel (spec 4.3 p.4).
        color = icon_color("panel", window.settings.theme)
        #: The color of the marks of the menu, kept for the browser item of the state.
        self._color = color
        menu = QMenu()
        self.show_action = menu.addAction(window_icon(color), tr("tray_show"))
        # One item of the menu for the browser window: the text follows the state, as
        # the button of the window does (spec 4.3).
        self.browser_action = menu.addAction(browser_icon(color, True), tr("window_open_browser"))
        self.console_action = menu.addAction(console_icon(color), tr("window_open_console"))
        self.check_action = menu.addAction(retry_icon(color), tr("tray_check_updates"))
        self.folder_action = menu.addAction(folder_icon(color), tr("tray_open_folder"))
        self.quit_action = menu.addAction(exit_icon(color), tr("tray_quit"))
        self.show_action.triggered.connect(window.show_from_tray)
        self.browser_action.triggered.connect(window.browser_toggle_request.emit)
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
        """The icon is the green arrow with a jumping animation while a download runs.

        The tray is the place the user sees when the window is minimized, so
        the colour is the state of the queue: green while the worker has tasks
        (spec 4.2 p.7), the white arrow of the program when every download is done.
        """
        if active == self._active:
            return
        self._active = active
        if active:
            self.setIcon(frame_icon(BOUNCE_SHIFTS[0]))
            self.bounce.start()
        else:
            self.bounce.stop()
            self.setIcon(idle_icon())

    def download_state(self) -> bool:
        """Whether the tray shows the green arrow."""
        return self._active

    def set_progress_lines(self, lines: list[str]) -> None:
        """The tooltip of the icon: the files that are downloading (spec 4.2 p.7).

        The window writes the lines on the progress of the queue: the name of the
        file, the percent, the speed, the time left. The tooltip is the only
        report a person gets when the window is hidden and the mouse is over the
        icon, so the text is written with no balloon.
        """
        text = BASE_TOOLTIP
        if lines:
            text = "\n".join([BASE_TOOLTIP, tr("tray_tooltip_download"), *lines])
        self.setToolTip(text)

    def notify(self, text: str) -> None:
        """A balloon next to the tray icon: the hint of the first minimize."""
        self.last_note = text
        self.showMessage(APP_NAME, text, QSystemTrayIcon.MessageIcon.Information, HINT_MS)

    def set_browser_running(self, running: bool) -> None:
        """The one item of the menu follows the browser window: the text, the mark (spec 4.3).

        The tray menu has the same button as the window: the item says what it will
        do, so the state of the thread is written on the item and nothing is
        disabled, which a person reading the menu of the tray cannot see at once.
        """
        key = "window_close_browser" if running else "window_open_browser"
        self.browser_action.setText(tr(key))
        self.browser_action.setIcon(browser_icon(self._color, not running))

    def set_theme(self, theme: ThemeName) -> None:
        """The marks of the tray menu take the colors of the theme (spec 4.3 p.4).

        The menu is built once, with the theme the program started with, so a theme
        picked in the settings leaves the items of the menu the color of the old
        theme. The item of the browser keeps the state of its own thread: the mark of
        the cross is drawn with the new color on the item that closes the window.
        """
        self._color = icon_color("panel", theme)
        color = self._color
        self.show_action.setIcon(window_icon(color))
        self.browser_action.setIcon(browser_icon(color, not self._window.browser_running()))
        self.console_action.setIcon(console_icon(color))
        self.check_action.setIcon(retry_icon(color))
        self.folder_action.setIcon(folder_icon(color))
        self.quit_action.setIcon(exit_icon(color))

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
    # The tray is created after the window, sometimes while a task is running
    # (the tray row of the settings): the state and the tooltip are written at once.
    tray.set_download_active(bool(window._runs))
    window._push_tray_tooltip(True)
    return tray


__all__ = [
    "ACTIVE_COLOR",
    "BASE_TOOLTIP",
    "BOUNCE_MS",
    "BOUNCE_SHIFTS",
    "HINT_MS",
    "IDLE_COLOR",
    "OPEN_DOUBLE",
    "OPEN_REASONS",
    "OPEN_TRIGGER",
    "Bounce",
    "TrayController",
    "frame_icon",
    "idle_icon",
    "make_tray",
]
