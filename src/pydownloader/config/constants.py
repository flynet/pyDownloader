"""Constants of the project: the GitHub repository used for updates."""

from __future__ import annotations

OWNER = "flynet"
REPO = "pyDownloader"

APP_NAME = "PyDownloader"
APP_ID = "{DD959C2D-4F33-43F3-A35D-3082096EF251}"

GITHUB_API_ROOT = "https://api.github.com"
#: The pages of the repository, the address a person opens in the browser.
GITHUB_WEB_ROOT = "https://github.com"


def releases_latest_url(owner: str = OWNER, repo: str = REPO) -> str:
    """``GET`` endpoint of the latest published release."""
    return f"{GITHUB_API_ROOT}/repos/{owner}/{repo}/releases/latest"


def issues_url(owner: str = OWNER, repo: str = REPO) -> str:
    """The page of the problems of the program, where a person reports one (spec 4.3, 8.3)."""
    return f"{GITHUB_WEB_ROOT}/{owner}/{repo}/issues"
