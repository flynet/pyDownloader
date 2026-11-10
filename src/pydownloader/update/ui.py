"""Update check in the window: dialog, download, install (spec 8.3).

The check runs in a thread so the window stays responsive. The dialog shows the
version and the release notes with the buttons «Обновить», «Позже», «Пропустить
эту версию». The installer is downloaded with a progress dialog, verified by
SHA-256, started with ``/SILENT /CLOSEAPPLICATIONS``, and the program exits.
"""

from __future__ import annotations

import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal, SignalInstance
from PySide6.QtWidgets import QMessageBox, QProgressDialog

from pydownloader.config.settings import Settings
from pydownloader.update import checker
from pydownloader.update.checker import Release, UpdateError

UPDATE_TITLE = "Доступна новая версия"
DOWNLOAD_TEXT = "Скачивание установщика…"
INSTALL_TEXT = "Запускается установщик, программа закроется."
WAIT_TEXT = "Идёт загрузка видео. Дождаться её окончания перед обновлением?"
SHA_FAIL = "SHA-256 не совпадает, обновление не установлено"
LATER_BUTTON = "Позже"
SKIP_BUTTON = "Пропустить эту версию"
UPDATE_BUTTON = "Обновить"
CANCEL_BUTTON = "Отмена"
NOTICES = "Уведомления"


def release_notes(body: str) -> str:
    """Release notes of the dialog: markdown markers are dropped."""
    lines = [line.strip().lstrip("#").strip() for line in body.splitlines()]
    return "\n".join(line for line in lines if line)[:600]


class Worker(QObject):
    """One background job; ``run`` calls the callable and reports the result."""

    result = Signal(object, str)
    failed = Signal(str)

    def __init__(self, job: Callable[[], object]) -> None:
        super().__init__()
        self.job = job

    def run(self) -> None:
        try:
            self.result.emit(self.job(), "")
        except UpdateError as exc:
            self.failed.emit(str(exc))


class UpdateMonitor(QObject):
    """Checks GitHub Releases and drives the update dialogs."""

    checked = Signal(object, str)  # Release | None, error message
    downloaded = Signal(object, str)  # installer path, error message

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
        self.checked.connect(self._on_checked)
        self.downloaded.connect(self._on_downloaded)

    # --- check ---------------------------------------------------------

    def check_on_startup(self) -> None:
        """Automatic check: off, cache fresh, version skipped → nothing to do."""
        last = checker.parse_last_check(self.settings)
        if not checker.should_check(self.settings, time.time(), last):
            return
        self.check_now()

    def check_now(self) -> None:
        """Manual check («Проверить обновления» in the settings dialog)."""
        self._start(self.fetch, self.checked)

    def _start(self, job: Callable[[], object], signal: SignalInstance) -> None:
        """Run ``job`` in a thread; the result arrives on ``signal`` in the GUI thread."""
        thread = QThread()
        worker = Worker(job)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.result.connect(signal)
        worker.failed.connect(lambda message: signal.emit(None, message))
        worker.result.connect(thread.quit)
        worker.failed.connect(thread.quit)
        self._threads.append((thread, worker))
        thread.start()

    def _on_checked(self, release: Release | None, error: str) -> None:
        self.settings.last_update_check = checker.stamp()
        self.window.persist_settings()
        if error:
            self.window.log_warning(error)
            return
        if release is None:
            return
        if not checker.is_newer(self.window.current_version(), release.version):
            return
        if self.settings.skipped_version == release.version:
            return
        self.window.set_update_status(f"Доступна версия {release.version}")
        self._show_dialog(release)

    def _show_dialog(self, release: Release) -> QMessageBox:
        """The dialog of spec 8.3 p.2: version, notes, three buttons."""
        dialog = QMessageBox(self.window)
        dialog.setWindowTitle(UPDATE_TITLE)
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setStandardButtons(QMessageBox.StandardButton.NoButton)
        dialog.setText(release.version)
        dialog.setInformativeText(release_notes(release.body))
        dialog.addButton(LATER_BUTTON, QMessageBox.ButtonRole.NoRole)
        update_button = dialog.addButton(UPDATE_BUTTON, QMessageBox.ButtonRole.AcceptRole)
        skip = dialog.addButton(SKIP_BUTTON, QMessageBox.ButtonRole.ActionRole)
        skip.clicked.connect(lambda: self._skip_version(release, dialog))
        dialog.addButton(NOTICES, QMessageBox.ButtonRole.HelpRole)
        dialog.setDefaultButton(update_button)
        self._dialog = dialog
        dialog.exec()
        if dialog.clickedButton() is update_button:
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
                UPDATE_TITLE,
                WAIT_TEXT,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._download(release)

    # --- download and install ---------------------------------------

    def _download(self, release: Release) -> None:
        """Progress dialog, streamed download, then SHA-256 verification."""
        self._release = release
        target = Path(tempfile.mkdtemp(prefix="pydownloader-")) / release.installer.name
        progress = QProgressDialog(DOWNLOAD_TEXT, CANCEL_BUTTON, 0, 0, self.window)
        progress.setWindowTitle("PyDownloader")
        progress.setWindowModality(Qt.WindowModality.NonModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        self._progress = progress
        self._start(
            lambda: checker.download_installer(release.installer.url, target, self._chunk),
            self.downloaded,
        )

    def _chunk(self, size: int) -> None:
        """One chunk written: the busy bar advances (the total size is unknown)."""
        if self._progress is not None:
            self._progress.setValue(min(100, self._progress.value() + 1))

    def _on_downloaded(self, path: object, error: str) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None
        if error:
            self.window.log_error(error)
            return
        installer = Path(str(path))
        release = self._release
        try:
            expected = _expected_sha(release, installer)
        except UpdateError as exc:
            self.window.log_error(str(exc))
            return
        if expected and not checker.verify(installer, expected):
            self.window.log_error(SHA_FAIL)
            return
        self.window.log_info(INSTALL_TEXT)
        checker.run_installer(installer)
        self.window.exit_after_update()


def _expected_sha(release: Release | None, installer: Path) -> str:
    """Digest published next to the installer; empty when the release has no asset."""
    if release is None or release.sha256_asset is None:
        return ""
    return checker.fetch_expected_sha(release.sha256_asset.url)


__all__ = ["UpdateMonitor", "Worker", "release_notes"]
