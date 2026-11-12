"""One copy of the program on the machine.

A second start of the program opens nothing: it does not make a second queue, a
second browser, a second tray icon, a second log file, and a person who clicks
the icon twice gets no copy of the window. The second copy sends the word ``show``
to the running one; the running one brings its window to the front (the same as
the double click on the tray icon, spec 4.2 p.7), writes one line in the console,
and the second copy quits without a window of its own.

The running copy announces itself by a local server, and the name of the server
carries the user: a pipe of Windows is seen by the whole machine, so two sessions
of one machine see each other's copies. The name keeps them apart, and every
session gets its own single instance.

The new copy of a restart (the language change, spec 8.1) is not a second start:
the flag ``--restart`` tells it that the old copy is closing, so it takes the
name of the server when the old copy lets it go.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from pydownloader.config.constants import APP_NAME
from pydownloader.i18n import tr

if TYPE_CHECKING:
    from pydownloader.ui.main_window import MainWindow

#: The flag of a restart: the new copy is the running copy starting again, not a
#: second start (spec 8.1).
RESTART_FLAG = "--restart"

#: The word the second copy sends to the running one: show the window.
SHOW = b"show"

#: The answer of the running copy: the word is read and the window is shown.
ANSWER = b"ok"

#: How long the second copy keeps the pipe open and pumps its loop for the
#: answer of the running copy, in ms. The running copy answers within the same
#: time as a click on the window, and a copy that leaves earlier loses the word.
KEEP_MS = 1200

#: How often the copy of a restart asks for the name again, in ms.
RETRY_MS = 400

#: Times the name is asked for again: the old copy of a restart closes the
#: window, the browser and the queue, which takes the time of a normal quit.
RETRIES = 25


def server_name() -> str:
    """Name of the running copy: the program and the user who runs it.

    Windows keeps a pipe in the namespace of the whole machine, so the copies of
    two sessions of one machine meet each other: the name of the user keeps them
    apart, and every session runs its own single instance.
    """
    who = os.environ.get("USERNAME") or os.environ.get("USER") or "user"
    return f"{APP_NAME}-{who.lower()}"


def is_restart(args: list[str]) -> bool:
    """Whether the command line says that this copy is the running copy starting again."""
    return RESTART_FLAG in args


def notify_running(app: QCoreApplication, name: str | None = None) -> bool:
    """Ask the running copy to show its window; ``True`` when it answered.

    The second copy opens no window and writes no log: one word travels, the
    running copy answers, and the program quits.

    The loop of the second copy pumps for the answer: the running copy comes to
    the connection when its own event loop reaches it, so the pipe is kept open
    for ``KEEP_MS`` — a copy that closes the pipe right after the word loses the
    word, and the window never comes to the front. ``False`` means that no copy
    runs, so the program starts as usual.
    """
    answered: list[bool] = []
    socket = QLocalSocket()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(app.quit)

    def send() -> None:
        socket.write(SHOW)
        socket.flush()

    def read() -> None:
        if ANSWER in bytes(socket.readAll()):
            answered.append(True)
            app.quit()

    socket.connected.connect(send)
    socket.readyRead.connect(read)
    # A name with no copy behind it gives the error right away: the loop quits
    # then, so a normal start is not held for the whole time of the answer.
    socket.errorOccurred.connect(lambda _code: app.quit())
    socket.connectToServer(server_name() if name is None else name)
    timer.start(KEEP_MS)
    app.exec()
    socket.disconnectFromServer()
    return bool(answered)


class InstanceServer(QLocalServer):
    """The running copy listens for the second one and shows the window.

    A copy killed by the system leaves the name behind, and the new copy of a
    restart meets the name of the copy that is closing: the name is asked for
    again, so the listener starts as soon as the name is free, and a person who
    starts the program gets a window in both cases.
    """

    def __init__(self, window: MainWindow, name: str) -> None:
        super().__init__()
        self.window = window
        self._name = name
        #: Times the name is asked for again while it is taken.
        self._left = RETRIES
        #: The second copies that are connected: the socket is kept while it answers.
        self._clients: list[QLocalSocket] = []
        self.newConnection.connect(self._accept)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._take_name)
        self._take_name()

    def _take_name(self) -> None:
        """Listen on the name, and ask for the name again when another copy has it."""
        if self.listen(self._name):
            self._timer.stop()
            return
        if self._left <= 0:
            self._timer.stop()
            return
        self._left -= 1
        QLocalServer.removeServer(self._name)
        self._timer.start(RETRY_MS)

    def _accept(self) -> None:
        """The second copy has connected: read its word when it sends it."""
        client = self.nextPendingConnection()
        if client is None:
            return
        self._clients.append(client)
        client.readyRead.connect(lambda: self._read(client))
        client.disconnected.connect(lambda: self._drop(client))
        if client.bytesAvailable():
            # The word comes right after the connection, so it can be in the
            # buffer before the signal is connected: read what is there.
            self._read(client)

    def _read(self, client: QLocalSocket) -> None:
        """The word of the second copy: the window comes to the front."""
        if SHOW in bytes(client.readAll()):
            self.window.show_from_tray()
            self.window.log_info(tr("app_second_copy"))
            # The answer tells the second copy that the word has arrived, so the
            # word is not lost when that copy closes the pipe on its way out.
            client.write(ANSWER)
            client.flush()

    def _drop(self, client: QLocalSocket) -> None:
        """The second copy has closed: the socket is not kept any more."""
        if client in self._clients:
            self._clients.remove(client)


def start_instance(window: MainWindow, name: str | None = None) -> InstanceServer:
    """The running copy announces itself so that the second copy finds it."""
    return InstanceServer(window, server_name() if name is None else name)


__all__ = [
    # ``--restart``: the copy of a restart is not a second start (spec 8.1).
    "RESTART_FLAG",
    # The running copy listens for the second one and shows the window.
    "InstanceServer",
    # Whether the command line is a restart.
    "is_restart",
    # Ask the running copy to show its window; ``False`` when no copy runs.
    "notify_running",
    # The name of the running copy: the program and the user who runs it.
    "server_name",
    # The running copy announces itself so the second one finds it.
    "start_instance",
]
