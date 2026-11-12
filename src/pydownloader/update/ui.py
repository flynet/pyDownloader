"""Update check in the window: dialog, download, install (spec 8.3).

The check runs in a thread so the window stays responsive. The dialog shows the
version and the release notes with the buttons «Обновить», «Позже», «Пропустить
эту версию». The installer is downloaded in the thread with a progress dialog of
real megabytes, verified by SHA-256 in the same thread, started with
``/SILENT /CLOSEAPPLICATIONS /NORESTART``, and the program exits; the installer
starts the new version at its end.

Every failure of the download, of the digest, and of the launch of the
installer goes to the console: the program must say why an update did not
arrive, and not close with a bar that moves forever.

The texts are keys of the catalog. The language is chosen at startup, so the
helpers read the text at the place of use, not at import time.
"""

from __future__ import annotations

import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal, SignalInstance
from PySide6.QtWidgets import QMessageBox, QProgressDialog

from pydownloader.config.settings import Settings
from pydownloader.i18n import tr
from pydownloader.update import checker
from pydownloader.update.checker import Release, UpdateError
from pydownloader.util.format import format_duration


def update_title() -> str:
    """Title of the dialog and of the waiting question (spec 8.3 p.2)."""
    return tr("update_title")


def download_text() -> str:
    """Text of the progress dialog while the installer is fetched."""
    return tr("update_download_text")


def install_text() -> str:
    """Console line printed when the installer is started."""
    return tr("update_install_text")


def wait_text() -> str:
    """Question asked before the download when a video is running."""
    return tr("update_wait_text")


def sha_fail() -> str:
    """Console line of a digest that does not match the installer."""
    return tr("update_sha_fail")


def later_label() -> str:
    """Button that closes the dialog without any action."""
    return tr("update_later")


def skip_label() -> str:
    """Button that hides this version from the next checks."""
    return tr("update_skip")


def update_label() -> str:
    """Button that starts the download of the installer."""
    return tr("update_button")


def cancel_label() -> str:
    """Button that cancels the download in the progress dialog."""
    return tr("update_cancel")


def megabytes(size: int) -> int:
    """Bytes in whole megabytes, the number a person reads in the progress bar."""
    return max(1, round(size / (1024 * 1024)))


def speed_text(bytes_per_second: float) -> str:
    """Speed of the download as a person reads it: megabytes per second."""
    return tr("card_speed_mb", speed=round(bytes_per_second / (1024 * 1024), 1))


class SpeedMeter:
    """Bytes per second of the last seconds of the download.

    A slow GitHub link gives the file in bursts: the average over the whole
    download shows the speed of the start and the number does not move, so the
    person cannot tell whether the file is coming at all. Only the samples of
    the last ``WINDOW`` seconds are kept, and the estimate of the time left
    follows that speed (spec 8.3 p.3.1).
    """

    #: Seconds of the window: long enough to be steady, short enough to follow
    #: the bursts of a slow link.
    WINDOW = 8.0

    def __init__(self) -> None:
        self._samples: list[tuple[float, int]] = []

    def add(self, written: int) -> None:
        """One chunk has landed: the sample is the time and the bytes on the disk."""
        now = time.monotonic()
        self._samples.append((now, written))
        while len(self._samples) > 2 and self._samples[0][0] < now - self.WINDOW:
            self._samples.pop(0)

    def speed(self) -> float:
        """Bytes per second of the window, ``0`` before two samples exist."""
        if len(self._samples) < 2:
            return 0.0
        (first_time, first_bytes), (last_time, last_bytes) = self._samples[0], self._samples[-1]
        return (last_bytes - first_bytes) / max(last_time - first_time, 1e-6)

    def left(self, written: int, total: int) -> int:
        """Seconds the download needs at the speed of the window, ``0`` when unknown."""
        speed = self.speed()
        if speed <= 0 or total <= written:
            return 0
        return int((total - written) / speed)


def progress_text(written: int, total: int, speed: float = 0.0, left: int = 0) -> str:
    """Label of the progress dialog: megabytes, percent, speed, time left.

    The size of the installer is known from the release, so the bar counts real
    megabytes and the percent is the part of the file that is on the disk. The
    speed and the time left come from :class:`SpeedMeter` and appear when the
    download has run long enough to measure them. A release that names no size
    keeps no percent, but the speed of the line is shown: on a slow GitHub the
    person sees the bytes arriving and knows the link is alive (spec 8.3 p.3.1).
    """
    if total <= 0:
        if speed > 0:
            return download_text() + "\n" + tr("update_speed_only", speed=speed_text(speed))
        return download_text()
    percent = round(100 * written / total)
    line = tr(
        "update_download_of", written=megabytes(written), total=megabytes(total), percent=percent
    )
    if speed > 0:
        line += "\n" + tr("update_speed_left", speed=speed_text(speed), left=format_duration(left))
    return line


def _clock() -> str:
    """Time of the answer of the check, the moment shown in the status bar."""
    return time.strftime("%H:%M")


def notices_label() -> str:
    """Button that opens the release notes."""
    return tr("update_notices")


def release_notes(body: str) -> str:
    """Release notes of the dialog: markdown markers are dropped.

    The body of a release carries the screenshots of the program as markdown
    links (``![…](https://…)``): the text of the dialog is one line, so an
    address of a picture is read as noise, and the lines of changes come below
    it. The image lines are dropped here (spec 8.3 p.2).
    """
    lines = [line.strip().lstrip("#").strip() for line in body.splitlines()]
    return "\n".join(line for line in lines if line and not line.startswith("!["))[:600]


class Worker(QObject):
    """One background job; ``run`` calls the callable and reports the result."""

    result = Signal(object, str)
    failed = Signal(str)
    #: The job reports its progress through this signal: the callback of the job
    #: runs in the worker thread, so the window is told through a signal and not
    #: by touching a widget of the GUI thread from the thread (spec 8.3 p.3.1).
    progress = Signal(int, int)

    def __init__(self, job: Callable[[Callable[[int, int], None]], object]) -> None:
        super().__init__()
        self.job = job

    def run(self) -> None:
        # Only ``UpdateError`` was caught here before: a network timeout of httpx
        # left the thread running, no signal was sent, the bar of the progress
        # moved forever, and the program closed with no word in the console.
        try:
            self.result.emit(self.job(self.progress.emit), "")
        except UpdateError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class UpdateMonitor(QObject):
    """Checks GitHub Releases and drives the update dialogs."""

    checked = Signal(object, str)  # Release | None, error message
    downloaded = Signal(object, str)  # installer path, error message
    #: Bytes of the installer that have landed, and the size the release promises.
    #: A signal, not a call: the download runs in the worker thread, and a widget
    #: of the window written from that thread is a cross-thread call that ends by
    #: closing the process (spec 8.3 p.3.1).
    progressed = Signal(int, int)

    def __init__(
        self,
        window,
        settings: Settings,
        fetch: Callable[[], Release | None] = checker.fetch_release,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.window = window
        self.settings = settings
        self.fetch = fetch
        self._threads: list[tuple[QThread, Worker]] = []
        self._progress: QProgressDialog | None = None
        self._release: Release | None = None
        #: A check the person asked for tells the window the result even when
        #: there is nothing to install; an automatic check stays silent.
        self._manual = False
        #: «Отмена» of the progress dialog: the download stops on the next chunk.
        self._cancelled = False
        #: Bytes per second of the last seconds, measured on the samples of the
        #: download; the label of the bar reads it (spec 8.3 p.3.1).
        self._meter = SpeedMeter()
        self.checked.connect(self._on_checked)
        self.downloaded.connect(self._on_downloaded)
        self.progressed.connect(self._on_progress)

    # --- check ---------------------------------------------------------

    def check_on_startup(self) -> None:
        """Automatic check: off, cache fresh, version skipped → nothing to do."""
        last = checker.parse_last_check(self.settings)
        if not checker.should_check(self.settings, time.time(), last):
            return
        self.check_now()

    def check_now(self) -> None:
        """Manual check («Проверить обновления» in the settings dialog)."""
        self._manual = True
        self._start(lambda report: self.fetch(), self.checked)

    def _start(
        self, job: Callable[[Callable[[int, int], None]], object], signal: SignalInstance
    ) -> None:
        """Run ``job`` in a thread; the result arrives on ``signal`` in the GUI thread."""
        thread = QThread()
        worker = Worker(job)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.result.connect(signal)
        worker.failed.connect(lambda message: signal.emit(None, message))
        # The progress of the job travels as a signal, so the bar is written by
        # the window and the worker thread never touches a widget of the GUI.
        worker.progress.connect(self.progressed)
        worker.result.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda pair=(thread, worker): self._drop(pair))
        self._threads.append((thread, worker))
        thread.start()

    def _drop(self, pair: tuple[QThread, Worker]) -> None:
        """Forget a finished job: the list keeps only the threads that run."""
        if pair in self._threads:
            self._threads.remove(pair)

    def _on_checked(self, release: Release | None, error: str) -> None:
        manual = self._manual
        self._manual = False
        self.settings.last_update_check = checker.stamp()
        self.window.persist_settings()
        if error:
            self.window.log_warning(error)
            return
        if release is None:
            return
        if not checker.is_newer(self.window.current_version(), release.version):
            # The person pressed «Проверить обновления», so the answer is shown:
            # a silent check leaves no clue whether the API answered at all.
            if manual:
                self.window.set_update_status(tr("update_none", time=_clock()))
            return
        if self.settings.skipped_version == release.version:
            return
        self.window.set_update_status(tr("update_available", version=release.version))
        self._show_dialog(release)

    def _show_dialog(self, release: Release) -> QMessageBox:
        """The dialog of spec 8.3 p.2: version, notes, three buttons."""
        dialog = QMessageBox(self.window)
        dialog.setWindowTitle(update_title())
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setStandardButtons(QMessageBox.StandardButton.NoButton)
        dialog.setText(release.version)
        dialog.setInformativeText(release_notes(release.body))
        dialog.addButton(later_label(), QMessageBox.ButtonRole.NoRole)
        accept = dialog.addButton(update_label(), QMessageBox.ButtonRole.AcceptRole)
        skip = dialog.addButton(skip_label(), QMessageBox.ButtonRole.ActionRole)
        skip.clicked.connect(lambda: self._skip_version(release, dialog))
        dialog.addButton(notices_label(), QMessageBox.ButtonRole.HelpRole)
        dialog.setDefaultButton(accept)
        self._dialog = dialog
        dialog.exec()
        if dialog.clickedButton() is accept:
            self._accept_update(release)
        return dialog

    def _skip_version(self, release: Release, dialog: QMessageBox) -> None:
        """«Пропустить эту версию»: remember it in the settings and close the dialog."""
        self.settings.skipped_version = release.version
        dialog.done(0)

    def _accept_update(self, release: Release) -> None:
        """Before the download, ask to wait for the running download (spec 8.3 p.3)."""
        worker = self.window.worker
        if worker is not None and worker.pending():
            answer = QMessageBox.question(
                self.window,
                update_title(),
                wait_text(),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._download(release)

    # --- download and install ---------------------------------------

    def _download(self, release: Release) -> None:
        """Progress dialog, streamed download, then SHA-256 verification.

        The bar counts the bytes of the file the release names, and it is driven
        by the ``progressed`` signal. The worker thread calls the callback, so the
        callback sends a signal; the old code wrote the bar from the thread of the
        download itself, a widget of the GUI touched from another thread, and Qt
        ends such a call by closing the process without a word in the log
        (spec 8.3 p.3.1).
        """
        self._release = release
        self._cancelled = False
        self._meter = SpeedMeter()
        target = Path(tempfile.mkdtemp(prefix="pydownloader-")) / release.installer.name
        total = int(release.installer.size or 0)
        progress = QProgressDialog(download_text(), cancel_label(), 0, total, self.window)
        progress.setWindowTitle("PyDownloader")
        progress.setWindowModality(Qt.WindowModality.NonModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        # «Отмена» closes the dialog by itself; the flag stops the download on the
        # next chunk, so the file is not written after the person has asked to stop.
        progress.canceled.connect(self._cancel_download)
        self._progress = progress
        self._start(self._job(release, target), self.downloaded)

    def _job(self, release: Release, target: Path) -> Callable[[Callable[[int, int], None]], Path]:
        """One update job: fetch the installer, check its size and its digest.

        The digest file is read in the same thread: the GUI thread blocked on it
        in the old code, so the window did not answer while the installer was
        verified (spec 8.3 p.3.2).
        """

        def job(report: Callable[[int, int], None]) -> Path:
            def landed(written: int, total: int) -> None:
                if self._cancelled:
                    raise UpdateError(tr("up_installer_cancelled"))
                report(written, total)

            checker.download_installer(release.installer.url, target, landed)
            promised = int(release.installer.size or 0)
            got = target.stat().st_size if target.exists() else 0
            if promised and got != promised:
                # A file of a slow GitHub that stopped half way installs a program
                # that cannot start; the digest is the check, and a release
                # without a digest file gets this one.
                raise UpdateError(
                    tr("up_installer_incomplete", got=megabytes(got), size=megabytes(promised))
                )
            digest = _expected_sha(release, target)
            if digest and not checker.verify(target, digest):
                raise UpdateError(sha_fail())
            return target

        return job

    def _cancel_download(self) -> None:
        """«Отмена» in the progress dialog: the download stops on the next chunk."""
        self._cancelled = True

    def _on_progress(self, written: int, total: int) -> None:
        """The worker has landed bytes: the bar of the window is written here.

        The slot runs in the GUI thread, the only thread that may touch a widget.
        The sample of the speed is taken here too: the signal arrives right after
        the chunk is written, so the time of the arrival is the time of the byte
        on the disk, and the meter stays in the thread of the window (spec 8.3 p.3.1).
        """
        if self._progress is None:
            return
        self._meter.add(written)
        speed = self._meter.speed()
        left = self._meter.left(written, total)
        if total > 0 and self._progress.maximum() != total:
            self._progress.setMaximum(total)
        self._progress.setLabelText(progress_text(written, total, speed, left))
        self._progress.setValue(written)

    def _on_downloaded(self, path: object, error: str) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None
        if error:
            self.window.log_error(error)
            return
        installer = Path(str(path))
        try:
            # Starting the installer can fail: Windows refuses a program that
            # came from the network, and a file of a temp folder can be denied.
            # The old code let that exception fall in the GUI thread: the program
            # closed, the installer never ran, the console said nothing.
            checker.run_installer(installer)
        except OSError as exc:
            self.window.log_error(tr("up_installer_start_failed", error=exc))
            return
        self.window.log_info(install_text())
        self.window.exit_after_update()


def _expected_sha(release: Release | None, installer: Path) -> str:
    """Digest published next to the installer; empty when the release has no asset."""
    if release is None or release.sha256_asset is None:
        return ""
    return checker.fetch_expected_sha(release.sha256_asset.url)


__all__ = [
    "SpeedMeter",
    "UpdateMonitor",
    "Worker",
    "cancel_label",
    "download_text",
    "install_text",
    "later_label",
    "megabytes",
    "notices_label",
    "progress_text",
    "release_notes",
    "sha_fail",
    "skip_label",
    "speed_text",
    "update_label",
    "update_title",
    "wait_text",
]
