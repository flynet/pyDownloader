"""fr texts of the update group: the keys come from update_en.py.

The errors of the GitHub Releases check (spec 8.3 p.6), the SHA-256 asset and
the download of the installer (spec 8.3 p.3.1-3.2). The dialog texts are in
the ui group (``ui_fr.py``).
"""

TEXTS: dict[str, str] = {
    # --- la réponse de l'API des versions (spec 8.3 p.6) ------------------
    "up_release_list_failed": "La liste des versions n'est pas récupérée : {error}",
    "up_rate_limited": "GitHub API : le nombre de requêtes est limité (limite par IP)",
    "up_api_http": "GitHub API : HTTP {status}",
    # --- le fichier .sha256 de la version (spec 8.3 p.3.2) ---------------
    "up_sha_file_failed": "Le fichier SHA-256 n'est pas récupéré : {error}",
    "up_sha_http": "SHA-256 : HTTP {status}",
    # --- téléchargement de l'installeur (spec 8.3 p.3.1) -----------------
    "up_installer_http": "Téléchargement de l'installeur : HTTP {status}",
}
