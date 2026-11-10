"""ru texts of the manifest group: the keys come from manifest_en.py.

The classifier, the registry and the quality filter (spec 5.1/5.2), the
console lines of the pipeline, the HLS and DASH parsers (spec 5.1) and
the YouTube source.
"""

TEXTS: dict[str, str] = {
    # --- классификация и реестр (спецификация 5.1) -------------------------
    "mf_reason_fragment": "фрагмент уже найденного манифеста",
    "mf_reason_playlist": "плейлист уже найденного потока",
    "mf_reason_small_file": "файл меньше порога, не видео",
    "mf_reason_with_url": "{reason}: {url}",
    "mf_range_merged": "Уже найден, Range-запрос объединён: {url}",
    "mf_found_already": "Уже найден: {url}",
    "mf_url_recorded": "Записан URL {key} -> {url}",
    "mf_playlist_owned": "Плейлист {url} принадлежит уже найденному потоку {owner}",
    "mf_new_manifest": "Новый манифест {kind}: {url}",
    "mf_segment_before_manifest": "Сегмент до манифеста ({dir}): {url}",
    # --- фильтр качества (спецификация 5.2 п.3) ----------------------------
    "mf_quality_unknown": "неизвестно",
    "mf_quality_mp3": "MP3",
    "mf_quality_no_audio": "Найден поток без аудиодорожки: пропущен",
    "mf_quality_video_skipped": "Видеопоток: пропущен (режим «только аудио»)",
    "mf_quality_no_heights": "Найден поток без {target}p: пропущен (разрешение не определяется)",
    "mf_quality_available": "Найден поток без {target}p: пропущен (доступно: {listed})",
    "mf_quality_debug": "Качество не подходит ({url}): {message}",
    # --- строки консоли конвейера (спецификация 5.2) -----------------------
    "mf_manifest_captured": "Манифест взят из перехваченного ответа: {url}",
    "mf_manifest_not_fetched": "Не получен манифест: {url}",
    "mf_manifest_not_parsed": "Манифест не разобран: {error}",
    "mf_parse_failed_debug": "Манифест не разобран ({url}): {error}",
    "mf_live_skipped": "Live-трансляция: пропущен ({url})",
    "mf_drm_message": "Контент защищён DRM, скачивание невозможно",
    "mf_drm_detected": "{message} ({system})",
    "mf_found_mp4": "Найден MP4 {quality}: {url}",
    "mf_found_audio": "Найден звук: {url}",
    "mf_found_dash": "Найден DASH-поток {height}p: {url}",
    "mf_found_hls_unknown": "Найден HLS-поток (разрешение неизвестно): {url}",
    "mf_found_hls": "Найден HLS-поток {height}p: {url}",
    "mf_found_hls_deferred": (
        "Найден HLS-поток {height}p: {url} (вариант будет запрошен при скачивании)"
    ),
    "mf_variant_not_fetched": (
        "Вариант {height}p не получен сейчас, будет запрошен при скачивании: {url}"
    ),
    "mf_variant_not_parsed_debug": "Вариант не разобран ({url}): {error}",
    "mf_nested_master_debug": "Вариант {url} — вложенный мастер-плейлист",
    "mf_master_debug": "Мастер {url}: выбран {height}p, вариант {variant} (записан: {recorded})",
    "mf_yes": "да",
    "mf_no": "нет",
    # --- парсеры HLS и DASH (спецификация 5.1) -----------------------------
    "mf_empty_response": "Пустой ответ манифеста",
    "hls_unclosed_quote": "Незакрытая кавычка в атрибутах: {text!r}",
    "hls_no_extm3u": "Нет маркера #EXTM3U — это не HLS-плейлист",
    "dash_parse_failed": "MPD не разобран: {error}",
    "dash_root_not_mpd": "Корневой элемент не MPD",
    "dash_timeline_no_time": "SegmentTimeline без @t и без предыдущего значения",
    # --- источник YouTube ---------------------------------------------------
    "yt_reason_login_required": "YouTube требует входа в аккаунт",
    "yt_reason_unplayable": "видео недоступно для воспроизведения",
    "yt_reason_error": "ошибка воспроизведения YouTube",
    "yt_reason_empty": "пустой ответ плеера",
    "yt_reason_malformed": "не удалось разобрать ответ плеера",
    "yt_reason_parse_error": "не удалось разобрать ответ плеера",
    "yt_reason_status": "YouTube: {status}",
    "yt_plan_error": "YouTube: {reason}",
    "yt_plan_live": "Live-трансляция: пропущена",
    "yt_plan_no_video": "YouTube: нет доступного видеоформата",
}
