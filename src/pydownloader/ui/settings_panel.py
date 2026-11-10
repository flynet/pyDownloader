"""Settings dialog (spec 4.3, 8.1): the values are saved in ``settings.json``.

Fields: download folder, number of segment threads, theme, target height,
minimum MP4 size, automatic update check. The dialog is opened from the
window; it does not write the settings until the user presses «Сохранить».
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
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pydownloader.config.paths import download_dir_default
from pydownloader.config.settings import THEMES, Settings, ThemeName

BROWSE_CAPTION = "Папка для скачанных видео"
MIN_THREADS = 1
MAX_THREADS = 16
#: The dialog takes most of the main window: a long download path must fit.
DIALOG_WIDTH_RATIO = 0.8
DIALOG_HEIGHT_RATIO = 0.8
MIN_DIALOG_WIDTH = 640
MIN_DIALOG_HEIGHT = 420
#: Localized names of the theme values (the value itself stays in the settings).
THEME_LABELS: dict[str, str] = {
    "dark": "Тёмная",
    "light": "Светлая",
    "system": "Системная",
}


class SettingsDialog(QDialog):
    """A small form collecting the settings."""

    #: «Проверить обновления» asks the window to run the check (spec 8.3).
    check_requested = Signal()

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки PyDownloader")
        self.settings = settings
        self._form = QFormLayout()
        self._form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.download_edit = QLineEdit(settings.download_dir or str(download_dir_default()))
        # A long path is wider than the field: the full text is visible on hover.
        self.download_edit.textChanged.connect(self.download_edit.setToolTip)
        self.download_edit.setToolTip(self.download_edit.text())
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.download_edit)
        browse = QPushButton("Обзор…")
        browse.clicked.connect(self._pick_folder)
        folder_row.addWidget(browse)
        self._form.addRow("Папка загрузок:", folder_row)

        self.threads_box = QSpinBox()
        self.threads_box.setRange(MIN_THREADS, MAX_THREADS)
        self.threads_box.setValue(settings.threads)
        self._form.addRow("Потоков сегментов:", self.threads_box)

        self.height_box = QSpinBox()
        self.height_box.setRange(144, 4320)
        self.height_box.setValue(settings.target_height)
        self._form.addRow("Разрешение (p):", self.height_box)

        self.size_box = QSpinBox()
        self.size_box.setRange(1, 1024)
        self.size_box.setValue(max(1, settings.min_mp4_size // (1024 * 1024)))
        self._form.addRow("Минимальный MP4 (МБ):", self.size_box)

        self.theme_box = QComboBox()
        for name in THEMES:
            self.theme_box.addItem(THEME_LABELS[name], name)
        self.theme_box.setCurrentIndex(max(0, self.theme_box.findData(settings.theme)))
        self._form.addRow("Тема:", self.theme_box)

        self.update_check = QCheckBox("Проверять обновления")
        self.update_check.setChecked(settings.auto_update)
        self._form.addRow("", self.update_check)

        layout = QVBoxLayout(self)
        layout.addLayout(self._form)

        buttons = QHBoxLayout()
        save = QPushButton("Сохранить")
        save.setDefault(True)
        save.clicked.connect(self._accept)
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        check = QPushButton("Проверить обновления")
        check.clicked.connect(self.check_requested.emit)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        buttons.addStretch(1)
        buttons.addWidget(check)
        layout.addLayout(buttons)

        self.setSizeGripEnabled(True)
        self.setMinimumSize(MIN_DIALOG_WIDTH, MIN_DIALOG_HEIGHT)
        if parent is not None:
            window = parent.window()
            self.resize(
                max(MIN_DIALOG_WIDTH, round(window.width() * DIALOG_WIDTH_RATIO)),
                max(MIN_DIALOG_HEIGHT, round(window.height() * DIALOG_HEIGHT_RATIO)),
            )

    def _pick_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, BROWSE_CAPTION, self.download_edit.text())
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
        target.auto_update = self.update_check.isChecked()
        return target
