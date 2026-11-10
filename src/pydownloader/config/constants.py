"""Constants of the project: the GitHub repository used for updates."""

from __future__ import annotations

OWNER = "flynet"
REPO = "pyDownloader"

APP_NAME = "PyDownloader"
APP_ID = "{DD959C2D-4F33-43F3-A35D-3082096EF251}"

GITHUB_API_ROOT = "https://api.github.com"


def releases_latest_url(owner: str = OWNER, repo: str = REPO) -> str:
    """``GET`` endpoint of the latest published release."""
    return f"{GITHUB_API_ROOT}/repos/{owner}/{repo}/releases/latest"
