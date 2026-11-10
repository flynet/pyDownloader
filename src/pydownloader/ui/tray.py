"""Tray icon: the program lives in the Windows notification area (spec 4.2).

Closing the window hides the program, the tray menu keeps it reachable: show the
window, open and close the browser, check for an update, open the download
folder, exit. The exit is the only way to quit when the window is hidden
(spec 4.3), so it runs the same teardown as closing the window with a request.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from pydownloader._version import VERSION
from pydownloader.config.constants import APP_NAME
from pydownloader.i18n import tr

if TYPE_CHECKING:
    from pydownloader.ui.main_window import MainWindow

#: Balloon of the first minimize: how long it stays on the screen, in ms.
HINT_MS = 4000
#: Reasons of ``QSystemTrayIcon.activated`` that open the window back.
OPEN_TRIGGER = QSystemTrayIcon.ActivationReason.Trigger
OPEN_DOUBLE = QSystemTrayIcon.ActivationReason.DoubleClick
OPEN_REASONS = (OPEN_TRIGGER, OPEN_DOUBLE)


class TrayController(QSystemTrayIcon):
    """Icon of the program in the tray, with the menu of the main window."""

    def __init__(self, window: MainWindow, icon: Path | None) -> None:
        super().__init__(QIcon(str(icon)) if icon is not None else QIcon(), window)
        self._window = window
        self.setToolTip(f"{APP_NAME} {VERSION}")
        menu = QMenu()
        self.show_action = menu.addAction(tr("tray_show"))
        self.open_action = menu.addAction(tr("tray_open_browser"))
        self.close_action = menu.addAction(tr("tray_close_browser"))
        self.check_action = menu.addAction(tr("tray_check_updates"))
        self.folder_action = menu.addAction(tr("tray_open_folder"))
        self.quit_action = menu.addAction(tr("tray_quit"))
        self.show_action.triggered.connect(window.show_from_tray)
        self.open_action.triggered.connect(window.browser_open_request.emit)
        self.close_action.triggered.connect(window.browser_close_request.emit)
        self.check_action.triggered.connect(window.check_updates_now)
        self.folder_action.triggered.connect(window.open_download_folder)
        self.quit_action.triggered.connect(window.quit_from_tray)
        self.setContextMenu(menu)
        self.activated.connect(self._open_window)
        # The menu items of the browser follow the thread, so the first state is
        # taken from the window that owns it (spec 4.3).
        self.set_browser_running(window.browser_running())

    def set_browser_running(self, running: bool) -> None:
        """The browser items follow the state of the browser window (spec 4.3)."""
        self.open_action.setEnabled(not running)
        self.close_action.setEnabled(running)

    def notify(self, text: str) -> None:
        """A balloon next to the tray icon: the hint of the first minimize."""
        self.showMessage(APP_NAME, text, QSystemTrayIcon.MessageIcon.Information, HINT_MS)

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


__all__ = ["HINT_MS", "OPEN_DOUBLE", "OPEN_REASONS", "OPEN_TRIGGER", "TrayController", "make_tray"]
