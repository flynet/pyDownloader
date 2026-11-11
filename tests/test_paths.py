"""Where settings, logs and the browser profile live."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

from pydownloader.browser.launcher import chromium_executable
from pydownloader.config import paths as paths_mod
from pydownloader.config.paths import application_dir, default_paths, isolate_app_data


@pytest.fixture(autouse=True)
def isolated_appdata(tmp_path, monkeypatch):
    """Never touch the real ``%APPDATA%``/``%LOCALAPPDATA%`` of the developer."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    return tmp_path


def test_profile_is_kept_next_to_the_program(isolated_appdata: Path):
    app = isolated_appdata / "app"
    app.mkdir()
    paths = default_paths(app_dir=app)
    assert paths.profile_dir == app / "profile"
    assert paths.settings_file == isolated_appdata / "roaming" / "PyDownloader" / "settings.json"
    assert paths.log_file == app / "logs" / "app.log"
    assert paths.data_dir == app
    assert paths.browsers_dir == app / "browsers"
    assert paths.legacy_browsers_dir == isolated_appdata / "local" / "PyDownloader" / "browsers"


def test_profile_in_downloads_wins_over_the_app_folder(isolated_appdata: Path):
    app = isolated_appdata / "app"
    app.mkdir()
    downloads = isolated_appdata / "videos"
    paths = default_paths(True, downloads, app_dir=app)
    assert paths.profile_dir == downloads / ".profile"


def test_profile_falls_back_to_local_appdata_when_the_app_folder_is_read_only(
    isolated_appdata: Path, monkeypatch
):
    app = isolated_appdata / "app"
    app.mkdir()
    monkeypatch.setattr(paths_mod, "_writable", lambda folder: False)
    paths = default_paths(app_dir=app)
    assert paths.profile_dir == isolated_appdata / "local" / "PyDownloader" / "profile"


def test_logs_and_browsers_fall_back_when_the_app_folder_is_read_only(
    isolated_appdata: Path, monkeypatch
):
    app = isolated_appdata / "app"
    app.mkdir()
    local = isolated_appdata / "local" / "PyDownloader"
    monkeypatch.setattr(paths_mod, "_writable", lambda folder: False)
    paths = default_paths(app_dir=app)
    assert paths.data_dir == local
    assert paths.log_file == local / "logs" / "app.log"
    assert paths.browsers_dir == local / "browsers"


def test_chromium_of_an_older_version_is_reused(isolated_appdata: Path):
    app = isolated_appdata / "app"
    local = isolated_appdata / "local" / "PyDownloader"
    old = local / "browsers" / "chromium-1248" / "chrome-win64" / "chrome.exe"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"MZ")

    paths = default_paths(app_dir=app)
    assert not (paths.browsers_dir / "chromium-1248").exists()
    assert chromium_executable(paths.browsers_dir, paths.legacy_browsers_dir) == old


def test_without_app_dir_the_profile_stays_in_local_appdata(isolated_appdata: Path):
    paths = default_paths()
    assert paths.profile_dir == isolated_appdata / "local" / "PyDownloader" / "profile"


def test_old_profile_is_migrated_once(isolated_appdata: Path):
    old = isolated_appdata / "local" / "PyDownloader" / "profile"
    old.mkdir(parents=True)
    (old / "Cookies").write_text("session", encoding="utf-8")
    app = isolated_appdata / "app"
    app.mkdir()

    paths = default_paths(app_dir=app)
    assert paths.profile_dir == app / "profile"
    assert (app / "profile" / "Cookies").read_text(encoding="utf-8") == "session"
    assert not old.exists()


def test_an_existing_profile_is_not_overwritten(isolated_appdata: Path):
    old = isolated_appdata / "local" / "PyDownloader" / "profile"
    old.mkdir(parents=True)
    (old / "old.txt").write_text("old", encoding="utf-8")
    app = isolated_appdata / "app"
    new = app / "profile"
    new.mkdir(parents=True)
    (new / "new.txt").write_text("new", encoding="utf-8")

    paths = default_paths(app_dir=app)
    assert paths.profile_dir == new
    assert (new / "new.txt").read_text(encoding="utf-8") == "new"
    assert (old / "old.txt").is_file()


def test_a_file_in_place_of_the_profile_falls_back(isolated_appdata: Path):
    old = isolated_appdata / "local" / "PyDownloader" / "profile"
    old.mkdir(parents=True)
    app = isolated_appdata / "app"
    app.mkdir()
    (app / "profile").write_text("not a folder", encoding="utf-8")

    paths = default_paths(app_dir=app)
    assert paths.profile_dir == old


def test_a_locked_old_profile_stays_in_use(isolated_appdata: Path, monkeypatch):
    old = isolated_appdata / "local" / "PyDownloader" / "profile"
    old.mkdir(parents=True)
    app = isolated_appdata / "app"
    app.mkdir()

    def refuse(source, destination):
        raise OSError("file is in use")

    monkeypatch.setattr(paths_mod.shutil, "move", refuse)
    paths = default_paths(app_dir=app)
    assert paths.profile_dir == old
    assert old.is_dir()


def test_application_dir_in_a_checkout_is_the_repository_root():
    root = application_dir()
    assert (root / "pyproject.toml").is_file()


def test_application_dir_of_a_frozen_build_is_the_exe_folder(
    tmp_path: Path, monkeypatch
):
    exe = tmp_path / "PyDownloader.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    assert application_dir() == tmp_path


def test_a_script_that_builds_a_window_runs_in_its_own_app_data(
    tmp_path: Path, monkeypatch
):
    """The tool of the screenshots and the suite run outside the folders of the user.

    A window writes ``%APPDATA%/PyDownloader/settings.json`` on the console toggle,
    the Apply of the dialog and the close, so a script that builds a window of the
    program has to run with its own app data, temp folder and data folders
    (spec 7.4).
    """
    old = tmp_path / "temp"
    old.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tempfile, "tempdir", str(old))
    root = isolate_app_data()
    paths = default_paths()
    for path in (paths.settings_file, paths.log_file, paths.profile_dir, paths.browsers_dir):
        assert path.is_relative_to(root)
    if paths.legacy_browsers_dir is not None:
        assert paths.legacy_browsers_dir.is_relative_to(root)
    assert Path(tempfile.gettempdir()).is_relative_to(root)
