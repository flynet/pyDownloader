"""Byte-range helpers shared by HLS, DASH and direct MP4 downloaders."""

from __future__ import annotations

import re
from dataclasses import dataclass

_CONTENT_RANGE_RE = re.compile(r"bytes\s+(\d+)\s*-\s*(\d+)\s*/\s*(\d+|\*)", re.IGNORECASE)
_CONTENT_RANGE_TOTAL_RE = re.compile(r"bytes\s+\*\s*/\s*(\d+)", re.IGNORECASE)
_HLS_BYTE_RANGE_RE = re.compile(r"^\s*(\d+)(?:@(\d+))?\s*$")


@dataclass(frozen=True)
class ByteRange:
    """Absolute byte range inside a file: ``start`` is 0-based, ``length`` is included."""

    start: int
    length: int

    @property
    def end(self) -> int:
        """Last byte of the range, inclusive."""
        return self.start + self.length - 1

    def header(self) -> str:
        """Value for an HTTP ``Range`` request header."""
        return f"bytes={self.start}-{self.end}"

    def to_hls(self) -> str:
        """Value of an ``EXT-X-BYTERANGE`` attribute, absolute form ``length@start``."""
        return f"{self.length}@{self.start}"


def parse_hls_byterange(value: str, previous_end: int | None) -> ByteRange:
    """Parse ``EXT-X-BYTERANGE`` (``length`` or ``length@start``).

    ``previous_end`` is the byte after the previous range in the same file; HLS
    requires continuation ranges, where only the length is given, to follow the
    previous segment.
    """
    match = _HLS_BYTE_RANGE_RE.match(value)
    if not match:
        raise ValueError(f"Некорректный BYTERANGE: {value!r}")
    length = int(match.group(1))
    if match.group(2) is not None:
        start = int(match.group(2))
    elif previous_end is not None:
        start = previous_end
    else:
        raise ValueError("BYTERANGE без offset и без предыдущего диапазона в том же файле")
    if length <= 0:
        raise ValueError(f"Длина BYTERANGE должна быть положительной: {value!r}")
    return ByteRange(start=start, length=length)


def content_range_total(value: str) -> int | None:
    """Total file size from a ``Content-Range`` header, ``None`` if it is absent.

    ``bytes 0-1/12345678`` gives 12345678. ``bytes 0-1/*`` (the server does not
    disclose the size) gives ``None``.
    """
    match = _CONTENT_RANGE_RE.match(value)
    if match:
        total = match.group(3)
        return int(total) if total.isdigit() else None
    match = _CONTENT_RANGE_TOTAL_RE.match(value)
    if match:
        return int(match.group(1))
    return None


def merge_ranges(ranges: list[ByteRange]) -> list[ByteRange]:
    """Sort and merge overlapping/adjacent ranges."""
    if not ranges:
        return []
    ordered = sorted(ranges, key=lambda r: (r.start, r.length))
    merged: list[ByteRange] = [ordered[0]]
    for current in ordered[1:]:
        last = merged[-1]
        if current.start <= last.end + 1:
            end = max(last.end, current.end)
            merged[-1] = ByteRange(start=last.start, length=end - last.start + 1)
        else:
            merged.append(current)
    return merged
