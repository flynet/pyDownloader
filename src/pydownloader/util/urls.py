"""URL helpers: candidate classification, normalization and resolving of relative links."""

from __future__ import annotations

from urllib.parse import parse_qsl, urljoin, urlsplit, urlunsplit

MANIFEST_EXTENSIONS = (".m3u8", ".mpd")

MANIFEST_CONTENT_TYPES = {
    "application/vnd.apple.mpegurl",
    "application/x-mpegurl",
    "audio/mpegurl",
    "application/dash+xml",
}
MP4_CONTENT_TYPE = "video/mp4"

# Query parameters that carry per-session tokens: they change between requests,
# so URLs are deduplicated without them.
VOLATILE_QUERY_KEYS = {
    "auth",
    "authkey",
    "amz",
    "ck",
    "expires",
    "expiry",
    "expire",
    "hash",
    "key",
    "kv",
    # phncdn CDN: h= signature, e= expiry, f= flag — all per-file volatile.
    "h",
    "e",
    "f",
    "policy",
    "session",
    "sid",
    "sig",
    "signature",
    "ss",
    "token",
    "tok",
    "x-amz-credential",
    "x-amz-date",
    "x-amz-expires",
    "x-amz-signature",
}


def normalize_content_type(content_type: str | None) -> str:
    """Content type without parameters, lower case (``charset`` part is dropped)."""
    if not content_type:
        return ""
    return content_type.split(";", 1)[0].strip().lower()


def path_extension(url: str) -> str:
    """Extension of the path part, lower case, ignoring the query string."""
    path = urlsplit(url).path
    dot = path.rfind(".")
    if dot == -1:
        return ""
    return path[dot:].lower()


def is_manifest_url(url: str) -> bool:
    """``True`` if the URL points to an HLS or DASH manifest (``.m3u8``/``.mpd``)."""
    ext = path_extension(url)
    if ext in MANIFEST_EXTENSIONS:
        return True
    # Some CDN serve manifests without a recognizable extension in the path.
    return any(ext in url for ext in MANIFEST_EXTENSIONS)


def normalize_url(url: str, volatile_keys: set[str] = VOLATILE_QUERY_KEYS) -> str:
    """Key for duplicate detection: fragment removed, volatile query params dropped.

    Remaining query parameters (tokens, signatures) are kept, because for many
    sites the full URL is the only reliable identifier.
    """
    parts = urlsplit(url)
    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in volatile_keys
    ]
    query = "&".join(f"{k}={v}" for k, v in kept)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def resolve_url(base: str, target: str) -> str:
    """Resolve a relative link against the URL of the manifest that contains it.

    A relative reference without a query inherits the query of the manifest
    (token/signature inheritance). Absolute references are returned unchanged:
    their own query is authoritative. This mirrors the Java app, where a CDN
    signature on the playlist applies to the segments below it.
    """
    if not target:
        return base
    ref = urlsplit(target)
    if ref.scheme:
        return target
    resolved = urljoin(base, target)
    if ref.query:
        return resolved
    base_query = urlsplit(base).query
    if not base_query:
        return resolved
    parts = urlsplit(resolved)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, base_query, parts.fragment))


def path_of(url: str) -> str:
    """Path part of a URL, query and fragment stripped."""
    return urlsplit(url).path


def last_segment(url: str) -> str:
    """File name of a URL (last path segment), query and fragment stripped."""
    path = urlsplit(url).path
    return path.rsplit("/", 1)[-1] if "/" in path else path


def dir_prefix(url: str) -> str:
    """Directory of a URL as ``scheme://host/dir/`` (query stripped)."""
    parts = urlsplit(url)
    path = parts.path
    trimmed = path.rsplit("/", 1)[0] if "/" in path else ""
    return urlunsplit((parts.scheme, parts.netloc, trimmed + "/", "", ""))


#: Extensions that identify a media segment of an HLS stream.
SEGMENT_EXTENSIONS = {".m4s", ".ts", ".mp2t", ".m4v", ".m4a", ".aac", ".ac3", ".ec3"}


def is_segment_path(url: str) -> bool:
    """``True`` for a media segment or key file of a stream."""
    ext = path_extension(url)
    return ext in SEGMENT_EXTENSIONS or ext == ".key"


def base_dir_url(final_url: str) -> str:
    """URL of the directory containing the manifest, for ``urljoin`` of relative links."""
    parts = urlsplit(final_url)
    path = parts.path
    if path.endswith("/"):
        return urlunsplit((parts.scheme, parts.netloc, path, "", ""))
    trimmed = path.rsplit("/", 1)[0] if "/" in path else ""
    return urlunsplit((parts.scheme, parts.netloc, trimmed + "/", "", ""))


def origin_of(url: str) -> str:
    """``Origin`` header value for a URL (``scheme://host[:port]``)."""
    parts = urlsplit(url)
    netloc = parts.netloc
    host = parts.hostname or ""
    port = parts.port
    if port and host:
        default = 443 if parts.scheme == "https" else 80
        if port == default:
            netloc = host
    return urlunsplit((parts.scheme, netloc, "", "", ""))
