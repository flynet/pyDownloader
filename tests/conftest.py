"""Test fixtures: sample manifests from ``tests/data``."""

from __future__ import annotations

from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent / "data"

# Final URL of a manifest after redirects: relative links are resolved against it.
HLS_URL = "https://cdn.example.com/video/master.m3u8"
MPD_URL = "https://cdn.example.com/dash/manifest.mpd"


@pytest.fixture
def read():
    """Callable reading a fixture file by name."""

    def _read(name: str) -> str:
        return (DATA_DIR / name).read_text(encoding="utf-8")

    return _read
