"""DRM detection (spec 5.2 p.2). Content protected by DRM is skipped, never bypassed.

HLS: ``EXT-X-KEY`` with a method other than ``NONE``/``AES-128`` (``SAMPLE-AES``,
``SAMPLE-AES-CTR`` ...) or a ``KEYFORMAT`` naming a DRM system.

DASH: ``ContentProtection`` with a Widevine, PlayReady, FairPlay or
Common Encryption scheme.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydownloader.dash.models import DashManifest
from pydownloader.hls.models import Key, Playlist

#: ``schemeIdUri`` (lower case) -> DRM system name.
DRM_SCHEMES = {
    "urn:uuid:1077efec-c0b2-4d02-ace3-3c15e701664b": "Widevine",
    "urn:uuid:ae9f8b9a-1d35-4f1b-9c2d-1c4a60444a97": "Widevine",
    "urn:uuid:3d793401-a9d6-417a-b485-334a1d421c37": "Widevine",
    "http://widevine.com/": "Widevine",
    "urn:uuid:9a04fbb5-1a71-4b91-936c-4d4d499734f1": "PlayReady",
    "urn:uuid:76fe3556-59fb-31b4-b59b-86899a14d657": "PlayReady",
    "http://schemas.microsoft.com/DRM/2007/03/protocols": "PlayReady",
    "http://schemas.microsoft.com/DRM/2007/sch": "PlayReady",
    "urn:uuid:94cec79f-72d9-4b07-8446-242b1c296c46": "FairPlay",
    "urn:uuid:276a70e0-c2a3-11e0-9b65-0800200c9a66": "FairPlay",
    "http://www.apple.com/fairplay/": "FairPlay",
    "urn:mpeg:cenc:2013": "CommonEncryption",
    "urn:mpeg:csb:2011": "CommonEncryption",
}
ALLOWED_HLS_METHODS = {"NONE", "AES-128"}
DRM_MESSAGE = "Контент защищён DRM, скачивание невозможно"


@dataclass(frozen=True)
class DrmVerdict:
    is_drm: bool
    system: str | None = None
    message: str = DRM_MESSAGE

    @property
    def ok(self) -> bool:
        return not self.is_drm


def detect_hls(playlist: Playlist, keys: list[Key | None] | None = None) -> DrmVerdict:
    """Check every key used by the playlist, including per-segment keys."""
    if keys is None:
        keys = [playlist.key] + [s.key for s in playlist.segments]
    seen: set[Key] = set()
    for key in keys:
        if key is None or key in seen:
            continue
        seen.add(key)
        method = key.method.upper()
        if method not in ALLOWED_HLS_METHODS:
            return DrmVerdict(is_drm=True, system=method)
        format_value = (key.key_format or "").lower()
        for scheme, system in DRM_SCHEMES.items():
            if scheme in format_value:
                return DrmVerdict(is_drm=True, system=system)
    return DrmVerdict(is_drm=False)


def detect_dash(mpd: DashManifest) -> DrmVerdict:
    for scheme, value in mpd.content_protection():
        scheme = scheme.strip().lower()
        if scheme in DRM_SCHEMES:
            return DrmVerdict(is_drm=True, system=DRM_SCHEMES[scheme])
        if scheme.startswith("urn:uuid:") and value:
            # An unknown UUID scheme with a licence value means encryption.
            return DrmVerdict(is_drm=True, system=scheme)
    return DrmVerdict(is_drm=False)


def detect_drm(source: Playlist | DashManifest) -> DrmVerdict:
    """Dispatch on the manifest type."""
    if isinstance(source, Playlist):
        return detect_hls(source)
    return detect_dash(source)
