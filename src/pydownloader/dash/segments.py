"""Building the segment list from a ``SegmentTemplate``.

Supported: ``$Number$`` (``@Duration`` + ``@StartNumber``/``@EndNumber``),
``$Time$`` with ``SegmentTimeline``, ``$RepresentationID$``, ``$Bandwidth$``,
printf style padding ``$Number%05d$``, ``@Timescale``.
"""

from __future__ import annotations

import re

from pydownloader.dash.models import DashSegment

_TOKEN_RE = re.compile(r"\$(\w+)(?:%0(\d+)d)?\$")
# ``$$`` is the DASH escape for a literal dollar sign.
_ESC = "\x00"


def expand_template(
    template: str,
    *,
    number: int | None = None,
    time: int | None = None,
    representation_id: str = "",
    bandwidth: int = 0,
) -> str:
    """Replace ``$Number$``/``$Time$``/``$RepresentationID$``/``$Bandwidth$`` tokens."""

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        width = int(match.group(2)) if match.group(2) else 0
        if name == "Number":
            value = str(number)
        elif name == "Time":
            value = str(time)
        elif name == "RepresentationID":
            value = representation_id
        elif name == "Bandwidth":
            value = str(bandwidth)
        else:
            return match.group(0)
        if value == "None":
            return match.group(0)
        return value.zfill(width) if width else value

    escaped = template.replace("$$", _ESC)
    return _TOKEN_RE.sub(repl, escaped).replace(_ESC, "$")


def build_segments(
    media_template: str,
    *,
    start_number: int = 1,
    timescale: int = 1,
    duration: int | None = None,
    end_number: int | None = None,
    timeline: list[tuple[int | None, int, int]] | None = None,
    representation_id: str = "",
    bandwidth: int = 0,
    period_duration: float | None = None,
) -> list[DashSegment]:
    """Expand a ``SegmentTemplate`` into a list of segments.

    ``timeline`` is a list of ``(t, d, r)`` triplets from ``SegmentTimeline``
    (``None`` ``t`` means "continue from the previous segment").

    For ``$Number$`` without ``SegmentTimeline`` the last segment is taken from
    ``@EndNumber`` if it is present, otherwise it is computed from
    ``period_duration`` (``MPD@mediaPresentationDuration`` minus the period start).
    """
    segments: list[DashSegment] = []
    if timeline:
        t: int | None = None
        number = start_number
        for entry_t, d, r in timeline:
            if entry_t is not None:
                t = entry_t
            if t is None:
                raise ValueError("SegmentTimeline без @t и без предыдущего значения")
            for _ in range(r + 1):
                url = expand_template(
                    media_template,
                    number=number,
                    time=t,
                    representation_id=representation_id,
                    bandwidth=bandwidth,
                )
                segments.append(
                    DashSegment(
                        url=url,
                        duration=d / timescale,
                        number=number,
                        start=t / timescale,
                    )
                )
                t += d
                number += 1
        return segments

    if duration is None:
        return segments
    if end_number is not None:
        last = end_number
    elif period_duration is not None:
        last = start_number + int(period_duration * timescale / duration) - 1
    else:
        return []
    for number in range(start_number, last + 1):
        url = expand_template(
            media_template,
            number=number,
            time=(number - start_number) * duration,
            representation_id=representation_id,
            bandwidth=bandwidth,
        )
        segments.append(
            DashSegment(
                url=url,
                duration=duration / timescale,
                number=number,
                start=(number - start_number) * duration / timescale,
            )
        )
    return segments
