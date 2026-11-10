"""zh texts of the download group: the keys come from download_en.py.

The queue, the engine, HTTP, AES-128, FFmpeg and the byte ranges
(spec 6.1-6.4, 7.3).
"""

TEXTS: dict[str, str] = {
    # 任务计划 (spec 6.2)
    "dl_source_not_parsed": "来源未解析: {url}",
    "dl_family_playlist_not_parsed": "片段组播放列表解析失败: {error}",
    "dl_live_skipped": "直播流: 已跳过",
    "dl_drm_detected": "{message} ({system})",
    "dl_manifest_not_fetched": "未能获取清单: {url}",
    "dl_manifest_not_parsed": "清单解析失败: {error}",
    "dl_manifest_fetch_failed": "未能获取清单: {url} ({error})",
    "dl_manifest_recorded_url": "来自已记录 URL 的清单: {url}",
    "dl_nested_master": "嵌套主播放列表 {url}: 转向 {target}",
    "dl_nested_master_deep": "清单解析失败: 嵌套主播放列表",
    "dl_no_variants": "主播放列表中没有版本",
    "dl_no_video_track": "清单中没有视频",
    "dl_audio_not_fetched": "未能获取音轨: {url}",
    "dl_variant_fallback": "{height}p 版本不可用, 正在下载 {fallback}p: {url}",
    "dl_variant_fallback_short": "{height}p 版本不可用, 正在下载 {fallback}p",
    # 任务队列 (spec 6.2)
    "dl_task_queued": "任务 {id} 已加入队列: {url}",
    "dl_cancel_task": "正在取消任务 {id}",
    "dl_queue_started": "队列已启动, 等待任务",
    "dl_queue_stopped": "队列已停止",
    "dl_task_start": "任务 {id}: {title} ({kind}, {name})",
    "dl_task_ready": "任务 {id} 已完成: {path}",
    "dl_task_cancelled": "任务已取消",
    "dl_task_cancelled_log": "任务 {id} 已取消",
    "dl_task_failed": "任务 {id} 失败: {error}",
    "dl_task_error": "任务错误 {title}: {error}",
    "dl_task_crashed": "任务 {id} 意外崩溃",
    "dl_cancelled_title": "已取消: {title}",
    "dl_cancelled": "已取消",
    "dl_nothing_to_download": "没有可下载的内容",
    "dl_plan_of_task": "任务 {id} 的计划: {count} 个文件, 流: {streams}",
    # 浏览器记录的签名 URL (spec 6.1, 6.2)
    "dl_recorded_url_failed": "已记录的 URL 未生效 ({error}): {url}",
    "dl_recorded_segment_failed": "已记录 URL 的片段未能获取 ({error}): {url}",
    "dl_try_recorded_playlist": "尝试同一目录中已记录的播放列表: {url}",
    "dl_recorded_playlist_failed": "已记录的播放列表未生效 ({error}): {url}",
    "dl_waiting_recorded_url": "等待已记录的 URL ({seconds:.0f} 秒): {url}",
    # 片段引擎 (spec 6.2)
    "dl_segments_incomplete": "并非所有片段都已下载",
    "dl_segment_not_downloaded": "片段未下载",
    "dl_segment_attempt_failed": "片段未下载 (第 {attempt} 次尝试): {url} ({error})",
    "dl_segment_failed_after": "经过 {attempts} 次尝试后片段仍未下载: {url} ({error})",
    "dl_segment_key_missing": "片段已加密, 未提供密钥: {url}",
    # HTTP (spec 6.1)
    "http_net_error": "网络错误: {error}",
    "http_net_error_log": "GET {url}: 网络错误 {error}",
    "http_get_chars": "GET {url} -> {status} ({chars} 字符)",
    "http_get_bytes": "GET {url} -> {status} ({size} 字节)",
    "http_status_for": "{url} 返回 HTTP {status}",
    # AES-128 (spec 6.3)
    "aes_key_size": "密钥长度为 {size} 字节, 应为 {expected}",
    "aes_key_must_be": "密钥必须为 {size} 字节",
    "aes_iv_must_be": "IV 必须为 {size} 字节",
    "aes_data_not_aligned": "片段数据不是 AES 块大小的整数倍",
    "aes_bad_padding": "PKCS#7 填充不正确",
    # FFmpeg (spec 6.4, 7.3)
    "ffmpeg_not_found": "未找到 FFmpeg。请将 ffmpeg.exe 放在程序旁的 bin 文件夹, 或将其加入 PATH",
    "ffmpeg_no_output": "无输出",
    "ffmpeg_exit_log": "FFmpeg 代码 {code}: {tail}",
    "ffmpeg_failed": "FFmpeg 以代码 {code} 退出: {tail}",
    "ffmpeg_done_output": "FFmpeg 完成, 输出 {lines} 行",
    "ffmpeg_direct_mp4": "直接 MP4",
    "ffmpeg_direct_mp3": "直接 MP3",
    # 字节范围 (spec 5.1)
    "range_bad_byterange": "BYTERANGE 无效: {value!r}",
    "range_no_offset": "BYTERANGE 没有偏移, 且同一文件中没有前一个范围",
    "range_bad_length": "BYTERANGE 长度必须为正数: {value!r}",
}
