"""de texts of the manifest group: the keys come from manifest_en.py.

The classifier, the registry and the quality filter (spec 5.1/5.2), the
console lines of the pipeline, the HLS and DASH parsers (spec 5.1) and
the YouTube source.
"""

TEXTS: dict[str, str] = {
    # --- Klassifizierung und Register (spec 5.1) ---------------------------
    "mf_reason_fragment": "Segment eines bereits gefundenen Manifests",
    "mf_reason_playlist": "Playlist eines bereits gefundenen Streams",
    "mf_reason_small_file": "Datei unter der Schwelle, kein Video",
    "mf_reason_with_url": "{reason}: {url}",
    "mf_range_merged": "Bereits gefunden, Range-Anfrage zusammengeführt: {url}",
    "mf_found_already": "Bereits gefunden: {url}",
    "mf_url_recorded": "URL aufgezeichnet {key} -> {url}",
    "mf_playlist_owned": "Playlist {url} gehört zum bereits gefundenen Stream {owner}",
    "mf_new_manifest": "Neues Manifest {kind}: {url}",
    "mf_segment_before_manifest": "Segment vor dem Manifest ({dir}): {url}",
    # --- Qualitätsfilter (spec 5.2 p.3) ------------------------------------
    "mf_quality_unknown": "unbekannt",
    "mf_quality_mp3": "MP3",
    "mf_quality_no_audio": "Stream ohne Tonspur: übersprungen",
    "mf_quality_video_skipped": "Videostream: übersprungen (Nur-Audio-Modus)",
    "mf_quality_no_heights": "Stream ohne {target}p gefunden: übersprungen (Auflösung unbekannt)",
    "mf_quality_available": "Stream ohne {target}p gefunden: übersprungen (verfügbar: {listed})",
    "mf_quality_debug": "Qualität passt nicht ({url}): {message}",
    # --- Konsolenzeilen der Pipeline (spec 5.2) ---------------------------
    "mf_manifest_captured": "Manifest aus der abgefangenen Antwort: {url}",
    "mf_manifest_not_fetched": "Manifest nicht abgerufen: {url}",
    "mf_manifest_not_parsed": "Manifest nicht analysiert: {error}",
    "mf_parse_failed_debug": "Manifest nicht analysiert ({url}): {error}",
    "mf_live_skipped": "Live-Übertragung: übersprungen ({url})",
    "mf_drm_message": "Inhalt ist durch DRM geschützt, Herunterladen nicht möglich",
    "mf_drm_detected": "{message} ({system})",
    "mf_found_mp4": "MP4 gefunden {quality}: {url}",
    "mf_found_audio": "Audio gefunden: {url}",
    "mf_found_dash": "DASH-Stream gefunden {height}p: {url}",
    "mf_found_hls_unknown": "HLS-Stream gefunden (Auflösung unbekannt): {url}",
    "mf_found_hls": "HLS-Stream gefunden {height}p: {url}",
    "mf_found_hls_deferred": (
        "HLS-Stream gefunden {height}p: {url} (Variante beim Download angefordert)"
    ),
    "mf_variant_not_fetched": (
        "Variante {height}p nicht abgerufen, beim Download angefordert: {url}"
    ),
    "mf_variant_not_parsed_debug": "Variante nicht analysiert ({url}): {error}",
    "mf_nested_master_debug": "Variante {url} ist eine verschachtelte Master-Playlist",
    "mf_master_debug": (
        "Master {url}: gewählt {height}p, Variante {variant} (aufgezeichnet: {recorded})"
    ),
    "mf_yes": "ja",
    "mf_no": "nein",
    # --- HLS- und DASH-Parser (spec 5.1) -----------------------------------
    "mf_empty_response": "Leere Manifest-Antwort",
    "hls_unclosed_quote": "Nicht geschlossenes Anführungszeichen in den Attributen: {text!r}",
    "hls_no_extm3u": "Kein #EXTM3U-Marker - das ist keine HLS-Playlist",
    "dash_parse_failed": "MPD nicht analysiert: {error}",
    "dash_root_not_mpd": "Das Wurzelelement ist nicht MPD",
    "dash_timeline_no_time": "SegmentTimeline ohne @t und ohne vorherigen Wert",
    # --- YouTube-Quelle ----------------------------------------------------
    "yt_reason_login_required": "YouTube erfordert die Anmeldung im Konto",
    "yt_reason_unplayable": "Video ist nicht abspielbar",
    "yt_reason_error": "YouTube-Wiedergabefehler",
    "yt_reason_empty": "leere Spieler-Antwort",
    "yt_reason_malformed": "die Spieler-Antwort konnte nicht analysiert werden",
    "yt_reason_parse_error": "die Spieler-Antwort konnte nicht analysiert werden",
    "yt_reason_status": "YouTube: {status}",
    "yt_plan_error": "YouTube: {reason}",
    "yt_plan_live": "Live-Übertragung: übersprungen",
    "yt_plan_no_video": "YouTube: kein verfügbares Videoformat",
}
