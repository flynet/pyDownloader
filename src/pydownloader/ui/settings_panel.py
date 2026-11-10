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
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pydownloader.config.paths import download_dir_default
from pydownloader.config.settings import (
    BROWSERS,
    THEMES,
    BrowserName,
    Settings,
    ThemeName,
)
from pydownloader.i18n import LANGUAGE_NAMES, SUPPORTED_LANGUAGES, Language, current_language, tr

MIN_THREADS = 1
MAX_THREADS = 16
#: The dialog takes most of the main window: a long download path must fit.
DIALOG_WIDTH_RATIO = 0.8
DIALOG_HEIGHT_RATIO = 0.8
MIN_DIALOG_WIDTH = 640
MIN_DIALOG_HEIGHT = 420
#: Theme value -> the key of its name (the value itself stays in the settings).
THEME_KEYS: dict[ThemeName, str] = {
    "dark": "theme_dark",
    "light": "theme_light",
    "system": "theme_system",
}
#: Browser value -> the key of its name, the names are the ones the vendors use.
BROWSER_KEYS: dict[BrowserName, str] = {
    "auto": "browser_auto",
    "chrome": "browser_chrome",
    "msedge": "browser_edge",
    "chromium": "browser_chromium",
}


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
        self._form = QFormLayout()
        self._form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.download_edit = QLineEdit(settings.download_dir or str(download_dir_default()))
        # A long path is wider than the field: the full text is visible on hover.
        self.download_edit.textChanged.connect(self.download_edit.setToolTip)
        self.download_edit.setToolTip(self.download_edit.text())
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.download_edit)
        browse = QPushButton(tr("settings_browse"))
        browse.clicked.connect(self._pick_folder)
        folder_row.addWidget(browse)
        self._form.addRow(tr("settings_folder_row"), folder_row)

        self.threads_box = QSpinBox()
        self.threads_box.setRange(MIN_THREADS, MAX_THREADS)
        self.threads_box.setValue(settings.threads)
        self._form.addRow(tr("settings_threads_row"), self.threads_box)

        self.height_box = QSpinBox()
        self.height_box.setRange(144, 4320)
        self.height_box.setValue(settings.target_height)
        self._form.addRow(tr("settings_height_row"), self.height_box)

        self.size_box = QSpinBox()
        self.size_box.setRange(1, 1024)
        self.size_box.setValue(max(1, settings.min_mp4_size // (1024 * 1024)))
        self._form.addRow(tr("settings_min_mp4_row"), self.size_box)

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

        # The tray keeps the program running when the window is hidden (spec 4.3).
        self.tray_check = QCheckBox(tr("settings_tray"))
        self.tray_check.setChecked(settings.tray_enabled)
        self._form.addRow("", self.tray_check)
        self.close_tray_check = QCheckBox(tr("settings_close_tray"))
        self.close_tray_check.setChecked(settings.close_to_tray)
        self._form.addRow("", self.close_tray_check)

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
        save = QPushButton(tr("settings_save"))
        save.setDefault(True)
        save.clicked.connect(self._accept)
        cancel = QPushButton(tr("settings_cancel"))
        cancel.clicked.connect(self.reject)
        check = QPushButton(tr("settings_check_updates_button"))
        check.clicked.connect(self.check_requested.emit)
        self.restart_button = QPushButton(tr("settings_restart"))
        self.restart_button.clicked.connect(self._restart)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        buttons.addStretch(1)
        buttons.addWidget(check)
        buttons.addWidget(self.restart_button)
        layout.addLayout(buttons)

        # The restart is only useful when the chosen language is not the running one.
        self.language_box.currentIndexChanged.connect(self._refresh_restart)
        self._refresh_restart()

        self.setSizeGripEnabled(True)
        self.setMinimumSize(MIN_DIALOG_WIDTH, MIN_DIALOG_HEIGHT)
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
        target.target_height = self.height_box.value()
        target.min_mp4_size = self.size_box.value() * 1024 * 1024
        target.theme = cast(ThemeName, self.theme_box.currentData())
        target.language = cast(Language, self.language_box.currentData())
        target.auto_update = self.update_check.isChecked()
        target.tray_enabled = self.tray_check.isChecked()
        target.close_to_tray = self.close_tray_check.isChecked()
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
