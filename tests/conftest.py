"""Test fixtures: sample manifests from ``tests/data``."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from pydownloader.i18n import set_language

DATA_DIR = Path(__file__).parent / "data"

# Final URL of a manifest after redirects: relative links are resolved against it.
HLS_URL = "https://cdn.example.com/video/master.m3u8"
MPD_URL = "https://cdn.example.com/dash/manifest.mpd"


@pytest.fixture(scope="session", autouse=True)
def isolated_app_data(tmp_path_factory: pytest.TempPathFactory):
    """The whole suite writes to its own ``%APPDATA%`` and ``%LOCALAPPDATA%``.

    A window of the UI tests saves the settings on every console toggle, on the
    Apply of the dialog and on the close, and the path it writes is
    ``%APPDATA%/PyDownloader/settings.json`` — the file of the user. Without the
    redirect the suite leaves the downloads folder of the developer as the temp
    folder of one test, so the installed program starts with that temp path, and
    the profile, the logs and Chromium of the tests go to the real LocalAppData.
    The redirect is for the whole session: the profile is moved once by the code
    of ``paths.py``, so a per-test folder would run the migration every time.

    The system temp folder is moved out of the tree of the tests as well: the
    startup code treats a settings path inside ``%TEMP%`` as the folder of a test
    run, and the temp folder of pytest would make every ``tmp_path`` one. The tool
    of the screenshots runs with the same rule (``isolate_app_data`` of
    ``config/paths.py``).
    """
    root = tmp_path_factory.mktemp("appdata")
    temp = root / "temp"
    temp.mkdir(parents=True, exist_ok=True)
    old_env = {key: os.environ.get(key) for key in ("APPDATA", "LOCALAPPDATA")}
    old_temp = tempfile.tempdir
    os.environ["APPDATA"] = str(root / "roaming")
    os.environ["LOCALAPPDATA"] = str(root / "local")
    tempfile.tempdir = str(temp)
    yield root
    for key, value in old_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    tempfile.tempdir = old_temp


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
