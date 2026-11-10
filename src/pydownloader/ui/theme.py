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
    "accent_hover": "#4a8ce0",
    "accent_pressed": "#2f6cbb",
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
    "accent_hover": "#1b74d4",
    "accent_pressed": "#11509b",
    "border": "#d0d0d0",
    "success": "#2e7d32",
    "error": "#b3261e",
}
QSS_TEMPLATE = """
QMainWindow, QWidget#central, QDialog {{ background: {background}; }}
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
QPushButton:hover {{ background: {accent_hover}; }}
QPushButton:pressed {{ background: {accent_pressed}; }}
QPushButton:disabled {{ color: {muted}; background: {panel}; }}
QToolButton {{
    background: {panel}; color: {text}; border: 1px solid {border};
    border-radius: 4px; padding: 4px 8px;
}}
QToolButton:hover {{ background: {border}; }}
QMenu {{ background: {panel}; color: {text}; border: 1px solid {border}; }}
QMenu::item {{ padding: 5px 22px 5px 16px; }}
QMenu::item:selected {{ background: {accent}; color: #ffffff; }}
QMenu::separator {{ height: 1px; background: {border}; margin: 4px 8px; }}
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
QSpinBox::up-button, QSpinBox::down-button {{
    background: {panel}; border-left: 1px solid {border};
}}
QComboBox QAbstractItemView {{
    background: {panel}; color: {text}; border: 1px solid {border};
    selection-background-color: {accent}; selection-color: #ffffff;
}}
QScrollArea {{ background: {background}; border: none; }}
QScrollBar:vertical {{ background: {background}; width: 12px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {border}; border-radius: 6px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {muted}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QSplitter::handle {{ background: {border}; }}
QTabWidget::pane {{ border: 1px solid {border}; }}
QTabBar::tab {{
    background: {panel}; color: {text}; padding: 5px 12px;
    border: 1px solid {border}; border-bottom: none;
}}
QTabBar::tab:selected {{ background: {background}; color: {text}; }}
"""


def qss_for(theme: ThemeName) -> str:
    """The stylesheet for the chosen theme, ``""`` for the system theme."""
    if theme == "dark":
        return QSS_TEMPLATE.format(**DARK)
    if theme == "light":
        return QSS_TEMPLATE.format(**LIGHT)
    return ""


def apply_palette(app: QApplication, theme: ThemeName) -> None:
    """Reset the palette to the style default for the system theme.

    The dark and light themes paint everything through QSS, so the palette of
    the style is only relevant for the ``system`` choice.
    """
    if theme != "system":
        return
    palette = app.style().standardPalette()
    app.setPalette(palette)


def color_for(theme: ThemeName, key: str) -> QColor:
    """Color of a theme key, used by the cards for the state colors."""
    colors = DARK if theme == "dark" else LIGHT
    return QColor(colors[key])


def apply_theme(app: QApplication, theme: ThemeName) -> None:
    """Apply the stylesheet and the palette of the theme.

    The Fusion style is used for every theme: the Windows style paints parts of
    the widgets natively and ignores the stylesheet, which is what makes buttons
    of a dark theme look broken (spec 4.3).
    """
    if app.style().objectName().lower() != "fusion":
        app.setStyle("Fusion")
    app.setStyleSheet(qss_for(theme))
    apply_palette(app, theme)


__all__ = ["DARK", "LIGHT", "apply_theme", "color_for", "qss_for"]
