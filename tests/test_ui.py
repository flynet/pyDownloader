"""GUI tests (pytest-qt): cards, console, settings, geometry (spec 4)."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtGui import QCloseEvent, QColor, QImage
from PySide6.QtWidgets import QApplication

from pydownloader.config.paths import Paths, default_paths
from pydownloader.config.settings import Settings
from pydownloader.i18n import tr
from pydownloader.manifest.registry import SourceEntry
from pydownloader.ui import main_window as main_window_mod
from pydownloader.ui import tray as tray_mod
from pydownloader.ui.app_icon import ACCENT, BACKGROUND, TRAY_SIZE, WHITE, draw
from pydownloader.ui.card import (
    DONE_COLOR,
    SourceCard,
    format_duration,
    format_quality,
    format_size,
)
from pydownloader.ui.console import MAX_LINES, ConsolePanel
from pydownloader.ui.main_window import (
    SPLIT_CONSOLE_MIN,
    LogBridge,
    MainWindow,
    RunInfo,
    geometry_from_hex,
    geometry_hex,
    tray_speed_line,
)
from pydownloader.ui.settings_panel import (
    DIALOG_HEIGHT_RATIO,
    DIALOG_WIDTH_RATIO,
    MIN_DIALOG_HEIGHT,
    MIN_DIALOG_WIDTH,
    SettingsDialog,
)
from pydownloader.ui.theme import apply_theme, qss_for
from pydownloader.ui.tray import ACTIVE_COLOR, IDLE_COLOR, TrayController, make_tray


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


def test_the_bar_of_a_finished_card_is_green(qtbot):
    card = SourceCard(entry())
    qtbot.addWidget(card)
    card.show()
    card.set_state("downloading")
    # A running download keeps the accent of the theme: the bar is blue (spec 4.1 p.3).
    assert card.bar.styleSheet() == ""
    card.set_progress(1, 4)
    assert card.bar.styleSheet() == ""
    card.set_state("done")
    # The file is on the disk: the bar turns green, so the end of the download is
    # seen without reading the text.
    assert DONE_COLOR in card.bar.styleSheet()
    assert card.bar.isVisible()
    assert card.bar.value() == 100
    card.set_state("error")
    # A cancelled or failed task is not a finished file: the green bar is taken back.
    assert card.bar.styleSheet() == ""


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
    # The program starts with the console hidden, so the ratio of the two sections
    # is measured with the panel shown (spec 4.2 p.5).
    window.show_console()
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
    dialog.height_box.setCurrentIndex(dialog.height_box.findData(720))
    dialog.size_box.setValue(3)
    dialog.theme_box.setCurrentIndex(dialog.theme_box.findData("light"))
    dialog.update_check.setChecked(False)
    dialog.tray_check.setChecked(True)
    dialog.close_tray_check.setChecked(True)
    dialog.console_check.setChecked(False)
    target = dialog.apply_to(Settings())
    assert target.threads == 4
    assert target.target_height == 720
    assert target.min_mp4_size == 3 * 1024 * 1024
    assert target.theme == "light"
    assert not target.auto_update
    # «X» hides the window to the tray (spec 4.3), and the console panel is a setting
    # of the window as well: hidden, the list of videos gets the room (spec 4.2 p.5).
    assert target.tray_enabled
    assert target.close_to_tray
    assert not target.console_open


def test_settings_dialog_shows_the_saved_tray_state(qtbot, tmp_path):
    settings = Settings(
        download_dir=str(tmp_path), tray_enabled=False, close_to_tray=False, console_open=False
    )
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    assert not dialog.tray_check.isChecked()
    assert not dialog.close_tray_check.isChecked()
    assert not dialog.console_check.isChecked()


def test_settings_dialog_writes_the_browser_choice(qtbot, tmp_path):
    settings = Settings(download_dir=str(tmp_path))
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    dialog.browser_box.setCurrentIndex(dialog.browser_box.findData("msedge"))
    dialog.agent_edit.setText("My player 1.0")
    dialog.anti_bot_check.setChecked(False)
    dialog.blocker_check.setChecked(False)
    target = dialog.apply_to(Settings())
    # The browser of the settings is the one the program launches (spec 7.2).
    assert target.browser_name == "msedge"
    assert target.user_agent == "My player 1.0"
    assert not target.anti_bot
    assert not target.ad_blocker


def test_the_browser_names_are_localized(qtbot, tmp_path):
    dialog = SettingsDialog(Settings(download_dir=str(tmp_path)))
    qtbot.addWidget(dialog)
    names = [dialog.browser_box.itemText(i) for i in range(dialog.browser_box.count())]
    # «Auto» is first, the order of spec 7.2; the names are the ones the vendors use.
    assert names[0] == tr("browser_auto")
    assert tr("browser_chromium") in names
    assert dialog.browser_box.currentData() == "auto"


def test_the_saved_browser_choice_is_shown(qtbot, tmp_path):
    settings = Settings(download_dir=str(tmp_path), browser_name="chromium", user_agent="Dev 1.0")
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    assert dialog.browser_box.currentData() == "chromium"
    assert dialog.agent_edit.text() == "Dev 1.0"
    assert dialog.anti_bot_check.isChecked()
    assert dialog.blocker_check.isChecked()


def test_the_quality_presets_are_the_three_heights(qtbot, tmp_path):
    """The quality dropdown offers exactly 1080, 720, 480 (spec 5.2 p.3)."""
    dialog = SettingsDialog(Settings(download_dir=str(tmp_path)))
    qtbot.addWidget(dialog)
    names = [dialog.height_box.itemText(i) for i in range(dialog.height_box.count())]
    assert names == ["1080p", "720p", "480p"]
    assert dialog.height_box.currentData() == 1080


def test_a_height_out_of_the_list_keeps_its_entry(qtbot, tmp_path):
    """An edited settings.json keeps its height: saving the dialog does not change it."""
    settings = Settings(download_dir=str(tmp_path), target_height=1440)
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    assert dialog.height_box.currentData() == 1440
    assert dialog.height_box.itemText(dialog.height_box.findData(1440)) == "1440p"
    assert dialog.apply_to(Settings()).target_height == 1440


def test_the_settings_write_the_audio_mode_and_the_bitrate(qtbot, tmp_path):
    """«Audio only (MP3)» and the bitrate of the MP3 file are settings (spec 5.2 p.4)."""
    dialog = SettingsDialog(Settings(download_dir=str(tmp_path)))
    qtbot.addWidget(dialog)
    dialog.bitrate_box.setCurrentIndex(dialog.bitrate_box.findData(320))
    dialog.audio_check.setChecked(True)
    target = dialog.apply_to(Settings())
    assert target.mp3_bitrate == 320
    assert target.audio_only


def test_the_saved_audio_settings_are_shown(qtbot, tmp_path):
    settings = Settings(download_dir=str(tmp_path), mp3_bitrate=128, audio_only=True)
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    assert dialog.bitrate_box.currentData() == 128
    assert dialog.audio_check.isChecked()


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
    """Stand-in for the tray icon: the balloons, the browser and the queue are recorded."""

    def __init__(self) -> None:
        self.hints: list[str] = []
        self.running: bool | None = None
        self.active: bool | None = None
        self.lines: list[str] = []

    def notify(self, text: str) -> None:
        self.hints.append(text)

    def set_progress_lines(self, lines: list[str]) -> None:
        """The tooltip text the window wrote for the notification area (spec 4.2 p.7)."""
        self.lines = lines

    def set_browser_running(self, running: bool) -> None:
        self.running = running

    def set_download_active(self, active: bool) -> None:
        self.active = active


class FakeWorker:
    """Stand-in of the queue: the ids of the tasks, the running one is out of the queue."""

    def __init__(self) -> None:
        self.queued: list[str] = []
        self.download_dir = ""
        self.parallel = 1

    def enqueue(self, entry: SourceEntry) -> str:
        self.queued.append(entry.id)
        return entry.id

    def cancel(self, task_id: str) -> None:
        if task_id in self.queued:
            self.queued.remove(task_id)

    def pending(self) -> list[str]:
        return list(self.queued)

    def stop(self) -> None:
        pass

    def wait(self, milliseconds: int) -> bool:
        return True


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

    # The window is hidden, the threads of the browser and of the queue stay alive,
    # so the green arrow of the tray keeps reporting the download (spec 4.3 p.4).
    assert not event.isAccepted()
    assert not window.isVisible()
    assert window.settings.tray_hint_seen
    assert tr("tray_hint") in tray.hints


def test_the_tray_hint_is_shown_on_the_first_start(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    tray = FakeTray()
    window.tray = tray

    window.hint_tray()
    assert tr("tray_hint") in tray.hints
    assert window.settings.tray_hint_seen

    window.hint_tray()
    # The balloon explains the tray once, the flag is stored in the settings (spec 4.3).
    assert len(tray.hints) == 1


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
    # Without the hide setting «X» is a normal close: the browser and the queue stop.
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
    # The console panel is in the menu, so the hidden panel is opened from the tray
    # (spec 4.2 p.5): the menu has the seven items of the window.
    assert tray.console_action.text() == tr("window_open_console")
    assert len(tray.contextMenu().actions()) == 7


def tray_image(tray: TrayController) -> QImage:
    """The tray icon as the notification area draws it."""
    return tray.icon().pixmap(TRAY_SIZE, TRAY_SIZE).toImage()


def pixels(image: QImage) -> list[QColor]:
    """Every pixel of an image, in one list the test can compare."""
    return [image.pixelColor(x, y) for y in range(image.width()) for x in range(image.width())]


def solid_pixels(image: QImage) -> list[QColor]:
    """The pixels of an image that are not blended with the desktop behind them.

    The notification area draws the icon over its own background, so the edge of an
    antialiased pixel is blended: the test compares the pixels it can see exactly.
    """
    return [pixel for pixel in pixels(image) if pixel.alpha() == 255]


def pure(image: QImage, color: QColor) -> int:
    """How many pixels of an image are exactly this colour."""
    return sum(1 for pixel in pixels(image) if pixel == color)


def icon_pixel(tray: TrayController, x: int, y: int) -> QColor:
    """A pixel of the tray icon, in the size the notification area draws it."""
    return tray_image(tray).pixelColor(x, y)


def tray_pixels(tray: TrayController) -> list[int]:
    """The pixels of the tray icon: the test compares the frames of the animation."""
    image = tray.icon().pixmap(TRAY_SIZE, TRAY_SIZE).toImage()
    return [image.pixelColor(x, y).green() for y in range(TRAY_SIZE) for x in range(TRAY_SIZE)]


def test_the_console_panel_is_hidden_and_shown(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    # The program starts with the console hidden: the list of found videos gets the
    # whole window, which is what a person picking a video needs (spec 4.2 p.5), and
    # the row of buttons stays on the screen as the way to show the panel back.
    assert not window.console.isVisible()
    assert not window.console_clear.isVisible()
    assert window.console_button.text() == tr("console_show")
    hidden = window.splitter.sizes()
    assert hidden[1] <= SPLIT_CONSOLE_MIN + 40

    window.toggle_console()
    # «Clear» belongs to the text of the console, so it appears with the panel.
    assert window.console.isVisible()
    assert window.console_clear.isVisible()
    shown = window.splitter.sizes()
    assert shown[1] > SPLIT_CONSOLE_MIN + 40
    assert window.settings.console_open
    assert window.console_button.text() == tr("console_hide")

    window.toggle_console()
    assert not window.console.isVisible()
    assert not window.console_clear.isVisible()
    assert window.settings.console_open is False


def test_the_window_opens_with_the_console_the_user_left(qtbot, tmp_path):
    settings = Settings(download_dir=str(tmp_path), console_open=True)
    paths = default_paths(downloads_dir=tmp_path)
    window = MainWindow(settings, paths, None, None)
    qtbot.addWidget(window)
    window.show()
    # The state of the panel is stored in the settings, so the window opens the way
    # the user left it (spec 4.2 p.1), and the button says how to hide the console.
    assert window.console.isVisible()
    assert window.console_clear.isVisible()
    assert window.console_button.text() == tr("console_hide")


def test_the_card_cross_takes_a_found_entry_out_of_the_list(qtbot, tmp_path, caplog):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.add_source(entry("s1"))
    assert "s1" in window.cards
    # The cross is on the right of the title, in every state of the card (spec 4.1 p.1).
    # `isVisibleTo` is used: a card is shown by the layout, which happens in the event
    # loop, so the plain `isVisible` of the test window is not the state to check.
    card = window.cards["s1"]
    assert card.remove_button.isVisibleTo(window)
    # The cross is an icon painted by hand: the text glyph «✕» is not in the UI
    # font of Windows, so a label with the character shows a box.
    assert not card.remove_button.icon().isNull()
    card.remove_button.click()
    assert "s1" not in window.cards
    assert tr("window_card_removed", title=entry("s1").title) in caplog.messages
    # The empty list shows the hint again (spec 4.1 p.3).
    assert window.hint_label.isVisibleTo(window)


def test_the_card_cross_cancels_a_task_of_the_queue(qtbot, tmp_path, caplog):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    worker = FakeWorker()
    window.worker = worker
    window.add_source(entry("s1"))
    window._start_download("s1")
    window._task_started("s1", "Clip")
    assert worker.queued == ["s1"]

    window.cards["s1"].remove_button.click()
    # Removing a running card cancels its download, the card disappears with it.
    assert worker.queued == []
    assert "s1" not in window.cards
    assert tr("window_card_removed_cancelled", title=entry("s1").title) in caplog.messages


def test_the_card_cross_of_a_finished_card_keeps_the_file(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    worker = FakeWorker()
    window.worker = worker
    video = tmp_path / "a.mp4"
    video.write_bytes(b"data")
    window.add_source(entry("s1"))
    window._start_download("s1")
    worker.queued.clear()
    window._task_finished("s1", str(video))

    window.cards["s1"].remove_button.click()
    # The card is taken out of the list, the file on the disk is not touched.
    assert "s1" not in window.cards
    assert video.is_file()


def test_the_tray_marks_the_running_download_and_reports_the_end(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    tray = FakeTray()
    window.tray = tray
    heard: list[int] = []
    window.play_sound = lambda: heard.append(1)
    worker = FakeWorker()
    window.worker = worker

    window.add_source(entry("s1"))
    window._start_download("s1")
    # The green arrow: the program downloads while the window is minimized (spec 4.2 p.7).
    assert tray.active is True

    # The last task leaves the queue before it is reported, so the queue is empty now.
    worker.queued.clear()
    window._task_finished("s1", str(tmp_path / "a.mp4"))
    assert tray.active is False
    assert tr("tray_download", n=1) in tray.hints
    assert heard == [1]


def test_the_tray_tooltip_lists_the_files_that_download(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    tray = FakeTray()
    window.tray = tray
    worker = FakeWorker()
    window.worker = worker

    window.add_source(entry("s1"))
    window.add_source(entry("s2"))
    window._start_download("s1")
    window._start_download("s2")
    window._task_started("s1", "Мой клип")
    # The window is in the tray and the mouse is over the icon: the tooltip is the
    # queue of the program, not a balloon (spec 4.2 p.7).
    text = "\n".join(tray.lines)
    assert "Мой клип" in text
    assert tr("tray_tooltip_queued", n=1) in text

    # The throttle of the tooltip is over, so the next progress is written.
    window._tooltip_due = 0.0
    window._task_progress("s1", 2, 4)
    assert "50%" in "\n".join(tray.lines)

    worker.queued.clear()
    window._task_finished("s1", str(tmp_path / "a.mp4"))
    # Nothing is downloading: the tooltip has no queue lines left.
    assert tray.lines == []


def test_the_card_cross_takes_a_running_file_out_of_the_tooltip(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    tray = FakeTray()
    window.tray = tray
    worker = FakeWorker()
    window.worker = worker

    window.add_source(entry("s1"))
    window._start_download("s1")
    window._task_started("s1", "Мой клип")
    assert "Мой клип" in "\n".join(tray.lines)

    window._remove_entry("s1")
    # The task is cancelled and the file is out of the tooltip with the card.
    assert tray.lines == []
    assert tray.active is False


def test_the_tray_line_of_a_source_without_size():
    info = RunInfo("Клип", None, 42, 0.0)
    # An unknown size has no speed and no time left to promise: only the percent.
    assert tray_speed_line(info, 10.0) == tr("tray_tooltip_line_plain", name="Клип", percent=42)


def test_the_tray_line_shows_the_speed_and_the_time_left():
    # Half of 100 MB in 10 seconds: 5 MB/s, 10 seconds left (spec 4.2 p.7).
    info = RunInfo("Клип", 100 * 1024 * 1024, 50, 0.0)
    line = tray_speed_line(info, 10.0)
    assert "Клип" in line
    assert "50%" in line
    assert "5.0" in line
    assert format_duration(10.0) in line


def test_the_tray_icon_is_the_same_picture_as_the_program(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    tray = TrayController(window, None)

    # The tray is the icon of the program: the dark square, the white arrow pointing
    # down, the line of the tray under it (spec 7.3, 4.2 p.7).
    assert solid_pixels(tray_image(tray)) == solid_pixels(draw(TRAY_SIZE))
    head = (TRAY_SIZE // 2, int(TRAY_SIZE * 0.55))
    assert icon_pixel(tray, *head) == IDLE_COLOR == WHITE
    # A pixel of the square away from the arrow: the dark background of the icon.
    assert icon_pixel(tray, int(TRAY_SIZE * 0.13), int(TRAY_SIZE * 0.62)) == BACKGROUND


def test_the_tray_arrow_turns_green_and_jumps_while_a_download_runs(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    tray = TrayController(window, None)

    tray.set_download_active(True)
    # A running download: the green arrow, and the animation is on. Only the colour of
    # the arrow changes: the square, the line of the tray and the shape of the arrow
    # are the icon of the program (spec 4.2 p.7, 7.3).
    running = tray_image(tray)
    program = draw(TRAY_SIZE)
    assert pure(running, ACTIVE_COLOR) == pure(program, WHITE)
    assert pure(running, WHITE) == 0
    assert pure(running, BACKGROUND) == pure(program, BACKGROUND)
    assert pure(running, ACCENT) == pure(program, ACCENT)
    assert tray.bounce.timer.isActive()

    arrow = (TRAY_SIZE // 2, int(TRAY_SIZE * 0.66))
    line = (TRAY_SIZE // 2, int(TRAY_SIZE * 0.80))
    first = tray_pixels(tray)
    assert icon_pixel(tray, *line) == ACCENT

    tray.bounce._frame()
    # The line of the tray does not move, the arrow of the icon does: that is the jump.
    assert icon_pixel(tray, *line) == ACCENT
    assert pure(tray_image(tray), ACCENT) == pure(program, ACCENT)
    assert icon_pixel(tray, *arrow) != icon_pixel(tray, *line)
    assert tray_pixels(tray) != first

    tray.bounce._frame()
    assert tray_pixels(tray) == first

    tray.set_download_active(False)
    # The queue is empty: the icon of the program with the white arrow, no animation.
    assert not tray.bounce.timer.isActive()
    assert pure(tray_image(tray), WHITE) == pure(program, WHITE)
    assert pure(tray_image(tray), ACTIVE_COLOR) == 0


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


def test_a_tray_created_while_a_task_runs_shows_the_file_and_the_green_arrow(
    qtbot, tmp_path, monkeypatch
):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    worker = FakeWorker()
    window.worker = worker
    window.add_source(entry("s1"))
    window._start_download("s1")
    window._task_started("s1", "Мой клип")
    monkeypatch.setattr(tray_mod.QSystemTrayIcon, "supportsMessages", lambda self: True)

    tray = make_tray(window, None)
    # The tray appears while the task runs (the tray row of the settings): the tooltip
    # and the green arrow are written at once, not after the next progress (spec 4.2 p.7).
    assert "Мой клип" in tray.toolTip()
    assert tr("tray_tooltip_download") in tray.toolTip()
    assert pure(tray_image(tray), ACTIVE_COLOR) > 0
