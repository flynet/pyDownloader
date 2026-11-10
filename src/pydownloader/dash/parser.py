"""MPEG-DASH manifest parser (``.mpd``).

Supported: ``BaseURL`` chains, multiple ``Period``, ``AdaptationSet``,
``Representation``, ``SegmentTemplate`` (``$Number$``/``$Time$``/
``$RepresentationID$``/``$Bandwidth$``), ``SegmentTimeline``, ``SegmentList``,
``SegmentBase`` (progressive single file), ``type="dynamic"``.
Namespaces are ignored, so the parser works with DASH IF, MPEG-DASH and
Microsoft/Smooth Streaming style manifests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from lxml import etree

from pydownloader.dash.models import (
    ContentType,
    DashInit,
    DashManifest,
    DashPeriod,
    DashRepresentation,
    DashSegment,
    MPDType,
)
from pydownloader.dash.segments import build_segments, expand_template
from pydownloader.util.ranges import ByteRange
from pydownloader.util.urls import base_dir_url, resolve_url

_ISO_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?", re.IGNORECASE)


class ManifestParseError(ValueError):
    """The text is not a valid MPD."""


def _local(tag: str) -> str:
    """Local name of a tagged element, ignoring its namespace."""
    return tag.split("}", 1)[1] if "}" in tag else tag


def _child(element, name: str):
    """First child element with a given local name (namespace ignored)."""
    for child in element:
        if _local(child.tag) == name:
            return child
    return None


def _attr(element, name: str) -> str | None:
    """Attribute of an element, accepting the schema capitalization and the common lowercase form.

    The MPEG-DASH schema writes ``SegmentTemplate/@Media`` and ``@Initialization``
    capitalized, while ``@duration``/``@timescale``/``@startNumber`` are lowercase;
    many packaging tools use lowercase for everything.
    """
    for key in (name, f"{name[0].lower()}{name[1:]}", name.lower()):
        value = element.get(key)
        if value is not None:
            return value
    return None


def _parse_iso_duration(value: str | None) -> float | None:
    if not value:
        return None
    match = _ISO_DURATION_RE.match(value.strip())
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = float(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def _parse_range(value: str | None) -> ByteRange | None:
    """``range="0-100"`` of DASH is an inclusive byte range."""
    if not value:
        return None
    parts = value.strip().split("-")
    if len(parts) != 2:
        return None
    try:
        start, end = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    return ByteRange(start=start, length=end - start + 1)


def _resolve_base(base: str, value: str | None) -> str:
    """DASH ``BaseURL`` rule: a relative value is appended, an absolute one replaces the base."""
    if not value or not value.strip():
        return base
    value = value.strip()
    if "://" in value:
        return value
    return (base if base.endswith("/") else f"{base}/") + value


def _content_type(
    content_type: str | None, mime: str | None, codecs: str | None, width, height
) -> ContentType:
    text = (content_type or mime or codecs or "").lower()
    if text.startswith("audio/"):
        return "audio"
    if text.startswith("text/") or text.startswith("application/sub") or "subtitles" in text:
        return "text"
    if text.startswith("video/"):
        return "video"
    # No explicit type: a representation with a resolution is video, otherwise audio.
    if width is not None and height is not None:
        return "video"
    return "audio"


@dataclass
class _Level:
    """Inherited settings of one XML level (MPD, Period, AdaptationSet)."""

    base: str
    content_type: str | None = None
    mime: str | None = None
    lang: str | None = None
    segment_template: Any = None
    segment_list: Any = None
    segment_base: Any = None
    content_protection: list[tuple[str, str]] = field(default_factory=list)


def _content_protection(element) -> list[tuple[str, str]]:
    """``ContentProtection`` entries of one element as ``(schemeIdUri, value)``."""
    entries: list[tuple[str, str]] = []
    for child in element:
        if _local(child.tag) == "ContentProtection":
            entries.append(
                (child.get("schemeIdUri", "").lower(), child.get("Value", child.get("value", "")))
            )
    return entries


def _level_from(element, base: str, parent: _Level) -> _Level:
    level = _Level(
        base=base,
        content_type=parent.content_type,
        mime=parent.mime,
        lang=parent.lang,
        segment_template=parent.segment_template,
        segment_list=parent.segment_list,
        segment_base=parent.segment_base,
        content_protection=list(parent.content_protection),
    )
    level.content_protection.extend(_content_protection(element))
    for child in element:
        name = _local(child.tag)
        if name == "BaseURL":
            level.base = _resolve_base(level.base, child.text)
    if element.get("contentType"):
        level.content_type = element.get("contentType")
    if element.get("mimeType"):
        level.mime = element.get("mimeType")
    if element.get("lang"):
        level.lang = element.get("lang")
    template = _child(element, "SegmentTemplate")
    if template is not None:
        level.segment_template = template
    segment_list = _child(element, "SegmentList")
    if segment_list is not None:
        level.segment_list = segment_list
    segment_base = _child(element, "SegmentBase")
    if segment_base is not None:
        level.segment_base = segment_base
    return level


def _init_from(element, base: str, keys: tuple[str, ...]) -> DashInit | None:
    """Init segment of a ``SegmentTemplate``/``SegmentList``/``SegmentBase``."""
    init_el = _child(element, "Initialization")
    if init_el is not None:
        for key in keys:
            source = init_el.get(key)
            if source:
                return DashInit(
                    url=resolve_url(base, source), byte_range=_parse_range(init_el.get("range"))
                )
        return None
    # ``SegmentTemplate`` allows the init URL as an attribute as well.
    source = _attr(element, "Initialization")
    if source:
        return DashInit(
            url=resolve_url(base, source), byte_range=_parse_range(_attr(element, "range"))
        )
    return None


def _timeline(element) -> list[tuple[int | None, int, int]] | None:
    timeline = _child(element, "SegmentTimeline")
    if timeline is None:
        return None
    entries: list[tuple[int | None, int, int]] = []
    for item in timeline:
        if _local(item.tag) != "S":
            continue
        d = item.get("d")
        if d is None:
            continue
        t_value = item.get("t")
        t = int(t_value) if t_value is not None else None
        r = int(item.get("r", 0))
        entries.append((t, int(d), r))
    return entries or None


def _build_representation(
    rep, level: _Level, base: str, period_duration: float | None = None
) -> DashRepresentation:
    """Build one representation, inheriting the AdaptationSet/Period level when needed."""
    if rep is not None:
        level = _level_from(rep, base, level)
        base = level.base
        if rep.get("baseURL"):
            base = _resolve_base(base, rep.get("baseURL"))
    rep_id = (rep.get("id") if rep is not None else None) or ""
    width = _int(rep.get("width")) if rep is not None else None
    height = _int(rep.get("height")) if rep is not None else None
    bandwidth = (_int(rep.get("bandwidth")) if rep is not None else None) or 0
    mime = (rep.get("mimeType") if rep is not None else None) or level.mime
    codecs = rep.get("codecs") if rep is not None else None
    content_type = _content_type(
        (rep.get("contentType") if rep is not None else None) or level.content_type,
        mime,
        codecs,
        width,
        height,
    )
    lang = (rep.get("lang") if rep is not None else None) or level.lang

    template = level.segment_template
    segment_list = level.segment_list
    segment_base = level.segment_base

    init: DashInit | None = None
    segments: list[DashSegment] = []
    progressive = False
    progressive_url: str | None = None

    media_template = _attr(template, "Media") if template is not None else None
    if template is not None and media_template:
        init = _init_from(template, base, ("sourceURL", "source"))
        timescale = _int(_attr(template, "Timescale")) or 1
        start_number = _int(_attr(template, "StartNumber")) or 1
        end_number = _int(_attr(template, "EndNumber"))
        duration = _int(_attr(template, "Duration"))
        raw = build_segments(
            media_template,
            start_number=start_number,
            timescale=timescale,
            duration=duration,
            end_number=end_number,
            timeline=_timeline(template),
            representation_id=rep_id,
            bandwidth=bandwidth,
            period_duration=period_duration,
        )
        segments = [
            DashSegment(
                url=resolve_url(base, seg.url),
                duration=seg.duration,
                number=seg.number,
                start=seg.start,
            )
            for seg in raw
        ]
    elif segment_list is not None:
        init = _init_from(segment_list, base, ("sourceURL", "source"))
        timeline = _timeline(segment_list)
        urls = [child for child in segment_list if _local(child.tag) == "SegmentURL"]
        durations = (
            [seg.duration for seg in build_segments("", timeline=timeline)] if timeline else []
        )
        for index, url_el in enumerate(urls):
            media = url_el.get("media", "")
            segment_duration = durations[index] if index < len(durations) else 0.0
            segments.append(
                DashSegment(
                    url=resolve_url(base, media),
                    duration=segment_duration,
                    number=index,
                    byte_range=_parse_range(url_el.get("range")),
                )
            )
    elif segment_base is not None:
        init = _init_from(segment_base, base, ("sourceURL", "source"))
        progressive = True
        progressive_url = base

    if init is not None:
        # The initialization URL may use $RepresentationID$/$Bandwidth$ too,
        # e.g. "$RepresentationID$/$RepresentationID$_0.m4v" (DASH-IF live profile).
        init = DashInit(
            url=expand_template(init.url, representation_id=rep_id, bandwidth=bandwidth),
            byte_range=init.byte_range,
        )

    return DashRepresentation(
        id=rep_id,
        content_type=content_type,
        mime_type=mime or "",
        codecs=codecs,
        width=width,
        height=height,
        bandwidth=bandwidth,
        language=lang,
        init=init,
        segments=segments,
        progressive=progressive,
        progressive_url=progressive_url,
        content_protection=list(level.content_protection),
    )


def _int(value: str | None) -> int | None:
    if value is None:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    return int(digits) if digits else None


def _parse_period(
    element, base: str, media_duration: float | None = None, default_start: float | None = None
) -> DashPeriod:
    start = _parse_iso_duration(element.get("start"))
    if start is None:
        start = default_start
    # Period@start defaults to 0 for the first period; without it the duration
    # of a $Number$ template could not be computed from the MPD duration.
    effective_start = start if start is not None else 0.0
    period_duration = (
        max(0.0, media_duration - effective_start) if media_duration is not None else None
    )
    level = _level_from(element, base, _Level(base=base))
    representations: list[DashRepresentation] = []
    for child in element:
        name = _local(child.tag)
        if name == "AdaptationSet":
            set_level = _level_from(child, level.base, level)
            reps = [c for c in child if _local(c.tag) == "Representation"]
            if reps:
                for rep in reps:
                    representations.append(
                        _build_representation(rep, set_level, set_level.base, period_duration)
                    )
            else:
                # An AdaptationSet without representations describes one stream itself.
                representations.append(
                    _build_representation(None, set_level, set_level.base, period_duration)
                )
        elif name == "Representation":
            representations.append(_build_representation(child, level, level.base, period_duration))
    return DashPeriod(id=element.get("id", ""), start=start, representations=representations)


def parse_mpd(text: str, manifest_url: str) -> DashManifest:
    """Parse ``.mpd`` XML into a :class:`DashManifest` with absolute URLs."""
    if not text.strip():
        raise ManifestParseError("Пустой ответ манифеста")
    try:
        root = etree.fromstring(text.encode("utf-8"))
    except etree.XMLSyntaxError as exc:
        raise ManifestParseError(f"MPD не разобран: {exc}") from exc
    if _local(root.tag) != "MPD":
        raise ManifestParseError("Корневой элемент не MPD")
    base = base_dir_url(manifest_url)
    media_duration = _parse_iso_duration(root.get("mediaPresentationDuration"))
    raw_type: str = str(root.get("type") or "static").lower()
    mpd_type: MPDType = "dynamic" if raw_type == "dynamic" else "static"
    periods: list[DashPeriod] = []
    next_start: float | None = 0.0
    for child in root:
        name = _local(child.tag)
        if name == "BaseURL":
            base = _resolve_base(base, child.text)
        elif name == "Period":
            period = _parse_period(child, base, media_duration, next_start)
            periods.append(period)
            next_start = period.start
    return DashManifest(
        url=manifest_url,
        mpd_type=mpd_type,
        periods=periods,
        media_presentation_duration=media_duration,
    )
