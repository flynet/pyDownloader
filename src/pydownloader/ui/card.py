"""The card of one found source (spec 4.1).

A card carries: the still of the video the page painted (on the left of the texts,
so a video is recognized by its frame; an audio source has none and its card starts
with the name), the type badge (HLS / DASH / MP4), the page title, the URL
(elided, full text in the tooltip, «Копировать ссылку» in the context menu),
resolution / duration / size when they are known, the «Скачать» button, the
progress of the download inside the card (spec 4.1 p.5), and the «✕» on the right
of the title: it takes this one entry out of the list (spec 4.1 p.1).

A card is as wide as the list of cards: every label of the card shows the line of
its text that fits the width the card has, the title is broken into the lines of
its words (at most ``TITLE_LINES`` of them), the rest is marked by the sign of
elision, and the whole text is read in the tooltip. A label asks for the width of
the text it shows, so the text is fitted when the card is resized: a long title
makes the card taller, never wider, and the list of cards gets no horizontal
scrollbar (spec 4.1 p.1).

State machine: ``new → queued → downloading → done | error``; a cancelled
download returns to ``error`` with the message «отменено».
"""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontMetrics, QGuiApplication, QPixmap, QResizeEvent
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
from pydownloader.ui.theme import DARK, PALETTES, badge_style

CardState = Literal["new", "queued", "downloading", "done", "error"]

#: The bar of a finished download is green: the colour says the file is on the
#: disk, so a person sees the end of the queue without reading the text (spec 4.1 p.3).
DONE_COLOR = "#2ea64f"


def bar_style(state: CardState, theme: ThemeName = "dark") -> str:
    """The bar of a card: the colors of the theme for the state (spec 4.1 p.3).

    A running file keeps the accent (the gradient of a theme that has a gradient), a
    finished file gets the green of the theme, and the «100%» of a finished bar is
    readable on it, so the same role of success is the same color in the bar, the
    badge and the console of the theme.
    """
    if state != "done":
        return ""
    colors = PALETTES.get(theme, DARK)
    return (
        f"QProgressBar {{ color: {colors['done_text']}; }} "
        f"QProgressBar::chunk {{ background: {colors['done']}; }}"
    )



# The «✕» of a card and the marks of its buttons are painted, not typed: the text
# glyph «✕» (U+2715) is not in the font of the Windows buttons, so a character with
# the glyph shows a box. The drawings of ``button_icons`` give the same marks in
# every theme, in every language, and in the screenshots of the README (spec 4.1 p.1).

#: The box of the cross on the right of a card: the icon of 16 px, the padding of
#: 4 px and the border of 1 px of the theme, so the box is a square 26 x 26 px and
#: the mark stands in the middle of it (spec 4.1 p.1). The row of the card gives a
#: button the height of the label, which is 16 px, so the size is fixed.
CROSS_BUTTON = 26

#: The title of a card takes at most two lines: a long page title is broken by the
#: width of the card, the letters that do not fit are marked by the sign of elision,
#: so the card stays as wide as the list of cards and the list never scrolls
#: sideways (spec 4.1 p.1). The full title is read in the tooltip of the card.
TITLE_LINES = 2

#: The URL and the path of a card are one word each: a line of 90 characters is the
#: floor of the width the label asks for, so a very long link cannot push the card
#: wider than the list; the full text is in the tooltip (spec 4.1 p.1).
URL_CHARS = 90

#: The still of a video on its card: 16:9, the shape a video frame has. The card
#: shows it on the left of the texts, so a video is recognized by its picture
#: before the name is read; an audio source has no still and its card starts with
#: the name (spec 4.1).
THUMBNAIL_WIDTH = 240
THUMBNAIL_HEIGHT = 135

#: The sign of elision: the cut letters of a title are marked, so a person sees that
#: the name goes on, and the tooltip is read for the whole of it.
ELLIPSIS = "…"

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
    return url[: width - 1] + ELLIPSIS


def fit_thumbnail(
    image: QPixmap, width: int = THUMBNAIL_WIDTH, height: int = THUMBNAIL_HEIGHT
) -> QPixmap:
    """The still cut to the frame of the card, the middle of the picture kept.

    A page can point at a picture of any shape (a wide still, a square cover, a
    poster of the player), so the picture is scaled until it covers the frame and
    the middle of it is taken: the card always shows one rectangle of one size and
    the layout of the card does not depend on the shape of the picture (spec 4.1).
    """
    if image.width() <= 0 or image.height() <= 0:
        return image
    scaled = image.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    left = max((scaled.width() - width) // 2, 0)
    top = max((scaled.height() - height) // 2, 0)
    return scaled.copy(left, top, width, height)


def take_line(words: list[str], width: int, fm: QFontMetrics) -> tuple[str, list[str]]:
    """The first words that fit one line, and the words that are left over.

    A word wider than the line is taken whole: Qt breaks it inside the label, so
    the loop never stops on the first word of a line.
    """
    line = words[0]
    index = 1
    while index < len(words) and fm.horizontalAdvance(line + " " + words[index]) <= width:
        line += " " + words[index]
        index += 1
    return line, words[index:]


def fit_title(text: str, width: int, fm: QFontMetrics, lines: int = TITLE_LINES) -> str:
    """The title as it fits the card: the lines of the words, the rest elided (spec 4.1 p.1).

    The card is as wide as the list of cards, so the width the title gets is known
    when the card is resized: the words that fit each line are written out, the
    words of the last line that do not fit are shortened by the font metrics with
    the sign of elision, so the title never asks for more width than the card has
    and the card grows by height, not by width.
    """
    if width <= 0:
        return text
    words = text.split()
    lines_out: list[str] = []
    left = words
    for _ in range(lines):
        if not left:
            break
        line, left = take_line(left, width, fm)
        lines_out.append(line)
    if left:
        # The words of the tail are the part that is cut: the sign of elision stands
        # at the end of the last line, so the letters of the tail are not shown.
        rest = " ".join([lines_out[-1], *left])
        lines_out[-1] = fm.elidedText(rest, Qt.TextElideMode.ElideRight, width)
    return "\n".join(lines_out)


def fit_line(text: str, width: int, fm: QFontMetrics, middle: bool = False) -> str:
    """One line of text as it fits the width of the card, the cut marked.

    A path and a URL are one word: the middle of the line is kept for them, so the
    end of the file name stays on the card; the full text is in the tooltip.
    """
    if width <= 0:
        return text
    mode = Qt.TextElideMode.ElideMiddle if middle else Qt.TextElideMode.ElideRight
    return fm.elidedText(text, mode, width)


class SourceCard(QFrame):
    """One row of the upper section."""

    download_clicked = Signal(str)
    cancel_clicked = Signal(str)
    open_file_clicked = Signal(str)
    #: «✕» on the right of the card: take this one entry out of the list (spec 4.1 p.1).
    remove_clicked = Signal(str)

    def __init__(
        self,
        entry: SourceEntry,
        parent=None,
        theme: ThemeName = "dark",
        thumbnail: QPixmap | None = None,
    ) -> None:
        super().__init__(parent)
        self.entry = entry
        self.state: CardState = "new"
        self.stage = "download"
        #: The theme the card is painted with: the colors of a theme change without a
        #: restart, so the card keeps what it was painted with (spec 4.3 p.2).
        self.theme = theme
        #: The kind the badge is painted for: an audio source is the MP3 badge.
        self.badge_kind = "mp3" if entry.is_audio else entry.kind
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

        #: The card is one row: the still of the video on the left, everything the
        #: card says in the column on the right. Without a still (an audio source)
        #: the column takes the whole card, so the card looks as it did before
        #: (spec 4.1).
        layout = QHBoxLayout(self)
        self._layout = layout
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        #: The full texts of the labels of the card before they are fitted to its
        #: width: a label shows the line that fits, the whole text is read in its
        #: tooltip. The flag marks the labels whose middle is worth keeping (a URL,
        #: the path of a saved file), so the end of the name stays on the card.
        self._full: dict[QLabel, tuple[str, bool]] = {}

        #: The still of the video: the picture the page painted stands on the left
        #: of the card, the name and the details are read on the right of it. An
        #: audio source has no still and the card starts with the name (spec 4.1).
        self.thumbnail_label: QLabel | None = None
        if thumbnail is not None and not thumbnail.isNull():
            self.thumbnail_label = QLabel()
            self.thumbnail_label.setObjectName("cardThumb")
            self.thumbnail_label.setFixedSize(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)
            self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.thumbnail_label.setPixmap(fit_thumbnail(thumbnail))
            layout.addWidget(self.thumbnail_label, 0, Qt.AlignmentFlag.AlignTop)

        #: The column of the texts and the buttons, on the right of the picture.
        texts = QVBoxLayout()
        self._texts = texts
        texts.setContentsMargins(0, 0, 0, 0)
        texts.setSpacing(4)
        layout.addLayout(texts, 1)

        top = QHBoxLayout()
        self._top = top
        # An audio source gets the MP3 badge: the file on disk is an MP3, not a video.
        badge_text = "MP3" if entry.is_audio else entry.kind.upper()
        self.badge = QLabel(badge_text)
        self.badge.setObjectName("badge")
        self.badge.setStyleSheet(badge_style(theme, self.badge_kind))
        top.addWidget(self.badge)
        #: The whole title of the card, as it arrived from the page.
        self._full_title = entry.title or entry.page_url or entry.url
        self.title_label = QLabel(self._full_title)
        self.title_label.setObjectName("cardTitle")
        # A long title is broken by the width of the card, not by the width the label
        # asks for: the label takes the width of the row and the words of the title
        # are written into its lines, so the card is as wide as the list of cards and
        # the list gets no horizontal scrollbar (spec 4.1 p.1).
        self.title_label.setWordWrap(True)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        # The alignment is written without the flag of a mnemonic: the ampersand of a
        # title ("Rock & Roll") is a letter of the name, not the sign of a key.
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.title_label.setTextFormat(Qt.TextFormat.PlainText)
        self.title_label.setToolTip(self._full_title)
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
        texts.addLayout(top)

        self.url_label = QLabel(elide(entry.url, URL_CHARS))
        self._full[self.url_label] = (entry.url, True)
        self.url_label.setObjectName("cardMeta")
        self.url_label.setToolTip(entry.url)
        self.url_label.setTextFormat(Qt.TextFormat.PlainText)
        self.url_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.url_label.customContextMenuRequested.connect(self._copy_menu)
        texts.addWidget(self.url_label)

        parts = [format_quality(entry.height, entry.is_audio)]
        if entry.duration:
            parts.append(format_duration(entry.duration))
        if entry.size:
            parts.append(format_size(entry.size))
        self.meta_label = QLabel()
        self.meta_label.setObjectName("cardMeta")
        texts.addWidget(self.meta_label)
        self._meta_base = parts
        self._write(self.meta_label, SEPARATOR.join(parts))

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setFixedHeight(18)
        self.bar.setFormat("")
        self.bar.hide()
        texts.addWidget(self.bar)

        self.stage_label = QLabel("")
        self.stage_label.setObjectName("cardMeta")
        self.stage_label.hide()
        texts.addWidget(self.stage_label)

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
        texts.addLayout(row)

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

    def _text_width(self) -> int:
        """The width of the right column: the card minus its margins and the still."""
        margins = self._layout.contentsMargins()
        width = self.width() - margins.left() - margins.right()
        if self.thumbnail_label is not None:
            width -= self.thumbnail_label.width() + self._layout.spacing()
        return width

    def _meta_width(self) -> int:
        """The width a label of the card has: the column on the right of the still."""
        return self._text_width()

    def _title_width(self) -> int:
        """The width of the title: the row is the badge, the title, the cross."""
        return (
            self._text_width()
            - self.badge.sizeHint().width()
            - self.remove_button.width()
            - self._top.spacing() * 2
        )

    def _write(self, label: QLabel, text: str, middle: bool = False) -> None:
        """The full text of a label, and the line of it that fits the card.

        A label asks for the width of the whole text it shows, so the long path of a
        saved file pushed the card wider than the list of cards: the whole text is
        kept in the tooltip and for the rewriting on resize, and the label shows the
        line the card can hold (spec 4.1 p.1).
        """
        self._full[label] = (text, middle)
        label.setText(fit_line(text, self._meta_width(), label.fontMetrics(), middle))

    def _refit(self) -> None:
        """Every label of the card is written again for the width the card has.

        The card is as wide as the list of cards, and the list is as wide as the
        window: a title that took two lines in a wide window takes three in a narrow
        one, so the lines are built from the width the card has now, and the card
        grows by height, never by width (spec 4.1 p.1).
        """
        title = fit_title(self._full_title, self._title_width(), self.title_label.fontMetrics())
        if title != self.title_label.text():
            self.title_label.setText(title)
        for label, (text, middle) in self._full.items():
            fitted = fit_line(text, self._meta_width(), label.fontMetrics(), middle)
            if fitted != label.text():
                label.setText(fitted)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._refit()
        self._update_floor()

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
        self.bar.setStyleSheet(bar_style(state, self.theme))
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
        self.bar.setStyleSheet(bar_style("downloading", self.theme))
        self.stage_label.setVisible(True)
        percent = done * 100 // total if total else 0
        self.bar.setRange(0, total)
        self.bar.setValue(done)
        self.bar.setFormat(tr("card_progress", percent=percent, done=done, total=total))
        text = stage_label(self.stage)
        if speed_mb is not None:
            text += SEPARATOR + tr("card_speed_mb", speed=speed_mb)
        self._write(self.stage_label, text)

    def set_theme(self, theme: ThemeName) -> None:
        """Repaint the card with the theme chosen in the settings (spec 4.3 p.2).

        The theme is applied without a restart, and the card is painted once: the
        marks of its buttons, the badge of its format and the bar of its state keep
        the colors of the theme of the last build, so every color of the card is
        written again from the keys of the new theme.
        """
        self.theme = theme
        self._panel = icon_color("panel", theme)
        self._accent = icon_color("accent", theme)
        attach(self.remove_button, cross_icon(self._panel))
        attach(self.download_button, download_icon(self._accent))
        attach(self.cancel_button, cross_icon(self._panel))
        attach(self.open_button, play_icon(self._panel))
        attach(self.retry_button, retry_icon(self._panel))
        self.badge.setStyleSheet(badge_style(theme, self.badge_kind))
        self.bar.setStyleSheet(bar_style(self.state, theme))

    def set_stage(self, stage: str) -> None:
        """Change the stage text: downloading / decrypting / muxing."""
        self.stage = stage
        self._write(self.stage_label, stage_label(stage))

    def set_error(self, message: str) -> None:
        self.set_state("error")
        self._write(self.meta_label, message, middle=True)
        self.meta_label.setObjectName("cardError")
        self.meta_label.style().polish(self.meta_label)

    def set_result(self, path: str) -> None:
        self.set_state("done")
        self._write(self.meta_label, f"{self._meta_base[0]}{SEPARATOR}{path}", middle=True)
        # The line of the card is as wide as the card, so the long path of the file
        # is cut in the middle: the quality and the end of the name stay, the whole
        # path is read in the tooltip (spec 4.1 p.1).
        self.meta_label.setToolTip(path)

    def _refresh_meta(self) -> None:
        if self.state == "error":
            return
        parts = list(self._meta_base)
        label = state_text(self.state)
        if label:
            parts.append(label)
        self.meta_label.setObjectName("cardMeta")
        self._write(self.meta_label, SEPARATOR.join(parts))
        self.meta_label.style().polish(self.meta_label)


__all__ = [
    "ELLIPSIS",
    "THUMBNAIL_HEIGHT",
    "THUMBNAIL_WIDTH",
    "TITLE_LINES",
    "URL_CHARS",
    "CardState",
    "SourceCard",
    "bar_style",
    "elide",
    "fit_line",
    "fit_thumbnail",
    "fit_title",
    "format_duration",
    "format_quality",
    "format_size",
    "stage_label",
    "state_text",
    "take_line",
]
