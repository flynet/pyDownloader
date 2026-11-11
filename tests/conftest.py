"""Test fixtures: sample manifests from ``tests/data``."""

from __future__ import annotations

from pathlib import Path

import pytest

from pydownloader.i18n import set_language

DATA_DIR = Path(__file__).parent / "data"

# Final URL of a manifest after redirects: relative links are resolved against it.
HLS_URL = "https://cdn.example.com/video/master.m3u8"
MPD_URL = "https://cdn.example.com/dash/manifest.mpd"


@pytest.fixture(scope="session", autouse=True)
def log_to_tmp(tmp_path_factory: pytest.TempPathFactory):
    """The suite writes its log to the test folder, never to ``{app}\\logs\\app.log``.

    The UI tests run the worker and the real FFmpeg, so a log handler of the
    production layout would write the test lines into the log the user sends as a
    report. ``setup_logging`` replaces the handlers of the logger, so one call at
    the start of the session keeps the trail in the test directory.
    """
    from pydownloader.util.logging_setup import setup_logging

    setup_logging(tmp_path_factory.mktemp("logs") / "app.log")


@pytest.fixture(scope="session", autouse=True)
def russian_language():
    """The suite checks the Russian texts: it is written in Russian (spec 4.3)."""
    set_language("ru")


@pytest.fixture
def read():
    """Callable reading a fixture file by name."""

    def _read(name: str) -> str:
        return (DATA_DIR / name).read_text(encoding="utf-8")

    return _read
