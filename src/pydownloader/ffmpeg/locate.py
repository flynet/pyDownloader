"""Locating ``ffmpeg.exe`` (spec 7.3).

The installer ships FFmpeg in ``{app}\bin\ffmpeg.exe``. In a source checkout
the binary comes from ``imageio-ffmpeg``, and a system ``ffmpeg`` on ``PATH``
is used when it is present.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

FFMPEG_NAME = "ffmpeg.exe"
NOT_FOUND = (
    "FFmpeg не найден. Положите ffmpeg.exe в папку bin рядом с программой или добавьте его в PATH"
)


class FfmpegNotFoundError(RuntimeError):
    """No FFmpeg binary is available."""


@dataclass(frozen=True)
class Ffmpeg:
    path: Path
    label: str

    @property
    def name(self) -> str:
        return self.path.name


def app_bin(production_root: Path | None) -> Path | None:
    """``{app}\bin`` of the installed application, ``None`` in a source checkout."""
    if production_root is None:
        return None
    return production_root / "bin"


def candidate_paths(
    production_root: Path | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> list[tuple[str, Path]]:
    """Paths to check, in the order of the spec: bundled first, then PATH."""
    out: list[tuple[str, Path]] = []
    bin_dir = app_bin(production_root)
    if bin_dir is not None:
        out.append(("bundled", bin_dir / FFMPEG_NAME))
    found = which("ffmpeg")
    if found:
        out.append(("PATH", Path(found)))
    return out


def imageio_ffmpeg_path() -> Path | None:
    """Binary of the ``imageio-ffmpeg`` package, ``None`` when it is not installed."""
    try:
        import imageio_ffmpeg
    except ImportError:
        return None
    try:
        path = imageio_ffmpeg.get_ffmpeg_exe()
    except (RuntimeError, OSError):
        # The package is present but its binary was removed from the bundle.
        return None
    return Path(path) if path else None


def locate_ffmpeg(
    production_root: Path | None = None,
    exists: Callable[[Path], bool] = lambda path: path.is_file(),
    which: Callable[[str], str | None] = shutil.which,
) -> Ffmpeg:
    """Bundled binary → ``PATH`` → the binary of ``imageio-ffmpeg``.

    Raises :class:`FfmpegNotFoundError` when nothing is found, so the UI can
    show :data:`NOT_FOUND`.
    """
    for label, path in candidate_paths(production_root, which):
        if exists(path):
            return Ffmpeg(path=path, label=label)
    dev = imageio_ffmpeg_path()
    if dev is not None and exists(dev):
        return Ffmpeg(path=dev, label="imageio-ffmpeg")
    raise FfmpegNotFoundError(NOT_FOUND)


def ffmpeg_env() -> dict[str, str]:
    """Environment for the FFmpeg process: quiet, no console prompts."""
    env = os.environ.copy()
    env.setdefault("AV_LOG_FORCE_NOCOLOR", "1")
    return env
