"""uk texts of the update group: the keys come from update_en.py."""

TEXTS: dict[str, str] = {
    # --- відповідь API релізів (spec 8.3 п.6) ---------------------------
    "up_release_list_failed": "Список релізів не отримано: {error}",
    "up_rate_limited": "GitHub API: число запитів обмежено (ліміт IP)",
    "up_api_http": "GitHub API: HTTP {status}",
    # --- актив .sha256 релізу (spec 8.3 п.3.2) -------------------------
    "up_sha_file_failed": "Файл SHA-256 не отримано: {error}",
    "up_sha_http": "SHA-256: HTTP {status}",
    # --- качування установника (spec 8.3 п.3.1) ------------------------
    "up_installer_http": "Завантаження установника: HTTP {status}",
}
