"""Draws the application icon and the Inno Setup wizard images (spec 7.3).

Run once with ``uv run python tools/make_icon.py``; the files are committed, so
the build does not need Qt to produce them:

- ``assets/icon.ico`` — the program and installer icon;
- ``installer/assets/wizard.bmp`` — the big side picture of the setup wizard;
- ``installer/assets/wizard-small.bmp`` — the small picture of the header.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

SIZE = 64
OUT = Path("assets") / "icon.ico"
WIZARD_BIG = Path("installer") / "assets" / "wizard.bmp"
WIZARD_SMALL = Path("installer") / "assets" / "wizard-small.bmp"
WIZARD_BIG_SIZE = (164, 314)
WIZARD_SMALL_SIZE = (55, 55)
BACKGROUND = QColor(28, 33, 40)
ACCENT = QColor(90, 168, 236)
WHITE = QColor(245, 247, 250)


def draw_arrow(painter: QPainter, left: float, top: float, size: float) -> None:
    """White arrow pointing down with a tray line, inside a ``size`` square."""
    shaft_w = size * 0.16
    painter.setBrush(WHITE)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(left + (size - shaft_w) / 2, top + size * 0.10, shaft_w, size * 0.44, 3, 3)
    head = size * 0.34
    painter.drawPolygon(
        [
            QPointF(left + size / 2 - head / 2, top + size * 0.46),
            QPointF(left + size / 2 + head / 2, top + size * 0.46),
            QPointF(left + size / 2, top + size * 0.70),
        ]
    )
    pen = QPen(ACCENT, max(2.0, size * 0.06), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    y = int(top + size * 0.80)
    painter.drawLine(int(left + size * 0.24), y, int(left + size * 0.76), y)


def draw(size: int = SIZE) -> QImage:
    """The icon: rounded square with the arrow."""
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(BACKGROUND)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(2, 2, size - 4, size - 4, 12, 12)
    draw_arrow(painter, 0, 0, float(size))
    painter.end()
    return image


def draw_wizard(width: int, height: int, with_title: bool) -> QImage:
    """A flat dark picture for the setup wizard with the arrow and the name."""
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(BACKGROUND)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    logo = min(width * 0.62, height * 0.34)
    left = (width - logo) / 2
    top = height * (0.34 if with_title else 0.18)
    draw_arrow(painter, left, top, logo)
    if with_title:
        painter.setPen(WHITE)
        font = QFont("Segoe UI", 13)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            QRectF(0, top + logo + 14, width, 30),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            "PyDownloader",
        )
    painter.end()
    return image


def main() -> None:
    QApplication([])  # Qt needs an application object to save images
    OUT.parent.mkdir(parents=True, exist_ok=True)
    WIZARD_BIG.parent.mkdir(parents=True, exist_ok=True)
    results = {
        OUT: draw().save(str(OUT), "ICO"),
        WIZARD_BIG: draw_wizard(*WIZARD_BIG_SIZE, with_title=True).save(str(WIZARD_BIG), "BMP"),
        WIZARD_SMALL: draw_wizard(*WIZARD_SMALL_SIZE, with_title=False).save(
            str(WIZARD_SMALL), "BMP"
        ),
    }
    for path, ok in results.items():
        print(f"{path}: {'saved' if ok else 'failed'}")


if __name__ == "__main__":
    main()
