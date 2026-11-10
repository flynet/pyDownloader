"""Update check: parsing, SemVer, cache, SHA-256 (spec 8.3)."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import httpx
import pytest
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QWidget

from pydownloader.config.settings import Settings
from pydownloader.update.checker import (
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
    LATER_BUTTON,
    SKIP_BUTTON,
    UPDATE_BUTTON,
    UpdateMonitor,
    release_notes,
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
    assert "/CLOSEAPPLICATIONS" in command
    assert flags == 0x00000008


def test_download_installer_writes_the_file(monkeypatch, tmp_path: Path):
    class Response:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def iter_bytes(self, size):
            yield b"inst"
            yield b"aller"

    monkeypatch.setattr(httpx, "stream", lambda method, url, **kwargs: Response())
    target = tmp_path / "nested" / "setup.exe"
    chunks: list[int] = []
    result = download_installer("https://real.example/setup.exe", target, chunks.append)
    assert result.read_bytes() == b"installer"
    assert chunks == [4, 5]


def test_download_installer_reports_http_errors(monkeypatch, tmp_path: Path):
    class Response:
        status_code = 404

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def iter_bytes(self, size):
            yield b""

    monkeypatch.setattr(httpx, "stream", lambda method, url, **kwargs: Response())
    with pytest.raises(UpdateError):
        download_installer("https://real.example/setup.exe", tmp_path / "setup.exe")


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


class FakeWindow:
    """The part of the window the monitor uses, recorded for the asserts."""

    def __init__(self, settings: Settings):
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
    assert UPDATE_BUTTON in names and SKIP_BUTTON in names and LATER_BUTTON in names
    skip = next(b for b in dialog.findChildren(QPushButton) if b.text() == SKIP_BUTTON)
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
    mon._release = rel
    mon.downloaded.emit(file, "")
    assert calls == []
    assert window.logs[-1][0] == "error"
