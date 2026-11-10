"""ru texts of the browser group: the keys come from browser_en.py."""

TEXTS: dict[str, str] = {
    # --- запускается браузер (spec 5, 6.4) ---------------------------------
    "browser_started": "Браузер: {browser}, профиль {profile}, расширение {extension}",
    "browser_started_line": "Браузер запущен: {browser}",
    "browser_closed_by_user": "Браузер закрыт пользователем",
    "browser_page": "Страница: {url} — {title}",
    "browser_page_unavailable": "Страница недоступна: {error}",
    "browser_no_browser": (
        "Не найдены Chrome и Edge, Chromium от Playwright не установлен. "
        "Установите Chrome или Edge, либо разрешите скачать Chromium."
    ),
    "browser_codec_warning": (
        "Chromium от Playwright может не проигрывать H.264/AAC на части сайтов: "
        "лучше использовать установленный Chrome или Edge"
    ),
    "browser_none": "нет",
    "browser_placeholder": "-",
    "browser_cookies": "Cookies для {url}: {count}",
    "browser_response": "Ответ {status} {type} {length} байт {url}",
    "browser_family": "Семейство сегментов: {url} ({count} файлов)",
    "browser_hls_group": "Найдена HLS-группа сегментов ({count} файлов): {url}",
    "browser_youtube_error": "YouTube: {error}",
    "browser_youtube_reason": "YouTube: {reason}",
    "browser_youtube_updated": "YouTube: поток обновлён — {title}",
    "browser_youtube_found": "Найден YouTube ({quality}): {title}",
    "browser_quality_none": "неизвестно",
    "browser_manifest_request": "Запрос манифеста {url} (cookies: {cookies})",
    "browser_manifest_failed": "Манифест не получен: {url} ({error})",
    "browser_failed": "Браузер: {error}",
    # --- скачивание Chromium (spec 6.4) ------------------------------------
    "chromium_installed": "Chromium установлен",
    "chromium_not_installed": "Chromium не установлен (код {code}): {tail}",
    "chromium_no_output": "нет вывода",
    # --- блокировщик рекламы (spec 6.4) ------------------------------------
    "ext_unpacked": "Расширение распаковано: {path}",
    "ext_not_crx": "файл не является расширением Chromium (.crx)",
    "ext_bad_header": "повреждённый заголовок CRX",
    "ext_no_manifest": "в архиве нет manifest.json",
    "ext_bad_zip": "расширение повреждено: ZIP-архив не читается",
    "ext_dir_unreadable": "Не удалось прочитать папку программы {path}: {error}",
    "ext_not_loaded": "Расширение {path} не загружено: {error}",
    "ext_unknown_version": "неизвестная версия CRX: {value}",
    "ext_bad_path": "недопустимый путь в архиве: {path}",
    "ext_connected": "Блокировщик рекламы подключён",
    "ext_not_connected": "Блокировщик рекламы не подключён",
    # --- данные программы и профиль (spec 7.2) ----------------------------
    "profile_moved": "Профиль браузера перенесён: {src} -> {dst}",
    "profile_data_dir_writable": (
        "Папка программы {dir} недоступна для записи, данные остаются в {fallback}"
    ),
    "profile_dir_taken": "Путь профиля занят файлом: {path}",
    "profile_dir_writable": (
        "Папка программы {dir} недоступна для записи, профиль остаётся в {fallback}"
    ),
    "profile_move_failed": "Не удалось перенести профиль {src} в {dst}: {error}",
    # --- FFmpeg (spec 6.5) -------------------------------------------------
    "ffmpeg_not_found": (
        "FFmpeg не найден. Положите ffmpeg.exe в папку bin рядом с программой "
        "или добавьте его в PATH"
    ),
    "ffmpeg_ready": "FFmpeg готов, вывод: {lines} строк",
    "ffmpeg_code": "FFmpeg код {code}: {output}",
    "ffmpeg_exit_code": "FFmpeg завершился с кодом {code}",
    "ffmpeg_no_output": "нет вывода",
    "ffmpeg_direct_mp4": "прямой MP4",
}
