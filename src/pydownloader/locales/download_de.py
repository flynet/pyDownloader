"""de texts of the download group: the keys come from download_en.py.

The queue, the engine, HTTP, AES-128, FFmpeg and the byte ranges
(spec 6.1-6.4, 7.3).
"""

TEXTS: dict[str, str] = {
    # --- Plan einer Aufgabe (spec 6.2) -------------------------------------
    "dl_source_not_parsed": "Quelle nicht analysiert: {url}",
    "dl_family_playlist_not_parsed": "Playlist der Segmentfamilie nicht analysiert: {error}",
    "dl_live_skipped": "Live-Übertragung: übersprungen",
    "dl_drm_detected": "{message} ({system})",
    "dl_manifest_not_fetched": "Manifest nicht abgerufen: {url}",
    "dl_manifest_not_parsed": "Manifest nicht analysiert: {error}",
    "dl_manifest_fetch_failed": "Manifest nicht abgerufen: {url} ({error})",
    "dl_manifest_recorded_url": "Manifest aus aufgezeichneter URL: {url}",
    "dl_nested_master": "Verschachtelter Master {url}: Wechsle zu {target}",
    "dl_nested_master_deep": "Manifest nicht analysiert: verschachtelte Master-Playlist",
    "dl_no_variants": "Master-Playlist hat keine Varianten",
    "dl_no_video_track": "Manifest enthält kein Video",
    "dl_audio_not_fetched": "Audiospur nicht abgerufen: {url}",
    "dl_variant_fallback": "Variante {height}p nicht verfügbar, lade {fallback}p: {url}",
    "dl_variant_fallback_short": "Variante {height}p nicht verfügbar, lade {fallback}p",
    # --- Warteschlange der Aufgaben (spec 6.2) ----------------------------
    "dl_task_queued": "Aufgabe {id} in die Warteschlange: {url}",
    "dl_cancel_task": "Aufgabe {id} wird abgebrochen",
    "dl_queue_started": "Warteschlange gestartet, warte auf Aufgaben",
    "dl_queue_stopped": "Warteschlange gestoppt",
    "dl_task_start": "Aufgabe {id}: {title} ({kind}, {name})",
    "dl_task_ready": "Aufgabe {id} fertig: {path}",
    "dl_task_cancelled": "Aufgabe abgebrochen",
    "dl_task_cancelled_log": "Aufgabe {id} abgebrochen",
    "dl_task_failed": "Aufgabe {id} fehlgeschlagen: {error}",
    "dl_task_error": "Fehler der Aufgabe {title}: {error}",
    "dl_task_crashed": "Aufgabe {id} unerwartet abgestürzt",
    "dl_cancelled_title": "Abgebrochen: {title}",
    "dl_cancelled": "abgebrochen",
    "dl_nothing_to_download": "Nichts herunterzuladen",
    "dl_plan_of_task": "Plan der Aufgabe {id}: {count} Dateien, Streams: {streams}",
    # --- aufgezeichnete URL des Browsers (spec 6.1, 6.2) -----------------
    "dl_recorded_url_failed": "Aufgezeichnete URL funktionierte nicht ({error}): {url}",
    "dl_recorded_segment_failed": "Segment der aufgezeichneten URL nicht geladen ({error}): {url}",
    "dl_try_recorded_playlist": "Versuche aufgezeichnete Playlist aus demselben Ordner: {url}",
    "dl_recorded_playlist_failed": "Aufgezeichnete Playlist funktionierte nicht ({error}): {url}",
    "dl_waiting_recorded_url": "Warte auf aufgezeichnete URL ({seconds:.0f} s): {url}",
    # --- Engine der Segmente (spec 6.2) -----------------------------------
    "dl_segments_incomplete": "Nicht alle Segmente sind heruntergeladen",
    "dl_segment_not_downloaded": "Segment nicht heruntergeladen",
    "dl_segment_attempt_failed": "Segment nicht geladen (Versuch {attempt}): {url} ({error})",
    "dl_segment_failed_after": "Segment nach {attempts} Versuchen nicht geladen: {url} ({error})",
    "dl_segment_key_missing": "Segment verschlüsselt, Schlüssel nicht angegeben: {url}",
    # --- HTTP (spec 6.1) --------------------------------------------------
    "http_net_error": "Netzwerkfehler: {error}",
    "http_net_error_log": "GET {url}: Netzwerkfehler {error}",
    "http_get_chars": "GET {url} -> {status} ({chars} Zeichen)",
    "http_get_bytes": "GET {url} -> {status} ({size} Bytes)",
    "http_status_for": "HTTP {status} für {url}",
    # --- AES-128 (spec 6.3) -----------------------------------------------
    "aes_key_size": "Der Schlüssel ist {size} Bytes, erwartet wurden {expected}",
    "aes_key_must_be": "Der Schlüssel muss {size} Bytes sein",
    "aes_iv_must_be": "Der IV muss {size} Bytes sein",
    "aes_data_not_aligned": "Segmentdaten sind kein Vielfaches der AES-Blockgröße",
    "aes_bad_padding": "Ungültige PKCS#7-Auffüllung",
    # --- FFmpeg (spec 6.4, 7.3) -------------------------------------------
    "ffmpeg_not_found": (
        "FFmpeg nicht gefunden. Legen Sie ffmpeg.exe in den Ordner bin neben dem Programm "
        "oder fügen Sie es dem PATH hinzu"
    ),
    "ffmpeg_no_output": "keine Ausgabe",
    "ffmpeg_exit_log": "FFmpeg Code {code}: {tail}",
    "ffmpeg_failed": "FFmpeg beendete mit Code {code}: {tail}",
    "ffmpeg_done_output": "FFmpeg fertig, Ausgabe: {lines} Zeilen",
    "ffmpeg_direct_mp4": "direktes MP4",
    "ffmpeg_direct_mp3": "direktes MP3",
    # --- Bytebereiche (spec 5.1) ------------------------------------------
    "range_bad_byterange": "Ungültiger BYTERANGE: {value!r}",
    "range_no_offset": "BYTERANGE ohne Offset und ohne vorherigen Bereich in derselben Datei",
    "range_bad_length": "BYTERANGE-Länge muss positiv sein: {value!r}",
}
