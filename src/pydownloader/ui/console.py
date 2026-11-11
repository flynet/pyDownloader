"""The console panel of the main window (spec 4.2, 4.3).

A read-only monospace text area showing every log line, including the reasons
why a source was skipped. The buffer is limited, so a long session does not
grow the memory.

The wall of the panel and the color of its text are the keys of the theme, so the log
is readable in every theme, and the level word of every line says which role the line
carries: the same roles as the yellow button and the red button of the top row
(spec 4.3 p.3).
"""

from __future__ import annotations

import logging
import time

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPlainTextEdit

#: Number of lines kept in the panel (spec 4.3).
MAX_LINES = 5000
MONOSPACE = "Consolas"
TIME_FORMAT = "%H:%M:%S"


class ConsolePanel(QPlainTextEdit):
    """Log view: the newest line is visible, older lines are dropped."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setMaximumBlockCount(MAX_LINES)
        self.setFont(QFont(MONOSPACE, 9))
        self.setObjectName("console")

    def append_line(self, line: str) -> None:
        """Add one line, keeping the view at the bottom when the user is there."""
        at_bottom = self.is_at_bottom()
        self.appendPlainText(line)
        if at_bottom:
            self._scroll_bottom()

    def is_at_bottom(self) -> bool:
        bar = self.verticalScrollBar()
        return bar.value() >= bar.maximum()

    def _scroll_bottom(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def show_info(self, message: str) -> None:
        self.append_line(f"[{self._stamp()}] INFO     {message}")

    def show_warning(self, message: str) -> None:
        self.append_line(f"[{self._stamp()}] WARNING  {message}")

    def show_error(self, message: str) -> None:
        self.append_line(f"[{self._stamp()}] ERROR    {message}")

    def clear_panel(self) -> None:
        self.clear()

    def logging_handler(self) -> logging.Handler:
        """Handler writing the application log into this panel."""
        from pydownloader.util.logging_setup import ConsoleHandler

        return ConsoleHandler(self.append_line)

    @staticmethod
    def _stamp() -> str:
        return time.strftime(TIME_FORMAT)


__all__ = ["MAX_LINES", "ConsolePanel"]
