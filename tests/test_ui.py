"""GUI tests (pytest-qt): cards, console, settings, geometry (spec 4)."""

from __future__ import annotations

import http.server
import json
import threading
from base64 import b64encode
from pathlib import Path

import pytest
from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QCloseEvent, QColor, QIcon, QImage, QPalette, QPixmap
from PySide6.QtWidgets import QAbstractButton, QApplication, QPushButton

from pydownloader.config.paths import Paths, default_paths
from pydownloader.config.settings import THEMES, Settings
from pydownloader.i18n import SUPPORTED_LANGUAGES, set_language, tr
from pydownloader.manifest.registry import SourceEntry
from pydownloader.ui import main_window as main_window_mod
from pydownloader.ui import tray as tray_mod
from pydownloader.ui.app_icon import ACCENT, BACKGROUND, TRAY_SIZE, WHITE, draw
from pydownloader.ui.button_icons import ICON_SIZE, browser_icon, icon_color
from pydownloader.ui.card import (
    DONE_COLOR,
    ELLIPSIS,
    THUMBNAIL_HEIGHT,
    THUMBNAIL_WIDTH,
    TITLE_LINES,
    SourceCard,
    fit_thumbnail,
    format_duration,
    format_quality,
    format_size,
)
from pydownloader.ui.console import MAX_LINES, ConsolePanel
from pydownloader.ui.main_window import (
    CONSOLE_HANDLE,
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
    theme_label,
)
from pydownloader.ui.theme import (
    CARTOONS,
    DARK,
    LIGHT,
    NEON,
    PALETTES,
    PINK,
    apply_theme,
    badge_style,
    color_for,
    contrast_ratio,
    qss_for,
)
from pydownloader.ui.thumbnail import ThumbnailLoader, preview_url
from pydownloader.ui.tray import (
    ACTIVE_COLOR,
    BASE_TOOLTIP,
    IDLE_COLOR,
    TOOLTIP_LIMIT,
    TrayController,
    make_tray,
    tooltip_text,
)


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


def test_the_cross_button_of_a_card_is_a_square(qtbot):
    """The cross on the right of a card is a square box with the mark in the middle.

    A `QToolButton` with no text is left as the icon only: asking for the text
    beside the icon reserves the room of a label, and the box of the cross becomes
    a rectangle with the mark shifted to the left (spec 4.1 p.1).
    """
    card = SourceCard(entry(), theme="dark")
    qtbot.addWidget(card)
    # The QSS of the theme is what gives the button its padding, so the test puts
    # the stylesheet of the dark theme on the card, as the window does.
    card.setStyleSheet(qss_for("dark"))
    button = card.remove_button
    assert button.text() == ""
    assert button.toolButtonStyle() != Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    card.resize(940, 110)
    card.show()
    assert button.width() == button.height()
    assert button.iconSize().width() == button.iconSize().height()
    # A button with a text keeps the text next to the mark (spec 4.1 p.4).
    card.set_state("downloading")
    assert card.cancel_button.text()
    assert card.cancel_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon


def test_card_url_is_elided_with_tooltip(qtbot):
    long = "https://cdn.example.com/" + "x" * 200
    item = entry()
    item.url = long
    card = SourceCard(item)
    qtbot.addWidget(card)
    assert len(card.url_label.text()) <= 91
    assert card.url_label.toolTip() == long


def thumbnail_image(width: int = 320, height: int = 180) -> QPixmap:
    """A still of a video for a card: a plain picture of the size a page serves."""
    picture = QPixmap(width, height)
    picture.fill(QColor("#2ea64f"))
    return picture


def test_a_video_card_shows_the_still_on_the_left_of_the_text(qtbot):
    """The picture stands on the left, the name and the details on the right (spec 4.1)."""
    card = SourceCard(entry(), thumbnail=thumbnail_image())
    qtbot.addWidget(card)
    card.show()
    QApplication.processEvents()
    assert card.thumbnail_label is not None
    assert card.thumbnail_label.pixmap().width() == THUMBNAIL_WIDTH
    assert card.thumbnail_label.pixmap().height() == THUMBNAIL_HEIGHT
    # The whole text column is on the right of the picture, not above or below it.
    assert card.thumbnail_label.geometry().right() < card.title_label.geometry().left()
    assert card.thumbnail_label.geometry().right() < card.url_label.geometry().left()
    assert card.thumbnail_label.geometry().top() <= card.title_label.geometry().top()
    # The title stays the first line of the text block.
    assert card.title_label.text().startswith("Мой клип")


def test_a_card_without_a_still_starts_with_the_name(qtbot):
    """An audio source has no picture: its card is the name of what is downloaded (spec 4.1)."""
    item = entry(kind="mp4")
    item.is_audio = True
    card = SourceCard(item)
    qtbot.addWidget(card)
    assert card.thumbnail_label is None
    assert card.title_label.text() == "Мой клип"


def test_the_still_is_cut_to_the_frame_of_the_card():
    """A picture of any shape is cut to one 16:9 frame, the middle of it kept (spec 4.1)."""
    wide = fit_thumbnail(thumbnail_image(400, 100))
    assert (wide.width(), wide.height()) == (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)
    tall = fit_thumbnail(thumbnail_image(100, 400))
    assert (tall.width(), tall.height()) == (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)


def test_preview_url_is_resolved_against_the_page():
    item = entry()
    item.thumbnail = "/img/still.jpg"
    assert preview_url(item) == "https://site.example/img/still.jpg"
    item.thumbnail = "//cdn.example.com/still.jpg"
    assert preview_url(item) == "https://cdn.example.com/still.jpg"
    # A frame painted into a canvas is already the picture, not an address to fetch.
    item.thumbnail = "data:image/jpeg;base64,AAAA"
    assert preview_url(item) == "data:image/jpeg;base64,AAAA"
    # An audio source has no still, a page without one gives no address.
    audio = entry(kind="mp4")
    audio.is_audio = True
    audio.thumbnail = "https://cdn.example.com/still.jpg"
    assert preview_url(audio) == ""
    assert preview_url(entry()) == ""


def test_the_card_of_a_video_waits_for_its_still(qtbot, tmp_path, monkeypatch):
    """The card is added after the picture arrived, not before (spec 4.1)."""
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    item = entry()
    item.thumbnail = "https://cdn.example.com/still.jpg"
    asked: list[tuple[str, str]] = []
    monkeypatch.setattr(
        window.thumbnail_loader,
        "load",
        lambda key, url, referer="", headers=None: asked.append((key, url)),
    )

    window.add_source(item)
    assert asked == [("s1", "https://cdn.example.com/still.jpg")]
    assert "s1" not in window.cards

    window._thumbnail_loaded("s1", thumbnail_image())
    assert "s1" in window.cards
    assert window.cards["s1"].thumbnail_label is not None
    assert not window.hint_label.isVisible()


def test_a_source_is_not_lost_when_its_still_did_not_arrive(qtbot, tmp_path, monkeypatch):
    """A broken preview is skipped: the card is still added, without a frame (spec 4.1)."""
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    item = entry()
    item.thumbnail = "https://cdn.example.com/still.jpg"
    monkeypatch.setattr(window.thumbnail_loader, "load", lambda *args, **kwargs: None)

    window.add_source(item)
    window._thumbnail_loaded("s1", None)
    assert "s1" in window.cards
    assert window.cards["s1"].thumbnail_label is None


def test_an_audio_source_is_added_without_waiting_for_a_still(qtbot, tmp_path):
    """An audio card has no picture, so nothing is waited for (spec 4.1)."""
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    item = entry(kind="mp4")
    item.is_audio = True
    item.thumbnail = "https://cdn.example.com/still.jpg"

    window.add_source(item)
    assert "s1" in window.cards
    assert window.cards["s1"].thumbnail_label is None


def test_clearing_the_list_drops_the_stills_on_their_way(qtbot, tmp_path, monkeypatch):
    """«Clear all» is the whole list: a picture that arrives later adds no card (spec 4.1)."""
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    item = entry()
    item.thumbnail = "https://cdn.example.com/still.jpg"
    monkeypatch.setattr(window.thumbnail_loader, "load", lambda *args, **kwargs: None)

    window.add_source(item)
    window.clear_all_cards()
    window._thumbnail_loaded("s1", thumbnail_image())
    assert window.cards == {}
    assert window.hint_label.isVisible()


def test_the_loader_reads_and_decodes_a_still(qtbot):
    """The bytes of a picture are read in the event loop and arrive as a picture (spec 4.1)."""
    image = QImage(8, 6, QImage.Format.Format_RGB32)
    image.fill(QColor("#123456"))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    data = bytes(buffer.data())

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # the test serves one picture
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args) -> None:
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        loader = ThumbnailLoader()
        received: list[tuple[str, object]] = []
        loader.loaded.connect(lambda key, picture: received.append((key, picture)))
        loader.load("s1", f"http://127.0.0.1:{server.server_port}/still.png")
        qtbot.waitUntil(lambda: bool(received), timeout=5000)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    key, picture = received[0]
    assert key == "s1"
    assert isinstance(picture, QPixmap)
    assert (picture.width(), picture.height()) == (8, 6)


def test_the_loader_decodes_a_frame_painted_by_the_player(qtbot):
    """A canvas frame arrives as a data URL: it is decoded here, no request is made (spec 4.1)."""
    image = QImage(8, 6, QImage.Format.Format_RGB32)
    image.fill(QColor("#123456"))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    url = "data:image/png;base64," + b64encode(bytes(buffer.data())).decode("ascii")

    loader = ThumbnailLoader()
    received: list[tuple[str, object]] = []
    loader.loaded.connect(lambda key, picture: received.append((key, picture)))
    loader.load("s1", url)
    qtbot.waitUntil(lambda: bool(received), timeout=1000)

    key, picture = received[0]
    assert key == "s1"
    assert isinstance(picture, QPixmap)
    assert (picture.width(), picture.height()) == (8, 6)


def test_the_loader_does_not_ask_for_a_picture_qt_cannot_decode(qtbot):
    """The request names only the formats Qt reads: AVIF would arrive but stay empty (spec 4.1).

    A host switches to AVIF as soon as the request advertises it (phncdn does),
    and Qt of this build has no AVIF plugin: the bytes arrive, the decode fails
    and the card is added without its picture.
    """
    image = QImage(8, 6, QImage.Format.Format_RGB32)
    image.fill(QColor("#123456"))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    data = bytes(buffer.data())
    accepted: list[str] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # the test serves one picture
            accepted.append(self.headers.get("Accept", ""))
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args) -> None:
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        loader = ThumbnailLoader()
        received: list[tuple[str, object]] = []
        loader.loaded.connect(lambda key, picture: received.append((key, picture)))
        loader.load("s1", f"http://127.0.0.1:{server.server_port}/still.jpg")
        qtbot.waitUntil(lambda: bool(received), timeout=5000)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert accepted, "the loader sent no request"
    assert "avif" not in accepted[0].lower()
    assert "image/webp" in accepted[0]
    assert "image/jpeg" in accepted[0]


def test_a_long_title_makes_the_card_taller_not_wider(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.resize(1000, 800)
    long = "Очень длинный клип с именем, которое не входит в одну линию " * 6
    item = entry()
    item.title = long
    window.add_source(item)
    QApplication.processEvents()
    card = window.cards["s1"]
    viewport = window.scroll_area.viewport().width()
    # The card is as wide as the list of cards, and the list is as wide as the
    # window: a long title takes the lines of the card, so the list of cards gets
    # no horizontal scrollbar (spec 4.1 p.1).
    assert card.width() <= viewport
    assert window.scroll_area.horizontalScrollBar().maximum() == 0
    lines = card.title_label.text().split("\n")
    assert len(lines) <= TITLE_LINES
    fm = card.title_label.fontMetrics()
    for line in lines:
        assert fm.horizontalAdvance(line) <= card.title_label.width()
    # A label asks for the width of its text, so the height of the title is the
    # room the card took: the title is read in the tooltip.
    assert card.title_label.height() > fm.height()
    assert card.title_label.toolTip() == long


def test_a_narrow_window_rewrites_the_lines_of_the_card(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    long = "Очень длинный клип " * 30
    item = entry()
    item.title = long
    window.add_source(item)
    window.resize(1000, 800)
    QApplication.processEvents()
    card = window.cards["s1"]
    window.resize(520, 800)
    QApplication.processEvents()
    # The width the title has changed, so its lines are built again: the letters that
    # do not fit are marked by the sign of elision, the whole title stays in the
    # tooltip (spec 4.1 p.1).
    lines = card.title_label.text().split("\n")
    assert len(lines) == TITLE_LINES
    assert ELLIPSIS in lines[-1]
    assert card.title_label.toolTip() == long
    assert card.width() <= window.scroll_area.viewport().width()
    assert window.scroll_area.horizontalScrollBar().maximum() == 0


def test_a_long_path_of_a_saved_file_does_not_widen_the_card(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.resize(1000, 800)
    window.add_source(entry())
    QApplication.processEvents()
    card = window.cards["s1"]
    name = ("клип_с_очень_длинным_именем_файла" * 3) + ".mp4"
    path = str(tmp_path / "файлы" / name)
    card.set_result(path)
    # A path is one word: the middle of the line is kept, so the quality and the end
    # of the name stay on the card, and the whole path is read in the tooltip.
    assert card.meta_label.toolTip() == path
    assert ELLIPSIS in card.meta_label.text()
    assert card.meta_label.text().startswith("1080p")
    assert card.width() <= window.scroll_area.viewport().width()
    assert window.scroll_area.horizontalScrollBar().maximum() == 0


def test_the_ampersand_of_a_title_is_a_letter_of_the_name(qtbot):
    item = entry()
    item.title = "Rock & Roll"
    card = SourceCard(item)
    qtbot.addWidget(card)
    card.show()
    # The label of the title has no flag of a mnemonic: the ampersand of a name is
    # a letter, not the underline of a key.
    assert card.title_label.text() == "Rock & Roll"
    assert int(card.title_label.alignment()) & int(Qt.TextFlag.TextShowMnemonic) == 0


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


def test_the_window_writes_its_settings_in_the_test_tree(qtbot, tmp_path, isolated_app_data):
    """The suite must not touch the settings of the developer (spec 3.1).

    A window saves the settings on every toggle of the console, on the Apply of the
    dialog and on the close, and the path it writes is the settings file of
    ``default_paths`` — the file of the user. The session fixture of ``conftest.py``
    redirects the app data, so the downloads folder the user chose survives a run of
    the suite: the temp folder of a test must never become his videos.
    """
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.toggle_console()  # the toggle of the console writes the settings
    written = json.loads(window.paths.settings_file.read_text(encoding="utf-8"))
    assert window.paths.settings_file.is_relative_to(isolated_app_data)
    assert written["download_dir"] == str(tmp_path)
    assert written["console_open"] is True


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


def test_the_main_buttons_of_the_settings_dialog_are_at_the_bottom_right(qtbot, tmp_path):
    """«Save» and «Cancel» are in the right lower corner, the update commands on the left.

    The buttons that finish a dialog are looked for in the bottom-right corner, so
    the two main buttons are right-aligned there, and "Check updates" and "Restart"
    stand on the left of the row (spec 4.3 p.2).
    """
    dialog = SettingsDialog(Settings(download_dir=str(tmp_path)))
    qtbot.addWidget(dialog)
    dialog.show()
    left = (dialog.update_check_button, dialog.restart_button)
    right = (dialog.save_button, dialog.cancel_button)
    # One row, the main buttons after the gap.
    for button in right:
        assert button.geometry().top() == left[0].geometry().top()
        assert button.geometry().left() > max(b.geometry().right() for b in left)
    # "Save" is the first of the two, "Cancel" is the last button of the row.
    assert dialog.save_button.geometry().left() < dialog.cancel_button.geometry().left()
    assert dialog.cancel_button.geometry().right() > dialog.save_button.geometry().right()
    # "Save" is the button of Enter, and it is one of the two in the corner.
    assert dialog.save_button.isDefault()


def test_the_settings_dialog_cannot_be_squeezed(qtbot, tmp_path):
    """The rows keep the height their text needs, so the dialog cannot be squeezed.

    A field of the form has the minimum height of zero, so a dialog shrunk by the
    user showed half of a letter in the fields, the selects and the buttons
    (spec 4.3 p.2). The floor of every widget is the height of its ``sizeHint``, the
    layout gets the minimum height of its rows, and the dialog cannot go under it.
    """
    dialog = SettingsDialog(Settings(download_dir=str(tmp_path)))
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()

    assert dialog.minimumSize().height() >= MIN_DIALOG_HEIGHT
    row = (
        dialog.download_edit,
        dialog.height_box,
        dialog.browser_box,
        dialog.theme_box,
        dialog.save_button,
    )
    for widget in row:
        assert widget.minimumHeight() == widget.sizeHint().height()

    # A request for a smaller dialog keeps every row at the height the font asks for.
    dialog.resize(dialog.width(), 300)
    QApplication.processEvents()
    for widget in row:
        assert widget.height() == widget.sizeHint().height()


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


def test_the_palette_follows_the_theme(qapp: QApplication):
    """The palette of the application is the palette of the theme, not of Windows.

    A widget with no rule of its own paints the palette, and the palette Qt reads
    from Windows is the palette of the system dark mode, so the light theme showed a
    dark wall behind the list of cards on a machine with the dark mode of Windows
    (spec 4.3). The system choice keeps the palette of the style.
    """
    apply_theme(qapp, "light")
    light = qapp.palette()
    assert light.color(QPalette.ColorRole.Window).name().lower() == LIGHT["background"]
    assert light.color(QPalette.ColorRole.Base).name().lower() == LIGHT["panel"]
    assert light.color(QPalette.ColorRole.Button).name().lower() == LIGHT["panel"]

    apply_theme(qapp, "dark")
    dark = qapp.palette()
    assert dark.color(QPalette.ColorRole.Window).name().lower() == DARK["background"]
    assert dark.color(QPalette.ColorRole.ButtonText).name().lower() == DARK["text"]
    assert dark.color(QPalette.ColorRole.Highlight).name().lower() == DARK["accent"]

    apply_theme(qapp, "system")
    standard = qapp.style().standardPalette()
    assert qapp.palette().color(QPalette.ColorRole.Window) == standard.color(
        QPalette.ColorRole.Window
    )


def test_the_theme_list_has_the_six_choices(qtbot, tmp_path):
    """The theme row of the settings carries the three new palettes (spec 4.3 p.3)."""
    settings = Settings(download_dir=str(tmp_path), theme="cartoons")
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    values = [dialog.theme_box.itemData(i) for i in range(dialog.theme_box.count())]
    assert values == list(THEMES)
    assert dialog.theme_box.currentData() == "cartoons"


def test_the_names_of_the_new_themes_are_localized():
    """Every theme has a name in every language of the catalog (spec 8.1)."""
    for language in SUPPORTED_LANGUAGES:
        set_language(language)
        for theme in THEMES:
            assert theme_label(theme).strip()
    set_language("ru")


@pytest.mark.parametrize("theme", ["cartoons", "neon", "pink"])
def test_the_new_themes_have_stylesheets(theme):
    """A theme palette paints the window, the cards and the console like the others."""
    qss = qss_for(theme)
    colors = PALETTES[theme]
    assert colors["background"] in qss
    assert colors["console_bg"] in qss
    assert "QPlainTextEdit#console" in qss
    assert "#cardArea" in qss


@pytest.mark.parametrize("theme", ["cartoons", "neon", "pink"])
def test_the_palette_of_a_theme_palette_follows_its_colors(qapp: QApplication, theme):
    apply_theme(qapp, theme)
    palette = qapp.palette()
    colors = PALETTES[theme]
    assert palette.color(QPalette.ColorRole.Window).name().lower() == colors["background"]
    assert palette.color(QPalette.ColorRole.Base).name().lower() == colors["panel"]
    assert palette.color(QPalette.ColorRole.WindowText).name().lower() == colors["text"]
    assert palette.color(QPalette.ColorRole.Highlight).name().lower() == colors["accent"]


#: The pairs of letters a person reads: the text on the wall of the window, the
#: letters of the buttons and of the badges, the log on the wall of the console.
#: The «100%» inside a bar that is already full is not in the list.
READABLE_PAIRS = [
    ("text", "background"),
    ("muted", "background"),
    ("text", "panel"),
    ("muted", "panel"),
    ("console_text", "console_bg"),
    ("accent", "#ffffff"),
    ("warn", "warn_text"),
    ("danger", "danger_text"),
    ("badge_hls_text", "badge_hls"),
    ("badge_dash_text", "badge_dash"),
    ("badge_mp4_text", "badge_mp4"),
    ("badge_youtube_text", "badge_youtube"),
    ("badge_mp3_text", "badge_mp3"),
]


def test_the_letters_of_every_theme_are_readable():
    """A pair of colors under the ratio 4.0 is not readable (WCAG AA, spec 4.3 p.3)."""
    for theme, colors in PALETTES.items():
        for first, second in READABLE_PAIRS:
            a = QColor(colors[first]) if first in colors else QColor(first)
            b = QColor(colors[second]) if second in colors else QColor(second)
            ratio = contrast_ratio(a, b)
            assert ratio >= 4.0, f"{theme}: {first} on {second} is {ratio:.2f}"


@pytest.mark.parametrize("theme", ["dark", "light", "cartoons", "neon", "pink"])
def test_the_wall_of_the_window_is_the_theme(qtbot, qapp, tmp_path, theme):
    """The wall behind the cards is the background of the theme, not of Windows."""
    settings = Settings(download_dir=str(tmp_path), theme=theme)
    window = MainWindow(settings, default_paths(downloads_dir=tmp_path), None, None)
    qtbot.addWidget(window)
    apply_theme(qapp, theme)
    window.resize(900, 600)
    window.show()
    wall = window.card_container.grab().toImage().pixelColor(120, 300)
    want = QColor(PALETTES[theme]["background"])
    assert (want.red(), want.green(), want.blue()) == (wall.red(), wall.green(), wall.blue())


@pytest.mark.parametrize("theme", ["dark", "light", "cartoons", "neon", "pink"])
def test_the_console_panel_is_the_wall_of_the_theme(qtbot, qapp, tmp_path, theme):
    """The log panel gets its own wall in every theme, so it reads as the console (spec 4.3 p.3)."""
    settings = Settings(download_dir=str(tmp_path), theme=theme, console_open=True)
    window = MainWindow(settings, default_paths(downloads_dir=tmp_path), None, None)
    qtbot.addWidget(window)
    apply_theme(qapp, theme)
    window.resize(900, 600)
    window.show()
    panel = window.console.grab().toImage().pixelColor(60, 30)
    want = QColor(PALETTES[theme]["console_bg"])
    assert (want.red(), want.green(), want.blue()) == (panel.red(), panel.green(), panel.blue())
    text = window.console.palette().color(QPalette.ColorRole.Text)
    assert text.name().lower() == PALETTES[theme]["console_text"]


def test_the_badge_of_a_card_is_the_color_of_the_theme(qtbot):
    card = SourceCard(entry(), theme="neon")
    qtbot.addWidget(card)
    colors = NEON
    assert colors["badge_hls"] in card.badge.styleSheet()
    assert colors["badge_hls_text"] in card.badge.styleSheet()


@pytest.mark.parametrize("theme", ["dark", "light", "cartoons", "neon", "pink"])
@pytest.mark.parametrize("kind", ["hls", "dash", "mp4", "youtube", "mp3"])
def test_every_format_badge_has_a_color_in_every_theme(theme, kind):
    """The badge of HLS, MP4, MP3 and DASH is painted in every theme (spec 4.3 p.3)."""
    style = badge_style(theme, kind)
    colors = PALETTES[theme]
    assert f"background: {colors[f'badge_{kind}']}" in style
    assert f"color: {colors[f'badge_{kind}_text']}" in style


def test_the_finished_bar_is_the_green_of_the_theme(qtbot):
    card = SourceCard(entry(), theme="pink")
    qtbot.addWidget(card)
    card.set_state("done")
    assert PINK["done"] in card.bar.styleSheet()
    assert PINK["done_text"] in card.bar.styleSheet()


def test_the_bar_of_a_finished_card_in_the_dark_theme_is_the_green_of_the_dark_theme(qtbot):
    card = SourceCard(entry())
    qtbot.addWidget(card)
    card.set_state("done")
    assert DONE_COLOR in card.bar.styleSheet()


def _icon_is(button, want: str) -> bool:
    """Whether the painted mark of the button carries the color of the theme."""
    image = button.icon().pixmap(ICON_SIZE, ICON_SIZE).toImage()
    target = QColor(want)
    for x in range(image.width()):
        for y in range(image.height()):
            color = image.pixelColor(x, y)
            if color.alpha() > 200 and color == target:
                return True
    return False


def test_the_window_repaints_the_buttons_and_the_cards_when_the_theme_changes(qtbot, tmp_path):
    """A theme chosen in the settings is applied to the window without a restart.

    The marks of the buttons are painted once, when the window is built, and the card
    is painted once, when it is added: a theme picked in the settings leaves them the
    colors of the old theme (spec 4.3 p.2).
    """
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.add_source(entry("s1"))
    card = window.cards["s1"]
    assert DARK["badge_hls"] in card.badge.styleSheet()
    assert _icon_is(window.go_button, "#ffffff")
    assert _icon_is(card.remove_button, DARK["text"])
    assert _icon_is(window.clear_downloaded_button, DARK["warn_text"])
    window.settings.theme = "pink"
    window._recolor_icons("pink")
    assert PINK["badge_hls"] in card.badge.styleSheet()
    assert PINK["badge_hls_text"] in card.badge.styleSheet()
    assert _icon_is(card.remove_button, PINK["text"])
    assert _icon_is(window.clear_downloaded_button, PINK["warn_text"])
    assert _icon_is(window.clear_all_button, PINK["danger_text"])


def test_the_buttons_of_a_theme_palette_are_the_colors_of_that_theme(qtbot, tmp_path):
    """The marks of the buttons take the colors of the theme the window was built with.

    A button of the accent is painted with the accent of the theme and the white
    letters, so its mark is white; the yellow button takes the dark text color of its
    own row, the red button the white of its row (spec 4.3 p.2).
    """
    settings = Settings(download_dir=str(tmp_path), theme="cartoons")
    window = MainWindow(settings, default_paths(downloads_dir=tmp_path), None, None)
    qtbot.addWidget(window)
    assert _icon_is(window.go_button, "#ffffff")
    assert _icon_is(window.settings_button, "#ffffff")
    assert _icon_is(window.browser_button, "#ffffff")
    assert _icon_is(window.clear_downloaded_button, CARTOONS["warn_text"])
    assert _icon_is(window.clear_all_button, CARTOONS["danger_text"])


def test_the_window_repaints_the_tray_menu_when_the_theme_changes(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    tray = FakeTray()
    window.tray = tray
    assert tray.theme is None
    window.settings.theme = "neon"
    window._recolor_icons("neon")
    assert tray.theme == "neon"


def test_the_marks_of_the_tray_menu_take_the_new_theme(qtbot, tmp_path):
    """The tray menu is painted once, so the theme picked in the settings repaints it.

    The marks of the menu are the marks of the window in the text color of the theme,
    and the menu is built when the tray is made, so a theme applied to the window has
    to be applied to the menu as well (spec 4.3 p.4).
    """
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    tray = TrayController(window, None)
    menu = tray.contextMenu()
    assert _icon_is(menu.actions()[0], DARK["text"])
    window.settings.theme = "neon"
    tray.set_theme("neon")
    assert _icon_is(menu.actions()[0], NEON["text"])
    assert _icon_is(tray.browser_action, NEON["text"])
    assert _icon_is(tray.quit_action, NEON["text"])


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
        #: The queue the window wrote: the name of a task and the line built from it.
        self.lines: list[tuple[str, str]] = []
        #: The text of the tooltip Windows would show: the queue within 128 characters.
        self.tooltip: str = BASE_TOOLTIP
        self.theme: str | None = None

    def notify(self, text: str) -> None:
        self.hints.append(text)

    def set_progress_lines(self, lines: list[tuple[str, str]]) -> None:
        """The tooltip text the window wrote for the notification area (spec 4.2 p.7)."""
        self.lines = lines
        self.tooltip = tooltip_text(lines)

    def set_browser_running(self, running: bool) -> None:
        self.running = running

    def set_download_active(self, active: bool) -> None:
        self.active = active

    def set_theme(self, theme: str) -> None:
        """The marks of the tray menu are drawn again with the theme (spec 4.3 p.4)."""
        self.theme = theme


class FakeSniffer:
    """Stand-in of the browser thread: the window reads only its running state."""

    def __init__(self, running: bool = True) -> None:
        self._running = running
        self.navigated: list[str] = []

    def isRunning(self) -> bool:
        return self._running

    def go(self, url: str) -> None:
        # The real thread takes the address from the queue of its pump loop (spec 4.2).
        self.navigated.append(url)

    def stop(self) -> None:
        self._running = False

    def wait(self, milliseconds: int) -> bool:
        return True


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


def test_browser_button_is_one_toggle_of_the_top_panel(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    # One button says what it will do: the thread is not up, so the label is
    # «Open browser», and the press asks app.py to start it (spec 4.3).
    assert window.browser_button.text() == tr("window_open_browser")
    assert window.browser_button.isEnabled()
    with qtbot.waitSignal(window.browser_toggle_request):
        window.browser_button.click()
    window.set_browser_running(True)
    assert window.browser_button.text() == tr("window_close_browser")
    assert window.browser_button.toolTip() == tr("window_close_browser_tip")
    # The same button is clickable in both states: it closes the window.
    assert window.browser_button.isEnabled()
    with qtbot.waitSignal(window.browser_toggle_request):
        window.browser_button.click()


def test_browser_closed_by_the_user_allows_to_open_it_again(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.set_browser_running(True)
    window._browser_closed()
    assert window.browser_button.text() == tr("window_open_browser")
    assert window.browser_button.isEnabled()
    # The running download is not stopped by the closed browser window (spec 3.7).
    assert window.worker is None


def test_the_browser_button_waits_for_the_launch(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    # Resolving the browser, the settings and the offer to download Chromium are on
    # the click, so a second press during the launch would start a second thread of
    # Playwright (spec 4.3 p.2): the button is disabled while it is starting.
    window.set_browser_starting(True)
    assert not window.browser_button.isEnabled()
    assert window.browser_button.toolTip() == tr("window_browser_starting")
    window.set_browser_starting(False)
    assert window.browser_button.isEnabled()
    assert window.browser_button.toolTip() == tr("window_open_browser_tip")
    # The state of the window is kept across the launch: the thread is up, so the
    # button goes back to «Close browser» when the launch is over.
    window.sniffer = FakeSniffer(running=True)
    window.set_browser_running(True)
    window.set_browser_starting(True)
    window.set_browser_starting(False)
    assert window.browser_button.text() == tr("window_close_browser")
    assert window.browser_button.toolTip() == tr("window_close_browser_tip")
    assert window.browser_button.isEnabled()


def painted(icon: QIcon) -> int:
    """The pixels a painted mark covers: an empty icon gives zero."""
    image = icon.pixmap(ICON_SIZE, ICON_SIZE).toImage()
    return sum(
        1
        for y in range(ICON_SIZE)
        for x in range(ICON_SIZE)
        if image.pixelColor(x, y).alpha() > 200
    )


def test_the_buttons_of_the_window_carry_their_marks(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    # Every button of the window is drawn by hand: the glyph of a font is not in the
    # UI font of Windows, so «⚙» shows a box (spec 4.3 p.2).
    buttons = window.findChildren(QAbstractButton)
    assert len(buttons) >= 8
    for button in buttons:
        assert not button.icon().isNull(), button.text()
        assert painted(button.icon()) > 10, button.text()


def test_the_buttons_of_a_card_carry_their_marks(qtbot):
    card = SourceCard(entry("s1"))
    qtbot.addWidget(card)
    for button in (
        card.download_button,
        card.cancel_button,
        card.open_button,
        card.retry_button,
        card.remove_button,
    ):
        assert not button.icon().isNull(), button
        assert painted(button.icon()) > 10, button
    # A QToolButton shows the icon only by default: the text of «Cancel» has to stay
    # next to the mark, or the button of a card loses its label (spec 4.1 p.4).
    for button in (card.cancel_button, card.open_button, card.retry_button):
        assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon


def test_the_buttons_of_the_settings_dialog_carry_their_marks(qtbot):
    dialog = SettingsDialog(Settings())
    qtbot.addWidget(dialog)
    # The check boxes and the combos draw their own marks in the stylesheet, only
    # the buttons of the dialog carry a painted icon (spec 4.3 p.2).
    buttons = dialog.findChildren(QPushButton)
    assert len(buttons) >= 4
    for button in buttons:
        assert not button.icon().isNull(), button.text()
        assert painted(button.icon()) > 10, button.text()


def test_the_two_states_of_the_browser_button_are_one_window():
    white = QColor("#ffffff")
    opening = browser_icon(white, True).pixmap(ICON_SIZE, ICON_SIZE).toImage()
    closing = browser_icon(white, False).pixmap(ICON_SIZE, ICON_SIZE).toImage()
    # The frame, the title bar and the globe of the page are the same drawing in both
    # icons: only the mark on the right of the title bar changes, so the button is
    # read as the browser of the program in both states (spec 4.3).
    for y in range(6, ICON_SIZE):
        for x in range(ICON_SIZE):
            assert opening.pixelColor(x, y) == closing.pixelColor(x, y)
    assert painted(browser_icon(white, True)) > 10
    assert painted(browser_icon(white, False)) > 10


def test_the_color_of_the_marks_follows_the_theme():
    # The buttons of the accent carry the white mark, the buttons of the panel carry
    # the color of the text of the theme (spec 4.3 p.2).
    assert icon_color("accent", "dark") == QColor("#ffffff")
    assert icon_color("accent", "light") == QColor("#ffffff")
    for theme in ("dark", "light"):
        assert icon_color("panel", theme) == color_for(theme, "text")
    # The system theme has no stylesheet: the mark takes the color of the palette.
    assert icon_color("panel", "system").isValid()


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
    # One item of the menu for the browser, as the button of the window: the text
    # says what the item will do, so nothing is disabled in the menu (spec 4.3).
    assert tray.browser_action.text() == tr("window_open_browser")
    assert tray.browser_action.isEnabled()
    tray.set_browser_running(True)
    assert tray.browser_action.text() == tr("window_close_browser")
    assert tray.browser_action.isEnabled()
    assert tray.contextMenu().actions()[0] is tray.show_action
    # The console panel is in the menu, so the hidden panel is opened from the tray
    # (spec 4.2 p.5): the menu has the six items of the window.
    assert tray.console_action.text() == tr("window_open_console")
    assert len(tray.contextMenu().actions()) == 6


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
    # whole window, which is what a person picking a video needs (spec 4.2 p.5). The
    # row of the console is one section with the panel, so hidden there is no row
    # and no divider of the splitter.
    assert not window.console.isVisible()
    assert not window.console_section.isVisible()
    assert not window.console_clear.isVisible()
    assert not window.log_button.isVisible()
    assert window.console_button.text() == tr("console_show")
    assert window.splitter.handleWidth() == 0
    hidden = window.splitter.sizes()
    assert hidden[1] == 0

    window.toggle_console()
    # «Clear» and «Open log file» belong to the panel, so they appear with it.
    assert window.console.isVisible()
    assert window.console_section.isVisible()
    assert window.console_clear.isVisible()
    assert window.log_button.isVisible()
    shown = window.splitter.sizes()
    assert shown[1] > SPLIT_CONSOLE_MIN + 40
    assert window.splitter.handleWidth() == CONSOLE_HANDLE
    assert window.settings.console_open
    assert window.console_button.text() == tr("console_hide")

    window.toggle_console()
    assert not window.console.isVisible()
    assert not window.console_section.isVisible()
    assert not window.console_clear.isVisible()
    assert not window.log_button.isVisible()
    assert window.settings.console_open is False


def test_the_top_row_carries_the_console_toggle_and_the_folder(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    # The commands of the window are in the header: the toggle of the console and the
    # downloads folder; «Open log file» is the row of the panel, so it is on the
    # screen only while the console is shown (spec 4.2 p.5). The two buttons of the
    # list are in the right end of the same row.
    header = window.splitter.widget(0)
    assert window.console_button.parent() is header
    assert window.folder_button.parent() is header
    assert window.log_button.parent() is window.console_section
    assert not window.log_button.isVisibleTo(window)
    assert window.folder_button.isVisibleTo(window)
    row = window.settings_button.geometry()
    assert window.clear_all_button.geometry().top() == row.top()
    assert window.clear_all_button.geometry().left() > row.right()
    window.toggle_console()
    assert window.log_button.isVisibleTo(window)
    assert window.console_button.text() == tr("console_hide")
    # The row of the list is not the console: it stays on the screen without the panel.
    assert window.clear_all_button.isVisibleTo(window)
    assert window.clear_downloaded_button.isVisibleTo(window)


def test_the_card_area_wall_follows_the_theme(qtbot, qapp, tmp_path):
    """The wall behind the cards is the background of the theme, not the palette.

    A plain `QWidget` paints the color of the palette of the style, which is not the
    color of the theme, so the list of cards stayed dark in the light theme (spec 4.3).
    """
    for theme, want in (("light", LIGHT["background"]), ("dark", DARK["background"])):
        settings = Settings(download_dir=str(tmp_path), theme=theme)
        window = MainWindow(settings, default_paths(downloads_dir=tmp_path), None, None)
        qtbot.addWidget(window)
        apply_theme(qapp, theme)
        window.resize(900, 600)
        window.show()
        # The container of the cards has no card in it, so the wall is on the screen.
        color = window.card_container.grab().toImage().pixelColor(120, 300)
        assert QColor(want).getRgb()[:3] == (color.red(), color.green(), color.blue())
        window.close()


def test_the_clear_buttons_are_the_right_end_of_the_top_row(qtbot, tmp_path):
    """«Clear downloaded» is yellow, «Clear all» is red, in the right corner of the top row.

    The colors are the keys of the theme and the QSS rules of the object names, so
    the two actions of the list are told apart by the color in the dark theme, the
    light theme and the screenshots (spec 4.1 p.1).
    """
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.show()
    yellow = window.clear_downloaded_button.geometry()
    red = window.clear_all_button.geometry()
    # The yellow is the left button, the red is the right one, both in the row of the
    # commands of the window, after the four blue buttons of the corner.
    assert yellow.right() < red.left()
    assert yellow.top() == red.top()
    assert yellow.left() > window.settings_button.geometry().right()
    assert window.clear_downloaded_button.objectName() == "clearDownloaded"
    assert window.clear_all_button.objectName() == "clearAll"
    # The colors of the buttons are the colors of the theme.
    dark = qss_for("dark")
    assert DARK["warn"] in dark
    assert DARK["danger"] in dark
    assert "#clearDownloaded" in dark
    assert "#clearAll" in dark
    light = qss_for("light")
    assert LIGHT["warn"] in light
    assert LIGHT["danger"] in light
    # The mark of a button takes the color of the text of that button: the dark of
    # the theme on the yellow, white on the red (spec 4.3).
    assert window._warn.name().lower() == DARK["warn_text"]
    assert window._danger.name().lower() == DARK["danger_text"]


def test_the_commands_of_the_window_are_in_the_upper_left_corner(qtbot, tmp_path):
    """The four commands stand in the upper-left corner, in one row, in their order.

    The row used to be pushed to the right by the label «Found videos», and the label
    is gone: the row of the commands starts at the left margin of the section, so the
    first button a person sees is the browser (spec 4.2 p.4).
    """
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.show()
    order = [
        window.browser_button,
        window.console_button,
        window.folder_button,
        window.settings_button,
    ]
    lefts = [b.geometry().left() for b in order]
    assert lefts == sorted(lefts)
    # The row is the first thing on the screen, at the left edge.
    assert order[0].geometry().left() <= 12
    assert all(b.geometry().bottom() == order[0].geometry().bottom() for b in order)


def test_the_row_under_the_commands_is_the_address_field_with_go(qtbot, tmp_path):
    """The row of the address is under the commands: the field and the «Go» button.

    The link is pasted in the window itself, so a download starts without opening the
    browser and typing the address inside it: the field takes the whole row, the
    button is at its right end, and the row of the console stays below (spec 4.2 p.4).
    """
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.show()
    header = window.splitter.widget(0)
    assert window.url_input.parent() is header
    assert window.go_button.parent() is header
    assert window.url_input.geometry().top() > window.settings_button.geometry().bottom()
    assert window.go_button.geometry().left() > window.url_input.geometry().right()
    assert window.url_input.placeholderText() == tr("window_url_placeholder")
    # A link longer than the field is read in the tooltip.
    long_url = "https://www.youtube.com/watch?v=" + "x" * 60
    window.url_input.setText(long_url)
    assert window.url_input.toolTip() == long_url


def test_go_sends_the_address_of_the_field_to_the_running_browser(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    sniffer = FakeSniffer(running=True)
    window.sniffer = sniffer
    window.url_input.setText("https://www.youtube.com/watch?v=abc")
    window.go_button.click()
    assert sniffer.navigated == ["https://www.youtube.com/watch?v=abc"]
    # The page of the browser is remembered, so «Open browser» opens the same site.
    assert window.last_url == "https://www.youtube.com/watch?v=abc"


def test_go_of_the_link_the_browser_is_on_says_so(qtbot, tmp_path, monkeypatch):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    sniffer = FakeSniffer(running=True)
    window.sniffer = sniffer
    window.last_url = "https://site.example/watch"
    window.url_input.setText("https://site.example/watch")
    messages: list[str] = []
    monkeypatch.setattr(window, "log_info", messages.append)
    window.go_button.click()
    assert sniffer.navigated == []
    assert messages == [tr("go_same_page")]


def test_go_launches_the_browser_when_the_browser_is_down(qtbot, tmp_path):
    """A domain pasted without the protocol is a page address as well (spec 4.2 p.4)."""
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    requests: list[str] = []
    window.browser_open_request.connect(requests.append)
    window.url_input.setText("youtube.com/watch?v=1")
    window.go_button.click()
    assert requests == ["https://youtube.com/watch?v=1"]


def test_go_without_a_link_says_that_the_field_is_empty(qtbot, tmp_path, monkeypatch):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.sniffer = FakeSniffer(running=True)
    messages: list[str] = []
    monkeypatch.setattr(window, "log_info", messages.append)
    window.go_button.click()
    assert messages == [tr("go_url_missing")]
    assert window.sniffer.navigated == []


def test_the_window_opens_with_the_console_the_user_left(qtbot, tmp_path):
    settings = Settings(download_dir=str(tmp_path), console_open=True)
    paths = default_paths(downloads_dir=tmp_path)
    window = MainWindow(settings, paths, None, None)
    qtbot.addWidget(window)
    window.show()
    # The state of the panel is stored in the settings, so the window opens the way
    # the user left it (spec 4.2 p.1), and the button in the top row says how to hide
    # the console. The row of the console is shown with the panel.
    assert window.console.isVisible()
    assert window.console_section.isVisible()
    assert window.console_clear.isVisible()
    assert window.log_button.isVisible()
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


def test_the_tray_marks_the_running_download_and_reports_the_end_of_a_batch(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    tray = FakeTray()
    window.tray = tray
    heard: list[int] = []
    window.play_sound = lambda: heard.append(1)
    worker = FakeWorker()
    window.worker = worker

    window.add_source(entry("s1"))
    window.add_source(entry("s2"))
    window._start_download("s1")
    window._start_download("s2")
    # The green arrow: the program downloads while the window is minimized (spec 4.2 p.7).
    assert tray.active is True

    # The first file of a batch is not its end: a task is left in the queue, so the
    # balloon and the sound stay away, and the arrow of the tray keeps the green mark.
    window._task_finished("s1", str(tmp_path / "a.mp4"))
    assert tray.active is True
    assert tray.hints == []
    assert heard == []

    # The last task leaves the queue before it is reported: the batch is over, so one
    # balloon for the whole batch and one sound (spec 4.2 p.7).
    worker.queued.clear()
    window._task_finished("s2", str(tmp_path / "b.mp4"))
    assert tray.active is False
    assert tray.hints == [tr("tray_download", n=2)]
    assert heard == [1]


def test_a_single_download_gives_no_balloon_and_no_sound(qtbot, tmp_path):
    """One download is not a batch: the icon goes quiet, the balloon stays away (spec 4.2 p.7)."""
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
    worker.queued.clear()
    window._task_finished("s1", str(tmp_path / "a.mp4"))
    assert tray.active is False
    assert tray.hints == []
    assert heard == []

    # The counter is per batch: the next single download starts from 0, so a row of
    # single downloads never becomes the report of a finished batch.
    window.add_source(entry("s2"))
    window._start_download("s2")
    worker.queued.clear()
    window._task_finished("s2", str(tmp_path / "b.mp4"))
    assert tray.hints == []
    assert heard == []


def test_removing_cards_gives_no_balloon_and_no_sound(qtbot, tmp_path):
    """The user downloaded nothing: taking cards out of the list is not a batch (spec 4.2 p.7)."""
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    tray = FakeTray()
    window.tray = tray
    heard: list[int] = []
    window.play_sound = lambda: heard.append(1)
    worker = FakeWorker()
    window.worker = worker

    window.add_source(entry("s1"))
    window.add_source(entry("s2"))
    for entry_id in ("s1", "s2"):
        window.cards[entry_id].remove_button.click()
    assert window.cards == {}
    assert tray.hints == []
    assert heard == []

    # Clearing the list is the same: the queue drains with no finished file.
    window.add_source(entry("s3"))
    window.clear_all_cards()
    assert tray.hints == []
    assert heard == []


def test_a_failed_task_gives_no_balloon(qtbot, tmp_path):
    """A batch that ends with an error is not the end of all downloads (spec 4.2 p.7)."""
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    tray = FakeTray()
    window.tray = tray
    heard: list[int] = []
    window.play_sound = lambda: heard.append(1)
    worker = FakeWorker()
    window.worker = worker

    window.add_source(entry("s1"))
    window.add_source(entry("s2"))
    window._start_download("s1")
    window._start_download("s2")
    window._task_finished("s1", str(tmp_path / "a.mp4"))
    worker.queued.clear()
    window._task_failed("s2", "HTTP 410: the signed link expired")
    assert tray.active is False
    assert tray.hints == []
    assert heard == []


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
    assert "Мой клип" in tray.tooltip
    assert tr("tray_tooltip_queued", n=1) in tray.tooltip

    # The throttle of the tooltip is over, so the next progress is written.
    window._tooltip_due = 0.0
    window._task_progress("s1", 2, 4)
    assert "50%" in tray.tooltip

    worker.queued.clear()
    window._task_finished("s1", str(tmp_path / "a.mp4"))
    # Nothing is downloading: the tooltip has no queue lines left.
    assert tray.lines == []


def test_the_tooltip_of_a_long_task_name_keeps_the_percent(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    tray = FakeTray()
    window.tray = tray
    worker = FakeWorker()
    window.worker = worker

    long = "Очень длинный клип, имя которого не входит в подсказку " * 4
    window.add_source(entry("s1"))
    window._start_download("s1")
    window._task_started("s1", long)

    # Windows keeps the tooltip of the icon in 128 characters, and the point of the
    # tooltip is the percent of the task: the name is cut, the percent stays on the
    # screen (spec 4.2 p.7).
    text = tray.tooltip
    assert len(text) <= TOOLTIP_LIMIT
    assert "0%" in text
    assert ELLIPSIS in text
    assert long not in text
    assert BASE_TOOLTIP in text


def test_a_long_queue_shows_the_percent_of_every_line_of_the_tooltip(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    tray = FakeTray()
    window.tray = tray
    worker = FakeWorker()
    window.worker = worker

    for i in range(4):
        name = f"клип номер {i} " * 20
        window.add_source(entry(f"s{i}"))
        window._start_download(f"s{i}")
        window._task_started(f"s{i}", name)

    # The budget of characters is spent on the report of the queue first: every task
    # that stays in the tooltip shows its percent, none is a line of pure name.
    text = tray.tooltip
    assert len(text) <= TOOLTIP_LIMIT
    tasks = text.split("\n")[2:]
    assert len(tasks) == 4
    for line in tasks:
        assert "%" in line
        assert ELLIPSIS in line


def test_the_tooltip_of_a_long_queue_never_grows_past_the_length_windows_keeps():
    names = [("имя " * 40, "имя " * 40 + " — 42% · 3.1 MB/s · осталось 0:20") for _ in range(6)]
    text = tooltip_text(names)
    # The last lines are the ones that do not fit: the tooltip ends with the percent
    # of a task, not with the tail of a name (spec 4.2 p.7).
    assert len(text) <= TOOLTIP_LIMIT
    lines = text.split("\n")
    assert all("%" in line for line in lines[2:])
    assert lines[0] == BASE_TOOLTIP


def test_the_real_tray_icon_shows_the_percent_of_a_long_name(qtbot, tmp_path):
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    tray = TrayController(window, None)
    long = "Очень длинный клип " * 30
    info = RunInfo(long, 100 * 1024 * 1024, 42, 0.0)
    tray.set_progress_lines([(long, tray_speed_line(info, 10.0))])
    text = tray.toolTip()
    assert len(text) <= TOOLTIP_LIMIT
    assert "42%" in text
    assert ELLIPSIS in text


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
    assert "Мой клип" in tray.tooltip

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
    # The browser thread is not running yet: the item of the menu says «Open browser».
    assert tray.browser_action.text() == tr("window_open_browser")


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
