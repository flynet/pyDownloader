"""Рисует снимки главного окна и диалога настроек для README.

Запуск: ``uv run python tools/make_screenshots.py``. Снимки пишутся в
``assets/screenshots`` и коммитятся, чтобы GitHub показывал внешний вид
программы без запуска. Ни браузера, ни загрузок здесь нет: карточки и консоль
заполняются демонстрационными данными, поэтому снимки воспроизводимы.

Окна не показываются на рабочем столе: снимок берётся ``QWidget.grab()`` на
offscreen-платформе Qt, а шрифты Windows регистрируются в приложении вручную —
без них кириллица рисуется квадратиками.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Заводится до импорта Qt: снимки рисуются без окна на рабочем столе.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from pydownloader.config.paths import Paths, default_paths
from pydownloader.config.settings import Settings
from pydownloader.manifest.registry import SourceEntry
from pydownloader.ui.main_window import MainWindow
from pydownloader.ui.settings_panel import SettingsDialog
from pydownloader.ui.theme import apply_theme

OUT = Path("assets") / "screenshots"
DOWNLOADS = Path("D:\\Видео")
#: Version printed in the console lines: the screenshots are for the release page,
#: so the tag is written out and stays stable between runs.
DISPLAY_VERSION = "0.2.0"
WINDOW_SIZE = (1060, 860)
#: Splitter sizes of the screenshot: the four demo cards and a dozen console lines.
CARD_SECTION_HEIGHT = (640, 220)
UI_FONT = "Segoe UI"
#: The offscreen platform has no font database: the Cyrillic text becomes boxes
#: until the fonts of Windows are registered in the application.
UI_FONT_SIZE = 9
MONOSPACE_FONT = "Consolas"
WINDOWS_FONTS = (
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/segoeui-bold.ttf",
    "C:/Windows/Fonts/consola.ttf",
)


def demo_cards() -> list[SourceEntry]:
    """Карточки в четырёх состояниях: найдено, скачивается, готово, ошибка."""
    entries = [
        SourceEntry(
            id="hls1080",
            kind="hls",
            url="https://cdn.example.com/720p_1080p/master.m3u8",
            normalized="https://cdn.example.com/720p_1080p/master.m3u8",
            title="Пример: HLS 1080p",
            height=1080,
            duration=1874.0,
            size=412_321_024,
        ),
        SourceEntry(
            id="hls720",
            kind="hls",
            url="https://cdn.example.com/pornhub/720p_1080p/master.m3u8",
            normalized="https://cdn.example.com/pornhub/720p_1080p/master.m3u8",
            title="Пример: HLS 720p, качается",
            height=720,
            duration=620.0,
            size=96_205_824,
        ),
        SourceEntry(
            id="mp4",
            kind="mp4",
            url="https://cdn.example.com/video/clip.mp4",
            normalized="https://cdn.example.com/video/clip.mp4",
            title="Пример: MP4",
            duration=240.0,
            size=84_000_000,
        ),
        SourceEntry(
            id="yt",
            kind="youtube",
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            normalized="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            title="Пример: YouTube",
            height=1080,
            duration=320.0,
            size=45_101_824,
        ),
    ]
    return entries


def fill_console(window: MainWindow) -> None:
    """Строки консоли: запуск, находка потока, пропуски, готовый файл."""
    console = window.console
    console.show_info(f"PyDownloader {DISPLAY_VERSION}, папка загрузок: {DOWNLOADS}")
    console.show_info("Лог-файл: D:\\PyDownloader\\logs\\app.log")
    console.show_info("Профиль браузера: D:\\PyDownloader\\profile")
    console.show_info("FFmpeg: D:\\PyDownloader\\bin\\ffmpeg.exe")
    console.show_info("Блокировщик рекламы подключён: uBlock Origin Lite")
    console.show_info("Найден HLS-поток 1080p: https://cdn.example.com/720p_1080p/master.m3u8")
    console.show_info("Показано в списке: https://cdn.example.com/720p_1080p/master.m3u8")
    console.show_info("Найден MP4 80.1 МБ: https://cdn.example.com/video/clip.mp4")
    console.show_warning("Live-трансляция: пропущен (https://cdn.example.com/live/master.m3u8)")
    console.show_warning("Widevine DRM: обход не поддерживается (system=widevine)")
    console.show_info("Вариант 1080p недоступен, скачиваю 720p")
    console.show_info("Готово: D:\\Видео\\clip_1080p.mp4")


def fill_cards(window: MainWindow) -> None:
    """Карточки: состояния «найдено», «скачивается», «готово», «ошибка»."""
    for entry in demo_cards():
        window.add_source(entry)
    cards = list(window.cards.values())
    cards[0].set_state("new")
    cards[1].set_state("downloading")
    cards[1].set_progress(204, 340, 3.8)
    cards[2].set_result(str(DOWNLOADS / "clip_1080p.mp4"))
    window.out_paths["mp4"] = DOWNLOADS / "clip_1080p.mp4"
    cards[3].set_error("HTTP 410: ссылка CDN протухла")


def shot(widget, name: str) -> None:
    """Снимок виджета в файл ``assets/screenshots/<name>``."""
    widget.show()
    widget.grab().save(str(OUT / name))
    widget.hide()


def register_fonts() -> None:
    """Add the fonts of Windows so the Cyrillic letters are drawn."""
    for path in WINDOWS_FONTS:
        if Path(path).is_file():
            QFontDatabase.addApplicationFont(path)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    register_fonts()
    app.setFont(QFont(UI_FONT, UI_FONT_SIZE))
    settings = Settings(download_dir=str(DOWNLOADS), theme="dark", threads=6, target_height=1080)
    apply_theme(app, settings.theme)
    paths: Paths = default_paths()
    window = MainWindow(settings, paths, None, None)
    window.console.setFont(QFont(MONOSPACE_FONT, UI_FONT_SIZE))
    window.resize(*WINDOW_SIZE)
    window.set_update_status("Обновлений нет · 08:12")
    # The status bar of the build in git says ``0.0.0-dev``; on the release page the
    # version of the tag is shown instead.
    window.status_label.setText(f"{DISPLAY_VERSION} · {settings.download_dir}")
    fill_cards(window)
    fill_console(window)
    # All four cards fit the upper section, and the console keeps its twelve lines.
    window.splitter.setSizes(list(CARD_SECTION_HEIGHT))
    shot(window, "window.png")

    dialog = SettingsDialog(settings, window)
    shot(dialog, "settings.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
