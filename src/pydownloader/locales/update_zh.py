"""zh texts of the update group: the keys come from update_en.py.

The errors of the GitHub Releases check (spec 8.3 p.6), the SHA-256 asset and
the download of the installer (spec 8.3 p.3.1-3.2). The dialog texts are in
the ui group (``ui_zh.py``).
"""

TEXTS: dict[str, str] = {
    # 发布 API 的应答 (spec 8.3 p.6)
    "up_release_list_failed": "未能获取发布列表: {error}",
    "up_rate_limited": "GitHub API: 请求数已达限制 (IP 限制)",
    "up_api_http": "GitHub API: HTTP {status}",
    # 发布版的 .sha256 文件 (spec 8.3 p.3.2)
    "up_sha_file_failed": "未能获取 SHA-256 文件: {error}",
    "up_sha_http": "SHA-256: HTTP {status}",
    # 下载安装程序 (spec 8.3 p.3.1)
    "up_installer_http": "下载安装程序: HTTP {status}",
    "up_installer_failed": "下载安装程序: {error}",
    "up_installer_cancelled": "下载安装程序: 已取消",
    "up_installer_incomplete": "安装程序未下载完整: {got} / {size} MB",
    "up_installer_start_failed": "未能启动安装程序: {error}",
}
