"""GUI tests (pytest-qt): cards, console, settings, geometry (spec 4)."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtWidgets import QApplication

from pydownloader.config.paths import Paths, default_paths
from pydownloader.config.settings import Settings
from pydownloader.manifest.registry import SourceEntry
from pydownloader.ui import main_window as main_window_mod
from pydownloader.ui.card import SourceCard, format_duration, format_quality, format_size
from pydownloader.ui.console import MAX_LINES, ConsolePanel
from pydownloader.ui.main_window import (
    HINT,
    LogBridge,
    MainWindow,
    geometry_from_hex,
    geometry_hex,
)
from pydownloader.ui.settings_panel import SettingsDialog
from pydownloader.ui.theme import apply_theme, qss_for


def entry(id: str = "s1", kind: str = "hls", height: int | None = 1080) -> SourceEntry:
    return SourceEntry(
        id=id,
        kind=kind,
        url=f"https://cdn.example.com/{id}.m3u8",
        normalized=f"https://cdn.example.com/{id}.m3u8",
        title="Мой клип",
        page_url="https://site.example/watch/42",
        size=12_000_000,
        height=height,
        duration=125.5,
    )


def make_window(tmp_path: Path) -> MainWindow:
    settings = Settings(download_dir=str(tmp_path))
    paths = default_paths(downloads_dir=tmp_path)
    window = MainWindow(settings, paths, None, None)
    window.show()
    return window


def test_card_shows_title_quality_and_size(qtbot):
    card = SourceCard(entry())
    qtbot.addWidget(card)
    assert "Мой клип" in card.title_label.text()
    assert card.badge.text() == "HLS"
    assert "1080p" in card.meta_label.text()
    assert "11.4 МБ" in card.meta_label.text()
    assert card.download_button.isEnabled()
    assert not card.cancel_button.isVisible()
    assert not card.bar.isVisible()


def test_card_url_is_elided_with_tooltip(qtbot):
    long = "https://cdn.example.com/" + "x" * 200
    item = entry()
    item.url = long
    card = SourceCard(item)
    qtbot.addWidget(card)
    assert len(card.url_label.text()) <= 91
    assert card.url_label.toolTip() == long


def test_card_state_machine(qtbot):
    card = SourceCard(entry())
    qtbot.addWidget(card)
    card.show()
    card.set_state("queued")
    assert not card.download_button.isEnabled()
    assert "В очереди" in card.meta_label.text()
    card.set_state("downloading")
    assert card.bar.isVisible()
    assert card.cancel_button.isVisible()
    card.set_progress(1, 4)
    assert card.bar.value() == 1
    assert "1 из 4" in card.bar.format()
    card.set_state("done")
    assert card.bar.value() == 100
    assert "Готово" in card.meta_label.text()
    assert card.open_button.isVisible()
    card.set_state("error")
    assert card.retry_button.isVisible()


def test_card_download_button_emits_the_id(qtbot):
    card = SourceCard(entry())
    qtbot.addWidget(card)
    with qtbot.waitSignal(card.download_clicked) as signal:
        card.download_button.click()
    assert signal.args == ["s1"]


def test_card_cancel_button_emits_the_id(qtbot):
    card = SourceCard(entry())
    qtbot.addWidget(card)
    card.set_state("downloading")
    with qtbot.waitSignal(card.cancel_clicked) as signal:
        card.cancel_button.click()
    assert signal.args == ["s1"]


def test_card_open_button_opens_the_file(qtbot):
    card = SourceCard(entry())
    qtbot.addWidget(card)
    card.set_state("done")
    assert card.open_button.text() == "Открыть файл"
    with qtbot.waitSignal(card.open_file_clicked) as signal:
        card.open_button.click()
    assert signal.args == ["s1"]


def test_open_result_file_plays_the_downloaded_video(tmp_path: Path, qtbot, monkeypatch):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    video = tmp_path / "video.mp4"
    video.write_bytes(b"data")
    window.out_paths["s1"] = video
    opened: list[Path] = []
    monkeypatch.setattr(
        main_window_mod, "_open_file", lambda path: opened.append(path) or True
    )

    window._open_result_file("s1")
    assert opened == [video]


def test_open_result_file_falls_back_to_the_folder(tmp_path: Path, qtbot, monkeypatch):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.out_paths["s1"] = tmp_path / "gone.mp4"
    folders: list[Path] = []
    monkeypatch.setattr(main_window_mod, "_show_in_explorer", folders.append)

    window._open_result_file("s1")
    assert folders == [tmp_path]


def test_formats():
    assert format_size(None) == "размер неизвестен"
    assert format_size(1024 * 1024) == "1.0 МБ"
    assert format_quality(None) == "разрешение неизвестно"
    assert format_quality(1080) == "1080p"
    assert format_duration(None) == ""
    assert format_duration(125.5) == "2:06"
    assert format_duration(3600) == "60:00"


def test_console_keeps_the_buffer(qtbot):
    panel = ConsolePanel()
    qtbot.addWidget(panel)
    for i in range(MAX_LINES + 500):
        panel.append_line(f"[00:00:00] INFO     line {i}")
    assert panel.blockCount() <= MAX_LINES
    assert "line 5499" in panel.toPlainText()
    panel.show_info("Найден HLS-поток")
    assert "INFO" in panel.toPlainText().splitlines()[-1]
    panel.show_warning("нет 1080p")
    assert "WARNING" in panel.toPlainText().splitlines()[-1]
    panel.show_error("ошибка")
    assert "ERROR" in panel.toPlainText().splitlines()[-1]
    panel.clear_panel()
    assert panel.toPlainText() == ""
    assert panel.isReadOnly()


def test_console_autoscroll_stops_when_scrolled_up(qtbot):
    panel = ConsolePanel()
    qtbot.addWidget(panel)
    for i in range(200):
        panel.append_line(f"line {i}")
    bar = panel.verticalScrollBar()
    bar.setValue(0)
    assert not panel.is_at_bottom()
    panel.append_line("new line")
    assert bar.value() == 0
    bar.setValue(bar.maximum())
    panel.append_line("last line")
    assert panel.is_at_bottom()


def test_window_starts_empty_with_the_hint(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    assert window.hint_label.isVisible()
    assert HINT in window.hint_label.text()
    assert window.cards == {}
    assert "PyDownloader" in window.windowTitle()
    assert str(tmp_path) in window.windowTitle()


def test_window_adds_a_card_and_hides_the_hint(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.add_source(entry())
    assert "s1" in window.cards
    assert not window.hint_label.isVisible()
    window.add_source(entry())  # the same id is not added twice
    assert len(window.cards) == 1


def test_download_button_keeps_its_height_with_many_cards(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.resize(900, 600)
    window.show()
    for index in range(5):
        window.add_source(entry(f"s{index}"))
    qtbot.wait(50)  # let the scroll area lay the cards out
    for card in window.cards.values():
        button = card.download_button
        # The old fixed minimum height squeezed the button and its text vanished.
        assert button.height() >= button.minimumSizeHint().height()
        assert card.height() >= card.sizeHint().height()


def test_window_splitter_ratio(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    sizes = window.splitter.sizes()
    assert len(sizes) == 2
    total = sum(sizes)
    assert 30 <= 100 * sizes[0] / total <= 50


def test_window_minimum_size(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    assert window.minimumWidth() >= 900
    assert window.minimumHeight() >= 600


def test_window_geometry_is_saved_and_restored(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.resize(1000, 700)
    text = geometry_hex(window.saveGeometry())
    assert text
    restored = geometry_from_hex(text)
    window2 = make_window(tmp_path)
    qtbot.addWidget(window2)
    settings = Settings(download_dir=str(tmp_path), window_geometry=text)
    window2.settings = settings
    window2.restoreGeometry(restored)
    window2.show()
    assert window2.width() == 1000


def test_console_buttons_clear_the_panel(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.console.show_info("сообщение")
    assert window.console.toPlainText()
    window.console.clear_panel()
    assert window.console.toPlainText() == ""


def test_status_bar_shows_version_and_folder(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    text = window.status_label.text()
    assert "0.0.0-dev" in text
    assert str(tmp_path) in text


def test_settings_dialog_writes_the_values(qtbot, tmp_path):
    settings = Settings(download_dir=str(tmp_path))
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    dialog.threads_box.setValue(4)
    dialog.height_box.setValue(720)
    dialog.size_box.setValue(3)
    dialog.theme_box.setCurrentIndex(dialog.theme_box.findData("light"))
    dialog.update_check.setChecked(False)
    target = dialog.apply_to(Settings())
    assert target.threads == 4
    assert target.target_height == 720
    assert target.min_mp4_size == 3 * 1024 * 1024
    assert target.theme == "light"
    assert not target.auto_update


def test_themes_have_stylesheets():
    assert qss_for("system") == ""
    dark = qss_for("dark")
    assert "#1e1e1e" in dark
    assert "QPlainTextEdit#console" in dark
    light = qss_for("light")
    assert "#ffffff" in light
    assert "#202020" in light


def test_apply_theme(qtbot, qapp: QApplication):
    apply_theme(qapp, "dark")
    assert qapp.styleSheet()
    apply_theme(qapp, "system")
    assert qapp.styleSheet() == ""


def test_log_bridge_forwards_from_another_thread(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    bridge = LogBridge(window)
    bridge.line.connect(window.console.append_line)
    thread = threading.Thread(target=lambda: bridge.line.emit("[00:00:00] INFO     из потока"))
    thread.start()
    thread.join()
    qtbot.waitUntil(lambda: "из потока" in window.console.toPlainText(), timeout=3000)


def test_paths_for_the_window(tmp_path):
    paths = default_paths(downloads_dir=tmp_path)
    window = make_window(tmp_path)
    assert window.paths.settings_file.name == "settings.json"
    assert window.paths.log_file.name == "app.log"
    assert isinstance(paths, Paths)
