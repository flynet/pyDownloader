"""ru texts of the download group: the keys come from download_en.py.

The queue, the engine, HTTP, AES-128, FFmpeg and the byte ranges
(spec 6.1-6.4, 7.3).
"""

TEXTS: dict[str, str] = {
    # --- план задачи (спецификация 6.2) ------------------------------------
    "dl_source_not_parsed": "Источник не разобран: {url}",
    "dl_family_playlist_not_parsed": "Плейлист группы сегментов не разобран: {error}",
    "dl_live_skipped": "Live-трансляция: пропущена",
    "dl_drm_detected": "{message} ({system})",
    "dl_manifest_not_fetched": "Не получен манифест: {url}",
    "dl_manifest_not_parsed": "Манифест не разобран: {error}",
    "dl_manifest_fetch_failed": "Манифест не получен: {url} ({error})",
    "dl_manifest_recorded_url": "Манифест по записанному URL: {url}",
    "dl_nested_master": "Вложенный мастер {url}: спускаюсь к {target}",
    "dl_nested_master_deep": "Манифест не разобран: вложенный мастер-плейлист",
    "dl_no_variants": "В мастер-плейлисте нет вариантов",
    "dl_no_video_track": "В манифесте нет видеоролика",
    "dl_audio_not_fetched": "Аудио-дорожка не получена: {url}",
    "dl_variant_fallback": "Вариант {height}p недоступен, скачиваю {fallback}p: {url}",
    "dl_variant_fallback_short": "Вариант {height}p недоступен, скачиваю {fallback}p",
    # --- очередь задач (спецификация 6.2) ---------------------------------
    "dl_task_queued": "В очередь добавлена задача {id}: {url}",
    "dl_cancel_task": "Отмена задачи {id}",
    "dl_queue_started": "Очередь запущена, ожидание задач",
    "dl_queue_stopped": "Очередь остановлена",
    "dl_task_start": "Задача {id}: {title} ({kind}, {name})",
    "dl_task_ready": "Задача {id} готова: {path}",
    "dl_task_cancelled": "Задача отменена",
    "dl_task_cancelled_log": "Задача {id} отменена",
    "dl_task_failed": "Задача {id} не выполнена: {error}",
    "dl_task_error": "Ошибка задачи {title}: {error}",
    "dl_task_crashed": "Задача {id} упала неожиданно",
    "dl_cancelled_title": "Отменено: {title}",
    "dl_cancelled": "отменено",
    "dl_nothing_to_download": "Нечего скачивать",
    "dl_plan_of_task": "План задачи {id}: {count} файлов, потоки: {streams}",
    # --- записанные URL браузера (спецификация 6.1, 6.2) -----------------
    "dl_recorded_url_failed": "Записанный URL не сработал ({error}): {url}",
    "dl_recorded_segment_failed": "Сегмент по записанному URL не получен ({error}): {url}",
    "dl_try_recorded_playlist": "Пробую записанный плейлист из того же каталога: {url}",
    "dl_recorded_playlist_failed": "Записанный плейлист не сработал ({error}): {url}",
    "dl_waiting_recorded_url": "Жду записанный URL ({seconds:.0f} с): {url}",
    # --- движок сегментов (спецификация 6.2) -----------------------------
    "dl_segments_incomplete": "Не все сегменты загружены",
    "dl_segment_not_downloaded": "Сегмент не скачан",
    "dl_segment_attempt_failed": "Сегмент не скачан (попытка {attempt}): {url} ({error})",
    "dl_segment_failed_after": "Сегмент не скачан после {attempts} попыток: {url} ({error})",
    "dl_segment_key_missing": "Сегмент зашифрован, ключ не указан: {url}",
    # --- HTTP (спецификация 6.1) ------------------------------------------
    "http_net_error": "Сетевая ошибка: {error}",
    "http_net_error_log": "GET {url}: сетевая ошибка {error}",
    "http_get_chars": "GET {url} -> {status} ({chars} символов)",
    "http_get_bytes": "GET {url} -> {status} ({size} байт)",
    "http_status_for": "HTTP {status} для {url}",
    # --- AES-128 (спецификация 6.3) ---------------------------------------
    "aes_key_size": "Ключ имеет размер {size} байт, ожидалось {expected}",
    "aes_key_must_be": "Ключ должен быть {size} байт",
    "aes_iv_must_be": "IV должен быть {size} байт",
    "aes_data_not_aligned": "Данные сегмента не кратны размеру блока AES",
    "aes_bad_padding": "Некорректное дополнение PKCS#7",
    # --- FFmpeg (спецификация 6.4, 7.3) ------------------------------------
    "ffmpeg_not_found": (
        "FFmpeg не найден. Положите ffmpeg.exe в папку bin рядом с программой "
        "или добавьте его в PATH"
    ),
    "ffmpeg_no_output": "нет вывода",
    "ffmpeg_exit_log": "FFmpeg код {code}: {tail}",
    "ffmpeg_failed": "FFmpeg завершился с кодом {code}: {tail}",
    "ffmpeg_done_output": "FFmpeg готов, вывод: {lines} строк",
    "ffmpeg_direct_mp4": "прямой MP4",
    "ffmpeg_direct_mp3": "прямой MP3",
    # --- байтовые диапазоны (спецификация 5.1) ---------------------------
    "range_bad_byterange": "Некорректный BYTERANGE: {value!r}",
    "range_no_offset": "BYTERANGE без offset и без предыдущего диапазона в том же файле",
    "range_bad_length": "Длина BYTERANGE должна быть положительной: {value!r}",
}
