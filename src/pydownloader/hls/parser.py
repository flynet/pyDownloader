"""HLS playlist parser (``.m3u8``).

Supported tags: ``EXTM3U``, ``EXT-X-TARGETDURATION``, ``EXT-X-MEDIA-SEQUENCE``,
``EXT-X-STREAM-INF``, ``EXTINF``, ``EXT-X-ENDLIST``, ``EXT-X-KEY`` (``NONE``/``AES-128``),
``EXT-X-MAP``, ``EXT-X-BYTERANGE``, ``EXT-X-MEDIA``, ``EXT-X-DISCONTINUITY``,
``EXT-X-PLAYLIST-TYPE``. Every relative URL is resolved against the manifest URL,
query parameters (tokens, signatures) are preserved.
"""

from __future__ import annotations

from dataclasses import replace

from pydownloader.hls.models import InitSegment, Key, Media, MediaKind, Playlist, Segment, Variant
from pydownloader.i18n import tr
from pydownloader.util.ranges import ByteRange, parse_hls_byterange
from pydownloader.util.urls import resolve_url


class PlaylistParseError(ValueError):
    """The text is not a valid HLS playlist."""


def parse_attributes(text: str) -> dict[str, str]:
    """Parse ``KEY=VALUE,KEY="a,b",KEY=VALUE`` respecting quotes inside values."""
    attrs: dict[str, str] = {}
    i = 0
    n = len(text)
    while i < n:
        eq = text.find("=", i)
        if eq == -1:
            break
        key = text[i:eq].strip()
        j = eq + 1
        if j < n and text[j] == '"':
            end = text.find('"', j + 1)
            if end == -1:
                raise PlaylistParseError(tr("hls_unclosed_quote", text=text))
            attrs[key] = text[j + 1 : end]
            i = end + 1
            while i < n and text[i] != ",":
                i += 1
            i += 1
        else:
            end = text.find(",", j)
            if end == -1:
                attrs[key] = text[j:].strip()
                i = n
            else:
                attrs[key] = text[j:end].strip()
                i = end + 1
    return attrs


def _yes(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().upper() == "YES"


def _parse_resolution(resolution: str | None) -> tuple[int | None, int | None]:
    if not resolution:
        return None, None
    parts = resolution.lower().split("x")
    if len(parts) != 2:
        return None, None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None, None


def _parse_iv(raw: str | None) -> int | None:
    """``IV=0x...`` is a 32 digit hex string; decimal IV is not legal HLS, accepted anyway."""
    if not raw:
        return None
    value = raw.strip()
    if value.lower().startswith("0x"):
        return int(value, 16)
    try:
        return int(value)
    except ValueError:
        return None


def _first_int(raw: str | None) -> int:
    if not raw:
        return 0
    digits = "".join(ch for ch in raw.split(",")[0] if ch.isdigit())
    return int(digits) if digits else 0


def parse_playlist(text: str, manifest_url: str) -> Playlist:
    """Parse ``.m3u8`` text into a :class:`Playlist` with absolute URLs.

    ``manifest_url`` is the final URL of the manifest after redirects; relative
    links are resolved against it with ``urljoin``.
    """
    if not text.strip():
        raise PlaylistParseError(tr("mf_empty_response"))
    lines = text.splitlines()
    if not lines[0].strip().startswith("#EXTM3U"):
        raise PlaylistParseError(tr("hls_no_extm3u"))

    kind: MediaKind = (
        "master" if any(line.strip().startswith("#EXT-X-STREAM-INF") for line in lines) else "media"
    )
    playlist = Playlist(kind=kind, url=manifest_url)

    media_sequence = 0
    key: Key | None = None
    init: InitSegment | None = None
    last_range_end: int | None = None
    pending_range: ByteRange | None = None
    pending_duration: float | None = None
    pending_variant: Variant | None = None
    index = 0

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        if line.startswith("#"):
            tag, _, value = line[1:].partition(":")
            tag = tag.strip().upper()
            if tag == "EXT-X-TARGETDURATION":
                playlist.target_duration = _first_int(value)
            elif tag == "EXT-X-MEDIA-SEQUENCE":
                media_sequence = _first_int(value)
            elif tag == "EXTINF":
                # ``#EXTINF:10.0,Title`` - the duration is the first comma separated part.
                duration_text = value.split(",")[0].strip()
                try:
                    pending_duration = float(duration_text)
                except ValueError:
                    pending_duration = 0.0
            elif tag == "EXT-X-ENDLIST":
                playlist.has_endlist = True
            elif tag == "EXT-X-KEY":
                attrs = parse_attributes(value)
                method = attrs.get("METHOD", "NONE").upper()
                if method == "NONE":
                    key = None
                else:
                    uri = attrs.get("URI")
                    key = Key(
                        method=method,
                        uri=resolve_url(manifest_url, uri) if uri else None,
                        iv=_parse_iv(attrs.get("IV")),
                        key_format=attrs.get("KEYFORMAT"),
                        key_format_versions=attrs.get("KEYFORMATVERSIONS"),
                    )
            elif tag == "EXT-X-MAP":
                attrs = parse_attributes(value)
                uri = attrs.get("URI", "")
                if uri:
                    byte_range = None
                    if attrs.get("BYTERANGE"):
                        byte_range = parse_hls_byterange(attrs["BYTERANGE"], None)
                        last_range_end = byte_range.end + 1
                    init = InitSegment(url=resolve_url(manifest_url, uri), byte_range=byte_range)
            elif tag == "EXT-X-BYTERANGE":
                pending_range = parse_hls_byterange(value, last_range_end)
            elif tag == "EXT-X-MEDIA":
                attrs = parse_attributes(value)
                uri = attrs.get("URI")
                playlist.media.append(
                    Media(
                        type=attrs.get("TYPE", "").upper(),
                        group_id=attrs.get("GROUP-ID", ""),
                        url=resolve_url(manifest_url, uri) if uri else None,
                        language=attrs.get("LANGUAGE"),
                        name=attrs.get("NAME"),
                        default=_yes(attrs.get("DEFAULT")),
                        autoselect=_yes(attrs.get("AUTOSELECT"), default=True),
                        forced=_yes(attrs.get("FORCED")),
                    )
                )
            elif tag == "EXT-X-STREAM-INF":
                attrs = parse_attributes(value)
                width, height = _parse_resolution(attrs.get("RESOLUTION"))
                pending_variant = Variant(
                    url="",
                    bandwidth=_first_int(attrs.get("BANDWIDTH")),
                    width=width,
                    height=height,
                    audio_group=attrs.get("AUDIO"),
                    subtitles_group=attrs.get("SUBTITLES"),
                    codecs=attrs.get("CODECS"),
                )
            # EXT-X-DISCONTINUITY, EXT-X-PLAYLIST-TYPE and unknown tags do not need handling here.
            continue

        url = resolve_url(manifest_url, line)
        if kind == "master":
            if pending_variant is not None:
                playlist.variants.append(replace(pending_variant, url=url))
                pending_variant = None
            continue

        # Media playlist: a segment URI line.
        duration = pending_duration if pending_duration is not None else 0.0
        pending_duration = None
        playlist.segments.append(
            Segment(
                url=url,
                duration=duration,
                sequence=media_sequence + index,
                index=index,
                byte_range=pending_range,
                key=key,
                init=init,
            )
        )
        if pending_range is not None:
            last_range_end = pending_range.end + 1
        pending_range = None
        index += 1

    playlist.media_sequence = media_sequence
    playlist.init = init
    playlist.key = key
    return playlist
