"""uk texts of the download group: the keys come from download_en.py."""

TEXTS: dict[str, str] = {
    # --- план задачі (spec 6.2) -------------------------------------------
    "dl_source_not_parsed": "Джерело не розібрано: {url}",
    "dl_family_playlist_not_parsed": "Плейлист сімейства сегментів не розібрано: {error}",
    "dl_live_skipped": "Прямий ефір: пропущено",
    "dl_drm_detected": "{message} ({system})",
    "dl_manifest_not_fetched": "Манифест не отримано: {url}",
    "dl_manifest_not_parsed": "Манифест не розібрано: {error}",
    "dl_manifest_fetch_failed": "Манифест не отримано: {url} ({error})",
    "dl_manifest_recorded_url": "Манифест із записаного URL: {url}",
    "dl_nested_master": "Вкладений мастер {url}: спуск до {target}",
    "dl_nested_master_deep": "Манифест не розібрано: вкладений мастер-плейлист",
    "dl_no_variants": "Майстер-плейлист не має варіантів",
    "dl_no_video_track": "Манифест не має відео",
    "dl_audio_not_fetched": "Аудіодоріжку не отримано: {url}",
    "dl_variant_fallback": "Варіант {height}p недоступний, качаю {fallback}p: {url}",
    "dl_variant_fallback_short": "Варіант {height}p недоступний, качаю {fallback}p",
    # --- черга задач (spec 6.2) -------------------------------------------
    "dl_task_queued": "Задача {id} додана в чергу: {url}",
    "dl_cancel_task": "Скасовую задачу {id}",
    "dl_queue_started": "Чергу запущено, чекаю на задачі",
    "dl_queue_stopped": "Чергу зупинено",
    "dl_task_start": "Задача {id}: {title} ({kind}, {name})",
    "dl_task_ready": "Задача {id} готова: {path}",
    "dl_task_cancelled": "Задачу скасовано",
    "dl_task_cancelled_log": "Задачу {id} скасовано",
    "dl_task_failed": "Задача {id} не вдалася: {error}",
    "dl_task_error": "Помилка задачі {title}: {error}",
    "dl_task_crashed": "Задача {id} впала неочікувано",
    "dl_cancelled_title": "Скасовано: {title}",
    "dl_cancelled": "скасовано",
    "dl_nothing_to_download": "Немає чого качати",
    "dl_plan_of_task": "План задачі {id}: {count} файлів, потоки: {streams}",
    # --- записані URL браузера (spec 6.1, 6.2) ---------------------------
    "dl_recorded_url_failed": "Записаний URL не спрацював ({error}): {url}",
    "dl_recorded_segment_failed": "Сегмент із записаного URL не отримано ({error}): {url}",
    "dl_try_recorded_playlist": "Пробую записаний плейлист із тої самої теки: {url}",
    "dl_recorded_playlist_failed": "Записаний плейлист не спрацював ({error}): {url}",
    "dl_waiting_recorded_url": "Чекаю на записаний URL ({seconds:.0f} с): {url}",
    # --- движок сегментів (spec 6.2) --------------------------------------
    "dl_segments_incomplete": "Не всі сегменти качано",
    "dl_segment_not_downloaded": "Сегмент не качано",
    "dl_segment_attempt_failed": "Сегмент не качано (спроба {attempt}): {url} ({error})",
    "dl_segment_failed_after": "Сегмент не качано після {attempts} спроб: {url} ({error})",
    "dl_segment_key_missing": "Сегмент шифровано, ключа не дано: {url}",
    # --- HTTP (spec 6.1) -------------------------------------------------
    "http_net_error": "Помилка мережі: {error}",
    "http_net_error_log": "GET {url}: помилка мережі {error}",
    "http_get_chars": "GET {url} -> {status} ({chars} знаків)",
    "http_get_bytes": "GET {url} -> {status} ({size} байтів)",
    "http_status_for": "HTTP {status} для {url}",
    # --- AES-128 (spec 6.3) ----------------------------------------------
    "aes_key_size": "Ключ {size} байтів, очікувалось {expected}",
    "aes_key_must_be": "Ключ мусить бути {size} байтів",
    "aes_iv_must_be": "IV мусить бути {size} байтів",
    "aes_data_not_aligned": "Дані сегмента не кратні розміру блоку AES",
    "aes_bad_padding": "Пошкоджене пополнення PKCS#7",
    # --- FFmpeg (spec 6.4, 7.3) ------------------------------------------
    "ffmpeg_not_found": (
        "FFmpeg не знайдено. Покладіть ffmpeg.exe в теку bin поруч із програмою, "
        "або додайте його до PATH"
    ),
    "ffmpeg_no_output": "немає виводу",
    "ffmpeg_exit_log": "FFmpeg код {code}: {tail}",
    "ffmpeg_failed": "FFmpeg завершився з кодом {code}: {tail}",
    "ffmpeg_done_output": "FFmpeg завершив, вивід: {lines} рядків",
    "ffmpeg_direct_mp4": "прямий MP4",
    "ffmpeg_direct_mp3": "прямий MP3",
    # --- байтові діапазони (spec 5.1) ------------------------------------
    "range_bad_byterange": "Невірний BYTERANGE: {value!r}",
    "range_no_offset": "BYTERANGE без зсуву й без попереднього діапазону в тому самому файлі",
    "range_bad_length": "Довжина BYTERANGE мусить бути додатною: {value!r}",
}
