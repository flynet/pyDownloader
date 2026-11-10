"""GUI tests (pytest-qt): cards, console, settings, geometry (spec 4)."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

from pydownloader.config.paths import Paths, default_paths
from pydownloader.config.settings import Settings
from pydownloader.i18n import tr
from pydownloader.manifest.registry import SourceEntry
from pydownloader.ui import main_window as main_window_mod
from pydownloader.ui import tray as tray_mod
from pydownloader.ui.card import SourceCard, format_duration, format_quality, format_size
from pydownloader.ui.console import MAX_LINES, ConsolePanel
from pydownloader.ui.main_window import (
    LogBridge,
    MainWindow,
    geometry_from_hex,
    geometry_hex,
)
from pydownloader.ui.settings_panel import (
    DIALOG_HEIGHT_RATIO,
    DIALOG_WIDTH_RATIO,
    MIN_DIALOG_HEIGHT,
    MIN_DIALOG_WIDTH,
    SettingsDialog,
)
from pydownloader.ui.theme import apply_theme, qss_for
from pydownloader.ui.tray import TrayController, make_tray


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


def test_clear_all_button_removes_every_card(tmp_path: Path, qtbot):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.add_source(entry("s1"))
    window.add_source(entry("s2"))

    window.clear_all_button.click()
    assert window.cards == {}
    assert window.hint_label.isVisible()


def test_clear_downloaded_button_keeps_videos_that_are_not_on_disk(tmp_path: Path, qtbot):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.add_source(entry("s1"))
    window.add_source(entry("s2"))
    saved = tmp_path / "s1.mp4"
    saved.write_bytes(b"data")
    window.out_paths["s1"] = saved
    window.out_paths["s2"] = tmp_path / "gone.mp4"

    window.clear_downloaded_button.click()
    assert set(window.cards) == {"s2"}
    assert "s1" not in window.out_paths
    assert "s2" in window.out_paths


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
    assert tr("window_empty") in window.hint_label.text()
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


def test_card_list_scrolls_when_cards_do_not_fit(qtbot, tmp_path):
    """The cards below the viewport stay reachable, not cut off (spec 4.1 p.1)."""
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.resize(900, 600)
    window.show()
    for index in range(5):
        window.add_source(entry(f"s{index}"))
    qtbot.wait(50)
    cards = list(window.cards.values())
    # The floor of the container is the floor of the cards, so the scroll area
    # gets a range to scroll and the widget is not resized to the viewport.
    assert window.card_container.minimumHeight() >= sum(
        card.sizeHint().height() for card in cards
    )
    assert window.scroll_area.verticalScrollBar().maximum() > 0
    # A state with more lines (progress bar, stage) raises the floor of the card.
    cards[0].set_state("downloading")
    qtbot.wait(50)
    assert cards[0].minimumHeight() >= cards[0].sizeHint().height()


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
    dialog.tray_check.setChecked(True)
    dialog.close_tray_check.setChecked(False)
    target = dialog.apply_to(Settings())
    assert target.threads == 4
    assert target.target_height == 720
    assert target.min_mp4_size == 3 * 1024 * 1024
    assert target.theme == "light"
    assert not target.auto_update
    # The tray and the «X» behaviour are settings of the window (spec 4.3).
    assert target.tray_enabled
    assert not target.close_to_tray


def test_settings_dialog_shows_the_saved_tray_state(qtbot, tmp_path):
    settings = Settings(download_dir=str(tmp_path), tray_enabled=False, close_to_tray=False)
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    assert not dialog.tray_check.isChecked()
    assert not dialog.close_tray_check.isChecked()


def test_settings_dialog_is_wide_and_resizable(tmp_path: Path, qtbot):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.resize(1000, 800)
    long_path = r"C:\Users\Home\Videos\Очень длинное название папки для скачанных видео"
    dialog = SettingsDialog(Settings(download_dir=long_path), window)
    qtbot.addWidget(dialog)

    assert dialog.width() == max(MIN_DIALOG_WIDTH, round(window.width() * DIALOG_WIDTH_RATIO))
    assert dialog.height() == max(
        MIN_DIALOG_HEIGHT, round(window.height() * DIALOG_HEIGHT_RATIO)
    )
    assert dialog.isSizeGripEnabled()
    assert dialog.maximumWidth() > dialog.width()
    assert dialog.download_edit.text() == long_path
    assert dialog.download_edit.toolTip() == long_path


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


class FakeTray:
    """Stand-in for the tray icon: the balloons and the browser state are recorded."""

    def __init__(self) -> None:
        self.hints: list[str] = []
        self.running: bool | None = None

    def notify(self, text: str) -> None:
        self.hints.append(text)

    def set_browser_running(self, running: bool) -> None:
        self.running = running


def test_browser_buttons_are_wired_to_the_top_panel(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    # The browser thread is not up yet, so only «Open browser» is clickable.
    assert window.open_browser_button.isEnabled()
    assert not window.close_browser_button.isEnabled()
    with qtbot.waitSignal(window.browser_open_request):
        window.open_browser_button.click()
    window.set_browser_running(True)
    assert not window.open_browser_button.isEnabled()
    assert window.close_browser_button.isEnabled()
    with qtbot.waitSignal(window.browser_close_request):
        window.close_browser_button.click()


def test_browser_closed_by_the_user_allows_to_open_it_again(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.set_browser_running(True)
    window._browser_closed()
    assert window.open_browser_button.isEnabled()
    assert not window.close_browser_button.isEnabled()
    # The running download is not stopped by the closed browser window (spec 3.7).
    assert window.worker is None


def test_page_url_is_remembered_for_open_browser(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window._page_changed("https://site.example/watch/42", "Clip")
    assert window.last_url == "https://site.example/watch/42"


def test_set_browser_running_updates_the_tray_menu(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    tray = FakeTray()
    window.tray = tray
    window.set_browser_running(True)
    assert tray.running is True
    window.set_browser_running(False)
    assert tray.running is False


def test_closing_the_window_hides_it_to_the_tray(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    tray = FakeTray()
    window.tray = tray

    event = QCloseEvent()
    window.closeEvent(event)

    # The window is hidden, the threads of the browser and of the queue stay alive.
    assert not event.isAccepted()
    assert not window.isVisible()
    assert window.settings.tray_hint_seen
    assert tr("tray_hint") in tray.hints


def test_the_tray_hint_is_shown_only_once(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    tray = FakeTray()
    window.tray = tray
    window.settings.tray_hint_seen = True

    window.closeEvent(QCloseEvent())
    assert tray.hints == []


def test_the_quitting_flag_closes_the_window_for_real(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.tray = FakeTray()
    window._quitting = True

    event = QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted()


def test_closing_quits_when_the_window_is_not_hidden_to_the_tray(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.tray = FakeTray()
    window.settings.close_to_tray = False

    event = QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted()


def test_tray_menu_tracks_the_browser_window(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    tray = TrayController(window, None)
    assert tray.show_action.text() == tr("tray_show")
    assert tray.quit_action.text() == tr("tray_quit")
    assert tray.open_action.isEnabled()
    assert not tray.close_action.isEnabled()
    tray.set_browser_running(True)
    assert not tray.open_action.isEnabled()
    assert tray.close_action.isEnabled()
    assert tray.contextMenu().actions()[0] is tray.show_action
    assert len(tray.contextMenu().actions()) == 6


def test_make_tray_is_skipped_without_a_notification_area(qtbot, tmp_path, monkeypatch):
    """A platform without a tray (the offscreen CI) must work without the icon."""
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    monkeypatch.setattr(tray_mod.QSystemTrayIcon, "supportsMessages", lambda self: False)

    assert make_tray(window, None) is None
    assert window.tray is None


def test_enabling_the_tray_setting_creates_the_icon(qtbot, tmp_path, monkeypatch, qapp):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    monkeypatch.setattr(tray_mod.QSystemTrayIcon, "supportsMessages", lambda self: True)

    window.settings.tray_enabled = True
    window._apply_tray_state(qapp)
    assert window.tray is not None
    assert not qapp.quitOnLastWindowClosed()

    # «X» is a way to quit again when the tray is turned off (spec 4.3).
    window.settings.tray_enabled = False
    window._apply_tray_state(qapp)
    assert window.tray is None
    assert qapp.quitOnLastWindowClosed()


def test_make_tray_shows_the_icon_and_keeps_the_window(qtbot, tmp_path, monkeypatch):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    monkeypatch.setattr(tray_mod.QSystemTrayIcon, "supportsMessages", lambda self: True)

    tray = make_tray(window, None)

    assert tray is not None
    assert window.tray is tray
    # The browser thread is not running yet: only «Open browser» is enabled.
    assert tray.open_action.isEnabled()
    assert not tray.close_action.isEnabled()
