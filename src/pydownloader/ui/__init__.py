"""Widgets of the main window: cards, console, settings dialog, themes."""

from pydownloader.ui.card import SourceCard
from pydownloader.ui.console import ConsolePanel
from pydownloader.ui.main_window import MainWindow
from pydownloader.ui.settings_panel import SettingsDialog
from pydownloader.ui.theme import apply_theme, qss_for

__all__ = [
    "ConsolePanel",
    "MainWindow",
    "SettingsDialog",
    "SourceCard",
    "apply_theme",
    "qss_for",
]
