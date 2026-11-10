"""Pipeline tests: response event → filters → registry (spec 5.1/5.2).

The manifest body is injected by a fake fetcher, so the tests run without a
browser and without a network.
"""

from __future__ import annotations

from pydownloader.browser.events import ResponseEvent
from pydownloader.manifest.pipeline import Fetch, process_event
from pydownloader.manifest.quality import QualityFilter
from pydownloader.manifest.registry import SourceRegistry
from tests.conftest import HLS_URL, MPD_URL

MIN_SIZE = 5 * 1024 * 1024
QUALITY = QualityFilter()
VARIANT_1080 = "https://cdn.example.com/video/video/1080.m3u8?token=abc"


def make_fetch(texts: dict[str, str]) -> Fetch:
    def fetch(url: str, headers: dict[str, str]) -> str | None:
        return texts.get(url)

    return fetch


def event(
    url: str,
    content_type: str | None = None,
    content_length: int | None = None,
    content_range: str | None = None,
    status: int = 200,
    page_title: str = "Страница",
) -> ResponseEvent:
    return ResponseEvent(
        url=url,
        page_url="https://site.example/watch/42",
        page_title=page_title,
        status=status,
        content_type=content_type,
        content_length=content_length,
        content_range=content_range,
        request_headers={"referer": "https://site.example/watch/42", "user-agent": "UA"},
    )


def run(
    events_text: dict[str, str],
    response: ResponseEvent,
    registry: SourceRegistry | None = None,
) -> tuple[SourceRegistry, list]:
    registry = registry if registry is not None else SourceRegistry(min_mp4_size=MIN_SIZE)
    outcomes = process_event(response, registry, make_fetch(events_text), QUALITY)
    return registry, outcomes


def test_master_with_1080p_is_shown(read):
    texts = {HLS_URL: read("master.m3u8"), VARIANT_1080: read("media.m3u8")}
    registry, outcomes = run(texts, event(HLS_URL, content_type="application/vnd.apple.mpegurl"))
    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.action == "show"
    assert outcome.message == "Найден HLS-поток 1080p: " + HLS_URL
    entry = registry.entries()[0]
    assert entry.height == 1080
    assert entry.choice.url == VARIANT_1080
    # Audio of DEFAULT=YES is attached to the choice for the downloader.
    assert entry.choice.audio_url == "https://cdn.example.com/video/audio/ru.m3u8"
    assert entry.headers["Referer"] == "https://site.example/watch/42"


def test_recorded_variant_url_is_fetched_and_kept_in_the_choice(read):
    signed = "https://cdn.example.com/video/video/1080.m3u8?h=7&e=8"
    texts = {HLS_URL: read("master.m3u8"), signed: read("media.m3u8")}
    registry = SourceRegistry(min_mp4_size=MIN_SIZE)
    registry.note_response(event(signed))
    registry, outcomes = run(texts, event(HLS_URL), registry)
    assert outcomes[0].action == "show"
    entry = registry.entries()[0]
    # A CDN that signs every path rejects the constructed variant URL.
    assert entry.choice.url == signed


def test_playlist_in_a_directory_owned_by_the_master_is_a_fragment(read):
    second = "https://cdn.example.com/video/extra.m3u8"
    texts = {HLS_URL: read("master.m3u8"), VARIANT_1080: read("media.m3u8")}
    registry, outcomes = run(texts, event(HLS_URL, content_type="application/vnd.apple.mpegurl"))
    assert outcomes[0].action == "show"
    # A playlist next to the master (a second rendition, an audio track) belongs
    # to the stream already shown: no second row, the URL is recorded instead.
    registry, outcomes = run(texts, event(second), registry)
    assert len(outcomes) == 1
    assert outcomes[0].action == "fragment"
    assert outcomes[0].message == f"плейлист уже найденного потока: {second}"
    assert len(registry.entries()) == 1
    assert registry.entries()[0].recorded["/video/extra.m3u8"] == second


def test_intercepted_body_is_parsed_without_a_second_request(read):
    calls: list[str] = []

    def fetch(url: str, headers: dict[str, str]) -> str | None:
        calls.append(url)
        return None

    registry = SourceRegistry(min_mp4_size=MIN_SIZE)
    response = event(HLS_URL)
    response.body = read("master.m3u8")
    outcomes = process_event(
        response, registry, fetch, QUALITY, body=response.body
    )
    # The master body came from the browser: only the variant is requested, and
    # its failure does not drop the source (the worker fetches it again).
    assert calls == [VARIANT_1080]
    assert outcomes[0].action == "show"
    assert "будет запрошен при скачивании" in outcomes[0].message


def test_variant_fetch_failure_keeps_the_source_for_the_download(read):
    registry, outcomes = run({HLS_URL: read("master.m3u8")}, event(HLS_URL))
    assert outcomes[0].action == "show"
    assert "1080p" in outcomes[0].message
    assert "будет запрошен при скачивании" in outcomes[0].message
    entry = registry.entries()[0]
    assert entry.choice.url == VARIANT_1080
    assert entry.height == 1080


def test_master_without_1080p_is_hidden(read):
    texts = {HLS_URL: read("no_1080.m3u8")}
    registry, outcomes = run(texts, event(HLS_URL, content_type="application/x-mpegURL"))
    assert outcomes[0].action == "skip-quality"
    assert outcomes[0].message == "Найден поток без 1080p: пропущен (доступно: 720p, 480p)"
    assert registry.entries() == []


def test_master_with_live_variant_is_skipped(read):
    texts = {HLS_URL: read("master.m3u8"), VARIANT_1080: read("live.m3u8")}
    registry, outcomes = run(texts, event(HLS_URL))
    assert outcomes[0].action == "skip-live"
    assert "Live-трансляция: пропущен" in outcomes[0].message
    assert registry.entries() == []


def test_media_playlist_live_is_skipped(read):
    texts = {HLS_URL: read("live.m3u8")}
    registry, outcomes = run(texts, event(HLS_URL))
    assert outcomes[0].action == "skip-live"
    assert registry.entries() == []


def test_media_playlist_vod_is_shown_as_unknown(read):
    texts = {HLS_URL: read("media.m3u8")}
    registry, outcomes = run(texts, event(HLS_URL))
    assert outcomes[0].action == "show"
    assert "разрешение неизвестно" in outcomes[0].message
    entry = registry.entries()[0]
    assert entry.height is None
    assert entry.duration == 29.5


def test_hls_sample_aes_is_drm(read):
    texts = {HLS_URL: read("drm_hls.m3u8")}
    registry, outcomes = run(texts, event(HLS_URL))
    assert outcomes[0].action == "skip-drm"
    assert outcomes[0].message.startswith("Контент защищён DRM, скачивание невозможно")
    assert registry.entries() == []


def test_dash_1080p_is_shown(read):
    texts = {MPD_URL: read("template.mpd")}
    registry, outcomes = run(texts, event(MPD_URL, content_type="application/dash+xml"))
    assert outcomes[0].action == "show"
    assert outcomes[0].message == "Найден DASH-поток 1080p: " + MPD_URL
    entry = registry.entries()[0]
    assert entry.choice.video.id == "v1080"
    assert entry.duration == 30.0


def test_dash_dynamic_is_live(read):
    texts = {MPD_URL: read("dynamic.mpd")}
    registry, outcomes = run(texts, event(MPD_URL, content_type="application/dash+xml"))
    assert outcomes[0].action == "skip-live"
    assert registry.entries() == []


def test_dash_widevine_is_drm(read):
    texts = {MPD_URL: read("drm_mpd.mpd")}
    registry, outcomes = run(texts, event(MPD_URL, content_type="application/dash+xml"))
    assert outcomes[0].action == "skip-drm"
    assert registry.entries() == []


def test_manifest_without_body_is_dropped(read):
    registry, outcomes = run({}, event(HLS_URL))
    assert outcomes[0].action == "fetch-error"
    assert registry.entries() == []


def test_not_a_manifest_text_is_dropped(read):
    texts = {HLS_URL: "<html><body>player</body></html>"}
    registry, outcomes = run(texts, event(HLS_URL))
    assert outcomes[0].action == "parse-error"
    assert registry.entries() == []


def test_direct_mp4_is_shown_and_merged():
    registry = SourceRegistry(min_mp4_size=MIN_SIZE)
    url = "https://cdn.example.com/movie.mp4?token=A"
    first = event(url, content_type="video/mp4", content_length=12_000_000)
    registry, outcomes = run({}, first, registry)
    assert outcomes[0].action == "show"
    assert "неизвестно" in outcomes[0].message
    entry = registry.entries()[0]
    assert entry.size == 12_000_000
    # A Range request of the same file is merged, not added again.
    second = event(
        "https://cdn.example.com/movie.mp4?token=B",
        content_type="video/mp4",
        content_length=12_000_000,
    )
    registry, outcomes = run({}, second, registry)
    assert outcomes[0].action == "duplicate"
    assert len(registry.entries()) == 1


def test_mp4_size_comes_from_content_range():
    registry = SourceRegistry(min_mp4_size=MIN_SIZE)
    response = event(
        "https://cdn.example.com/movie.mp4",
        content_type="video/mp4",
        content_length=2,
        content_range="bytes 0-1/12345678",
    )
    registry, outcomes = run({}, response, registry)
    assert registry.entries()[0].size == 12345678
    assert "12345678" not in outcomes[0].message  # the size is not part of the console line


def test_small_mp4_is_dropped():
    registry = SourceRegistry(min_mp4_size=MIN_SIZE)
    response = event(
        "https://cdn.example.com/trailer.mp4", content_type="video/mp4", content_length=200_000
    )
    registry, outcomes = run({}, response, registry)
    assert outcomes[0].action == "skip-size"
    assert registry.entries() == []


def test_fragments_of_a_known_manifest_are_skipped(read):
    registry = SourceRegistry(min_mp4_size=MIN_SIZE)
    texts = {HLS_URL: read("master.m3u8"), VARIANT_1080: read("media.m3u8")}
    run(texts, event(HLS_URL), registry)
    fragment = event(
        "https://cdn.example.com/video/video/seg-1.mp4",
        content_type="video/mp4",
        content_length=6_000_000,
    )
    registry, outcomes = run(texts, fragment, registry)
    assert outcomes[0].action == "fragment"
    assert len(registry.entries()) == 1


def test_manifest_duplicate_is_reported(read):
    registry = SourceRegistry(min_mp4_size=MIN_SIZE)
    texts = {HLS_URL: read("master.m3u8"), VARIANT_1080: read("media.m3u8")}
    run(texts, event(HLS_URL), registry)
    registry, outcomes = run(texts, event(HLS_URL, content_type="application/x-mpegURL"), registry)
    assert outcomes[0].action == "duplicate"
    assert len(registry.entries()) == 1


def test_non_video_and_errors_are_ignored():
    _, outcomes = run({}, event("https://cdn.example.com/image.jpg", content_type="image/jpeg"))
    assert outcomes == []
    _, outcomes = run({}, event(HLS_URL, content_type="application/x-mpegURL", status=404))
    assert outcomes == []
    # Segments (.m4s) are not candidates at all.
    _, outcomes = run(
        {},
        event(
            "https://cdn.example.com/v/seg-1.m4s",
            content_type="video/mp4",
            content_length=6_000_000,
        ),
    )
    assert outcomes == []
