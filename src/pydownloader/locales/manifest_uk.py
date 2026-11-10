"""uk texts of the manifest group: the keys come from manifest_en.py."""

TEXTS: dict[str, str] = {
    # --- класифікація та реєстр (spec 5.1) -------------------------------
    "mf_reason_fragment": "фрагмент уже знайденого манифесту",
    "mf_reason_playlist": "плейлист уже знайденого потоку",
    "mf_reason_small_file": "файл нижче порогу, не відео",
    "mf_reason_with_url": "{reason}: {url}",
    "mf_range_merged": "Уже знайдено, Range-запит об'єднано: {url}",
    "mf_found_already": "Уже знайдено: {url}",
    "mf_url_recorded": "Записано URL {key} -> {url}",
    "mf_playlist_owned": "Плейлист {url} належить уже знайденому потоку {owner}",
    "mf_new_manifest": "Новий манифест {kind}: {url}",
    "mf_segment_before_manifest": "Сегмент до манифесту ({dir}): {url}",
    # --- фільтр якості (spec 5.2 п.3) ------------------------------------
    "mf_quality_unknown": "невідомо",
    "mf_quality_mp3": "MP3",
    "mf_quality_no_audio": "Знайдено потік без аудіодоріжки: пропущено",
    "mf_quality_video_skipped": "Відеопотік: пропущено (режим «тільки аудіо»)",
    "mf_quality_no_heights": (
        "Знайдено потік без {target}p: пропущено (роздільна здатність невідома)"
    ),
    "mf_quality_available": "Знайдено потік без {target}p: пропущено (доступно: {listed})",
    "mf_quality_debug": "Якість не підходить ({url}): {message}",
    # --- консоль конвеєра (spec 5.2) -------------------------------------
    "mf_manifest_captured": "Манифест із перехопленої відповіді: {url}",
    "mf_manifest_not_fetched": "Манифест не отримано: {url}",
    "mf_manifest_not_parsed": "Манифест не розібрано: {error}",
    "mf_parse_failed_debug": "Манифест не розібрано ({url}): {error}",
    "mf_live_skipped": "Прямий ефір: пропущено ({url})",
    "mf_drm_message": "Контент захищено DRM, качати неможливо",
    "mf_drm_detected": "{message} ({system})",
    "mf_found_mp4": "Знайдено MP4 {quality}: {url}",
    "mf_found_audio": "Знайдено звук: {url}",
    "mf_found_dash": "Знайдено DASH-потік {height}p: {url}",
    "mf_found_hls_unknown": "Знайдено HLS-потік (роздільна здатність невідома): {url}",
    "mf_found_hls": "Знайдено HLS-потік {height}p: {url}",
    "mf_found_hls_deferred": (
        "Знайдено HLS-потік {height}p: {url} (варіант качається на початку завантаження)"
    ),
    "mf_variant_not_fetched": "Варіант {height}p не отримано, запит при завантаженні: {url}",
    "mf_variant_not_parsed_debug": "Варіант не розібрано ({url}): {error}",
    "mf_nested_master_debug": "Варіант {url} — вкладений мастер-плейлист",
    "mf_master_debug": "Майстер {url}: обрано {height}p, варіант {variant} (записано: {recorded})",
    "mf_yes": "так",
    "mf_no": "ні",
    # --- парсери HLS і DASH (spec 5.1) -----------------------------------
    "mf_empty_response": "Порожня відповідь манифесту",
    "hls_unclosed_quote": "Не закрито лапку в атрибутах: {text!r}",
    "hls_no_extm3u": "Немає маркера #EXTM3U — це не HLS-плейлист",
    "dash_parse_failed": "MPD не розібрано: {error}",
    "dash_root_not_mpd": "Кореневий елемент не є MPD",
    "dash_timeline_no_time": "SegmentTimeline без @t і без попереднього значення",
    # --- джерело YouTube -------------------------------------------------
    "yt_reason_login_required": "YouTube вимагає входу в акаунт",
    "yt_reason_unplayable": "відео не відтворюється",
    "yt_reason_error": "Помилка програвання YouTube",
    "yt_reason_empty": "порожня відповідь плеєра",
    "yt_reason_malformed": "не можу розібрати відповідь плеєра",
    "yt_reason_parse_error": "не можу розібрати відповідь плеєра",
    "yt_reason_status": "YouTube: {status}",
    "yt_plan_error": "YouTube: {reason}",
    "yt_plan_live": "Прямий ефір: пропущено",
    "yt_plan_no_video": "YouTube: жодного відеоформату немає",
}
