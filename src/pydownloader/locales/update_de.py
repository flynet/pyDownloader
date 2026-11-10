"""de texts of the update group: the keys come from update_en.py.

The errors of the GitHub Releases check (spec 8.3 p.6), the SHA-256 asset and
the download of the installer (spec 8.3 p.3.1-3.2). The dialog texts are in
the ui group (``ui_de.py``).
"""

TEXTS: dict[str, str] = {
    # --- die Antwort der Releases-API (spec 8.3 p.6) ----------------------
    "up_release_list_failed": "Die Release-Liste ist nicht abgerufen: {error}",
    "up_rate_limited": "GitHub-API: die Zahl der Anfragen ist begrenzt (IP-Limit)",
    "up_api_http": "GitHub-API: HTTP {status}",
    # --- die .sha256-Datei der Release (spec 8.3 p.3.2) ------------------
    "up_sha_file_failed": "Die SHA-256-Datei ist nicht abgerufen: {error}",
    "up_sha_http": "SHA-256: HTTP {status}",
    # --- Download des Installers (spec 8.3 p.3.1) -------------------------
    "up_installer_http": "Installer-Download: HTTP {status}",
}
