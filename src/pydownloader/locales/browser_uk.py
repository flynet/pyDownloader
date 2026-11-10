"""uk texts of the browser group: the keys come from browser_en.py."""

TEXTS: dict[str, str] = {
    # --- запускається браузер (spec 5, 6.4) ---------------------------------
    "browser_started": "Браузер: {browser}, профіль {profile}, розширення {extension}",
    "browser_started_line": "Браузер запущено: {browser}",
    "browser_launch_args": "Прапорці браузера: {args}",
    "browser_stealth": "Прихованість {stealth}, локаль {locale}, юзер-агент {ua}",
    "browser_on": "увімкнено",
    "browser_off": "вимкнено",
    "browser_auto_ua": "авто",
    "browser_page_state": "Стан сторінки: UA {ua}, webdriver {driver}, мови {languages}",
    "browser_state_failed": "Не можу прочитати стан сторінки: {error}",
    "browser_ext_state": "Розширення браузера: {state}",
    "browser_closed_by_user": "Браузер закрито користувачем",
    "browser_page": "Сторінка: {url} — {title}",
    "browser_page_unavailable": "Сторінка недоступна: {error}",
    "browser_no_browser": (
        "Не знайдено Chrome і Edge, Chromium від Playwright не встановлено. "
        "Встановіть Chrome або Edge, або дозвольте качати Chromium."
    ),
    "browser_codec_warning": (
        "Chromium від Playwright може не програвати H.264/AAC на частині сайтів, "
        "краще використати встановлені Chrome або Edge"
    ),
    "browser_none": "немає",
    "browser_placeholder": "-",
    "browser_cookies": "Cookies для {url}: {count}",
    "browser_response": "Відповідь {status} {type} {length} байт {url}",
    "browser_family": "Сімейство сегментів: {url} ({count} файлів)",
    "browser_hls_group": "Знайдено HLS-групу сегментів ({count} файлів): {url}",
    "browser_youtube_error": "YouTube: {error}",
    "browser_youtube_reason": "YouTube: {reason}",
    "browser_youtube_updated": "YouTube: потік оновлено — {title}",
    "browser_youtube_found": "Знайдено YouTube ({quality}): {title}",
    "browser_quality_none": "невідомо",
    "browser_manifest_request": "Запит манифесту {url} (cookies: {cookies})",
    "browser_manifest_failed": "Манифест не отримано: {url} ({error})",
    "browser_failed": "Браузер: {error}",
    # --- качування Chromium (spec 6.4) ------------------------------------
    "chromium_installed": "Chromium встановлено",
    "chromium_not_installed": "Chromium не встановлено (код {code}): {tail}",
    "chromium_no_output": "немає виводу",
    # --- блодувач реклами (spec 6.4) ---------------------------------------
    "ext_unpacked": "Розширення розпаковано: {path}",
    "ext_not_crx": "файл не є розширенням Chromium (.crx)",
    "ext_bad_header": "пошкоджений заголовок CRX",
    "ext_no_manifest": "архів не має manifest.json",
    "ext_bad_zip": "розширення пошкоджено: ZIP-архів не читається",
    "ext_dir_unreadable": "Не можу прочитати теку програми {path}: {error}",
    "ext_not_loaded": "Розширення {path} не завантажено: {error}",
    "ext_unknown_version": "невідомий номер CRX: {value}",
    "ext_bad_path": "невірний шлях в архіві: {path}",
    "ext_connected": "Блодувач реклами під'єднано",
    "ext_not_connected": "Блодувач реклами не під'єднано",
    # --- дані програми та профіль (spec 7.2) -----------------------------
    "profile_moved": "Профіль браузера переміщено: {src} -> {dst}",
    "profile_data_dir_writable": (
        "Тека програми {dir} не доступна для запису, дані залишаються у {fallback}"
    ),
    "profile_dir_taken": "Шлях профілю зайнятий файлом: {path}",
    "profile_dir_writable": (
        "Тека програми {dir} не доступна для запису, профіль залишається у {fallback}"
    ),
    "profile_move_failed": "Не можу перемістити профіль {src} у {dst}: {error}",
    # --- FFmpeg (spec 6.5) -------------------------------------------------
    "ffmpeg_not_found": (
        "FFmpeg не знайдено. Покладіть ffmpeg.exe в теку bin поруч із програмою, "
        "або додайте його до PATH"
    ),
    "ffmpeg_ready": "FFmpeg готовий, вивід: {lines} рядків",
    "ffmpeg_code": "FFmpeg код {code}: {output}",
    "ffmpeg_exit_code": "FFmpeg завершився з кодом {code}",
    "ffmpeg_no_output": "немає виводу",
    "ffmpeg_direct_mp4": "прямий MP4",
}
