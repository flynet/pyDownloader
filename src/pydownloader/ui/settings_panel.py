"""Settings dialog (spec 4.3, 8.1): the values are saved in ``settings.json``.

Fields: download folder, number of segment threads, target height, minimum MP4
size, language, theme, automatic update check. The dialog is opened from the
window; it does not write the settings until the user presses «Сохранить».
The language is applied at startup, so the dialog offers a restart (spec 8.1).
"""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pydownloader.config.paths import download_dir_default
from pydownloader.config.settings import (
    BROWSERS,
    MP3_BITRATES,
    QUALITY_PRESETS,
    THEMES,
    BrowserName,
    Settings,
    ThemeName,
)
from pydownloader.i18n import LANGUAGE_NAMES, SUPPORTED_LANGUAGES, Language, current_language, tr
from pydownloader.ui.button_icons import (
    attach,
    check_icon,
    cross_icon,
    folder_icon,
    icon_color,
    retry_icon,
)

MIN_THREADS = 1
MAX_THREADS = 16
#: The dialog takes most of the main window: a long download path must fit.
DIALOG_WIDTH_RATIO = 0.8
DIALOG_HEIGHT_RATIO = 0.8
MIN_DIALOG_WIDTH = 640
#: The floor of the height of the dialog. Every row of the form sets its own floor
#: (``_set_row_floor``), so the dialog cannot be squeezed under the height the font
#: of the rows asks for; this number is the least height the dialog gets, so a small
#: main window does not make the dialog unreadable (spec 4.3 p.2).
MIN_DIALOG_HEIGHT = 420
#: Theme value -> the key of its name (the value itself stays in the settings).
THEME_KEYS: dict[ThemeName, str] = {
    "dark": "theme_dark",
    "light": "theme_light",
    "cartoons": "theme_cartoons",
    "neon": "theme_neon",
    "pink": "theme_pink",
    "system": "theme_system",
}
#: Browser value -> the key of its name, the names are the ones the vendors use.
BROWSER_KEYS: dict[BrowserName, str] = {
    "auto": "browser_auto",
    "chrome": "browser_chrome",
    "msedge": "browser_edge",
    "chromium": "browser_chromium",
}


def _set_row_floor(layout: QLayout) -> None:
    """Give every widget of a layout the height its own text asks for.

    A field of the form has the minimum height of zero, so the layout can squeeze a
    row to 15 px: the letters of the text show half and cannot be read. The
    ``sizeHint`` of a widget is the height its font and its content ask for, and it
    becomes the floor of the widget, so the rows keep their height, the layout gets
    the minimum height it needs, and the dialog cannot be squeezed under it
    (spec 4.3 p.2).
    """
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            widget.setMinimumHeight(widget.sizeHint().height())
        inner = item.layout()
        if inner is not None:
            _set_row_floor(inner)


def theme_label(name: ThemeName) -> str:
    """Name of a theme in the current language."""
    return tr(THEME_KEYS[name])


def browser_label(name: BrowserName) -> str:
    """Name of a browser in the current language."""
    return tr(BROWSER_KEYS[name])


class SettingsDialog(QDialog):
    """A small form collecting the settings."""

    #: «Проверить обновления» asks the window to run the check (spec 8.3).
    check_requested = Signal()
    #: «Перезапустить» asks the window to start the program again (spec 8.1).
    restart_requested = Signal()

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("settings_title"))
        self.settings = settings
        #: The buttons of the dialog are of the accent of the theme, so the marks are white.
        self._accent = icon_color("accent", settings.theme)
        self._form = QFormLayout()
        self._form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.download_edit = QLineEdit(settings.download_dir or str(download_dir_default()))
        # A long path is wider than the field: the full text is visible on hover.
        self.download_edit.textChanged.connect(self.download_edit.setToolTip)
        self.download_edit.setToolTip(self.download_edit.text())
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.download_edit)
        browse = QPushButton(tr("settings_browse"))
        # The folder is the mark of the picker of the downloads folder (spec 4.3 p.2).
        attach(browse, folder_icon(self._accent))
        browse.clicked.connect(self._pick_folder)
        folder_row.addWidget(browse)
        self._form.addRow(tr("settings_folder_row"), folder_row)

        self.threads_box = QSpinBox()
        self.threads_box.setRange(MIN_THREADS, MAX_THREADS)
        self.threads_box.setValue(settings.threads)
        self._form.addRow(tr("settings_threads_row"), self.threads_box)

        # Quality presets (spec 5.2 p.3): the settings offer 1080, 720, 480, and the
        # match is exact, so a source of another height is not shown in the list.
        self.height_box = QComboBox()
        for preset in QUALITY_PRESETS:
            self.height_box.addItem(f"{preset}p", preset)
        if settings.target_height not in QUALITY_PRESETS:
            # A height from an edited settings.json is not silently dropped: the
            # combo gets one extra entry so saving keeps the value the user had.
            self.height_box.addItem(f"{settings.target_height}p", settings.target_height)
        self.height_box.setCurrentIndex(max(0, self.height_box.findData(settings.target_height)))
        self._form.addRow(tr("settings_height_row"), self.height_box)

        self.size_box = QSpinBox()
        self.size_box.setRange(1, 1024)
        self.size_box.setValue(max(1, settings.min_mp4_size // (1024 * 1024)))
        self._form.addRow(tr("settings_min_mp4_row"), self.size_box)

        # The bitrate of the MP3 file an audio source is written with (spec 5.2 p.4).
        self.bitrate_box = QComboBox()
        for rate in MP3_BITRATES:
            self.bitrate_box.addItem(f"{rate} kbps", rate)
        self.bitrate_box.setCurrentIndex(max(0, self.bitrate_box.findData(settings.mp3_bitrate)))
        self._form.addRow(tr("settings_bitrate_row"), self.bitrate_box)

        # «Audio only (MP3)»: the video sources are not shown in the list (spec 5.2 p.4).
        self.audio_check = QCheckBox(tr("settings_audio_only"))
        self.audio_check.setChecked(settings.audio_only)
        self._form.addRow("", self.audio_check)

        # The browser the program opens: «auto» is the order of spec 7.2, and the
        # Chromium of Playwright is the one that can load the ad blocker (spec 7.2).
        self.browser_box = QComboBox()
        for choice in BROWSERS:
            self.browser_box.addItem(browser_label(choice), choice)
        self.browser_box.setCurrentIndex(max(0, self.browser_box.findData(settings.browser_name)))
        self._form.addRow(tr("settings_browser_row"), self.browser_box)

        # The text a bot reads first; an empty field takes the Chrome form of the
        # version that is launched, so the field is a way to imitate a device.
        self.agent_edit = QLineEdit(settings.user_agent)
        self.agent_edit.setPlaceholderText(tr("settings_user_agent_hint"))
        self.agent_edit.textChanged.connect(self.agent_edit.setToolTip)
        self.agent_edit.setToolTip(self.agent_edit.text())
        self._form.addRow(tr("settings_user_agent_row"), self.agent_edit)

        self.anti_bot_check = QCheckBox(tr("settings_anti_bot"))
        self.anti_bot_check.setChecked(settings.anti_bot)
        self._form.addRow("", self.anti_bot_check)
        self.blocker_check = QCheckBox(tr("settings_ad_blocker"))
        self.blocker_check.setChecked(settings.ad_blocker)
        self._form.addRow("", self.blocker_check)

        # The name of a language is written in its own language, so the combo is
        # readable whatever the current language is (spec 8.1).
        self.language_box = QComboBox()
        for code in SUPPORTED_LANGUAGES:
            self.language_box.addItem(LANGUAGE_NAMES[code], code)
        self.language_box.setCurrentIndex(max(0, self.language_box.findData(settings.language)))
        self._form.addRow(tr("settings_language_row"), self.language_box)

        self.theme_box = QComboBox()
        for name in THEMES:
            self.theme_box.addItem(theme_label(name), name)
        self.theme_box.setCurrentIndex(max(0, self.theme_box.findData(settings.theme)))
        self._form.addRow(tr("settings_theme_row"), self.theme_box)

        # The tray keeps the program reachable when the window is hidden (spec 4.3).
        self.tray_check = QCheckBox(tr("settings_tray"))
        self.tray_check.setChecked(settings.tray_enabled)
        self._form.addRow("", self.tray_check)
        self.close_tray_check = QCheckBox(tr("settings_close_tray"))
        self.close_tray_check.setChecked(settings.close_to_tray)
        self._form.addRow("", self.close_tray_check)
        # The console panel: hidden, the list of videos takes the whole window (spec 4.2 p.5).
        self.console_check = QCheckBox(tr("settings_console"))
        self.console_check.setToolTip(tr("settings_console_tip"))
        self.console_check.setChecked(settings.console_open)
        self._form.addRow("", self.console_check)

        self.update_check = QCheckBox(tr("settings_check_updates"))
        self.update_check.setChecked(settings.auto_update)
        self._form.addRow("", self.update_check)

        layout = QVBoxLayout(self)
        layout.addLayout(self._form)

        # The language is chosen once at startup, so a change needs a restart.
        hint = QLabel(tr("settings_restart_hint"))
        hint.setObjectName("cardMeta")
        layout.addWidget(hint)

        buttons = QHBoxLayout()
        # The update commands are secondary, so they stand on the left. "Save" and
        # "Cancel" are the main buttons of the dialog: they are in the bottom-right
        # corner, where a person looks for the buttons that finish a dialog
        # (spec 4.3 p.2).
        self.update_check_button = QPushButton(tr("settings_check_updates_button"))
        # The arc of the arrow is the mark of the update check (spec 8.3).
        attach(self.update_check_button, retry_icon(self._accent))
        self.update_check_button.clicked.connect(self.check_requested.emit)
        self.restart_button = QPushButton(tr("settings_restart"))
        attach(self.restart_button, retry_icon(self._accent))
        self.restart_button.clicked.connect(self._restart)
        self.save_button = QPushButton(tr("settings_save"))
        # The check is the mark of the values written to settings.json (spec 4.3 p.2).
        attach(self.save_button, check_icon(self._accent))
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._accept)
        self.cancel_button = QPushButton(tr("settings_cancel"))
        attach(self.cancel_button, cross_icon(self._accent))
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.update_check_button)
        buttons.addWidget(self.restart_button)
        buttons.addStretch(1)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)

        # The restart is only useful when the chosen language is not the running one.
        self.language_box.currentIndexChanged.connect(self._refresh_restart)
        self._refresh_restart()

        self.setSizeGripEnabled(True)
        # The rows keep the height the font asks for, and the height of the dialog
        # cannot go under the height of the rows (spec 4.3 p.2).
        _set_row_floor(layout)
        floor = max(MIN_DIALOG_HEIGHT, layout.totalMinimumSize().height())
        self.setMinimumSize(MIN_DIALOG_WIDTH, floor)
        if parent is not None:
            window = parent.window()
            self.resize(
                max(MIN_DIALOG_WIDTH, round(window.width() * DIALOG_WIDTH_RATIO)),
                max(MIN_DIALOG_HEIGHT, round(window.height() * DIALOG_HEIGHT_RATIO)),
            )

    def _refresh_restart(self) -> None:
        """«Перезапустить» is useful only when the chosen language is not the running one."""
        self.restart_button.setEnabled(self.language_box.currentData() != current_language())

    def _restart(self) -> None:
        """Write the form into the settings and ask the window to start a new process."""
        self.apply_to(self.settings)
        self.accept()
        self.restart_requested.emit()

    def _pick_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, tr("settings_download_folder"), self.download_edit.text()
        )
        if path:
            self.download_edit.setText(path)

    def _accept(self) -> None:
        self.apply_to(self.settings)
        self.accept()

    def apply_to(self, target: Settings) -> Settings:
        """Write the values of the form into a settings object."""
        target.download_dir = self.download_edit.text().strip()
        target.threads = self.threads_box.value()
        target.target_height = int(self.height_box.currentData())
        target.min_mp4_size = self.size_box.value() * 1024 * 1024
        target.mp3_bitrate = int(self.bitrate_box.currentData())
        target.audio_only = self.audio_check.isChecked()
        target.theme = cast(ThemeName, self.theme_box.currentData())
        target.language = cast(Language, self.language_box.currentData())
        target.auto_update = self.update_check.isChecked()
        target.tray_enabled = self.tray_check.isChecked()
        target.close_to_tray = self.close_tray_check.isChecked()
        target.console_open = self.console_check.isChecked()
        target.browser_name = cast(BrowserName, self.browser_box.currentData())
        target.user_agent = self.agent_edit.text().strip()
        target.anti_bot = self.anti_bot_check.isChecked()
        target.ad_blocker = self.blocker_check.isChecked()
        return target


__all__ = [
    "BROWSER_KEYS",
    "THEME_KEYS",
    "SettingsDialog",
    "browser_label",
    "theme_label",
]
