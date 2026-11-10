"""zh texts of the browser group: the keys come from browser_en.py."""

TEXTS: dict[str, str] = {
    # --- 浏览器 (spec 5, 6.4) ---------------------------------------------
    "browser_started": "浏览器: {browser}, 配置文件 {profile}, 扩展程序 {extension}",
    "browser_started_line": "浏览器已启动: {browser}",
    "browser_closed_by_user": "浏览器已由用户关闭",
    "browser_page": "页面: {url} - {title}",
    "browser_page_unavailable": "页面不可用: {error}",
    "browser_no_browser": (
        "未找到 Chrome 和 Edge, Playwright 的 Chromium 未安装。"
        "请安装 Chrome 或 Edge, 或允许下载 Chromium。"
    ),
    "browser_codec_warning": (
        "Playwright 的 Chromium 在部分网站可能无法播放 H.264/AAC: "
        "建议使用已安装的 Chrome 或 Edge"
    ),
    "browser_none": "无",
    "browser_placeholder": "-",
    "browser_cookies": "{url} 的 Cookie: {count}",
    "browser_response": "响应 {status} {type} {length} 字节 {url}",
    "browser_family": "分段族: {url} ({count} 个文件)",
    "browser_hls_group": "找到 HLS 分段组 ({count} 个文件): {url}",
    "browser_youtube_error": "YouTube: {error}",
    "browser_youtube_reason": "YouTube: {reason}",
    "browser_youtube_updated": "YouTube: 流已更新 - {title}",
    "browser_youtube_found": "找到 YouTube ({quality}): {title}",
    "browser_quality_none": "未知",
    "browser_manifest_request": "请求清单 {url} (Cookie: {cookies})",
    "browser_manifest_failed": "清单未获取: {url} ({error})",
    "browser_failed": "浏览器: {error}",
    # --- 下载 Chromium (spec 6.4) ----------------------------------------
    "chromium_installed": "Chromium 已安装",
    "chromium_not_installed": "Chromium 未安装 (代码 {code}): {tail}",
    "chromium_no_output": "无输出",
    # --- 广告拦截器 (spec 6.4) -------------------------------------------
    "ext_unpacked": "扩展程序已解包: {path}",
    "ext_not_crx": "文件不是 Chromium 扩展程序 (.crx)",
    "ext_bad_header": "CRX 文件头已损坏",
    "ext_no_manifest": "压缩包内没有 manifest.json",
    "ext_bad_zip": "扩展程序已损坏: ZIP 压缩包无法读取",
    "ext_dir_unreadable": "无法读取程序文件夹 {path}: {error}",
    "ext_not_loaded": "扩展程序 {path} 未加载: {error}",
    "ext_unknown_version": "未知的 CRX 版本: {value}",
    "ext_bad_path": "压缩包内路径无效: {path}",
    "ext_connected": "广告拦截器已连接",
    "ext_not_connected": "广告拦截器未连接",
    # --- 程序数据与配置文件 (spec 7.2) ------------------------------------
    "profile_moved": "浏览器配置文件已迁移: {src} -> {dst}",
    "profile_data_dir_writable": "程序文件夹 {dir} 不可写入, 数据保留在 {fallback}",
    "profile_dir_taken": "配置文件路径被文件占用: {path}",
    "profile_dir_writable": "程序文件夹 {dir} 不可写入, 配置文件保留在 {fallback}",
    "profile_move_failed": "无法将配置文件 {src} 移动到 {dst}: {error}",
    # --- FFmpeg (spec 6.5) -----------------------------------------------
    "ffmpeg_not_found": (
        "未找到 FFmpeg。请把 ffmpeg.exe 放在程序旁的 bin 文件夹, "
        "或将其加入 PATH"
    ),
    "ffmpeg_ready": "FFmpeg 就绪, 输出 {lines} 行",
    "ffmpeg_code": "FFmpeg 代码 {code}: {output}",
    "ffmpeg_exit_code": "FFmpeg 以代码 {code} 退出",
    "ffmpeg_no_output": "无输出",
    "ffmpeg_direct_mp4": "直接 MP4",
}
