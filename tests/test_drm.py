"""DRM detection tests (spec 11: DrmDetector). DRM content is skipped, never bypassed."""

from __future__ import annotations

from pydownloader.dash.parser import parse_mpd
from pydownloader.hls.parser import parse_playlist
from pydownloader.i18n import set_language
from pydownloader.manifest.drm import detect_dash, detect_drm, detect_hls, drm_message
from tests.conftest import HLS_URL, MPD_URL


def test_hls_plain_playlist_is_ok(read):
    playlist = parse_playlist(read("master.m3u8"), HLS_URL)
    verdict = detect_hls(playlist)
    assert verdict.ok
    assert verdict.system is None


def test_hls_aes128_is_not_drm(read):
    playlist = parse_playlist(read("aes.m3u8"), HLS_URL)
    verdict = detect_hls(playlist)
    assert verdict.ok


def test_hls_sample_aes_is_drm(read):
    playlist = parse_playlist(read("drm_hls.m3u8"), HLS_URL)
    verdict = detect_hls(playlist)
    assert verdict.is_drm
    assert verdict.system == "SAMPLE-AES"
    assert verdict.message == drm_message()
    # the text follows the language of the program (spec 4.3)
    english = set_language("en")
    assert verdict.message == "Content is protected by DRM, downloading is not possible"
    set_language(english)


def test_hls_fairplay_keyformat_is_drm():
    # AES-128 with a non-DRM key format is not DRM.
    plain = (
        '#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="https://k/key.bin",'
        'KEYFORMAT="com.apple.externalplayer",KEYFORMATVERSIONS="1"\n'
        "#EXTINF:6.0,\nseg.ts\n#EXT-X-ENDLIST\n"
    )
    # AES-128 with a DRM key format is DRM.
    fairplay = (
        '#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="https://k/key.bin",'
        'KEYFORMAT="urn:uuid:94cec79f-72d9-4b07-8446-242b1c296c46"\n'
        "#EXTINF:6.0,\nseg.ts\n#EXT-X-ENDLIST\n"
    )
    assert detect_hls(parse_playlist(plain, HLS_URL)).ok
    assert detect_hls(parse_playlist(fairplay, HLS_URL)).is_drm


def test_mpd_widevine_is_drm(read):
    mpd = parse_mpd(read("drm_mpd.mpd"), MPD_URL)
    verdict = detect_dash(mpd)
    assert verdict.is_drm
    assert verdict.system in ("CommonEncryption", "Widevine", "PlayReady", "FairPlay")


def test_mpd_plain_is_ok(read):
    mpd = parse_mpd(read("template.mpd"), MPD_URL)
    assert detect_dash(mpd).ok


def test_mpd_mp4protection_is_not_drm():
    # urn:mpeg:dash:mp4protection:2011 signals ISO BMFF, not encryption.
    text = (
        '<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static">'
        '<Period><AdaptationSet contentType="video" mimeType="video/mp4">'
        '<ContentProtection schemeIdUri="urn:mpeg:dash:mp4protection:2011" value="cenc"/>'
        '<Representation id="v" width="1920" height="1080" bandwidth="1000">'
        '<SegmentBase><Initialization sourceURL="f.mp4"/></SegmentBase></Representation>'
        "</AdaptationSet></Period></MPD>"
    )
    mpd = parse_mpd(text, MPD_URL)
    assert detect_dash(mpd).ok


def test_mpd_playready_is_drm():
    text = (
        '<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static">'
        '<Period><AdaptationSet contentType="video">'
        '<ContentProtection schemeIdUri="urn:uuid:9a04fbb5-1a71-4b91-936c-4d4d499734f1"/>'
        '<Representation id="v" width="1920" height="1080" bandwidth="1000">'
        '<SegmentBase><Initialization sourceURL="f.mp4"/></SegmentBase></Representation>'
        "</AdaptationSet></Period></MPD>"
    )
    verdict = detect_drm(parse_mpd(text, MPD_URL))
    assert verdict.is_drm
    assert verdict.system == "PlayReady"


def test_dispatch_on_manifest_type(read):
    assert detect_drm(parse_playlist(read("aes.m3u8"), HLS_URL)).ok
    assert detect_drm(parse_mpd(read("drm_mpd.mpd"), MPD_URL)).is_drm
