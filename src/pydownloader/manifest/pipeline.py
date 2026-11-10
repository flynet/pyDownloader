"""The detection pipeline: response event → candidate → filters → registry entry.

Order of the filters is fixed by spec 5.2: live, DRM, quality 1080p, duplicates.
The manifest body of the intercepted response is used when the sniffer captured
it (a signed CDN rejects a second request for the same path); otherwise it is
fetched with the headers and cookies of the browser (spec 6.1).

Every outcome carries the console message for the UI console panel; the text is
a key of the catalog (``locales/manifest_*.py``), so the console follows the
language of the program.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal

from pydownloader.browser.events import ResponseEvent
from pydownloader.dash.models import DashManifest
from pydownloader.dash.parser import ManifestParseError, parse_mpd
from pydownloader.download.http import capture_headers
from pydownloader.hls.models import Playlist
from pydownloader.hls.parser import PlaylistParseError, parse_playlist
from pydownloader.i18n import tr
from pydownloader.manifest.detector import Candidate, classify, mp4_size_skip
from pydownloader.manifest.drm import detect_dash, detect_hls
from pydownloader.manifest.quality import Choice, QualityFilter, pick_audio
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

logger = logging.getLogger("pydownloader.pipeline")


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
    body: str | None = None,
) -> list[Outcome]:
    """Apply the filters of spec 5.1/5.2 to one intercepted response.

    ``body`` is the manifest text captured from the intercepted response (the
    sniffer reads it in the pump loop); ``None`` means the body must be fetched
    again with the browser headers.

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
            message = tr("mf_reason_with_url", reason=reason, url=event.url)
            return [Outcome("skip-size", None, message)]
        return []
    if candidate.kind == "mp4":
        return _process_mp4(candidate, registry, quality, probe_height)
    return _process_manifest(candidate, registry, fetch, quality, body)


def _process_mp4(
    candidate: Candidate,
    registry: SourceRegistry,
    quality: QualityFilter,
    probe_height: ProbeHeight | None,
) -> list[Outcome]:
    result = registry.add_mp4(candidate)
    if result.reason:
        action: Action = "fragment" if result.fragment else "skip-size"
        message = tr("mf_reason_with_url", reason=result.reason, url=candidate.url)
        return [Outcome(action, None, message)]
    if not result.is_new:
        entry = result.entry
        return [Outcome("duplicate", entry, tr("mf_range_merged", url=entry.url))]
    entry = result.entry
    height = probe_height(candidate.url, candidate.headers) if probe_height else None
    entry.height = height
    decision = quality.decide_mp4(candidate.url, height)
    if not decision.show or decision.choice is None:
        registry.remove(entry.normalized)
        return [Outcome("skip-quality", None, decision.message)]
    entry.choice = decision.choice
    message = tr("mf_found_mp4", quality=entry.display_quality(), url=entry.url)
    return [Outcome("show", entry, message)]


def _process_manifest(
    candidate: Candidate,
    registry: SourceRegistry,
    fetch: Fetch,
    quality: QualityFilter,
    body: str | None = None,
) -> list[Outcome]:
    result = registry.add_manifest(candidate)
    if not result.is_new:
        if result.reason:
            message = tr("mf_reason_with_url", reason=result.reason, url=candidate.url)
            return [Outcome("fragment", result.entry, message)]
        return [Outcome("duplicate", result.entry, tr("mf_found_already", url=result.entry.url))]
    entry = result.entry
    text: str | None
    if body is not None:
        text = body
        logger.debug(tr("mf_manifest_captured", url=candidate.url))
    else:
        text = fetch(candidate.url, candidate.headers)
    if text is None:
        registry.remove(entry.normalized)
        return [Outcome("fetch-error", None, tr("mf_manifest_not_fetched", url=candidate.url))]
    try:
        if candidate.kind == "dash":
            mpd = parse_mpd(text, candidate.url)
        else:
            playlist = parse_playlist(text, candidate.url)
    except (ManifestParseError, PlaylistParseError) as exc:
        logger.debug(tr("mf_parse_failed_debug", url=candidate.url, error=exc))
        registry.remove(entry.normalized)
        return [Outcome("parse-error", None, tr("mf_manifest_not_parsed", error=exc))]
    if candidate.kind == "dash":
        return _dash_outcomes(entry, mpd, registry, quality)
    return _hls_outcomes(entry, playlist, registry, fetch, quality)


def _dash_outcomes(
    entry: SourceEntry, mpd: DashManifest, registry: SourceRegistry, quality: QualityFilter
) -> list[Outcome]:
    if mpd.is_live:
        registry.remove(entry.normalized)
        return [Outcome("skip-live", None, tr("mf_live_skipped", url=entry.url))]
    verdict = detect_dash(mpd)
    if verdict.is_drm:
        registry.remove(entry.normalized)
        message = tr("mf_drm_detected", message=verdict.message, system=verdict.system)
        return [Outcome("skip-drm", None, message)]
    decision = quality.decide_dash(mpd)
    if not decision.show or decision.choice is None:
        registry.remove(entry.normalized)
        return [Outcome("skip-quality", None, decision.message)]
    choice = decision.choice
    entry.choice = choice
    entry.height = choice.height
    entry.duration = mpd.media_presentation_duration
    registry.remember_prefix(entry.url, entry)
    return [Outcome("show", entry, tr("mf_found_dash", height=entry.height, url=entry.url))]


def _audio_url(playlist: Playlist, group: str | None) -> str | None:
    """URL of the audio track of one variant (``None`` when it is muxed)."""
    audio = pick_audio(playlist.audio_tracks(group))
    return audio.url if audio else None


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
            return [Outcome("skip-live", None, tr("mf_live_skipped", url=entry.url))]
        verdict = detect_hls(playlist)
        if verdict.is_drm:
            registry.remove(entry.normalized)
            message = tr("mf_drm_detected", message=verdict.message, system=verdict.system)
            return [Outcome("skip-drm", None, message)]
        decision = quality.decide_hls(playlist)
        choice = decision.choice
        if choice is None:
            registry.remove(entry.normalized)
            return [Outcome("parse-error", None, tr("mf_manifest_not_parsed", error=entry.url))]
        entry.choice = choice
        entry.duration = sum(s.duration for s in playlist.segments)
        registry.remember_prefix(entry.url, entry)
        return [Outcome("show", entry, tr("mf_found_hls_unknown", url=entry.url))]

    decision = quality.decide_hls(playlist)
    if not decision.show or decision.choice is None:
        logger.debug(tr("mf_quality_debug", url=entry.url, message=decision.message))
        registry.remove(entry.normalized)
        return [Outcome("skip-quality", None, decision.message)]
    choice = decision.choice
    # Every variant of the master is kept: a CDN may sign only the quality the
    # player actually requested, so the downloader can fall back to a recorded
    # variant instead of failing on the chosen one.
    entry.variants = [
        Choice(
            kind="hls-variant",
            url=variant.url,
            height=variant.height,
            width=variant.width,
            bandwidth=variant.bandwidth,
            audio_url=_audio_url(playlist, variant.audio_group),
        )
        for variant in playlist.variants
    ]
    # A master playlist has no #EXT-X-ENDLIST, so live is decided by the selected variant.
    # A CDN that signs every path individually rejects the URL inherited from the
    # master, so the exact variant URL seen in browser traffic is preferred. The
    # choice keeps it, so the download plan parses the variant against its own query.
    registry.adopt_pending(choice.url, entry)
    variant_url = entry.recorded_url(choice.url) or choice.url
    audio_url = entry.recorded_url(choice.audio_url) if choice.audio_url else None
    choice = replace(choice, url=variant_url, audio_url=audio_url or choice.audio_url)
    recorded = tr("mf_yes") if variant_url != choice.url else tr("mf_no")
    logger.debug(
        tr(
            "mf_master_debug",
            url=entry.url,
            height=choice.height,
            variant=choice.url,
            recorded=recorded,
        )
    )
    variant_text = fetch(variant_url, entry.headers)
    if variant_text is None:
        # Java defers this check to the download: a per-path signature
        # (phncdn) rejects the URL inherited from the master, while the exact
        # signed URL of the variant appears in browser traffic when the player
        # requests it. The worker prefers that recorded URL.
        logger.warning(tr("mf_variant_not_fetched", height=choice.height, url=choice.url))
        entry.choice = choice
        entry.height = choice.height
        registry.remember_prefix(choice.url, entry)
        if choice.audio_url:
            registry.remember_prefix(choice.audio_url, entry)
        message = tr("mf_found_hls_deferred", height=entry.height, url=entry.url)
        return [Outcome("show", entry, message)]
    try:
        variant = parse_playlist(variant_text, entry.effective_url(choice.url))
    except (ManifestParseError, PlaylistParseError) as exc:
        logger.debug(tr("mf_variant_not_parsed_debug", url=choice.url, error=exc))
        registry.remove(entry.normalized)
        return [Outcome("parse-error", None, tr("mf_manifest_not_parsed", error=exc))]
    if variant.kind == "master":
        # A nested master (phncdn serves one per quality): the download plan
        # descends into it, here only the quality/live checks matter.
        logger.debug(tr("mf_nested_master_debug", url=choice.url))
    if variant.is_live:
        registry.remove(entry.normalized)
        return [Outcome("skip-live", None, tr("mf_live_skipped", url=choice.url))]
    verdict = detect_hls(variant)
    if verdict.is_drm:
        registry.remove(entry.normalized)
        message = tr("mf_drm_detected", message=verdict.message, system=verdict.system)
        return [Outcome("skip-drm", None, message)]
    entry.choice = choice
    entry.height = choice.height
    entry.duration = sum(s.duration for s in variant.segments)
    registry.remember_prefix(choice.url, entry)
    if choice.audio_url:
        registry.remember_prefix(choice.audio_url, entry)
    return [Outcome("show", entry, tr("mf_found_hls", height=entry.height, url=entry.url))]
