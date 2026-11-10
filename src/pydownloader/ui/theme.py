"""Dark and light styling (spec 4.3).

The theme is applied as a QSS stylesheet, so the widgets of the window follow
the choice in the settings. ``system`` uses the palette of Windows.
"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from pydownloader.config.settings import ThemeName

DARK = {
    "background": "#1e1e1e",
    "panel": "#262626",
    "text": "#e6e6e6",
    "muted": "#9a9a9a",
    "accent": "#3b7fd7",
    "border": "#3a3a3a",
    "success": "#2e7d32",
    "error": "#b3261e",
}
LIGHT = {
    "background": "#ffffff",
    "panel": "#f2f2f2",
    "text": "#202020",
    "muted": "#6a6a6a",
    "accent": "#1565c0",
    "border": "#d0d0d0",
    "success": "#2e7d32",
    "error": "#b3261e",
}
QSS_TEMPLATE = """
QMainWindow, QWidget#central {{ background: {background}; }}
QPlainTextEdit#console {{
    background: {panel}; color: {text}; border: 1px solid {border};
    font-family: Consolas; font-size: 9pt;
}}
QFrame#card {{
    background: {panel}; border: 1px solid {border}; border-radius: 6px;
    padding: 8px;
}}
QLabel#cardTitle {{ color: {text}; font-size: 10pt; font-weight: bold; }}
QLabel#cardMeta {{ color: {muted}; font-size: 9pt; }}
QPushButton {{
    background: {accent}; color: #ffffff; border: 1px solid {border};
    border-radius: 4px; padding: 6px 12px;
}}
QPushButton:disabled {{ color: {muted}; background: {panel}; }}
QProgressBar {{
    background: {panel}; border: 1px solid {border}; border-radius: 4px;
    text-align: center; color: {text};
}}
QProgressBar::chunk {{ background: {accent}; }}
QStatusBar {{ background: {panel}; color: {text}; }}
QStatusBar QLabel {{ color: {text}; }}
QGroupBox {{ color: {text}; border: 1px solid {border}; border-radius: 4px; }}
QLabel {{ color: {text}; }}
QCheckBox {{ color: {text}; }}
QSpinBox, QComboBox, QLineEdit {{
    background: {background}; color: {text}; border: 1px solid {border};
    border-radius: 4px; padding: 3px;
}}
QSplitter::handle {{ background: {border}; }}
"""


def qss_for(theme: ThemeName) -> str:
    """The stylesheet for the chosen theme, ``""`` for the system theme."""
    if theme == "dark":
        return QSS_TEMPLATE.format(**DARK)
    if theme == "light":
        return QSS_TEMPLATE.format(**LIGHT)
    return ""


def apply_palette(app: QApplication, theme: ThemeName) -> None:
    """Set the palette for the system theme, so the widgets follow Windows."""
    if theme != "system":
        return
    palette = app.style().standardPalette()
    app.setPalette(palette)


def color_for(theme: ThemeName, key: str) -> QColor:
    """Color of a theme key, used by the cards for the state colors."""
    colors = DARK if theme == "dark" else LIGHT
    return QColor(colors[key])


def apply_theme(app: QApplication, theme: ThemeName) -> None:
    """Apply the stylesheet and the palette of the theme."""
    app.setStyleSheet(qss_for(theme))
    apply_palette(app, theme)


__all__ = ["DARK", "LIGHT", "apply_theme", "color_for", "qss_for"]
