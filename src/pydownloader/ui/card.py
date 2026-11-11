"""The card of one found source (spec 4.1).

A card carries: the type badge (HLS / DASH / MP4), the page title, the URL
(elided, full text in the tooltip, «Копировать ссылку» in the context menu),
resolution / duration / size when they are known, the «Скачать» button, the
progress of the download inside the card (spec 4.1 p.5), and the «✕» on the right
of the title: it takes this one entry out of the list (spec 4.1 p.1).

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

from pydownloader.config.settings import ThemeName
from pydownloader.i18n import tr
from pydownloader.manifest.registry import SourceEntry
from pydownloader.ui.button_icons import (
    attach,
    cross_icon,
    download_icon,
    icon_color,
    play_icon,
    retry_icon,
)

CardState = Literal["new", "queued", "downloading", "done", "error"]

#: The bar of a finished download is green: the colour says the file is on the
#: disk, so a person sees the end of the queue without reading the text (spec 4.1 p.3).
DONE_COLOR = "#2ea64f"
#: The rule of the bar for the finished state, the theme gives the rest.
DONE_BAR = f"QProgressBar::chunk {{ background: {DONE_COLOR}; }}"


def bar_style(state: CardState) -> str:
    """The chunk colour of the progress bar of a state (spec 4.1 p.3)."""
    return DONE_BAR if state == "done" else ""


# The «✕» of a card and the marks of its buttons are painted, not typed: the text
# glyph «✕» (U+2715) is not in the font of the Windows buttons, so a character with
# the glyph shows a box. The drawings of ``button_icons`` give the same marks in
# every theme, in every language, and in the screenshots of the README (spec 4.1 p.1).

#: The box of the cross on the right of a card: the icon of 16 px, the padding of
#: 4 px and the border of 1 px of the theme, so the box is a square 26 x 26 px and
#: the mark stands in the middle of it (spec 4.1 p.1). The row of the card gives a
#: button the height of the label, which is 16 px, so the size is fixed.
CROSS_BUTTON = 26

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

BADGE_COLORS = {
    "hls": "#3b7fd7",
    "dash": "#7b5cc7",
    "mp4": "#2e7d32",
    "youtube": "#c4302b",
    # An audio source is shown with its own badge, the file is written as MP3.
    "mp3": "#a86a2d",
}


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


def format_quality(height: int | None, audio: bool = False) -> str:
    """Quality of the card line: ``1080p`` for video, ``MP3`` for an audio source (spec 4.1 p.2)."""
    if audio:
        return tr("card_quality_mp3")
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
    #: «✕» on the right of the card: take this one entry out of the list (spec 4.1 p.1).
    remove_clicked = Signal(str)

    def __init__(self, entry: SourceEntry, parent=None, theme: ThemeName = "dark") -> None:
        super().__init__(parent)
        self.entry = entry
        self.state: CardState = "new"
        self.stage = "download"
        #: The color of the marks of the card: the buttons of the card are of the panel
        #: background, so the icon takes the text color of the theme (spec 4.3 p.2).
        self._panel = icon_color("panel", theme)
        self._accent = icon_color("accent", theme)
        self.setObjectName("card")
        # The height comes from the layout (labels, progress bar, buttons): an
        # explicit minimum used to win over the layout minimum and squeezed the
        # download button to a few pixels once several cards shared the viewport.
        # ``Fixed`` behaved the same way in a scroll area: when the cards did not
        # fit, the layout shrank them below their size hint. ``Minimum`` keeps the
        # size hint as the floor, so the scroll area shows a scrollbar instead of
        # cutting the button off (spec 4.1 p.1).
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        self._layout = layout
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        top = QHBoxLayout()
        # An audio source gets the MP3 badge: the file on disk is an MP3, not a video.
        badge_text = "MP3" if entry.is_audio else entry.kind.upper()
        badge_color = BADGE_COLORS["mp3"] if entry.is_audio else BADGE_COLORS[entry.kind]
        self.badge = QLabel(badge_text)
        self.badge.setObjectName("badge")
        self.badge.setStyleSheet(f"color: #ffffff; background: {badge_color};")
        top.addWidget(self.badge)
        self.title_label = QLabel(entry.title or entry.page_url or entry.url)
        self.title_label.setObjectName("cardTitle")
        top.addWidget(self.title_label, 1)
        # The cross on the right is the way to take one card out of the list, so it
        # is visible in every state: the user removes a found video, a queued task,
        # a finished card, an error card (spec 4.1 p.1).
        self.remove_button = QToolButton()
        self.remove_button.setObjectName("cardRemove")
        attach(self.remove_button, cross_icon(self._panel))
        self.remove_button.setFixedSize(CROSS_BUTTON, CROSS_BUTTON)
        self.remove_button.setAutoRaise(True)
        self.remove_button.setToolTip(tr("card_remove_tip"))
        self.remove_button.clicked.connect(lambda: self.remove_clicked.emit(self.entry.id))
        top.addWidget(self.remove_button)
        layout.addLayout(top)

        self.url_label = QLabel(elide(entry.url, 90))
        self.url_label.setObjectName("cardMeta")
        self.url_label.setToolTip(entry.url)
        self.url_label.setTextFormat(Qt.TextFormat.PlainText)
        self.url_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.url_label.customContextMenuRequested.connect(self._copy_menu)
        layout.addWidget(self.url_label)

        parts = [format_quality(entry.height, entry.is_audio)]
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
        # The arrow to the line of the disk is the mark of the program icon: the button
        # is the start of the download (spec 4.1 p.6).
        attach(self.download_button, download_icon(self._accent))
        # The floor of the button is its own hint: a squeezed layout can give an
        # item less than minimumSizeHint(), and the text of «Download» disappeared
        # with the last pixel of the row. minimumSize() is the hard floor of QLayout.
        self.download_button.setMinimumSize(self.download_button.minimumSizeHint())
        self.download_button.clicked.connect(lambda: self.download_clicked.emit(self.entry.id))
        row.addWidget(self.download_button)

        self.cancel_button = QToolButton()
        self.cancel_button.setText(tr("card_cancel"))
        attach(self.cancel_button, cross_icon(self._panel))
        self.cancel_button.clicked.connect(lambda: self.cancel_clicked.emit(self.entry.id))
        self.cancel_button.hide()
        row.addWidget(self.cancel_button)

        self.open_button = QToolButton()
        self.open_button.setText(tr("card_open_file"))
        # The triangle of a player: the file opens in the player of the system (spec 4.1 p.4).
        attach(self.open_button, play_icon(self._panel))
        self.open_button.clicked.connect(lambda: self.open_file_clicked.emit(self.entry.id))
        self.open_button.hide()
        row.addWidget(self.open_button)

        self.retry_button = QToolButton()
        self.retry_button.setText(tr("card_retry"))
        # The arc of the arrow is the same mark as the check for an update (spec 8.3).
        attach(self.retry_button, retry_icon(self._panel))
        self.retry_button.clicked.connect(lambda: self.download_clicked.emit(self.entry.id))
        self.retry_button.hide()
        row.addWidget(self.retry_button)

        row.addStretch(1)
        layout.addLayout(row)

        self._update_floor()

    def _update_floor(self) -> None:
        """The card never shrinks below the height of its own widgets.

        A resizable scroll area resizes its widget to the viewport, and QLayout
        squeezes the items below ``minimumSizeHint`` when the space is short: with
        a long list of cards the labels and the button lost their lines. The hint
        of the layout is written into ``minimumSize``, the hard floor of QLayout,
        so every card keeps the height of its labels, bar and buttons (spec 4.1 p.1).
        """
        hint = self._layout.totalSizeHint()
        if self.minimumHeight() != hint.height():
            self.setMinimumSize(0, hint.height())

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
        # The bar of a finished file is green, the bar of a running one is the
        # accent of the theme (spec 4.1 p.3).
        self.bar.setStyleSheet(bar_style(state))
        self.stage_label.setVisible(state == "downloading")
        if state == "done":
            self.bar.setRange(0, 100)
            self.bar.setValue(100)
            self.bar.setFormat("100%")
            self.stage_label.hide()
        elif state == "new":
            self.bar.setValue(0)
        self._refresh_meta()
        self._update_floor()

    def set_progress(self, done: int, total: int, speed_mb: float | None = None) -> None:
        """Segments downloaded, percentage and speed inside the card (spec 4.1 p.3)."""
        self.state = "downloading"
        self.bar.setVisible(True)
        self.bar.setStyleSheet(bar_style("downloading"))
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
    "bar_style",
    "format_duration",
    "format_quality",
    "format_size",
    "stage_label",
    "state_text",
]
