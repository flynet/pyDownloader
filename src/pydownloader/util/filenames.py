"""File names for the downloaded videos: sanitizing, path limit, name conflicts."""

from __future__ import annotations

from pathlib import Path

# Reserved characters in Windows file names.
RESERVED_CHARS = set('<>:"/\\|?*')
_CONTROL_CHARS = {chr(i) for i in range(32)}
_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
# Windows paths are limited to 260 characters; keep a safety margin for the folder.
MAX_TITLE_LENGTH = 120


def sanitize_filename(title: str, suffix: str = ".mp4", max_length: int = MAX_TITLE_LENGTH) -> str:
    """Turn a page title into a legal Windows file name.

    Control characters and characters forbidden in Windows are replaced with
    ``_``, trailing dots and spaces are dropped (Windows ignores them), names
    reserved by Windows (``CON``, ``COM1`` ...) are prefixed to stay unique.
    The name is cut to ``max_length`` characters so that the full path stays
    inside the 260 character limit.
    """
    # Line breaks and tabs become spaces, other control characters become underscores.
    title = title.replace("\n", " ").replace("\t", " ").replace("\r", " ")
    cleaned = "".join("_" if ch in RESERVED_CHARS or ch in _CONTROL_CHARS else ch for ch in title)
    cleaned = cleaned.strip()
    cleaned = cleaned.strip(" .")
    if not cleaned:
        cleaned = "video"
    if cleaned.upper().split(".")[0] in _RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    stem = cleaned
    if len(stem) + len(suffix) > max_length:
        stem = stem[: max_length - len(suffix)]
        stem = stem.strip(" .")
        if not stem:
            stem = "video"
    return f"{stem}{suffix}"


def unique_path(directory: Path, name: str, suffix: str = ".mp4") -> Path:
    """Path for the output file; on a name conflict append `` (1)``, `` (2)`` and so on."""
    base = sanitize_filename(name, suffix)
    stem = base[: -len(suffix)] if base.endswith(suffix) else base
    candidate = directory / f"{stem}{suffix}"
    index = 1
    while candidate.exists():
        candidate = directory / f"{stem} ({index}){suffix}"
        index += 1
    return candidate


def fits_path(path: Path, limit: int = 260) -> bool:
    """Whether the full path stays within the classic Windows ``MAX_PATH`` limit."""
    return len(str(path)) <= limit
