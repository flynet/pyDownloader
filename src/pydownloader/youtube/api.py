"""Inner-tube player API of YouTube, called from inside the watch page.

A plain HTTP call from the app is rejected with a bot check, so the request is
issued by the page itself (cookies and ``visitorData`` included). The VISIONOS
client is used deliberately: it still answers with classic signed stream URLs
for every adaptive format, while the WEB client only exposes server-side ABR
(``POST /videoplayback`` with UMP framing), which the sniffer cannot download.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

#: Inner-tube client id of the VISIONOS client.
CLIENT_ID = 101
CLIENT_NAME = "VISIONOS"
CLIENT_VERSION = "1.02"
#: Safari user agent of the VISIONOS client (sent inside the inner-tube context).
CLIENT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_7_3) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Safari/605.1.15"
)
#: Public web inner-tube key (the same one the watch page uses).
API_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"

#: JS executed inside the page: reads ``visitorData`` and calls the player API.
PAGE_FETCH_SCRIPT = """
async (args) => {
  try {
    let visitor = args.visitor;
    if (!visitor) {
      try {
        visitor = (window.ytcfg.get('INNERTUBE_CONTEXT').client || {}).visitorData || '';
      } catch (e) { visitor = ''; }
    }
    const payload = JSON.parse(args.payloadTemplate.replace('__VISITOR__', visitor));
    const r = await fetch('/youtubei/v1/player?key=' + args.key, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-YouTube-Client-Name': args.clientName,
        'X-YouTube-Client-Version': args.clientVersion
      },
      body: JSON.stringify(payload)
    });
    return await r.text();
  } catch (e) {
    return '';
  }
}
"""


def payload_template(video_id: str) -> str:
    """Inner-tube player payload with a ``__VISITOR__`` placeholder for the page."""
    return (
        '{"videoId":"' + video_id + '","context":{"client":{'
        '"clientName":"' + CLIENT_NAME + '",'
        '"clientVersion":"' + CLIENT_VERSION + '",'
        '"hl":"en","gl":"US",'
        '"userAgent":"' + CLIENT_UA + '",'
        '"deviceMake":"Apple","deviceModel":"RealityDevice17,1",'
        '"osName":"visionOS","osVersion":"26.5.23O471",'
        '"visitorData":"__VISITOR__"}},'
        '"contentCheckOk":true,"racyCheckOk":true}'
    )


def video_id_from_url(url: str) -> str | None:
    """11-character video id of a YouTube watch/short/embed URL, ``None`` otherwise."""
    if not url:
        return None
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host.endswith("youtu.be"):
        candidate = parts.path.strip("/").split("/")[0]
        return candidate or None
    if "youtube.com" not in host and "youtube-nocookie.com" not in host:
        return None
    query = parse_qs(parts.query)
    if query.get("v"):
        return query["v"][0] or None
    segments = [part for part in parts.path.split("/") if part]
    if len(segments) >= 2 and segments[0] in {"shorts", "embed", "live", "v"}:
        return segments[1]
    return None
