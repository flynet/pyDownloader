"""de texts of the browser group: the keys come from browser_en.py."""

TEXTS: dict[str, str] = {
    # --- gestarteter Browser (spec 5, 6.4) ---------------------------------
    "browser_started": "Browser: {browser}, Profil {profile}, Erweiterung {extension}",
    "browser_started_line": "Browser gestartet: {browser}",
    "browser_closed_by_user": "Browser vom Benutzer geschlossen",
    "browser_page": "Seite: {url} — {title}",
    "browser_page_unavailable": "Seite nicht verfügbar: {error}",
    "browser_no_browser": (
        "Chrome und Edge wurden nicht gefunden, Chromium von Playwright ist nicht "
        "installiert. Installieren Sie Chrome oder Edge, oder erlauben Sie den "
        "Download von Chromium."
    ),
    "browser_codec_warning": (
        "Chromium von Playwright kann H.264/AAC auf manchen Seiten nicht abspielen: "
        "das installierte Chrome oder Edge ist die bessere Wahl"
    ),
    "browser_none": "keine",
    "browser_placeholder": "-",
    "browser_cookies": "Cookies für {url}: {count}",
    "browser_response": "Antwort {status} {type} {length} Bytes {url}",
    "browser_family": "Segmentfamilie: {url} ({count} Dateien)",
    "browser_hls_group": "HLS-Segmentgruppe gefunden ({count} Dateien): {url}",
    "browser_youtube_error": "YouTube: {error}",
    "browser_youtube_reason": "YouTube: {reason}",
    "browser_youtube_updated": "YouTube: Stream aktualisiert — {title}",
    "browser_youtube_found": "YouTube gefunden ({quality}): {title}",
    "browser_quality_none": "unbekannt",
    "browser_manifest_request": "Manifest-Anfrage {url} (Cookies: {cookies})",
    "browser_manifest_failed": "Manifest nicht abgerufen: {url} ({error})",
    "browser_failed": "Browser: {error}",
    # --- Chromium-Download (spec 6.4) -------------------------------------
    "chromium_installed": "Chromium ist installiert",
    "chromium_not_installed": "Chromium ist nicht installiert (Code {code}): {tail}",
    "chromium_no_output": "keine Ausgabe",
    # --- Werbeblocker (spec 6.4) ------------------------------------------
    "ext_unpacked": "Erweiterung ausgepackt: {path}",
    "ext_not_crx": "die Datei ist keine Chromium-Erweiterung (.crx)",
    "ext_bad_header": "beschädigter CRX-Header",
    "ext_no_manifest": "das Archiv hat keine manifest.json",
    "ext_bad_zip": "die Erweiterung ist beschädigt: das ZIP-Archiv ist nicht lesbar",
    "ext_dir_unreadable": "Der Programmordner {path} kann nicht gelesen werden: {error}",
    "ext_not_loaded": "Erweiterung {path} wird nicht geladen: {error}",
    "ext_unknown_version": "unbekannte CRX-Version: {value}",
    "ext_bad_path": "ungültiger Pfad im Archiv: {path}",
    "ext_connected": "Werbeblocker verbunden",
    "ext_not_connected": "Werbeblocker nicht verbunden",
    # --- Programmdaten und Profil (spec 7.2) -----------------------------
    "profile_moved": "Browserprofil verschoben: {src} -> {dst}",
    "profile_data_dir_writable": (
        "Der Programmordner {dir} ist nicht beschreibbar, "
        "die Daten bleiben in {fallback}"
    ),
    "profile_dir_taken": "Der Profilpfad ist durch eine Datei belegt: {path}",
    "profile_dir_writable": (
        "Der Programmordner {dir} ist nicht beschreibbar, "
        "das Profil bleibt in {fallback}"
    ),
    "profile_move_failed": "Der Profil {src} lässt sich nicht nach {dst} verschieben: {error}",
    # --- FFmpeg (spec 6.5) ------------------------------------------------
    "ffmpeg_not_found": (
        "FFmpeg wurde nicht gefunden. Legen Sie ffmpeg.exe im Ordner bin "
        "neben dem Programm ab, oder fügen Sie ihn zu PATH hinzu"
    ),
    "ffmpeg_ready": "FFmpeg bereit, Ausgabe: {lines} Zeilen",
    "ffmpeg_code": "FFmpeg Code {code}: {output}",
    "ffmpeg_exit_code": "FFmpeg wurde mit Code {code} beendet",
    "ffmpeg_no_output": "keine Ausgabe",
    "ffmpeg_direct_mp4": "direktes MP4",
}
