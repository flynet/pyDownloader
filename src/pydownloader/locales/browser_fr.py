"""fr texts of the browser group: the keys come from browser_en.py."""

TEXTS: dict[str, str] = {
    # --- navigateur lancé (spec 5, 6.4) -------------------------------------
    "browser_started": "Navigateur : {browser}, profil {profile}, extension {extension}",
    "browser_started_line": "Navigateur démarré : {browser}",
    "browser_closed_by_user": "Navigateur fermé par l'utilisateur",
    "browser_page": "Page : {url} — {title}",
    "browser_page_unavailable": "Page indisponible : {error}",
    "browser_no_browser": (
        "Chrome et Edge sont introuvables, Chromium de Playwright n'est pas installé. "
        "Installez Chrome ou Edge, ou autorisez le téléchargement de Chromium."
    ),
    "browser_codec_warning": (
        "Chromium de Playwright peut ne pas lire H.264/AAC sur certains sites : "
        "préférez le Chrome ou l'Edge installé"
    ),
    "browser_none": "aucune",
    "browser_placeholder": "-",
    "browser_cookies": "Cookies pour {url} : {count}",
    "browser_response": "Réponse {status} {type} {length} octets {url}",
    "browser_family": "Famille de segments : {url} ({count} fichiers)",
    "browser_hls_group": "Groupe HLS de segments trouvé ({count} fichiers) : {url}",
    "browser_youtube_error": "YouTube : {error}",
    "browser_youtube_reason": "YouTube : {reason}",
    "browser_youtube_updated": "YouTube : flux mis à jour — {title}",
    "browser_youtube_found": "YouTube trouvé ({quality}) : {title}",
    "browser_quality_none": "inconnu",
    "browser_manifest_request": "Demande du manifeste {url} (cookies : {cookies})",
    "browser_manifest_failed": "Manifeste non obtenu : {url} ({error})",
    "browser_failed": "Navigateur : {error}",
    # --- téléchargement de Chromium (spec 6.4) ----------------------------
    "chromium_installed": "Chromium est installé",
    "chromium_not_installed": "Chromium n'est pas installé (code {code}) : {tail}",
    "chromium_no_output": "aucune sortie",
    # --- bloqueur de publicités (spec 6.4) --------------------------------
    "ext_unpacked": "Extension décompressée : {path}",
    "ext_not_crx": "le fichier n'est pas une extension Chromium (.crx)",
    "ext_bad_header": "en-tête CRX endommagé",
    "ext_no_manifest": "l'archive n'a pas de manifest.json",
    "ext_bad_zip": "l'extension est endommagée : l'archive ZIP est illisible",
    "ext_dir_unreadable": "Impossible de lire le dossier du programme {path} : {error}",
    "ext_not_loaded": "L'extension {path} n'est pas chargée : {error}",
    "ext_unknown_version": "version CRX inconnue : {value}",
    "ext_bad_path": "chemin invalide dans l'archive : {path}",
    "ext_connected": "Bloqueur de publicités connecté",
    "ext_not_connected": "Bloqueur de publicités non connecté",
    # --- données du programme et profil (spec 7.2) ------------------------
    "profile_moved": "Profil du navigateur déplacé : {src} -> {dst}",
    "profile_data_dir_writable": (
        "Le dossier du programme {dir} n'est pas accessible en écriture, "
        "les données restent dans {fallback}"
    ),
    "profile_dir_taken": "Le chemin du profil est occupé par un fichier : {path}",
    "profile_dir_writable": (
        "Le dossier du programme {dir} n'est pas accessible en écriture, "
        "le profil reste dans {fallback}"
    ),
    "profile_move_failed": "Impossible de déplacer le profil {src} vers {dst} : {error}",
    # --- FFmpeg (spec 6.5) ------------------------------------------------
    "ffmpeg_not_found": (
        "FFmpeg est introuvable. Placez ffmpeg.exe dans le dossier bin "
        "à côté du programme, ou ajoutez-le au PATH"
    ),
    "ffmpeg_ready": "FFmpeg prêt, sortie : {lines} lignes",
    "ffmpeg_code": "FFmpeg code {code} : {output}",
    "ffmpeg_exit_code": "FFmpeg a quitté avec le code {code}",
    "ffmpeg_no_output": "aucune sortie",
    "ffmpeg_direct_mp4": "MP4 direct",
}
