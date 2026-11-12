"""ru texts of the update group: the keys come from update_en.py.

The errors of the GitHub Releases check (spec 8.3 p.6), the SHA-256 asset and
the download of the installer (spec 8.3 p.3.1-3.2). The dialog texts are in
the ui group (``ui_ru.py``).
"""

TEXTS: dict[str, str] = {
    # --- ответ API релизов (спецификация 8.3 p.6) -------------------------
    "up_release_list_failed": "Не получен список релизов: {error}",
    "up_rate_limited": "GitHub API: ограничено число запросов (лимит на IP)",
    "up_api_http": "GitHub API: HTTP {status}",
    # --- файл .sha256 релиза (спецификация 8.3 p.3.2) --------------------
    "up_sha_file_failed": "Не получен файл SHA-256: {error}",
    "up_sha_http": "SHA-256: HTTP {status}",
    # --- скачивание установщика (спецификация 8.3 p.3.1) -----------------
    "up_installer_http": "Скачивание установщика: HTTP {status}",
    "up_installer_failed": "Скачивание установщика: {error}",
    "up_installer_cancelled": "Скачивание установщика: отменено",
    "up_installer_incomplete": "Установщик скачан не целиком: {got} из {size} МБ",
    "up_installer_start_failed": "Установщик не запущен: {error}",
}
