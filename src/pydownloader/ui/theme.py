"""Dark, light and themed styling (spec 4.3).

The theme is applied as a QSS stylesheet and as the palette of the application, so
the widgets of the window follow the choice in the settings: a widget with no rule
of its own paints the palette, and the palette of Windows is not the theme.
``system`` uses the palette of Windows.

Every color of a theme is a key, so one role is one color in the whole window: the
accent of the buttons, the yellow of «Clear downloaded», the red of «Clear all», the
color of a finished file, the badge of a format, the wall of the console (spec 4.3
p.3). The three theme palettes — «Cartoons», «Neon», «Pink» — are named by their
style, not by the age or the sex of the person who uses them (spec 4.3 p.3).
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
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
    # The second row of the window: «Clear downloaded» is yellow, «Clear all» is
    # red, so the two actions of the list are told apart by the color (spec 4.1 p.1).
    "warn": "#d9a441",
    "warn_hover": "#e3b155",
    "warn_pressed": "#b98c36",
    "warn_text": "#202020",
    "danger": "#b3261e",
    "danger_hover": "#c23127",
    "danger_pressed": "#8e1f19",
    "danger_text": "#ffffff",
    # The console panel and the words of its levels: the dark theme paints the log
    # the same color as before, so the new themes do not change the dark one.
    "console_bg": "#262626",
    "console_text": "#e6e6e6",
    # The bar of a running file is the accent, the bar of a finished one is the
    # green of the theme (spec 4.1 p.3).
    "chunk_start": "#3b7fd7",
    "chunk_end": "#3b7fd7",
    "done": "#2ea64f",
    "done_text": "#e6e6e6",
    # The badge of a format: the color of the kind, the text of the badge.
    "badge_hls": "#3b7fd7",
    "badge_hls_text": "#ffffff",
    "badge_dash": "#7b5cc7",
    "badge_dash_text": "#ffffff",
    "badge_mp4": "#2e7d32",
    "badge_mp4_text": "#ffffff",
    "badge_youtube": "#c4302b",
    "badge_youtube_text": "#ffffff",
    "badge_mp3": "#a86a2d",
    "badge_mp3_text": "#ffffff",
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
    # The same two colors of the second row in the light theme: the yellow of
    # «Clear downloaded» is darker than the white of the window, so the yellow text
    # stays dark and the row reads the same in both themes.
    "warn": "#d9a441",
    "warn_hover": "#e3b155",
    "warn_pressed": "#b98c36",
    "warn_text": "#202020",
    "danger": "#b3261e",
    "danger_hover": "#c23127",
    "danger_pressed": "#8e1f19",
    "danger_text": "#ffffff",
    "console_bg": "#f2f2f2",
    "console_text": "#202020",
    "chunk_start": "#1565c0",
    "chunk_end": "#1565c0",
    "done": "#2ea64f",
    "done_text": "#202020",
    "badge_hls": "#3b7fd7",
    "badge_hls_text": "#ffffff",
    "badge_dash": "#7b5cc7",
    "badge_dash_text": "#ffffff",
    "badge_mp4": "#2e7d32",
    "badge_mp4_text": "#ffffff",
    "badge_youtube": "#c4302b",
    "badge_youtube_text": "#ffffff",
    "badge_mp3": "#a86a2d",
    "badge_mp3_text": "#ffffff",
}
# «Cartoons»: a warm cream wall, white cards, the dark navy of the text, the blue of
# the sky for the buttons, the orange of the bar of a running file. The text of a
# badge is dark when the badge is bright, so a child reads the format of the video.
CARTOONS = {
    "background": "#fff6e0",
    "panel": "#ffffff",
    "text": "#2d2a4a",
    "muted": "#6b6890",
    # «Cartoons» is bright, so the accent and the red are taken to the darker edge of
    # the family: the white letters of a button read on them (spec 4.3 p.3).
    "accent": "#257de1",
    "accent_hover": "#3d95f0",
    "accent_pressed": "#1d6fd6",
    "border": "#2d2a4a",
    "success": "#4cd964",
    "error": "#e63e45",
    "warn": "#ffc93c",
    "warn_hover": "#ffd45c",
    "warn_pressed": "#e0a92e",
    "warn_text": "#2d2a4a",
    "danger": "#e63e45",
    "danger_hover": "#ef4a51",
    "danger_pressed": "#c81e26",
    "danger_text": "#ffffff",
    "console_bg": "#fffdf5",
    "console_text": "#2d2a4a",
    "chunk_start": "#ff8a3d",
    "chunk_end": "#ff8a3d",
    "done": "#4cd964",
    "done_text": "#2d2a4a",
    "badge_hls": "#7b61ff",
    "badge_hls_text": "#ffffff",
    "badge_dash": "#ff8fab",
    "badge_dash_text": "#2d2a4a",
    "badge_mp4": "#4cd964",
    "badge_mp4_text": "#2d2a4a",
    "badge_youtube": "#e63e45",
    "badge_youtube_text": "#ffffff",
    "badge_mp3": "#ff8a3d",
    "badge_mp3_text": "#2d2a4a",
}
# «Neon»: the wall of a game, the violet of the buttons, the cyan of the badges, the
# lime of a finished file. The text on a bright badge is the dark of the card, so the
# neon does not eat the letters.
NEON = {
    "background": "#0e0e1a",
    "panel": "#1a1a2e",
    "text": "#ededff",
    "muted": "#9a9ac0",
    "accent": "#8b5cf6",
    "accent_hover": "#9d70f8",
    "accent_pressed": "#7343d1",
    "border": "#2e2e4d",
    "success": "#a3e635",
    "error": "#e53252",
    "warn": "#fbbf24",
    "warn_hover": "#fcd34d",
    "warn_pressed": "#d9a413",
    "warn_text": "#1a1a2e",
    "danger": "#e53252",
    "danger_hover": "#ef4160",
    "danger_pressed": "#c01035",
    "danger_text": "#ffffff",
    "console_bg": "#08080f",
    "console_text": "#cfcff5",
    # The bar of a running file is the gradient of the theme: violet into cyan.
    "chunk_start": "#8b5cf6",
    "chunk_end": "#22d3ee",
    "done": "#a3e635",
    "done_text": "#1a1a2e",
    "badge_hls": "#22d3ee",
    "badge_hls_text": "#1a1a2e",
    "badge_dash": "#8b5cf6",
    "badge_dash_text": "#ffffff",
    "badge_mp4": "#a3e635",
    "badge_mp4_text": "#1a1a2e",
    "badge_youtube": "#e53252",
    "badge_youtube_text": "#ffffff",
    "badge_mp3": "#f472b6",
    "badge_mp3_text": "#1a1a2e",
}
# «Pink»: pastel on a light base, the rose of the buttons, the lavender of the badge
# of HLS, the mint of a finished file. The names of the theme is its style.
PINK = {
    "background": "#fff0f6",
    "panel": "#ffffff",
    "text": "#4a2340",
    "muted": "#8a5c7e",
    # «Pink» is pastel, and pastel is bright: the accent and the red go to the deeper
    # edge of the family so the white letters of the buttons read (spec 4.3 p.3).
    "accent": "#d7447e",
    "accent_hover": "#e5558b",
    "accent_pressed": "#b83364",
    "border": "#f8c8dc",
    "success": "#5ed3b0",
    "error": "#e04448",
    "warn": "#ffb86b",
    "warn_hover": "#ffc484",
    "warn_pressed": "#e79c50",
    "warn_text": "#4a2340",
    "danger": "#e04448",
    "danger_hover": "#ea5458",
    "danger_pressed": "#b3261e",
    "danger_text": "#ffffff",
    "console_bg": "#ffffff",
    "console_text": "#4a2340",
    "chunk_start": "#ff5fa2",
    "chunk_end": "#b794f6",
    "done": "#5ed3b0",
    "done_text": "#4a2340",
    "badge_hls": "#b794f6",
    "badge_hls_text": "#4a2340",
    "badge_dash": "#c084fc",
    "badge_dash_text": "#4a2340",
    "badge_mp4": "#5ed3b0",
    "badge_mp4_text": "#4a2340",
    "badge_youtube": "#e04448",
    "badge_youtube_text": "#ffffff",
    "badge_mp3": "#ff8fb8",
    "badge_mp3_text": "#4a2340",
}
#: Theme value -> the colors of its palette. The system theme has no palette of its
#: own: it paints the palette of the style, so its QSS is empty.
PALETTES: dict[ThemeName, dict[str, str]] = {
    "dark": DARK,
    "light": LIGHT,
    "cartoons": CARTOONS,
    "neon": NEON,
    "pink": PINK,
}
QSS_TEMPLATE = """
QMainWindow, QWidget#central, QDialog {{ background: {background}; }}
QPlainTextEdit#console {{
    background: {console_bg}; color: {console_text}; border: 1px solid {border};
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
#clearDownloaded {{
    background: {warn}; color: {warn_text}; border: 1px solid {border};
}}
#clearDownloaded:hover {{ background: {warn_hover}; }}
#clearDownloaded:pressed {{ background: {warn_pressed}; }}
#clearAll {{
    background: {danger}; color: {danger_text}; border: 1px solid {border};
}}
#clearAll:hover {{ background: {danger_hover}; }}
#clearAll:pressed {{ background: {danger_pressed}; }}
QToolButton {{
    background: {panel}; color: {text}; border: 1px solid {border};
    border-radius: 4px; padding: 4px 8px;
}}
QToolButton:hover {{ background: {border}; }}
#cardRemove {{ padding: 4px; }}
QMenu {{ background: {panel}; color: {text}; border: 1px solid {border}; }}
QMenu::item {{ padding: 5px 22px 5px 16px; }}
QMenu::item:selected {{ background: {accent}; color: #ffffff; }}
QMenu::separator {{ height: 1px; background: {border}; margin: 4px 8px; }}
QProgressBar {{
    background: {panel}; border: 1px solid {border}; border-radius: 4px;
    text-align: center; color: {text};
}}
QProgressBar::chunk {{
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 {chunk_start}, stop: 1 {chunk_end});
}}
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
#cardArea {{ background: {background}; }}
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
    colors = PALETTES.get(theme)
    if colors is None:
        return ""
    return QSS_TEMPLATE.format(**colors)


def apply_palette(app: QApplication, theme: ThemeName) -> None:
    """Set the palette of the app to the colors of the theme.

    The dark, the light and the three theme palettes paint the widgets through QSS,
    but a widget with no rule of its own (the wall behind the cards, the wrapper of a
    section, the box of a checkbox) paints the color of the palette. The palette Qt
    reads from Windows follows the system theme: on a machine with the dark mode of
    Windows the palette is dark, so the light theme showed a dark wall behind the list
    of cards. The palette of the app is set to the colors of the chosen theme, so
    every widget takes the theme, whatever Windows says (spec 4.3). The ``system``
    choice takes the palette of the style.
    """
    palette = app.style().standardPalette()
    colors = PALETTES.get(theme)
    if colors is None:
        app.setPalette(palette)
        return
    window = QColor(colors["background"])
    panel = QColor(colors["panel"])
    text = QColor(colors["text"])
    accent = QColor(colors["accent"])
    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, panel)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, panel)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.ToolTipBase, panel)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(colors["muted"]))
    palette.setColor(QPalette.ColorRole.Highlight, accent)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)


def color_for(theme: ThemeName, key: str) -> QColor:
    """Color of a theme key, used by the cards for the state colors.

    The system theme has no palette of its own, so its colors are the colors of the
    light theme: the light theme is the one the palette of Windows shows on a machine
    without the dark mode, and the marks of the buttons stay readable on it.
    """
    return QColor(PALETTES.get(theme, LIGHT)[key])


def badge_style(theme: ThemeName, kind: str) -> str:
    """The QSS of the badge of a format: the colors of the theme for that kind.

    A badge is small, and its letters are the whole message of it, so the text is the
    dark of the theme when the badge is bright and white when the badge is deep
    (spec 4.3 p.3).
    """
    colors = PALETTES.get(theme, LIGHT)
    return f"color: {colors[f'badge_{kind}_text']}; background: {colors[f'badge_{kind}']};"


def luminance(color: QColor) -> float:
    """The relative luminance of a color, the WCAG formula."""
    channels = []
    for value in (color.red(), color.green(), color.blue()):
        part = value / 255
        channels.append(part / 12.92 if part <= 0.03928 else ((part + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(a: QColor, b: QColor) -> float:
    """The WCAG contrast ratio of two colors: 1 is the same color, 21 is black on white."""
    first, second = luminance(a), luminance(b)
    high, low = max(first, second), min(first, second)
    return (high + 0.05) / (low + 0.05)


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


__all__ = [
    "CARTOONS",
    "DARK",
    "LIGHT",
    "NEON",
    "PALETTES",
    "PINK",
    "apply_palette",
    "apply_theme",
    "badge_style",
    "color_for",
    "contrast_ratio",
    "luminance",
    "qss_for",
]
