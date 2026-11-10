"""Startup: the download folder is asked once and then taken from the settings."""

from __future__ import annotations

from pydownloader.config.settings import Settings
from pydownloader.ui import app as app_mod


def test_saved_folder_is_used_without_a_dialog(tmp_path, monkeypatch):
    saved = tmp_path / "Мои видео"
    settings = Settings(download_dir=str(saved))
    asked: list[object] = []
    monkeypatch.setattr(app_mod, "pick_download_dir", lambda start: asked.append(start))

    assert app_mod.resolve_download_dir(settings) == saved
    # The folder is created when it was deleted: no dialog on a normal start.
    assert saved.is_dir()
    assert asked == []


def test_first_start_asks_for_the_folder(tmp_path, monkeypatch):
    settings = Settings()  # no folder saved yet
    monkeypatch.setattr(app_mod, "pick_download_dir", lambda start: tmp_path)

    assert app_mod.resolve_download_dir(settings) == tmp_path


def test_cancelled_first_start_stops_the_program(monkeypatch):
    monkeypatch.setattr(app_mod, "pick_download_dir", lambda start: None)
    assert app_mod.resolve_download_dir(Settings()) is None


def test_unusable_saved_folder_asks_again(tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("not a folder", encoding="utf-8")
    settings = Settings(download_dir=str(blocker / "sub"))
    chosen = tmp_path / "new"
    monkeypatch.setattr(app_mod, "pick_download_dir", lambda start: chosen)

    assert app_mod.resolve_download_dir(settings) == chosen
