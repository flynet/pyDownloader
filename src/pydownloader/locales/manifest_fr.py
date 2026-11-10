"""fr texts of the manifest group: the keys come from manifest_en.py.

The classifier, the registry and the quality filter (spec 5.1/5.2), the
console lines of the pipeline, the HLS and DASH parsers (spec 5.1) and
the YouTube source.
"""

TEXTS: dict[str, str] = {
    # --- classification et registre (spec 5.1) -----------------------------
    "mf_reason_fragment": "segment d'un manifeste déjà trouvé",
    "mf_reason_playlist": "liste d'un flux déjà trouvé",
    "mf_reason_small_file": "fichier sous le seuil, pas une vidéo",
    "mf_reason_with_url": "{reason} : {url}",
    "mf_range_merged": "Déjà trouvé, requête Range fusionnée : {url}",
    "mf_found_already": "Déjà trouvé : {url}",
    "mf_url_recorded": "URL enregistrée {key} -> {url}",
    "mf_playlist_owned": "La liste {url} appartient au flux déjà trouvé {owner}",
    "mf_new_manifest": "Nouveau manifeste {kind} : {url}",
    "mf_segment_before_manifest": "Segment avant le manifeste ({dir}) : {url}",
    # --- filtre de qualité (spec 5.2 p.3) ----------------------------------
    "mf_quality_unknown": "inconnue",
    "mf_quality_mp3": "MP3",
    "mf_quality_no_audio": "Flux sans piste audio : ignoré",
    "mf_quality_video_skipped": "Flux vidéo : ignoré (mode audio uniquement)",
    "mf_quality_no_heights": "Flux trouvé sans {target}p : ignoré (résolution inconnue)",
    "mf_quality_available": "Flux trouvé sans {target}p : ignoré (disponible : {listed})",
    "mf_quality_debug": "Qualité insuffisante ({url}) : {message}",
    # --- lignes de console du pipeline (spec 5.2) -------------------------
    "mf_manifest_captured": "Manifeste pris de la réponse interceptée : {url}",
    "mf_manifest_not_fetched": "Manifeste non récupéré : {url}",
    "mf_manifest_not_parsed": "Manifeste non analysé : {error}",
    "mf_parse_failed_debug": "Manifeste non analysé ({url}) : {error}",
    "mf_live_skipped": "Diffusion en direct : ignorée ({url})",
    "mf_drm_message": "Le contenu est protégé par DRM, téléchargement impossible",
    "mf_drm_detected": "{message} ({system})",
    "mf_found_mp4": "MP4 trouvé {quality} : {url}",
    "mf_found_audio": "Son trouvé : {url}",
    "mf_found_dash": "Flux DASH trouvé {height}p : {url}",
    "mf_found_hls_unknown": "Flux HLS trouvé (résolution inconnue) : {url}",
    "mf_found_hls": "Flux HLS trouvé {height}p : {url}",
    "mf_found_hls_deferred": (
        "Flux HLS trouvé {height}p : {url} (variante demandée au téléchargement)"
    ),
    "mf_variant_not_fetched": (
        "Variante {height}p non récupérée, demandée au téléchargement : {url}"
    ),
    "mf_variant_not_parsed_debug": "Variante non analysée ({url}) : {error}",
    "mf_nested_master_debug": "La variante {url} est une liste principale imbriquée",
    "mf_master_debug": (
        "Maître {url} : choisi {height}p, variante {variant} (enregistré : {recorded})"
    ),
    "mf_yes": "oui",
    "mf_no": "non",
    # --- parseurs HLS et DASH (spec 5.1) -----------------------------------
    "mf_empty_response": "Réponse du manifeste vide",
    "hls_unclosed_quote": "Guillemet non fermé dans les attributs : {text!r}",
    "hls_no_extm3u": "Pas de balise #EXTM3U - ce n'est pas une liste HLS",
    "dash_parse_failed": "MPD non analysé : {error}",
    "dash_root_not_mpd": "L'élément racine n'est pas MPD",
    "dash_timeline_no_time": "SegmentTimeline sans @t et sans valeur précédente",
    # --- source YouTube ----------------------------------------------------
    "yt_reason_login_required": "YouTube exige la connexion au compte",
    "yt_reason_unplayable": "la vidéo n'est pas disponible à la lecture",
    "yt_reason_error": "erreur de lecture YouTube",
    "yt_reason_empty": "réponse du lecteur vide",
    "yt_reason_malformed": "impossible d'analyser la réponse du lecteur",
    "yt_reason_parse_error": "impossible d'analyser la réponse du lecteur",
    "yt_reason_status": "YouTube : {status}",
    "yt_plan_error": "YouTube : {reason}",
    "yt_plan_live": "Diffusion en direct : ignorée",
    "yt_plan_no_video": "YouTube : aucun format vidéo disponible",
}
