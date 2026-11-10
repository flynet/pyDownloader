"""Quality filter: the streams shown in the list (spec 5.2 p.3, p.4).

The threshold lives in settings (``target_height``, default 1080). If there is
no variant of that height, the source is not shown in the list, only the
console message is written. An audio-only source is shown whatever the height
is, and in the «Audio only (MP3)» mode the video sources are not shown at all
(spec 5.2 p.4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydownloader.config.settings import DEFAULT_TARGET_HEIGHT
from pydownloader.dash.models import DashManifest, DashPeriod, DashRepresentation
from pydownloader.hls.models import Media, Playlist, Variant
from pydownloader.i18n import tr

StreamKind = Literal["hls-variant", "hls-media", "dash-video", "dash-audio", "mp4"]
#: Codecs of an audio-only HLS variant, the names the playlist writes in ``CODECS``.
AUDIO_CODECS = ("mp4a", "aac", "ac-3", "ec-3", "opus", "mp3", "flac", "alac")


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
    #: ``True`` when the track is audio only: the file is saved as ``.mp3`` (spec 5.2 p.4).
    audio_only: bool = False


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


def is_audio_codec(codecs: str | None) -> bool:
    """``True`` when the codec list of a variant carries no video codec.

    ``CODECS=mp4a.40.2`` is the form SoundCloud writes; a list with a video codec
    (``avc1.64001f,mp4a.40.2``) is a video variant, so every part of the list
    must be an audio codec.
    """
    if not codecs:
        return False
    parts = [part.strip().lower() for part in codecs.split(",")]
    return bool(parts) and all(part.split(".")[0] in AUDIO_CODECS for part in parts)


def is_audio_variants(variants: list[Variant]) -> bool:
    """``True`` for a master playlist with no video: every variant is audio.

    A variant has no ``RESOLUTION`` and an audio-only ``CODECS`` list. The audio
    group of ``EXT-X-MEDIA`` alone is not enough: a video variant without a
    codec list is the common case, and it is not an audio source.
    """
    return bool(variants) and all(
        variant.height is None and is_audio_codec(variant.codecs) for variant in variants
    )


def best_audio_variant(variants: list[Variant]) -> Variant | None:
    """Audio variant with the maximum bandwidth: the best quality of an audio stream."""
    pool = [v for v in variants if v.height is None]
    if not pool:
        return None
    return max(pool, key=lambda v: (v.bandwidth, v.url))


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
    #: «Audio only (MP3)»: the video sources are not shown, the audio sources are
    #: shown, and the audio is saved as ``.mp3`` (spec 5.2 p.4).
    audio_only: bool = False

    def video_skip(self) -> QualityDecision | None:
        """The skip of a video source when the program saves audio only (spec 5.2 p.4)."""
        if self.audio_only:
            return QualityDecision(show=False, message=tr("mf_quality_video_skipped"))
        return None

    def decide_hls(self, playlist: Playlist, audio: bool = False) -> QualityDecision:
        if playlist.kind == "media":
            if audio:
                return QualityDecision(
                    show=True,
                    choice=Choice(kind="hls-media", url=playlist.url, height=None, audio_only=True),
                )
            skip = self.video_skip()
            if skip is not None:
                return skip
            return QualityDecision(
                show=True,
                choice=Choice(kind="hls-media", url=playlist.url, height=None),
            )
        if audio:
            variant = best_audio_variant(playlist.variants)
            if variant is None:
                return QualityDecision(show=False, message=tr("mf_quality_no_audio"))
            audio_track = pick_audio(playlist.audio_tracks(variant.audio_group))
            return QualityDecision(
                show=True,
                choice=Choice(
                    kind="hls-variant",
                    url=variant.url,
                    height=None,
                    width=variant.width,
                    bandwidth=variant.bandwidth,
                    audio_url=audio_track.url if audio_track else None,
                    audio_name=audio_track.name if audio_track else None,
                    audio_language=audio_track.language if audio_track else None,
                    audio_only=True,
                ),
            )
        skip = self.video_skip()
        if skip is not None:
            return skip
        variant = best_variant(playlist.variants, self.target_height)
        if variant is None:
            return QualityDecision(
                show=False,
                message=heights_message(playlist.available_heights(), self.target_height),
                available_heights=playlist.available_heights(),
            )
        track = pick_audio(playlist.audio_tracks(variant.audio_group))
        return QualityDecision(
            show=True,
            choice=Choice(
                kind="hls-variant",
                url=variant.url,
                height=variant.height,
                width=variant.width,
                bandwidth=variant.bandwidth,
                audio_url=track.url if track else None,
                audio_name=track.name if track else None,
                audio_language=track.language if track else None,
            ),
            available_heights=playlist.available_heights(),
        )

    def decide_dash(self, mpd: DashManifest, audio: bool = False) -> QualityDecision:
        if audio:
            best_audio: DashRepresentation | None = None
            for period in mpd.periods:
                candidate = best_dash_audio(period.audios())
                if candidate and (best_audio is None or candidate.bandwidth > best_audio.bandwidth):
                    best_audio = candidate
            if best_audio is None:
                return QualityDecision(show=False, message=tr("mf_quality_no_audio"))
            return QualityDecision(
                show=True,
                choice=Choice(
                    kind="dash-audio",
                    url=mpd.url,
                    height=None,
                    bandwidth=best_audio.bandwidth,
                    audio_url=best_audio.progressive_url if best_audio.progressive else None,
                    audio_language=best_audio.language,
                    audio_name=best_audio.id,
                    audio=best_audio,
                    audio_only=True,
                ),
            )
        skip = self.video_skip()
        if skip is not None:
            return skip
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
        track = best_dash_audio(best_period.audios() if best_period else [], best_video.language)
        return QualityDecision(
            show=True,
            choice=Choice(
                kind="dash-video",
                url=mpd.url,
                height=best_video.height,
                width=best_video.width,
                bandwidth=best_video.bandwidth,
                audio_url=track.progressive_url if track and track.progressive else None,
                audio_language=track.language if track else None,
                audio_name=track.id if track else None,
                video=best_video,
                audio=track,
            ),
            available_heights=mpd.available_heights(),
        )

    def decide_mp4(self, url: str, height: int | None, audio: bool = False) -> QualityDecision:
        """Direct file: audio is shown as ``.mp3``, video needs the target height (spec 5.1)."""
        if audio:
            return QualityDecision(
                show=True,
                choice=Choice(kind="mp4", url=url, height=None, audio_only=True),
            )
        skip = self.video_skip()
        if skip is not None:
            return skip
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
