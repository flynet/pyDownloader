"""Quality filter: only streams with a 1080p variant are shown (spec 5.2 p.3).

The threshold lives in settings (``target_height``, default 1080) without UI.
If there is no 1080p variant, the source is not shown in the list, only
the console message is written.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydownloader.config.settings import DEFAULT_TARGET_HEIGHT
from pydownloader.dash.models import DashManifest, DashPeriod, DashRepresentation
from pydownloader.hls.models import Media, Playlist, Variant
from pydownloader.i18n import tr

StreamKind = Literal["hls-variant", "hls-media", "dash-video", "mp4"]


@dataclass(frozen=True)
class Choice:
    """The selected track: the best video plus the best audio.

    ``video``/``audio`` are set for DASH (the representation objects); for HLS
    ``url`` is the media playlist of the chosen variant.
    """

    kind: StreamKind
    url: str
    height: int | None
    width: int | None = None
    bandwidth: int | None = None
    audio_url: str | None = None
    audio_name: str | None = None
    audio_language: str | None = None
    video: DashRepresentation | None = None
    audio: DashRepresentation | None = None


@dataclass
class QualityDecision:
    show: bool
    choice: Choice | None = None
    message: str = ""
    available_heights: list[int] = field(default_factory=list)


def heights_message(heights: list[int], target: int) -> str:
    """Console text for a stream without the required quality (spec 5.2 p.3)."""
    if not heights:
        return tr("mf_quality_no_heights", target=target)
    listed = ", ".join(f"{h}p" for h in sorted(set(heights), reverse=True))
    return tr("mf_quality_available", target=target, listed=listed)


def pick_audio(candidates: list[Media], language: str | None = None) -> Media | None:
    """Best audio track: the ``DEFAULT=YES`` one, then the requested language, then the first."""
    if not candidates:
        return None
    for media in candidates:
        if media.default:
            return media
    if language:
        for media in candidates:
            if (media.language or "").lower() == language.lower():
                return media
    for media in candidates:
        if media.autoselect:
            return media
    return candidates[0]


def best_variant(variants: list[Variant], target_height: int) -> Variant | None:
    """Variant with the required height and the maximum bandwidth."""
    matching = [v for v in variants if v.height == target_height]
    if not matching:
        return None
    return max(matching, key=lambda v: (v.bandwidth, v.url))


def best_dash_video(
    reps: list[DashRepresentation], target_height: int
) -> DashRepresentation | None:
    matching = [r for r in reps if r.height == target_height]
    if not matching:
        return None
    return max(matching, key=lambda r: (r.bandwidth, r.id))


@dataclass
class QualityFilter:
    target_height: int = DEFAULT_TARGET_HEIGHT

    def decide_hls(self, playlist: Playlist) -> QualityDecision:
        if playlist.kind == "media":
            height = None
            return QualityDecision(
                show=True,
                choice=Choice(kind="hls-media", url=playlist.url, height=height),
            )
        variant = best_variant(playlist.variants, self.target_height)
        if variant is None:
            return QualityDecision(
                show=False,
                message=heights_message(playlist.available_heights(), self.target_height),
                available_heights=playlist.available_heights(),
            )
        audio = pick_audio(playlist.audio_tracks(variant.audio_group))
        return QualityDecision(
            show=True,
            choice=Choice(
                kind="hls-variant",
                url=variant.url,
                height=variant.height,
                width=variant.width,
                bandwidth=variant.bandwidth,
                audio_url=audio.url if audio else None,
                audio_name=audio.name if audio else None,
                audio_language=audio.language if audio else None,
            ),
            available_heights=playlist.available_heights(),
        )

    def decide_dash(self, mpd: DashManifest) -> QualityDecision:
        best_video: DashRepresentation | None = None
        best_period: DashPeriod | None = None
        for period in mpd.periods:
            candidate = best_dash_video(period.videos(), self.target_height)
            if candidate and (best_video is None or candidate.bandwidth > best_video.bandwidth):
                best_video, best_period = candidate, period
        if best_video is None:
            available = mpd.available_heights()
            return QualityDecision(
                show=False,
                message=heights_message(available, self.target_height),
                available_heights=available,
            )
        # Audio is taken from the same Period as the chosen video.
        audio = best_dash_audio(best_period.audios() if best_period else [], best_video.language)
        return QualityDecision(
            show=True,
            choice=Choice(
                kind="dash-video",
                url=mpd.url,
                height=best_video.height,
                width=best_video.width,
                bandwidth=best_video.bandwidth,
                audio_url=audio.progressive_url if audio and audio.progressive else None,
                audio_language=audio.language if audio else None,
                audio_name=audio.id if audio else None,
                video=best_video,
                audio=audio,
            ),
            available_heights=mpd.available_heights(),
        )

    def decide_mp4(self, url: str, height: int | None) -> QualityDecision:
        """Direct MP4: shown when the height is 1080, when it is known, and kept when unknown."""
        if height is None:
            return QualityDecision(show=True, choice=Choice(kind="mp4", url=url, height=None))
        if height == self.target_height:
            return QualityDecision(show=True, choice=Choice(kind="mp4", url=url, height=height))
        return QualityDecision(
            show=False,
            message=heights_message([height], self.target_height),
            available_heights=[height],
        )


def best_dash_audio(
    audios: list[DashRepresentation],
    language: str | None = None,
) -> DashRepresentation | None:
    """Best audio representation: matching language first, then the highest bandwidth."""
    if not audios:
        return None
    pool = audios
    if language:
        matching = [a for a in audios if (a.language or "").lower() == language.lower()]
        if matching:
            pool = matching
    return max(pool, key=lambda a: (a.bandwidth, a.id))
