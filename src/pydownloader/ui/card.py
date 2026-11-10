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

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
)

from pydownloader.i18n import tr
from pydownloader.manifest.registry import SourceEntry

CardState = Literal["new", "queued", "downloading", "done", "error"]

#: State -> the key of its text in the meta line (spec 4.1 p.2); ``new`` shows none.
STATE_KEYS: dict[CardState, str] = {
    "new": "",
    "queued": "card_state_queued",
    "downloading": "card_state_downloading",
    "done": "card_state_done",
    "error": "card_state_error",
}

#: Stage of the worker -> the key of its text; the stage name comes from the queue.
STAGE_KEYS: dict[str, str] = {
    "download": "card_stage_download",
    "decrypt": "card_stage_decrypt",
    "mux": "card_stage_mux",
}

#: The parts of a card line are joined by a plain separator, never by a text.
SEPARATOR = " · "

BADGE_COLORS = {"hls": "#3b7fd7", "dash": "#7b5cc7", "mp4": "#2e7d32", "youtube": "#c4302b"}


def state_text(state: CardState) -> str:
    """Text of a state in the current language, ``""`` for ``new``."""
    key = STATE_KEYS[state]
    return tr(key) if key else ""


def stage_label(stage: str) -> str:
    """Text of a stage; a stage the catalog does not know is shown as it arrives."""
    key = STAGE_KEYS.get(stage)
    return tr(key) if key else stage


def format_size(size: int | None) -> str:
    """Size in MB, ``размер неизвестен`` when the size was not reported."""
    if size is None:
        return tr("card_size_unknown")
    return tr("card_size_mb", mb=size / (1024 * 1024))


def format_duration(seconds: float | None) -> str:
    """``12:34`` for 12 minutes 34 seconds, ``""`` when the length is unknown."""
    if seconds is None:
        return ""
    total = round(seconds)
    minutes, rest = divmod(total, 60)
    return f"{minutes}:{rest:02d}"


def format_quality(height: int | None) -> str:
    return f"{height}p" if height else tr("card_quality_unknown")


def elide(url: str, width: int) -> str:
    """Shorten a URL for one line, with the full text in the tooltip."""
    if len(url) <= width:
        return url
    return url[: width - 1] + "…"


class SourceCard(QFrame):
    """One row of the upper section."""

    download_clicked = Signal(str)
    cancel_clicked = Signal(str)
    open_file_clicked = Signal(str)

    def __init__(self, entry: SourceEntry, parent=None) -> None:
        super().__init__(parent)
        self.entry = entry
        self.state: CardState = "new"
        self.stage = "download"
        self.setObjectName("card")
        # The height comes from the layout (labels, progress bar, buttons): an
        # explicit minimum used to win over the layout minimum and squeezed the
        # «Скачать» button to a few pixels once several cards shared the viewport.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

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
        self.meta_label = QLabel(SEPARATOR.join(parts))
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
        self.download_button = QPushButton(tr("card_download"))
        self.download_button.setObjectName("download")
        self.download_button.clicked.connect(lambda: self.download_clicked.emit(self.entry.id))
        row.addWidget(self.download_button)

        self.cancel_button = QToolButton()
        self.cancel_button.setText(tr("card_cancel"))
        self.cancel_button.clicked.connect(lambda: self.cancel_clicked.emit(self.entry.id))
        self.cancel_button.hide()
        row.addWidget(self.cancel_button)

        self.open_button = QToolButton()
        self.open_button.setText(tr("card_open_file"))
        self.open_button.clicked.connect(lambda: self.open_file_clicked.emit(self.entry.id))
        self.open_button.hide()
        row.addWidget(self.open_button)

        self.retry_button = QToolButton()
        self.retry_button.setText(tr("card_retry"))
        self.retry_button.clicked.connect(lambda: self.download_clicked.emit(self.entry.id))
        self.retry_button.hide()
        row.addWidget(self.retry_button)

        row.addStretch(1)
        layout.addLayout(row)

    def _copy_menu(self, position) -> None:
        menu = QMenu(self)
        action = menu.addAction(tr("card_copy_link"))
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
        self.bar.setFormat(tr("card_progress", percent=percent, done=done, total=total))
        text = stage_label(self.stage)
        if speed_mb is not None:
            text += SEPARATOR + tr("card_speed_mb", speed=speed_mb)
        self.stage_label.setText(text)

    def set_stage(self, stage: str) -> None:
        """Change the stage text: downloading / decrypting / muxing."""
        self.stage = stage
        self.stage_label.setText(stage_label(stage))

    def set_error(self, message: str) -> None:
        self.set_state("error")
        self.meta_label.setText(f"{message}")
        self.meta_label.setObjectName("cardError")
        self.meta_label.style().polish(self.meta_label)

    def set_result(self, path: str) -> None:
        self.set_state("done")
        self.meta_label.setText(f"{self._meta_base[0]}{SEPARATOR}{path}")

    def _refresh_meta(self) -> None:
        if self.state == "error":
            return
        parts = list(self._meta_base)
        label = state_text(self.state)
        if label:
            parts.append(label)
        self.meta_label.setObjectName("cardMeta")
        self.meta_label.setText(SEPARATOR.join(parts))
        self.meta_label.style().polish(self.meta_label)


__all__ = [
    "CardState",
    "SourceCard",
    "format_duration",
    "format_quality",
    "format_size",
    "stage_label",
    "state_text",
]
