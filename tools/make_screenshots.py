"""Рисует снимки главного окна и диалога настроек для README.

Запуск: ``uv run python tools/make_screenshots.py``. Снимки пишутся в
``assets/screenshots`` и коммитятся, чтобы GitHub показывал внешний вид
программы без запуска. Ни браузера, ни загрузок здесь нет: карточки и консоль
заполняются демонстрационными данными, поэтому снимки воспроизводимы.

Язык снимков — английский, язык программы по умолчанию (spec 8.1). Все строки
берутся из каталога переводов, поэтому снимок совпадает с тем, что видит
пользователь.

Окно снимков сохраняет настройки, поэтому рисование запускается со своими
``%APPDATA%``, ``%LOCALAPPDATA%`` и временной папкой: файл настроек
пользователя от запуска снимков не меняется (spec 7.4).

Окна не показываются на рабочем столе: снимок берётся ``QWidget.grab()`` на
offscreen-платформе Qt, а шрифты Windows регистрируются в приложении вручную —
без них текст рисуется квадратиками.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Заводится до импорта Qt: снимки рисуются без окна на рабочем столе.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from pydownloader.config.paths import Paths, default_paths, isolate_app_data
from pydownloader.config.settings import Settings
from pydownloader.i18n import DEFAULT_LANGUAGE, set_language, tr
from pydownloader.manifest.registry import SourceEntry
from pydownloader.ui.main_window import MainWindow
from pydownloader.ui.settings_panel import SettingsDialog
from pydownloader.ui.theme import apply_theme

OUT = Path("assets") / "screenshots"
DOWNLOADS = Path("D:\\Videos")
#: Version printed in the console lines: the screenshots are for the release page,
#: so the tag is written out and stays stable between runs.
DISPLAY_VERSION = "0.4.6"
WINDOW_SIZE = (1060, 860)
#: Splitter sizes of the screenshot: the five demo cards, the row of the console
#: buttons and a dozen console lines.
CARD_SECTION_HEIGHT = (690, 170)
UI_FONT = "Segoe UI"
#: The offscreen platform has no font database: the letters become boxes
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
    return [
        SourceEntry(
            id="hls1080",
            kind="hls",
            url="https://cdn.example.com/720p_1080p/master.m3u8",
            normalized="https://cdn.example.com/720p_1080p/master.m3u8",
            title="Example: HLS 1080p",
            height=1080,
            duration=1874.0,
            size=412_321_024,
        ),
        SourceEntry(
            id="hls720",
            kind="hls",
            url="https://cdn.example.com/site/720p_1080p/master.m3u8",
            normalized="https://cdn.example.com/site/720p_1080p/master.m3u8",
            title="Example: HLS 720p, downloading",
            height=720,
            duration=620.0,
            size=96_205_824,
        ),
        SourceEntry(
            id="mp4",
            kind="mp4",
            url="https://cdn.example.com/video/clip.mp4",
            normalized="https://cdn.example.com/video/clip.mp4",
            title="Example: MP4",
            duration=240.0,
            size=84_000_000,
        ),
        SourceEntry(
            id="mp3",
            kind="mp4",
            url="https://cdn.example.com/audio/track.mp3",
            normalized="https://cdn.example.com/audio/track.mp3",
            title="Example: SoundCloud audio",
            duration=212.0,
            size=5_200_000,
            is_audio=True,
        ),
        SourceEntry(
            id="yt",
            kind="youtube",
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            normalized="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            title="Example: YouTube",
            height=1080,
            duration=320.0,
            size=45_101_824,
        ),
    ]


def fill_console(window: MainWindow) -> None:
    """Строки консоли из каталога: запуск, находка потока, пропуски, готовый файл."""
    console = window.console
    log_file = Path("D:\\PyDownloader\\logs\\app.log")
    console.show_info(tr("app_started", version=DISPLAY_VERSION, dir=DOWNLOADS))
    console.show_info(tr("app_log_file", path=log_file))
    console.show_info(tr("app_profile_dir", path=Path("D:\\PyDownloader\\profile")))
    console.show_info(tr("app_data_dir", path=Path("D:\\PyDownloader\\extensions")))
    console.show_info(tr("app_blocker_state", state=tr("app_blocker_on")))
    console.show_info(
        tr("mf_found_hls", height=1080, url="https://cdn.example.com/720p_1080p/master.m3u8")
    )
    console.show_info(tr("window_shown", url="https://cdn.example.com/720p_1080p/master.m3u8"))
    console.show_info(tr("mf_found_mp4", quality="80.1 MB", url="https://cdn.example.com/video/clip.mp4"))
    console.show_info(tr("mf_found_audio", url="https://cdn.example.com/audio/master.m3u8"))
    console.show_info(tr("mf_found_mp4", quality="MP3", url="https://cdn.example.com/audio/track.mp3"))
    console.show_warning(tr("mf_live_skipped", url="https://cdn.example.com/live/master.m3u8"))
    console.show_warning(tr("dl_drm_detected", message=tr("mf_drm_message"), system="Widevine"))
    console.show_info(
        tr("dl_variant_fallback", height=1080, fallback=720, url="https://cdn.example.com/720p/master.m3u8")
    )
    console.show_info(tr("window_finished", path=DOWNLOADS / "clip_1080p.mp4"))
    console.show_info(tr("window_finished", path=DOWNLOADS / "sound.mp3"))


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
    # The audio card keeps the MP3 badge of an audio source (spec 5.2 p.4).
    cards[3].set_state("new")
    cards[4].set_error("HTTP 410: the signed CDN link expired")


def shot(widget, name: str) -> None:
    """Снимок виджета в файл ``assets/screenshots/<name>``."""
    widget.show()
    widget.grab().save(str(OUT / name))
    widget.hide()


def register_fonts() -> None:
    """Add the fonts of Windows so the letters of every language are drawn."""
    for path in WINDOWS_FONTS:
        if Path(path).is_file():
            QFontDatabase.addApplicationFont(path)


def main() -> int:
    # Настройки пишутся в дерево снимков, файл пользователя не трогается (spec 7.4).
    isolate_app_data()
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    register_fonts()
    app.setFont(QFont(UI_FONT, UI_FONT_SIZE))
    # the screenshots show the language the program starts with (spec 8.1)
    set_language(DEFAULT_LANGUAGE)
    settings = Settings(
        download_dir=str(DOWNLOADS),
        theme="dark",
        language=DEFAULT_LANGUAGE,
        threads=6,
        target_height=1080,
        # The screenshot shows the console section: its row of buttons is on the
        # screen only with the panel, so the panel has to be open for the picture.
        console_open=True,
    )
    apply_theme(app, settings.theme)
    paths: Paths = default_paths()
    window = MainWindow(settings, paths, None, None)
    window.console.setFont(QFont(MONOSPACE_FONT, UI_FONT_SIZE))
    window.resize(*WINDOW_SIZE)
    window.set_update_status(tr("update_none", time="08:12"))
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
