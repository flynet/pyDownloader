"""Formatting of the length of a task into the text a person reads."""

from __future__ import annotations


def format_duration(seconds: float | None) -> str:
    """``12:34`` for 12 minutes 34 seconds, ``""`` when the length is unknown.

    The minutes and the seconds are digits, so the text needs no translation and
    is read the same way in every language of the catalog.
    """
    if seconds is None:
        return ""
    total = round(seconds)
    minutes, rest = divmod(total, 60)
    return f"{minutes}:{rest:02d}"
