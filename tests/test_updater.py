"""Update check: parsing, SemVer, cache, SHA-256 (spec 8.3)."""

from __future__ import annotations

import hashlib
import time
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QWidget

from pydownloader.config.settings import Settings
from pydownloader.i18n import tr
from pydownloader.ui.card import format_duration
from pydownloader.update.checker import (
    Asset,
    Release,
    UpdateError,
    download_installer,
    fetch_release,
    is_newer,
    parse_last_check,
    parse_release,
    parse_sha,
    run_installer,
    should_check,
    stamp,
    strip_v,
    verify,
)
from pydownloader.update.ui import (
    SpeedMeter,
    UpdateMonitor,
    Worker,
    download_text,
    later_label,
    megabytes,
    progress_text,
    release_notes,
    sha_fail,
    skip_label,
    update_label,
)


def payload(
    tag: str = "v1.2.0",
    prerelease: bool = False,
    draft: bool = False,
    assets: list[dict] | None = None,
) -> dict:
    if assets is None:
        assets = [
            {
                "name": "PyDownloader-Setup-1.2.0.exe",
                "browser_download_url": "https://real.example/setup.exe",
                "size": 100,
            },
            {
                "name": "PyDownloader-Setup-1.2.0.exe.sha256",
                "browser_download_url": "https://real.example/setup.sha256",
                "size": 64,
            },
        ]
    return {
        "tag_name": tag,
        "prerelease": prerelease,
        "draft": draft,
        "body": "## Fixes\n- one",
        "assets": assets,
    }


def release(tag: str = "v1.2.0") -> Release:
    result = parse_release(payload(tag=tag))
    assert result is not None
    return result


def test_parse_release_keeps_the_assets_and_notes():
    rel = parse_release(payload())
    assert rel is not None
    assert rel.version == "1.2.0"
    assert rel.tag == "v1.2.0"
    assert rel.installer.name == "PyDownloader-Setup-1.2.0.exe"
    assert rel.sha256_asset is not None
    assert rel.has_installer


def test_parse_release_ignores_prerelease_draft_and_missing_assets():
    assert parse_release(payload(prerelease=True)) is None
    assert parse_release(payload(draft=True)) is None
    assert parse_release(payload(assets=[])) is None
    assert parse_release(payload(tag="")) is None


def test_version_compare():
    assert strip_v("v1.2.3") == "1.2.3"
    assert strip_v("1.2.3") == "1.2.3"
    assert is_newer("1.2.0", "1.2.1")
    assert not is_newer("1.2.1", "1.2.0")
    assert not is_newer("1.2.0", "1.2.0")
    # the development version is below any release
    assert is_newer("0.0.0.dev0", "1.2.0")
    assert not is_newer("not-a-version", "1.2.0")
    assert not is_newer("1.2.0", "also-not-a-version")


def test_should_check_respects_the_cache_window():
    settings = Settings(auto_update=True, update_check_hours=24)
    assert should_check(settings, now=100.0, last_check=None)
    last = 100.0
    assert not should_check(settings, now=last + 23 * 3600, last_check=last)
    assert should_check(settings, now=last + 24 * 3600, last_check=last)
    assert not should_check(Settings(auto_update=False), now=10 * 24 * 3600, last_check=None)


def test_parse_sha_handles_both_forms():
    assert parse_sha("abc123 PyDownloader-Setup.exe") == "abc123"
    assert parse_sha("  ABC123\n") == "abc123"
    assert parse_sha("") == ""


def test_verify_installer_digest(tmp_path: Path):
    file = tmp_path / "setup.exe"
    file.write_bytes(b"installer bytes")
    digest = hashlib.sha256(b"installer bytes").hexdigest()
    assert verify(file, digest)
    assert not verify(file, "0" * 64)


class FakeResponse:
    def __init__(self, status_code: int, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def test_fetch_release_reads_the_api(monkeypatch):
    def fake_get(self, url, headers=None):
        return FakeResponse(200, payload())

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    rel = fetch_release("https://api.example/latest")
    assert rel is not None and rel.version == "1.2.0"


def test_fetch_release_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(httpx.Client, "get", lambda self, url, headers=None: FakeResponse(403, {}))
    with pytest.raises(UpdateError):
        fetch_release("https://api.example/latest")


def test_fetch_release_raises_on_network_failure(monkeypatch):
    def fake_get(self, url, headers=None):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    with pytest.raises(UpdateError):
        fetch_release("https://api.example/latest")


def test_installer_command_is_silent_and_closes_apps(tmp_path: Path, monkeypatch):
    calls: list = []

    def fake_popen(command, creationflags=0):
        calls.append((command, creationflags))
        return "process"

    monkeypatch.setattr("pydownloader.update.checker.subprocess.Popen", fake_popen)
    path = tmp_path / "PyDownloader-Setup-1.2.0.exe"
    path.write_bytes(b"x")
    assert run_installer(path) == "process"
    command, flags = calls[0]
    assert command[0] == str(path)
    assert "/SILENT" in command
    assert "/SUPPRESSMSGBOXES" in command
    assert "/CLOSEAPPLICATIONS" in command
    # The machine is not rebooted and not asked about a reboot: the update runs
    # while the person is away from the keyboard.
    assert "/NORESTART" in command
    assert flags == 0x00000008


def test_download_installer_writes_the_file(monkeypatch, tmp_path: Path):
    class Response:
        status_code = 200
        headers = {"content-length": "9"}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def iter_bytes(self, size):
            yield b"inst"
            yield b"aller"

    monkeypatch.setattr(httpx, "stream", lambda method, url, **kwargs: Response())
    target = tmp_path / "nested" / "setup.exe"
    chunks: list[tuple[int, int]] = []
    result = download_installer(
        "https://real.example/setup.exe", target, lambda w, t: chunks.append((w, t))
    )
    assert result.read_bytes() == b"installer"
    # The bar of the progress counts the bytes that are on the disk against the
    # whole file, so the numbers grow and do not restart from zero.
    assert chunks == [(4, 9), (9, 9)]


def test_download_installer_reports_http_errors(monkeypatch, tmp_path: Path):
    class Response:
        status_code = 404
        headers: dict[str, str] = {}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def iter_bytes(self, size):
            yield b""

    monkeypatch.setattr(httpx, "stream", lambda method, url, **kwargs: Response())
    with pytest.raises(UpdateError):
        download_installer("https://real.example/setup.exe", tmp_path / "setup.exe")


def test_download_installer_names_a_network_failure(monkeypatch, tmp_path: Path):
    """GitHub is slow and the read times out: the reason must reach the console.

    The old code let the timeout of httpx escape: the thread of the download
    stopped with no signal, the bar moved forever, the program closed, and the
    console said nothing about the update (spec 8.3 p.3.1).
    """

    def fake_stream(method, url, **kwargs):
        raise httpx.ReadTimeout("read timed out")

    monkeypatch.setattr(httpx, "stream", fake_stream)
    with pytest.raises(UpdateError):
        download_installer("https://real.example/setup.exe", tmp_path / "setup.exe")


def test_download_installer_continues_from_the_last_byte(monkeypatch, tmp_path: Path):
    """A broken connection continues the file, not the download from zero."""
    requests: list[dict] = []

    class Response:
        def __init__(self, status, headers, chunks, break_after=None):
            self.status_code = status
            self.headers = headers
            self._chunks = chunks
            self._break_after = break_after

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def iter_bytes(self, size):
            for number, chunk in enumerate(self._chunks):
                yield chunk
                if self._break_after is not None and number >= self._break_after:
                    raise httpx.ReadTimeout("connection reset")

    answers = [
        Response(200, {"content-length": "9"}, [b"inst"], break_after=0),
        Response(206, {"content-range": "bytes 4-8/9", "content-length": "5"}, [b"aller"]),
    ]

    def fake_stream(method, url, **kwargs):
        requests.append(kwargs.get("headers") or {})
        return answers[len(requests) - 1]

    monkeypatch.setattr(httpx, "stream", fake_stream)
    target = tmp_path / "setup.exe"
    seen: list[tuple[int, int]] = []
    result = download_installer(
        "https://real.example/setup.exe", target, lambda w, t: seen.append((w, t))
    )
    assert result.read_bytes() == b"installer"
    assert requests[1]["Range"] == "bytes=4-"
    # The second answer names the whole size in Content-Range, so the bar keeps
    # counting against the full file.
    assert seen[-1] == (9, 9)


def test_settings_cache_round_trip(tmp_path: Path):
    from pydownloader.config.settings import load_settings, save_settings

    path = tmp_path / "settings.json"
    settings = Settings()
    settings.last_update_check = stamp(1234.0)
    save_settings(settings, path)
    back = load_settings(path)
    assert parse_last_check(back) == 1234.0
    assert parse_last_check(Settings()) is None


# --- the dialog and the check flow ------------------------------------------


class FakeWindow(QWidget):
    """The part of the window the monitor uses, recorded for the asserts.

    A ``QWidget`` is the parent of the progress dialog of the download, so the
    fake carries that base: a plain object passed as the parent of a dialog is
    rejected by Qt, and the download never starts in the test.
    """

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.logs: list[tuple[str, str]] = []
        self.status = ""
        self.worker = None
        self.exited = False
        self.version_seen = ""

    def log_info(self, message: str) -> None:
        self.logs.append(("info", message))

    def log_warning(self, message: str) -> None:
        self.logs.append(("warning", message))

    def log_error(self, message: str) -> None:
        self.logs.append(("error", message))

    def set_update_status(self, text: str) -> None:
        self.status = text

    def current_version(self) -> str:
        return self.version_seen

    def persist_settings(self) -> None:
        self.logs.append(("settings", "saved"))

    def exit_after_update(self) -> None:
        self.exited = True


def monitor(settings: Settings, window: FakeWindow, fetch):
    return UpdateMonitor(window, settings, fetch=fetch)


def test_release_notes_strips_markdown():
    assert release_notes("## Fixes\n- one\n\n") == "Fixes\n- one"
    assert release_notes("") == ""


def test_check_on_startup_is_skipped_when_auto_update_is_off(qtbot, tmp_path):
    settings = Settings(auto_update=False)
    window = FakeWindow(settings)
    calls: list[int] = []
    mon = monitor(settings, window, lambda: calls.append(1) or release())
    mon.check_on_startup()
    assert calls == []


def test_check_on_startup_uses_the_cache_window(qtbot, tmp_path):
    settings = Settings(auto_update=True, update_check_hours=24)
    settings.last_update_check = str(time.time())
    window = FakeWindow(settings)
    calls: list[int] = []
    mon = monitor(settings, window, lambda: calls.append(1) or release())
    mon.check_on_startup()
    assert calls == []
    settings.last_update_check = str(time.time() - 30 * 3600)
    mon.check_on_startup()
    QApplication.processEvents()
    qtbot.wait(100)
    assert calls == [1]


def test_checked_newer_version_shows_the_dialog_and_the_status(qtbot, tmp_path, monkeypatch):
    settings = Settings(auto_update=True)
    settings.last_update_check = str(time.time())
    window = FakeWindow(settings)
    window.version_seen = "1.0.0"
    mon = monitor(settings, window, lambda: None)
    shown: list = []
    monkeypatch.setattr(mon, "_show_dialog", lambda rel: shown.append(rel))
    mon.checked.emit(release("v1.2.0"), "")
    assert shown and shown[0].version == "1.2.0"
    assert "1.2.0" in window.status
    assert window.logs[-1] == ("settings", "saved")


def test_checked_same_or_older_version_shows_nothing(qtbot, tmp_path):
    settings = Settings(auto_update=True)
    settings.last_update_check = str(time.time())
    window = FakeWindow(settings)
    window.version_seen = "1.2.0"
    mon = monitor(settings, window, lambda: None)
    shown: list = []
    mon._show_dialog = lambda rel: shown.append(rel)
    mon.checked.emit(release("v1.2.0"), "")
    mon.checked.emit(release("v1.1.0"), "")
    assert shown == []
    assert window.status == ""


def test_checked_error_is_a_console_warning(qtbot, tmp_path):
    settings = Settings(auto_update=True)
    settings.last_update_check = str(time.time())
    window = FakeWindow(settings)
    mon = monitor(settings, window, lambda: None)
    mon.checked.emit(None, "GitHub API: ограничено число запросов")
    assert window.logs[-1][0] == "warning"


def test_skipped_version_is_not_shown_again(qtbot, tmp_path):
    settings = Settings(auto_update=True, skipped_version="1.2.0")
    settings.last_update_check = str(time.time())
    window = FakeWindow(settings)
    window.version_seen = "1.0.0"
    mon = monitor(settings, window, lambda: None)
    shown: list = []
    mon._show_dialog = lambda rel: shown.append(rel)
    mon.checked.emit(release("v1.2.0"), "")
    assert shown == []


def test_dialog_shows_the_version_and_skip_writes_the_settings(qtbot, tmp_path, monkeypatch):
    settings = Settings(auto_update=True)
    window = QWidget()
    qtbot.addWidget(window)
    mon = monitor(settings, window, lambda: None)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    dialog = mon._show_dialog(release("v1.2.0"))
    assert "1.2.0" in dialog.text()
    assert "Fixes" in dialog.informativeText()
    names = {b.text() for b in dialog.findChildren(QPushButton)}
    assert update_label() in names and skip_label() in names and later_label() in names
    skip = next(b for b in dialog.findChildren(QPushButton) if b.text() == skip_label())
    skip.click()
    assert settings.skipped_version == "1.2.0"


def test_download_failure_logs_the_reason(qtbot, tmp_path):
    settings = Settings(auto_update=True)
    window = FakeWindow(settings)
    mon = monitor(settings, window, lambda: None)
    mon.downloaded.emit(None, "Скачивание установщика: HTTP 404")
    assert window.logs[-1] == ("error", "Скачивание установщика: HTTP 404")


def test_verified_installer_is_launched_and_the_program_exits(qtbot, tmp_path, monkeypatch):
    settings = Settings(auto_update=True)
    window = FakeWindow(settings)
    calls: list = []
    monkeypatch.setattr(
        "pydownloader.update.ui.checker.run_installer",
        lambda path: calls.append(path) or "proc",
    )
    monkeypatch.setattr("pydownloader.update.ui.checker.verify", lambda path, sha: True)

    def fake_sha(release, installer):
        return "abc"

    monkeypatch.setattr("pydownloader.update.ui._expected_sha", fake_sha)
    rel = release("v1.2.0")
    file = tmp_path / rel.installer.name
    file.write_bytes(b"installer")
    mon = monitor(settings, window, lambda: None)
    mon._release = rel
    mon.downloaded.emit(file, "")
    assert calls == [file]
    assert window.exited


def test_bad_sha_blocks_the_install(qtbot, tmp_path, monkeypatch):
    settings = Settings(auto_update=True)
    window = FakeWindow(settings)
    calls: list = []
    monkeypatch.setattr(
        "pydownloader.update.ui.checker.run_installer",
        lambda path: calls.append(path) or "proc",
    )
    monkeypatch.setattr("pydownloader.update.ui.checker.verify", lambda path, sha: False)

    def fake_sha(release, installer):
        return "abc"

    monkeypatch.setattr("pydownloader.update.ui._expected_sha", fake_sha)
    rel = release("v1.2.0")
    file = tmp_path / rel.installer.name
    file.write_bytes(b"installer")
    mon = monitor(settings, window, lambda: None)
    # The digest is checked in the job of the download, so the GUI thread does not
    # block on the file of SHA-256 (spec 8.3 p.3.2).
    job = mon._job(rel, file)
    with pytest.raises(UpdateError):
        job(lambda written, total: None)
    assert calls == []
    mon.downloaded.emit(None, sha_fail())
    assert window.logs[-1][0] == "error"


def test_half_an_installer_is_not_installed(qtbot, tmp_path, monkeypatch):
    """A download that stopped half way must not be run: the program would break.

    The release names the size of the installer, so the bytes on the disk are
    counted against it before the installer is started (spec 8.3 p.3.1).
    """
    settings = Settings(auto_update=True)
    window = FakeWindow(settings)
    calls: list = []
    monkeypatch.setattr(
        "pydownloader.update.ui.checker.run_installer",
        lambda path: calls.append(path) or "proc",
    )
    rel = release("v1.2.0")
    file = tmp_path / rel.installer.name
    file.write_bytes(b"installer")  # 9 bytes, the release promises 100
    monkeypatch.setattr(
        "pydownloader.update.ui.checker.download_installer",
        lambda url, target, cb: target,
    )
    mon = monitor(settings, window, lambda: None)
    job = mon._job(rel, file)
    with pytest.raises(UpdateError) as caught:
        job(lambda written, total: None)
    # The text names the megabytes that landed and the size the release promises.
    assert str(caught.value) == tr("up_installer_incomplete", got=megabytes(9), size=megabytes(100))
    # The answer of the job goes through the same signal as a real download, so
    # the console hears it and the installer is never started.
    mon.downloaded.emit(None, str(caught.value))
    assert calls == []
    assert window.logs[-1][0] == "error"


def test_fetch_release_without_releases_is_silent(monkeypatch):
    """A repository with no published releases answers 404: no warning, no update."""
    monkeypatch.setattr(httpx.Client, "get", lambda self, url, headers=None: FakeResponse(404, {}))
    assert fetch_release("https://api.example/latest") is None


# --- the failure of a download must be visible -------------------------------


def test_worker_reports_a_crash_of_the_job(qtbot):
    """A plain exception of the job reaches the window: the bar does not move alone.

    The old code caught only ``UpdateError``, so a timeout of httpx left the
    thread running, no signal was sent, and the program closed with the progress
    dialog open and no word in the console (spec 8.3 p.3.1).
    """

    def job(report):
        raise httpx.ReadTimeout("read timed out")

    worker = Worker(job)
    got: list[str] = []
    worker.failed.connect(got.append)
    worker.run()
    assert got and "ReadTimeout" in got[0]


def test_worker_reports_a_network_failure_of_the_job(qtbot):
    def job(report):
        raise UpdateError("Скачивание установщика: read timed out")

    worker = Worker(job)
    got: list[str] = []
    worker.failed.connect(got.append)
    worker.run()
    assert got == ["Скачивание установщика: read timed out"]


def test_progress_of_the_download_writes_the_bar_of_the_window(qtbot, monkeypatch, tmp_path):
    """The bytes the worker has landed reach the bar through a signal, not a widget.

    The download runs in the thread, so the worker must not touch the dialog:
    the bar is written in the GUI thread by the slot of the signal.
    """
    meg = 1024 * 1024
    settings = Settings(auto_update=True)
    window = FakeWindow(settings)
    qtbot.addWidget(window)
    rel = replace(
        release("v1.2.0"), installer=Asset("Setup.exe", "https://real.example/s.exe", 2 * meg)
    )

    def fake_download(url, path, cb):
        # Half of the file, then the whole file, as a real stream reports it.
        cb(meg, 2 * meg)
        path.write_bytes(b"x" * 2 * meg)
        cb(2 * meg, 2 * meg)
        return path

    def launched(path):
        seen.append(path)
        return "proc"

    seen: list = []
    # The dialog closes itself when the value reaches the maximum, so the numbers
    # of the download are read from the signal, and the label is read in the GUI
    # thread where the bar is written.
    bar: list[tuple[int, int, str]] = []
    monkeypatch.setattr("pydownloader.update.ui.checker.download_installer", fake_download)
    monkeypatch.setattr("pydownloader.update.ui.checker.run_installer", launched)
    monkeypatch.setattr("pydownloader.update.ui._expected_sha", lambda release, installer: "")
    mon = UpdateMonitor(window, settings, fetch=lambda: None)
    mon.progressed.connect(lambda w, t: bar.append((w, t, mon._progress.labelText())))
    mon._download(rel)
    qtbot.wait(300)
    # The bar counts the bytes on the disk against the size the release promises.
    assert [(w, t) for w, t, _ in bar] == [(meg, 2 * meg), (2 * meg, 2 * meg)]
    # The label of the bar carries the megabytes, the percent, and the speed as
    # soon as two samples of the meter exist.
    assert bar[0][2] == tr("update_download_of", written=1, total=2, percent=50)
    assert bar[1][2].startswith(tr("update_download_of", written=2, total=2, percent=100))
    # The second line of the label is the speed and the time left: the download
    # in the test is whole, so nothing is left to fetch.
    assert "\n" in bar[1][2]
    assert "0:00" in bar[1][2]
    # The installer of the whole file is launched, and the program exits for it.
    assert seen
    assert window.exited


def test_cancelled_download_is_told_to_the_console(qtbot, tmp_path, monkeypatch):
    settings = Settings(auto_update=True)
    window = FakeWindow(settings)
    rel = release("v1.2.0")
    file = tmp_path / rel.installer.name
    mon = monitor(settings, window, lambda: None)

    def stop(url, target, cb):
        # The person presses «Отмена» while the file is on its way.
        mon._cancel_download()
        cb(10, 100)
        return target

    monkeypatch.setattr("pydownloader.update.ui.checker.download_installer", stop)
    job = mon._job(rel, file)
    with pytest.raises(UpdateError) as caught:
        job(lambda written, total: None)
    mon.downloaded.emit(None, str(caught.value))
    assert window.logs[-1] == ("error", tr("up_installer_cancelled"))


def test_installer_that_cannot_start_keeps_the_program_running(qtbot, tmp_path, monkeypatch):
    """Windows can refuse a program downloaded from the network: the console says so.

    The old code let the exception fall in the GUI thread after the download:
    the program closed, the installer never ran, and nothing was written.
    """
    settings = Settings(auto_update=True)
    window = FakeWindow(settings)

    def blocked(path):
        raise OSError("SmartScreen blocked the program")

    monkeypatch.setattr("pydownloader.update.ui.checker.run_installer", blocked)
    mon = monitor(settings, window, lambda: None)
    file = tmp_path / "PyDownloader-Setup-1.2.0.exe"
    file.write_bytes(b"x")
    mon.downloaded.emit(file, "")
    assert window.exited is False
    assert window.logs[-1][0] == "error"


def test_manual_check_with_no_update_shows_the_answer(qtbot, tmp_path):
    """«Проверить обновления» answers even when there is nothing to install."""
    settings = Settings(auto_update=True)
    settings.last_update_check = str(time.time())
    window = FakeWindow(settings)
    window.version_seen = "1.2.0"
    mon = monitor(settings, window, lambda: None)
    mon._manual = True
    mon.checked.emit(release("v1.2.0"), "")
    # The text is a key of the catalog, so the test reads the answer in whatever
    # language the suite runs in.
    assert window.status.startswith(tr("update_none", time="").strip())
    assert window.logs[-1] == ("settings", "saved")


def test_automatic_check_stays_silent_when_there_is_no_update(qtbot, tmp_path):
    settings = Settings(auto_update=True)
    settings.last_update_check = str(time.time())
    window = FakeWindow(settings)
    window.version_seen = "1.2.0"
    mon = monitor(settings, window, lambda: None)
    mon.checked.emit(release("v1.2.0"), "")
    assert window.status == ""


def test_release_notes_drop_the_image_links(qtbot):
    """The body of a release carries the screenshots as links: the dialog is text."""
    body = (
        "![Main window](https://raw.githubusercontent.com/flynet/pyDownloader/main/a.png)\n"
        "\n"
        "## [0.4.9]\n"
        "\n"
        "### Added\n"
        "- the card shows the still of the video\n"
    )
    notes = release_notes(body)
    assert "http" not in notes
    assert notes.startswith("[0.4.9]")
    assert "the card shows the still" in notes


def test_progress_text_shows_the_megabytes(qtbot):
    assert progress_text(1024, 20 * 1024 * 1024) == tr(
        "update_download_of", written=1, total=20, percent=0
    )
    # A release that names no size keeps the plain text.
    assert progress_text(1024, 0) == download_text()


def test_progress_text_shows_the_percent_and_the_speed(qtbot):
    """The person reads how much has landed, the part of the file, and the pace."""
    meg = 1024 * 1024
    line = progress_text(10 * meg, 20 * meg, 2 * meg, 75)
    assert line.startswith(tr("update_download_of", written=10, total=20, percent=50))
    # The speed and the time left are written with the same words as the cards
    # of the downloads and the tooltip of the tray.
    assert tr("card_speed_mb", speed=2.0) in line
    assert format_duration(75) in line


def test_speed_meter_follows_the_last_seconds(qtbot, monkeypatch):
    """The speed is the bytes of the last seconds, not the average of the whole file.

    A slow GitHub link gives the file in bursts: the average of the whole
    download shows the speed of the start and the number does not move, so the
    person cannot tell whether the file is coming (spec 8.3 p.3.1).
    """
    clock = [0.0]
    monkeypatch.setattr("pydownloader.update.ui.time.monotonic", lambda: clock[0])
    meter = SpeedMeter()
    meg = 1024 * 1024
    meter.add(0)
    clock[0] = 10.0
    meter.add(10 * meg)  # 1 MB/s over the first 10 seconds
    clock[0] = 12.0
    meter.add(14 * meg)  # the last 2 seconds give 2 MB/s
    # The window of 8 seconds keeps the samples of the last seconds, so the burst
    # of the slow link is the speed the person reads, and the estimate follows it.
    assert meter.speed() == 2 * meg
    assert meter.left(14 * meg, 20 * meg) == 3


def test_progress_text_shows_the_speed_without_a_size(qtbot):
    """A release that names no size has no percent, but the line shows the speed.

    On a slow GitHub the person sees the bytes arriving and knows the link is
    alive, instead of watching a bar that spins with no number (spec 8.3 p.3.1).
    """
    meg = 1024 * 1024
    assert progress_text(meg, 0) == download_text()
    line = progress_text(3 * meg, 0, 2 * meg)
    assert line.startswith(download_text())
    assert tr("card_speed_mb", speed=2.0) in line
