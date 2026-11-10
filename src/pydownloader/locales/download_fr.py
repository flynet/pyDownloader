"""fr texts of the download group: the keys come from download_en.py.

The queue, the engine, HTTP, AES-128, FFmpeg and the byte ranges
(spec 6.1-6.4, 7.3).
"""

TEXTS: dict[str, str] = {
    # --- plan de la tâche (spec 6.2) ---------------------------------------
    "dl_source_not_parsed": "Source non analysée : {url}",
    "dl_family_playlist_not_parsed": "Liste de la famille de segments non analysée : {error}",
    "dl_live_skipped": "Diffusion en direct : ignorée",
    "dl_drm_detected": "{message} ({system})",
    "dl_manifest_not_fetched": "Manifeste non récupéré : {url}",
    "dl_manifest_not_parsed": "Manifeste non analysé : {error}",
    "dl_manifest_fetch_failed": "Manifeste non récupéré : {url} ({error})",
    "dl_manifest_recorded_url": "Manifeste depuis l'URL enregistrée : {url}",
    "dl_nested_master": "Maître imbriqué {url} : accès à {target}",
    "dl_nested_master_deep": "Manifeste non analysé : liste principale imbriquée",
    "dl_no_variants": "La liste principale n'a aucune variante",
    "dl_no_video_track": "Le manifeste n'a pas de vidéo",
    "dl_audio_not_fetched": "Piste audio non récupérée : {url}",
    "dl_variant_fallback": "Variante {height}p indisponible, téléchargement de {fallback}p : {url}",
    "dl_variant_fallback_short": "Variante {height}p indisponible, téléchargement de {fallback}p",
    # --- file des tâches (spec 6.2) ----------------------------------------
    "dl_task_queued": "Tâche {id} ajoutée à la file : {url}",
    "dl_cancel_task": "Annulation de la tâche {id}",
    "dl_queue_started": "File démarrée, en attente de tâches",
    "dl_queue_stopped": "File arrêtée",
    "dl_task_start": "Tâche {id} : {title} ({kind}, {name})",
    "dl_task_ready": "Tâche {id} terminée : {path}",
    "dl_task_cancelled": "Tâche annulée",
    "dl_task_cancelled_log": "Tâche {id} annulée",
    "dl_task_failed": "Tâche {id} échouée : {error}",
    "dl_task_error": "Erreur de la tâche {title} : {error}",
    "dl_task_crashed": "Tâche {id} arrêtée de façon inattendue",
    "dl_cancelled_title": "Annulé : {title}",
    "dl_cancelled": "annulé",
    "dl_nothing_to_download": "Rien à télécharger",
    "dl_plan_of_task": "Plan de la tâche {id} : {count} fichiers, flux : {streams}",
    # --- URL signées enregistrées par le navigateur (spec 6.1, 6.2) -------
    "dl_recorded_url_failed": "L'URL enregistrée n'a pas fonctionné ({error}) : {url}",
    "dl_recorded_segment_failed": "Segment de l'URL enregistrée non récupéré ({error}) : {url}",
    "dl_try_recorded_playlist": "Essai de la liste enregistrée du même dossier : {url}",
    "dl_recorded_playlist_failed": "La liste enregistrée n'a pas fonctionné ({error}) : {url}",
    "dl_waiting_recorded_url": "Attente de l'URL enregistrée ({seconds:.0f} s) : {url}",
    # --- moteur des segments (spec 6.2) ------------------------------------
    "dl_segments_incomplete": "Tous les segments ne sont pas téléchargés",
    "dl_segment_not_downloaded": "Segment non téléchargé",
    "dl_segment_attempt_failed": "Segment non téléchargé (essai {attempt}) : {url} ({error})",
    "dl_segment_failed_after": "Segment non téléchargé après {attempts} essais : {url} ({error})",
    "dl_segment_key_missing": "Segment chiffré, clé non indiquée : {url}",
    # --- HTTP (spec 6.1) ---------------------------------------------------
    "http_net_error": "Erreur réseau : {error}",
    "http_net_error_log": "GET {url} : erreur réseau {error}",
    "http_get_chars": "GET {url} -> {status} ({chars} caractères)",
    "http_get_bytes": "GET {url} -> {status} ({size} octets)",
    "http_status_for": "HTTP {status} pour {url}",
    # --- AES-128 (spec 6.3) ------------------------------------------------
    "aes_key_size": "La clé fait {size} octets, {expected} étaient attendus",
    "aes_key_must_be": "La clé doit faire {size} octets",
    "aes_iv_must_be": "L'IV doit faire {size} octets",
    "aes_data_not_aligned": "Les données du segment ne sont pas un multiple de bloc AES",
    "aes_bad_padding": "Remplissage PKCS#7 incorrect",
    # --- FFmpeg (spec 6.4, 7.3) --------------------------------------------
    "ffmpeg_not_found": (
        "FFmpeg introuvable. Placez ffmpeg.exe dans le dossier bin à côté du programme, "
        "ou ajoutez-le au PATH"
    ),
    "ffmpeg_no_output": "aucune sortie",
    "ffmpeg_exit_log": "FFmpeg code {code} : {tail}",
    "ffmpeg_failed": "FFmpeg s'est terminé avec le code {code} : {tail}",
    "ffmpeg_done_output": "FFmpeg terminé, sortie : {lines} lignes",
    "ffmpeg_direct_mp4": "MP4 direct",
    "ffmpeg_direct_mp3": "MP3 direct",
    # --- plages d'octets (spec 5.1) ----------------------------------------
    "range_bad_byterange": "BYTERANGE invalide : {value!r}",
    "range_no_offset": "BYTERANGE sans décalage et sans plage précédente dans le même fichier",
    "range_bad_length": "La longueur BYTERANGE doit être positive : {value!r}",
}
