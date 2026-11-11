"""Draws the application icon and the Inno Setup wizard images (spec 7.3).

Run once with ``uv run python tools/make_icon.py``; the files are committed, so
the build does not need Qt to produce them:

- ``assets/icon.ico`` — the program and installer icon;
- ``installer/assets/wizard.bmp`` — the big side picture of the setup wizard;
- ``installer/assets/wizard-small.bmp`` — the small picture of the header.

The picture is drawn by ``pydownloader.ui.app_icon``, the same code the tray icon
of the notification area uses, so the program, the installer and the tray are the
same style (spec 4.2 p.7).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

from pydownloader.ui.app_icon import BACKGROUND, SIZE, WHITE, draw, draw_arrow

OUT = Path("assets") / "icon.ico"
WIZARD_BIG = Path("installer") / "assets" / "wizard.bmp"
WIZARD_SMALL = Path("installer") / "assets" / "wizard-small.bmp"
WIZARD_BIG_SIZE = (164, 314)
WIZARD_SMALL_SIZE = (55, 55)


def draw_wizard(width: int, height: int, with_title: bool) -> QImage:
    """A flat dark picture for the setup wizard with the arrow and the name."""
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(BACKGROUND)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    logo = min(width * 0.62, height * 0.34)
    left = (width - logo) / 2
    top = height * (0.34 if with_title else 0.18)
    draw_arrow(painter, left, top, logo, WHITE)
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
        OUT: draw(SIZE).save(str(OUT), "ICO"),
        WIZARD_BIG: draw_wizard(*WIZARD_BIG_SIZE, with_title=True).save(str(WIZARD_BIG), "BMP"),
        WIZARD_SMALL: draw_wizard(*WIZARD_SMALL_SIZE, with_title=False).save(
            str(WIZARD_SMALL), "BMP"
        ),
    }
    for path, ok in results.items():
        print(f"{path}: {'saved' if ok else 'failed'}")


if __name__ == "__main__":
    main()
