"""Settings, paths and project constants."""

from pydownloader.config.constants import APP_ID, APP_NAME, OWNER, REPO, releases_latest_url
from pydownloader.config.paths import Paths, default_paths, task_tmp_dir
from pydownloader.config.settings import Settings, load_settings, save_settings

__all__ = [
    "APP_ID",
    "APP_NAME",
    "OWNER",
    "REPO",
    "Paths",
    "Settings",
    "default_paths",
    "load_settings",
    "releases_latest_url",
    "save_settings",
    "task_tmp_dir",
]
