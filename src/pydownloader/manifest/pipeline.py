"""The detection pipeline: response event → candidate → filters → registry entry.

Order of the filters is fixed by spec 5.2: live, DRM, quality 1080p, duplicates.
The manifest body is not taken from the intercepted response: it is fetched by a
new ``GET`` with the headers and cookies of the browser (spec 6.1), which keeps
the pipeline testable and gives the same bytes the downloader will use.

Every outcome carries the console message for the UI console panel.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal

from pydownloader.browser.events import ResponseEvent
from pydownloader.dash.models import DashManifest
from pydownloader.dash.parser import ManifestParseError, parse_mpd
from pydownloader.download.http import capture_headers
from pydownloader.hls.models import Playlist
from pydownloader.hls.parser import PlaylistParseError, parse_playlist
from pydownloader.manifest.detector import Candidate, classify, mp4_size_skip
from pydownloader.manifest.drm import DRM_MESSAGE, detect_dash, detect_hls
from pydownloader.manifest.quality import QualityFilter
from pydownloader.manifest.registry import SourceEntry, SourceRegistry

Action = Literal[
    "show",
    "skip-live",
    "skip-drm",
    "skip-quality",
    "skip-size",
    "fragment",
    "duplicate",
    "fetch-error",
    "parse-error",
]

#: ``fetch(url, headers) -> text | None``; ``None`` means the request failed.
Fetch = Callable[[str, dict[str, str]], str | None]
#: ``probe(url, headers) -> height | None`` (FFmpeg probe of a direct MP4).
ProbeHeight = Callable[[str, dict[str, str]], int | None]


@dataclass(frozen=True)
class Outcome:
    """One console line, plus the registry entry for ``show``."""

    action: Action
    entry: SourceEntry | None
    message: str


def process_event(
    event: ResponseEvent,
    registry: SourceRegistry,
    fetch: Fetch,
    quality: QualityFilter,
    probe_height: ProbeHeight | None = None,
) -> list[Outcome]:
    """Apply the filters of spec 5.1/5.2 to one intercepted response.

    Returns the outcomes to log; an empty list means the response was not a
    video source. The registry is updated as a side effect.
    """
    if event.status >= 400:
        return []
    headers = capture_headers(event.request_headers, event.page_url)
    size = event.total_size()
    candidate = classify(
        event.url,
        content_type=event.content_type,
        page_url=event.page_url,
        page_title=event.page_title,
        headers=headers,
        content_length=size,
        min_mp4_size=registry.min_mp4_size,
    )
    if candidate is None:
        reason = mp4_size_skip(event.url, event.content_type, size, registry.min_mp4_size)
        if reason:
            return [Outcome("skip-size", None, f"{reason}: {event.url}")]
        return []
    if candidate.kind == "mp4":
        return _process_mp4(candidate, registry, quality, probe_height)
    return _process_manifest(candidate, registry, fetch, quality)


def _process_mp4(
    candidate: Candidate,
    registry: SourceRegistry,
    quality: QualityFilter,
    probe_height: ProbeHeight | None,
) -> list[Outcome]:
    result = registry.add_mp4(candidate)
    if result.reason:
        action: Action = "fragment" if "фрагмент" in result.reason else "skip-size"
        return [Outcome(action, None, f"{result.reason}: {candidate.url}")]
    if not result.is_new:
        entry = result.entry
        return [Outcome("duplicate", entry, f"Уже найден, Range-запрос объединён: {entry.url}")]
    entry = result.entry
    height = probe_height(candidate.url, candidate.headers) if probe_height else None
    entry.height = height
    decision = quality.decide_mp4(candidate.url, height)
    if not decision.show or decision.choice is None:
        registry.remove(entry.normalized)
        return [Outcome("skip-quality", None, decision.message)]
    entry.choice = decision.choice
    return [Outcome("show", entry, f"Найден MP4 {entry.display_quality()}: {entry.url}")]


def _process_manifest(
    candidate: Candidate,
    registry: SourceRegistry,
    fetch: Fetch,
    quality: QualityFilter,
) -> list[Outcome]:
    result = registry.add_manifest(candidate)
    if not result.is_new:
        if result.reason:
            return [Outcome("fragment", result.entry, f"{result.reason}: {candidate.url}")]
        return [Outcome("duplicate", result.entry, f"Уже найден: {result.entry.url}")]
    entry = result.entry
    text = fetch(candidate.url, candidate.headers)
    if text is None:
        registry.remove(entry.normalized)
        return [Outcome("fetch-error", None, f"Не получен манифест: {candidate.url}")]
    try:
        if candidate.kind == "dash":
            mpd = parse_mpd(text, candidate.url)
        else:
            playlist = parse_playlist(text, candidate.url)
    except (ManifestParseError, PlaylistParseError) as exc:
        registry.remove(entry.normalized)
        return [Outcome("parse-error", None, f"Манифест не разобран: {exc}")]
    if candidate.kind == "dash":
        return _dash_outcomes(entry, mpd, registry, quality)
    return _hls_outcomes(entry, playlist, registry, fetch, quality)


def _dash_outcomes(
    entry: SourceEntry, mpd: DashManifest, registry: SourceRegistry, quality: QualityFilter
) -> list[Outcome]:
    if mpd.is_live:
        registry.remove(entry.normalized)
        return [Outcome("skip-live", None, f"Live-трансляция: пропущен ({entry.url})")]
    verdict = detect_dash(mpd)
    if verdict.is_drm:
        registry.remove(entry.normalized)
        return [Outcome("skip-drm", None, f"{DRM_MESSAGE} ({verdict.system})")]
    decision = quality.decide_dash(mpd)
    if not decision.show or decision.choice is None:
        registry.remove(entry.normalized)
        return [Outcome("skip-quality", None, decision.message)]
    choice = decision.choice
    entry.choice = choice
    entry.height = choice.height
    entry.duration = mpd.media_presentation_duration
    registry.remember_prefix(entry.url, entry)
    return [Outcome("show", entry, f"Найден DASH-поток {entry.height}p: {entry.url}")]


def _hls_outcomes(
    entry: SourceEntry,
    playlist: Playlist,
    registry: SourceRegistry,
    fetch: Fetch,
    quality: QualityFilter,
) -> list[Outcome]:
    if playlist.kind == "media":
        if playlist.is_live:
            registry.remove(entry.normalized)
            return [Outcome("skip-live", None, f"Live-трансляция: пропущен ({entry.url})")]
        verdict = detect_hls(playlist)
        if verdict.is_drm:
            registry.remove(entry.normalized)
            return [Outcome("skip-drm", None, f"{DRM_MESSAGE} ({verdict.system})")]
        decision = quality.decide_hls(playlist)
        choice = decision.choice
        if choice is None:
            registry.remove(entry.normalized)
            return [Outcome("parse-error", None, f"Манифест не разобран: {entry.url}")]
        entry.choice = choice
        entry.duration = sum(s.duration for s in playlist.segments)
        registry.remember_prefix(entry.url, entry)
        return [Outcome("show", entry, f"Найден HLS-поток (разрешение неизвестно): {entry.url}")]

    decision = quality.decide_hls(playlist)
    if not decision.show or decision.choice is None:
        registry.remove(entry.normalized)
        return [Outcome("skip-quality", None, decision.message)]
    choice = decision.choice
    # A master playlist has no #EXT-X-ENDLIST, so live is decided by the selected variant.
    # A CDN that signs every path individually rejects the URL inherited from the
    # master, so the exact variant URL seen in browser traffic is preferred. The
    # choice keeps it, so the download plan parses the variant against its own query.
    registry.adopt_pending(choice.url, entry)
    variant_url = entry.recorded_url(choice.url) or choice.url
    audio_url = entry.recorded_url(choice.audio_url) if choice.audio_url else None
    choice = replace(choice, url=variant_url, audio_url=audio_url or choice.audio_url)
    variant_text = fetch(variant_url, entry.headers)
    if variant_text is None:
        registry.remove(entry.normalized)
        return [Outcome("fetch-error", None, f"Не получен манифест: {choice.url}")]
    try:
        variant = parse_playlist(variant_text, choice.url)
    except (ManifestParseError, PlaylistParseError) as exc:
        registry.remove(entry.normalized)
        return [Outcome("parse-error", None, f"Манифест не разобран: {exc}")]
    if variant.is_live:
        registry.remove(entry.normalized)
        return [Outcome("skip-live", None, f"Live-трансляция: пропущен ({choice.url})")]
    verdict = detect_hls(variant)
    if verdict.is_drm:
        registry.remove(entry.normalized)
        return [Outcome("skip-drm", None, f"{DRM_MESSAGE} ({verdict.system})")]
    entry.choice = choice
    entry.height = choice.height
    entry.duration = sum(s.duration for s in variant.segments)
    registry.remember_prefix(choice.url, entry)
    if choice.audio_url:
        registry.remember_prefix(choice.audio_url, entry)
    return [Outcome("show", entry, f"Найден HLS-поток {entry.height}p: {entry.url}")]
