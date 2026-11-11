"""Icons of the buttons, drawn by hand (spec 4.1, 4.3).

The marks of the interface font are not reliable on Windows: «⚙» of the settings
button and «✕» of the card show a box, because the font a button uses does not
carry these code points (the same reason the cross of a card is painted, spec
4.1 p.1, and the icon of the program is drawn in code, spec 7.3). Every mark of
a button is drawn with ``QPainter`` in a 16 px grid, so it is the same picture in
the dark theme, the light theme, the system theme, in every language, and in the
screenshots of the README.

The color is the color of the button, not a fixed one: white on the accent of the
theme (``QPushButton``), the text color of the theme on a button of the panel
background (``QToolButton``) and in the tray menu, the text color of the palette
when the theme is the system one.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QAbstractButton, QApplication, QToolButton

from pydownloader.config.settings import ThemeName
from pydownloader.ui.theme import color_for

#: The side of the grid every icon is drawn in, in pixels: what a button shows.
#: The grid is fixed, not scaled: a 16 px mark is the size the button of the
#: interface has next to the 9 pt text, and every drawing keeps its own stroke.
ICON_SIZE = 16
#: The stroke of the frames and the lines.
STROKE = 1.6
#: The stroke of a mark: the cross, the check, the arrow, the tip of a chevron.
MARK = 1.9
#: The stroke of the thin lines of the globe.
THIN = 1.2


def icon_color(kind: str, theme: ThemeName) -> QColor:
    """Color of an icon on a button of ``kind``: ``accent``, ``panel``, ``warn``, ``danger``.

    The QSS of the dark and light themes paints the ``QPushButton`` with the accent
    color and white text, and the ``QToolButton`` with the panel background and the
    text color of the theme. The two buttons of the second row are painted with the
    yellow and the red of the theme, so their mark takes the color of the text of
    that button: white on the red, the dark of the text on the yellow. The system
    theme has no stylesheet at all, so the palette of the style is the only source
    of the color there, and every kind of the button gets the color of the text of
    a button.
    """
    if theme == "system":
        return QApplication.palette().color(QPalette.ColorRole.ButtonText)
    if kind == "accent":
        return QColor("#ffffff")
    if kind in ("warn", "danger"):
        return color_for(theme, f"{kind}_text")
    return color_for(theme, "text")


def _begin(color: QColor, width: float) -> tuple[QPixmap, QPainter]:
    """A transparent 16 px picture with a round pen of ``width``."""
    pixmap = QPixmap(ICON_SIZE, ICON_SIZE)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(_pen(color, width))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    return pixmap, painter


def _pen(color: QColor, width: float) -> QPen:
    pen = QPen(color)
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _set_pen(painter: QPainter, color: QColor, width: float) -> None:
    painter.setPen(_pen(color, width))


def _fill(painter: QPainter, color: QColor) -> None:
    """Fill a shape (the head of an arrow, the triangle of «play»)."""
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)


def _done(pixmap: QPixmap, painter: QPainter) -> QIcon:
    painter.end()
    return QIcon(pixmap)


def browser_icon(color: QColor, is_open: bool) -> QIcon:
    """A browser window: the frame, the title bar, the globe of the page (spec 4.3).

    ``is_open`` is the action of the button, not the state of the window: the arrow
    points down into the title bar when the button will show the window, the cross
    in the title bar when the button will close it. The frame, the bar and the
    globe are the same drawing in both cases, so the button is one thing that
    changes its mark.
    """
    pixmap, painter = _begin(color, STROKE)
    painter.drawRoundedRect(QRectF(1.5, 2.0, 13.0, 12.0), 2.2, 2.2)
    painter.drawLine(QPointF(1.5, 5.2), QPointF(14.5, 5.2))
    # The two dots of the title bar.
    _set_pen(painter, color, MARK)
    painter.drawPoint(QPointF(3.2, 3.6))
    painter.drawPoint(QPointF(5.4, 3.6))
    # The globe of the page: the circle, the meridian, the equator.
    _set_pen(painter, color, THIN)
    painter.drawEllipse(QRectF(4.4, 7.2, 5.6, 5.2))
    painter.drawEllipse(QRectF(6.4, 7.2, 1.6, 5.2))
    painter.drawLine(QPointF(4.4, 9.8), QPointF(10.0, 9.8))
    # The mark of the action, on the right of the title bar.
    _set_pen(painter, color, MARK)
    if is_open:
        painter.drawLine(QPointF(12.4, 2.4), QPointF(12.4, 4.2))
        _fill(painter, color)
        painter.drawPolygon(
            QPolygonF([QPointF(11.1, 3.9), QPointF(13.7, 3.9), QPointF(12.4, 5.6)])
        )
    else:
        painter.drawLine(QPointF(11.1, 2.6), QPointF(13.7, 4.6))
        painter.drawLine(QPointF(13.7, 2.6), QPointF(11.1, 4.6))
    return _done(pixmap, painter)


def clear_all_icon(color: QColor) -> QIcon:
    """Clear all: the list of cards and the cross over it (spec 4.1 p.7)."""
    pixmap, painter = _begin(color, STROKE)
    for y in (4.0, 8.0, 12.0):
        painter.drawLine(QPointF(2.0, y), QPointF(9.4, y))
    _set_pen(painter, color, MARK)
    painter.drawLine(QPointF(10.6, 6.2), QPointF(14.4, 10.0))
    painter.drawLine(QPointF(14.4, 6.2), QPointF(10.6, 10.0))
    return _done(pixmap, painter)


def clear_downloaded_icon(color: QColor) -> QIcon:
    """Clear downloaded: the list of cards and the check of a file on the disk (spec 4.1 p.7)."""
    pixmap, painter = _begin(color, STROKE)
    for y in (4.0, 8.0, 12.0):
        painter.drawLine(QPointF(2.0, y), QPointF(9.4, y))
    _set_pen(painter, color, MARK)
    painter.drawLine(QPointF(10.2, 8.6), QPointF(11.8, 10.4))
    painter.drawLine(QPointF(11.8, 10.4), QPointF(14.6, 6.0))
    return _done(pixmap, painter)


def gear_icon(color: QColor) -> QIcon:
    """Settings: the ring and the teeth of a gear (spec 4.3 p.2).

    The glyph «⚙» is drawn as a box by the font of the buttons, the painted gear is
    the same mark in every theme, as the cross of a card.
    """
    pixmap, painter = _begin(color, STROKE)
    painter.drawEllipse(QRectF(5.0, 5.0, 6.0, 6.0))
    # The teeth are short and thick: long thin spokes of the same size read as a
    # sun, not as a gear, when the picture is 16 px on the screen.
    _set_pen(painter, color, 2.4)
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        painter.drawLine(
            QPointF(8.0 + 3.4 * math.cos(rad), 8.0 + 3.4 * math.sin(rad)),
            QPointF(8.0 + 5.4 * math.cos(rad), 8.0 + 5.4 * math.sin(rad)),
        )
    return _done(pixmap, painter)


def go_icon(color: QColor) -> QIcon:
    """Arrow going into a frame: the address of the field is carried to the browser.

    The frame is open at the right side, the arrow points into it, so the mark reads
    as "send this address there" (spec 4.2 p.4).
    """
    pixmap, painter = _begin(color, STROKE)
    # The frame of the browser window: its right side is left open for the arrow.
    painter.drawLine(QPointF(4.2, 2.8), QPointF(4.2, 13.2))
    painter.drawLine(QPointF(4.2, 2.8), QPointF(10.8, 2.8))
    painter.drawLine(QPointF(4.2, 13.2), QPointF(10.8, 13.2))
    _set_pen(painter, color, MARK)
    painter.drawLine(QPointF(8.6, 8.0), QPointF(14.4, 8.0))
    painter.drawLine(QPointF(11.4, 5.4), QPointF(14.4, 8.0))
    painter.drawLine(QPointF(14.4, 8.0), QPointF(11.4, 10.6))
    return _done(pixmap, painter)


def folder_icon(color: QColor) -> QIcon:
    """A folder: the body and the tab of its lid (spec 4.2 p.6)."""
    pixmap, painter = _begin(color, STROKE)
    painter.drawRoundedRect(QRectF(1.5, 5.0, 13.0, 9.0), 1.5, 1.5)
    painter.drawLine(QPointF(1.5, 5.0), QPointF(4.2, 5.0))
    painter.drawLine(QPointF(4.2, 5.0), QPointF(5.6, 3.2))
    painter.drawLine(QPointF(5.6, 3.2), QPointF(9.4, 3.2))
    painter.drawLine(QPointF(9.4, 3.2), QPointF(10.8, 5.0))
    return _done(pixmap, painter)


def log_icon(color: QColor) -> QIcon:
    """A log file: the page and the lines of the text (spec 4.2 p.6)."""
    pixmap, painter = _begin(color, THIN + 0.2)
    painter.drawRoundedRect(QRectF(3.0, 1.5, 10.0, 13.0), 1.5, 1.5)
    for y in (5.0, 7.5, 10.0, 12.5):
        painter.drawLine(QPointF(5.0, y), QPointF(11.0, y))
    return _done(pixmap, painter)


def console_icon(color: QColor) -> QIcon:
    """Show console: the panel with the prompt of a terminal (spec 4.2 p.5)."""
    pixmap, painter = _begin(color, STROKE)
    painter.drawRoundedRect(QRectF(1.5, 2.5, 13.0, 11.0), 2.0, 2.0)
    _set_pen(painter, color, MARK)
    painter.drawLine(QPointF(4.0, 6.2), QPointF(6.4, 8.4))
    painter.drawLine(QPointF(6.4, 8.4), QPointF(4.0, 10.6))
    painter.drawLine(QPointF(8.8, 10.1), QPointF(11.8, 10.1))
    return _done(pixmap, painter)


def chevron_icon(color: QColor, down: bool) -> QIcon:
    """Hide console: the tip of a chevron, up when the panel goes away (spec 4.2 p.5)."""
    pixmap, painter = _begin(color, MARK)
    middle, tip = (9.6, 6.4) if down else (6.4, 9.6)
    painter.drawLine(QPointF(3.5, tip), QPointF(8.0, middle))
    painter.drawLine(QPointF(8.0, middle), QPointF(12.5, tip))
    return _done(pixmap, painter)


def download_icon(color: QColor) -> QIcon:
    """Download: the arrow to the line of the disk, the arrow of the program icon (spec 4.1 p.6)."""
    pixmap, painter = _begin(color, STROKE)
    painter.drawLine(QPointF(8.0, 2.0), QPointF(8.0, 9.4))
    _fill(painter, color)
    painter.drawPolygon(QPolygonF([QPointF(5.3, 7.7), QPointF(10.7, 7.7), QPointF(8.0, 11.3)]))
    _set_pen(painter, color, MARK)
    painter.drawLine(QPointF(3.0, 14.0), QPointF(13.0, 14.0))
    return _done(pixmap, painter)


def play_icon(color: QColor) -> QIcon:
    """Open file: the triangle of a player, the file opens in the default one (spec 4.1 p.4)."""
    pixmap, painter = _begin(color, STROKE)
    _fill(painter, color)
    painter.drawPolygon(QPolygonF([QPointF(4.5, 3.0), QPointF(13.0, 8.0), QPointF(4.5, 13.0)]))
    return _done(pixmap, painter)


def retry_icon(color: QColor) -> QIcon:
    """Retry and check for updates: the arc with the head of the arrow (spec 4.1 p.5, 8.3)."""
    pixmap, painter = _begin(color, MARK)
    painter.drawArc(QRectF(2.5, 2.5, 11.0, 11.0), 40 * 16, 250 * 16)
    painter.drawLine(QPointF(11.6, 2.7), QPointF(13.7, 4.7))
    painter.drawLine(QPointF(13.7, 4.7), QPointF(11.2, 6.2))
    return _done(pixmap, painter)


def cross_icon(color: QColor) -> QIcon:
    """A cross: cancel of a task, clear of the console, the cross of a card (spec 4.1 p.1)."""
    pixmap, painter = _begin(color, MARK)
    painter.drawLine(QPointF(4.5, 4.5), QPointF(11.5, 11.5))
    painter.drawLine(QPointF(11.5, 4.5), QPointF(4.5, 11.5))
    return _done(pixmap, painter)


def check_icon(color: QColor) -> QIcon:
    """Save: the check of the settings written to the file (spec 4.3 p.2)."""
    pixmap, painter = _begin(color, MARK)
    painter.drawLine(QPointF(3.0, 8.5), QPointF(6.5, 12.0))
    painter.drawLine(QPointF(6.5, 12.0), QPointF(13.0, 5.0))
    return _done(pixmap, painter)


def window_icon(color: QColor) -> QIcon:
    """Show the window: the frame and its title bar (spec 4.3 p.4)."""
    pixmap, painter = _begin(color, STROKE)
    painter.drawRoundedRect(QRectF(1.5, 2.5, 13.0, 11.0), 2.0, 2.0)
    painter.drawLine(QPointF(1.5, 5.2), QPointF(14.5, 5.2))
    _set_pen(painter, color, MARK)
    painter.drawPoint(QPointF(3.4, 3.8))
    return _done(pixmap, painter)


def exit_icon(color: QColor) -> QIcon:
    """Exit: the ring with the gap at the top and the line of the power (spec 4.3 p.4)."""
    pixmap, painter = _begin(color, MARK)
    # The gap of the ring is at the top: 30°..150° of Qt angles, 90° is 12 o'clock.
    painter.drawArc(QRectF(3.0, 3.0, 10.0, 10.0), 150 * 16, 240 * 16)
    painter.drawLine(QPointF(8.0, 1.6), QPointF(8.0, 7.2))
    return _done(pixmap, painter)


def attach(button: QAbstractButton, icon: QIcon) -> None:
    """Put the icon on the button, the text stays next to it.

    ``QToolButton`` shows the icon only by default, so the text of «Cancel», «Open
    file» and «Retry» on a card would disappear; the style asks for the text beside
    the icon (spec 4.1 p.4). A button without a text is left as the icon only:
    asking for the text beside it reserves the room of a label, and the square
    button of the cross on a card becomes a rectangle with the mark shifted to the
    left of the box (spec 4.1 p.1).
    """
    button.setIcon(icon)
    button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
    if isinstance(button, QToolButton) and button.text():
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)


__all__ = [
    "ICON_SIZE",
    "attach",
    "browser_icon",
    "check_icon",
    "chevron_icon",
    "clear_all_icon",
    "clear_downloaded_icon",
    "console_icon",
    "cross_icon",
    "download_icon",
    "exit_icon",
    "folder_icon",
    "gear_icon",
    "icon_color",
    "log_icon",
    "play_icon",
    "retry_icon",
    "window_icon",
]
