"""The icon of the program, drawn once for every place it is shown (spec 7.3).

The desktop icon is a dark rounded square with a white arrow pointing down and
the accent line of a tray under it. The tray icon of the notification area is the
same picture: only the colour of the arrow changes with the state of the queue,
white when nothing is downloaded, green while a download runs (spec 4.2 p.7).
The same drawing makes `assets/icon.ico`, the pictures of the setup wizard and
the icon of the window title bar, so the program looks the same everywhere.

Windows draws the icon of the notification area in its own grid: the icon cannot
be moved there, so the animation of a running download is the arrow of the
picture drawn in the shifted frames of a timer, which reads as the arrow
jumping up and down.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap, QPolygonF

#: The dark square of the icon.
BACKGROUND = QColor(28, 33, 40)
#: The line under the arrow: the tray the arrow points to.
ACCENT = QColor(90, 168, 236)
#: The arrow of the icon when nothing is downloaded.
WHITE = QColor(245, 247, 250)
#: The arrow of a running download (spec 4.2 p.7).
GREEN = QColor(46, 164, 79)
#: The side of the icon the notification area draws.
TRAY_SIZE = 32
#: The sizes the notification area asks for, so Windows does not scale one picture.
TRAY_SIZES = (16, 20, 32)
#: The side of the `.ico` file of the program.
SIZE = 64


def draw_arrow(
    painter: QPainter, left: float, top: float, size: float, color: QColor, shift: float = 0.0
) -> None:
    """The arrow pointing down and the line of the tray, inside a ``size`` square.

    ``color`` is the arrow: white for the icon of the program, green for the tray
    of a running download (spec 4.2 p.7). ``shift`` moves the arrow only, the line
    of the tray stays where it is: that is the jump of the animation.
    """
    shaft_w = size * 0.16
    painter.setBrush(color)
    painter.setPen(Qt.PenStyle.NoPen)
    shaft_x = left + (size - shaft_w) / 2
    shaft_y = top + shift + size * 0.10
    painter.drawRoundedRect(
        QRectF(shaft_x, shaft_y, shaft_w, size * 0.44), shaft_w / 4, shaft_w / 4
    )
    head = size * 0.34
    middle = left + size / 2
    painter.drawPolygon(
        QPolygonF(
            [
                QPointF(middle - head / 2, top + shift + size * 0.46),
                QPointF(middle + head / 2, top + shift + size * 0.46),
                QPointF(middle, top + shift + size * 0.70),
            ]
        )
    )
    pen = QPen(ACCENT, max(2.0, size * 0.06), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    y = int(top + size * 0.80)
    painter.drawLine(int(left + size * 0.24), y, int(left + size * 0.76), y)


def draw(size: int, arrow: QColor = WHITE, shift: int = 0) -> QImage:
    """The icon: the dark square, the arrow of ``arrow``, the line of the tray.

    ``shift`` moves the arrow down by the pixels: that is how the frames of the
    jumping animation of the tray are drawn (spec 4.2 p.7).
    """
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(BACKGROUND)
    painter.setPen(Qt.PenStyle.NoPen)
    radius = max(2, size // 5)
    painter.drawRoundedRect(1, 1, size - 2, size - 2, radius, radius)
    draw_arrow(painter, 0.0, 0.0, float(size), arrow, float(shift))
    painter.end()
    return image


def tray_icon(
    arrow: QColor = WHITE, shift: int = 0, sizes: tuple[int, ...] = TRAY_SIZES
) -> QIcon:
    """The icon of the notification area: the icon of the program with the arrow of the state.

    Every size the notification area asks for is drawn on its own, so the arrow
    stays sharp in the small grid of Windows and the picture is the same.
    """
    icon = QIcon()
    for size in sizes:
        # The shift of the jump is in the pixels of the 32 px drawing, so a smaller
        # size of the notification area gets the same jump in its own pixels.
        shift_px = round(shift * size / TRAY_SIZE)
        icon.addPixmap(QPixmap.fromImage(draw(size, arrow, shift_px)))
    return icon


__all__ = [
    "ACCENT",
    "BACKGROUND",
    "GREEN",
    "SIZE",
    "TRAY_SIZE",
    "TRAY_SIZES",
    "WHITE",
    "draw",
    "draw_arrow",
    "tray_icon",
]
