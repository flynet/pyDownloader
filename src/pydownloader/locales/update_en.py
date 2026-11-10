"""en texts of the update group: the keys come from update_en.py.

The errors of the GitHub Releases check (spec 8.3 p.6): the API answer, the
SHA-256 asset and the download of the installer (spec 8.3 p.3.1-3.2). The
dialog texts of the update live in the ui group (the ``update_*`` keys of
``ui_en.py``), so they are not repeated here. Placeholders are filled by
``tr`` with keyword arguments.
"""

TEXTS: dict[str, str] = {
    # --- the answer of the releases API (spec 8.3 p.6) ---------------------
    "up_release_list_failed": "Releases list is not fetched: {error}",
    "up_rate_limited": "GitHub API: the number of requests is limited (IP limit)",
    "up_api_http": "GitHub API: HTTP {status}",
    # --- the .sha256 asset of the release (spec 8.3 p.3.2) ----------------
    "up_sha_file_failed": "SHA-256 file is not fetched: {error}",
    "up_sha_http": "SHA-256: HTTP {status}",
    # --- downloading the installer (spec 8.3 p.3.1) ------------------------
    "up_installer_http": "Installer download: HTTP {status}",
}
