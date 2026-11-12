"""One copy of the program on the machine.

The second start opens nothing: it asks the running copy to show its window and
quits. The running copy keeps the name of the server, the copy of a restart waits
for the name, and a copy killed by the system leaves the name behind.
"""

from __future__ import annotations

from PySide6.QtNetwork import QLocalServer

from pydownloader.i18n import tr
from pydownloader.ui import single_instance as si
from pydownloader.ui.app import is_second_start, restart_command


class FakeWindow:
    """Stand-in of the window: it remembers the asks of a second copy.

    The window of the program shows itself and writes one line in the console,
    so the stand-in keeps the count of the shows and the lines of the console.
    """

    def __init__(self) -> None:
        self.shown = 0
        self.messages: list[str] = []

    def show_from_tray(self) -> None:
        self.shown += 1

    def log_info(self, message: str) -> None:
        self.messages.append(message)


def server(tag: str) -> str:
    """Name of the server for one test, so the tests of the file do not meet."""
    return f"PyDownloader-test-{tag}"


def test_the_second_copy_shows_the_window_of_the_running_one(app, qtbot):
    """The word ``show`` travels to the running copy, its window comes to the front."""
    window = FakeWindow()
    listener = si.start_instance(window, server("shown"))
    assert listener.isListening()

    assert si.notify_running(app, server("shown")) is True
    # The word arrives in the loop of the running copy, so the show is checked
    # after its loop has pumped the connection.
    qtbot.waitUntil(lambda: window.shown == 1)
    # The running copy says in the console that a second copy asked for the window.
    assert window.messages == [tr("app_second_copy")]
    listener.close()


def test_no_running_copy_leaves_a_normal_start(app, qtbot):
    """Nothing answers on the name, so the program starts as usual."""
    assert si.notify_running(app, server("none")) is False


def test_the_name_carries_the_user_of_the_session(monkeypatch):
    """A pipe of Windows is seen by the whole machine, so the user is in the name.

    Two sessions of one machine get their own single instance, and the copy of
    one session does not show the window of the other.
    """
    monkeypatch.setenv("USERNAME", "Lena")
    monkeypatch.setenv("USER", "lena")
    assert si.server_name() == "PyDownloader-lena"


def test_a_copy_that_dies_leaves_the_name(qtbot, monkeypatch):
    """A copy killed by the system leaves the name, and the next copy takes it.

    The name is asked for again, so the person gets a window and not a program
    that hides itself because a dead copy had the name.
    """
    real = QLocalServer.listen
    taken = [True]  # the name of the copy that was killed is left behind

    def listen(self, target: str) -> bool:
        if taken:
            taken.pop(0)
            return False
        return real(self, target)

    monkeypatch.setattr(QLocalServer, "listen", listen)
    listener = si.start_instance(FakeWindow(), server("stale"))
    assert not listener.isListening()  # the dead copy had the name
    qtbot.waitUntil(lambda: listener.isListening(), timeout=6000)
    listener.close()


def test_the_copy_of_a_restart_waits_for_the_name(qtbot, monkeypatch):
    """The copy of a restart meets the copy that is closing and waits for its name.

    The old copy holds the name while it closes the window, the browser and the
    queue, so the new copy asks for the name again until it is free, and then
    opens its own window (spec 8.1).
    """
    real = QLocalServer.listen
    taken = [True] * 3  # the copy that is closing holds the name for three asks

    def listen(self, target: str) -> bool:
        if taken:
            taken.pop(0)
            return False
        return real(self, target)

    monkeypatch.setattr(QLocalServer, "listen", listen)
    listener = si.start_instance(FakeWindow(), server("restart"))
    assert not listener.isListening()  # the name is taken by the copy that quits
    qtbot.waitUntil(lambda: listener.isListening(), timeout=6000)
    listener.close()


def test_a_second_copy_stops_the_program_before_the_window(app, monkeypatch):
    """The check of the second copy is done before the window and the settings dialog."""
    monkeypatch.setattr("pydownloader.ui.app.notify_running", lambda a, name=None: True)
    assert is_second_start(app, []) is True
    # The copy of a language change is the program the person asked for.
    assert is_second_start(app, [si.RESTART_FLAG]) is False


def test_the_restart_of_the_language_change_gets_the_flag():
    """The new copy of a restart is not a second start, so the command carries the flag."""
    exe, args = restart_command()
    assert exe
    assert args in ([si.RESTART_FLAG], ["-m", "pydownloader", si.RESTART_FLAG])
