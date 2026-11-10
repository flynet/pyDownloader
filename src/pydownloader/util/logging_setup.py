"""Logging: a rotating file in %LOCALAPPDATA%/PyDownloader/logs plus a console handler.

The Qt console panel (``ui/console_panel.py``, M7) registers itself as a handler, so
every record goes to the file and to the window at the same time. Records are formatted
as required by the spec: ``[12:34:56] INFO  Найден HLS-поток 1080p: https://...``
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path

MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3
TIME_FORMAT = "%H:%M:%S"


def record_line(record: logging.LogRecord) -> str:
    """Format a record as ``[HH:MM:SS] LEVEL  message``."""
    stamp = time.strftime(TIME_FORMAT, time.localtime(record.created))
    level = record.levelname.ljust(7)
    return f"[{stamp}] {level}  {record.getMessage()}"


class ConsoleHandler(logging.Handler):
    """Handler forwarding records to a callback (the console panel)."""

    def __init__(self, callback: Callable[[str], None]) -> None:
        super().__init__()
        self._callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._callback(record_line(record))
        except Exception:  # pragma: no cover - the GUI must never break logging
            self.handleError(record)


def setup_logging(
    log_file: Path,
    console_callback: Callable[[str], None] | None = None,
    level: int = logging.DEBUG,
) -> logging.Logger:
    """Configure the application logger: rotating file plus the console panel."""
    logger = logging.getLogger("pydownloader")
    logger.setLevel(level)
    logger.propagate = False
    logger.handlers.clear()

    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(file_handler)

    if console_callback is not None:
        logger.addHandler(ConsoleHandler(console_callback))
    return logger
