"""The card of one found source (spec 4.1).

A card carries: the type badge (HLS / DASH / MP4), the page title, the URL
(elided, full text in the tooltip, «Копировать ссылку» in the context menu),
resolution / duration / size when they are known, the «Скачать» button and the
progress of the download inside the card (spec 4.1 p.5).

State machine: ``new → queued → downloading → done | error``; a cancelled
download returns to ``error`` with the message «отменено».
"""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QToolButton,
    QVBoxLayout,
)

from pydownloader.manifest.registry import SourceEntry

CardState = Literal["new", "queued", "downloading", "done", "error"]

#: Text shown in the meta line for each state (spec 4.1 p.2).
STATE_TEXT: dict[CardState, str] = {
    "new": "",
    "queued": "В очереди",
    "downloading": "Скачивание",
    "done": "Готово",
    "error": "Ошибка",
}

STAGE_LABELS = {
    "download": "скачивание",
    "decrypt": "расшифровка",
    "mux": "склейка",
}

BADGE_COLORS = {"hls": "#3b7fd7", "dash": "#7b5cc7", "mp4": "#2e7d32"}


def format_size(size: int | None) -> str:
    """Size in MB, ``размер неизвестен`` when the size was not reported."""
    if size is None:
        return "размер неизвестен"
    return f"{size / (1024 * 1024):.1f} МБ"


def format_duration(seconds: float | None) -> str:
    """``12:34`` for 12 minutes 34 seconds, ``""`` when the length is unknown."""
    if seconds is None:
        return ""
    total = round(seconds)
    minutes, rest = divmod(total, 60)
    return f"{minutes}:{rest:02d}"


def format_quality(height: int | None) -> str:
    return f"{height}p" if height else "разрешение неизвестно"


def elide(url: str, width: int) -> str:
    """Shorten a URL for one line, with the full text in the tooltip."""
    if len(url) <= width:
        return url
    return url[: width - 1] + "…"


class SourceCard(QFrame):
    """One row of the upper section."""

    download_clicked = Signal(str)
    cancel_clicked = Signal(str)
    open_folder_clicked = Signal(str)

    def __init__(self, entry: SourceEntry, parent=None) -> None:
        super().__init__(parent)
        self.entry = entry
        self.state: CardState = "new"
        self.stage = "download"
        self.setObjectName("card")
        self.setMinimumHeight(96)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        top = QHBoxLayout()
        self.badge = QLabel(entry.kind.upper())
        self.badge.setObjectName("badge")
        self.badge.setStyleSheet(f"color: #ffffff; background: {BADGE_COLORS[entry.kind]};")
        top.addWidget(self.badge)
        self.title_label = QLabel(entry.title or entry.page_url or entry.url)
        self.title_label.setObjectName("cardTitle")
        top.addWidget(self.title_label, 1)
        layout.addLayout(top)

        self.url_label = QLabel(elide(entry.url, 90))
        self.url_label.setObjectName("cardMeta")
        self.url_label.setToolTip(entry.url)
        self.url_label.setTextFormat(Qt.TextFormat.PlainText)
        self.url_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.url_label.customContextMenuRequested.connect(self._copy_menu)
        layout.addWidget(self.url_label)

        parts = [format_quality(entry.height)]
        if entry.duration:
            parts.append(format_duration(entry.duration))
        if entry.size:
            parts.append(format_size(entry.size))
        self.meta_label = QLabel(" · ".join(parts))
        self.meta_label.setObjectName("cardMeta")
        layout.addWidget(self.meta_label)
        self._meta_base = parts

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setFixedHeight(18)
        self.bar.setFormat("")
        self.bar.hide()
        layout.addWidget(self.bar)

        self.stage_label = QLabel("")
        self.stage_label.setObjectName("cardMeta")
        self.stage_label.hide()
        layout.addWidget(self.stage_label)

        row = QHBoxLayout()
        self.download_button = QPushButton("Скачать")
        self.download_button.setObjectName("download")
        self.download_button.clicked.connect(lambda: self.download_clicked.emit(self.entry.id))
        row.addWidget(self.download_button)

        self.cancel_button = QToolButton()
        self.cancel_button.setText("Отмена")
        self.cancel_button.clicked.connect(lambda: self.cancel_clicked.emit(self.entry.id))
        self.cancel_button.hide()
        row.addWidget(self.cancel_button)

        self.open_button = QToolButton()
        self.open_button.setText("Открыть папку")
        self.open_button.clicked.connect(lambda: self.open_folder_clicked.emit(self.entry.id))
        self.open_button.hide()
        row.addWidget(self.open_button)

        self.retry_button = QToolButton()
        self.retry_button.setText("Повторить")
        self.retry_button.clicked.connect(lambda: self.download_clicked.emit(self.entry.id))
        self.retry_button.hide()
        row.addWidget(self.retry_button)

        row.addStretch(1)
        layout.addLayout(row)

    def _copy_menu(self, position) -> None:
        menu = QMenu(self)
        action = menu.addAction("Копировать ссылку")
        action.triggered.connect(self._copy_url)
        menu.exec(self.url_label.mapToGlobal(position))

    def _copy_url(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.entry.url)

    def set_state(self, state: CardState) -> None:
        """Move to a state: only the widgets of that state are visible."""
        self.state = state
        # In the queue the button stays in place but is blocked (spec 4.1 p.2).
        self.download_button.setVisible(state in {"new", "queued"})
        self.download_button.setEnabled(state == "new")
        self.retry_button.setVisible(state == "error")
        self.cancel_button.setVisible(state == "downloading")
        self.open_button.setVisible(state == "done")
        self.bar.setVisible(state in {"downloading", "done"})
        self.stage_label.setVisible(state == "downloading")
        if state == "done":
            self.bar.setRange(0, 100)
            self.bar.setValue(100)
            self.bar.setFormat("100%")
            self.stage_label.hide()
        elif state == "new":
            self.bar.setValue(0)
        self._refresh_meta()

    def set_progress(self, done: int, total: int, speed_mb: float | None = None) -> None:
        """Segments downloaded, percentage and speed inside the card (spec 4.1 p.3)."""
        self.state = "downloading"
        self.bar.setVisible(True)
        self.stage_label.setVisible(True)
        percent = done * 100 // total if total else 0
        self.bar.setRange(0, total)
        self.bar.setValue(done)
        self.bar.setFormat(f"{percent}% · сегменты {done} из {total}")
        text = STAGE_LABELS[self.stage]
        if speed_mb is not None:
            text += f" · {speed_mb:.1f} МБ/с"
        self.stage_label.setText(text)

    def set_stage(self, stage: str) -> None:
        """Change the stage text: downloading / decrypting / muxing."""
        self.stage = stage
        self.stage_label.setText(STAGE_LABELS.get(stage, stage))

    def set_error(self, message: str) -> None:
        self.set_state("error")
        self.meta_label.setText(f"{message}")
        self.meta_label.setObjectName("cardError")
        self.meta_label.style().polish(self.meta_label)

    def set_result(self, path: str) -> None:
        self.set_state("done")
        self.meta_label.setText(f"{self._meta_base[0]} · {path}")

    def open_in_folder(self, path) -> None:
        QDesktopServices.openUrl(QUrl(f"file:///{str(path).replace('\\', '/')}"))

    def _refresh_meta(self) -> None:
        if self.state == "error":
            return
        parts = list(self._meta_base)
        label = STATE_TEXT[self.state]
        if label:
            parts.append(label)
        self.meta_label.setObjectName("cardMeta")
        self.meta_label.setText(" · ".join(parts))
        self.meta_label.style().polish(self.meta_label)


__all__ = ["CardState", "SourceCard", "format_duration", "format_quality", "format_size"]
