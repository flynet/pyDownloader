"""zh texts of the manifest group: the keys come from manifest_en.py.

The classifier, the registry and the quality filter (spec 5.1/5.2), the
console lines of the pipeline, the HLS and DASH parsers (spec 5.1) and
the YouTube source.
"""

TEXTS: dict[str, str] = {
    # 分类与登记 (spec 5.1)
    "mf_reason_fragment": "已找到清单的片段",
    "mf_reason_playlist": "已找到流的播放列表",
    "mf_reason_small_file": "文件小于阈值, 不是视频",
    "mf_reason_with_url": "{reason}: {url}",
    "mf_range_merged": "已找到, Range 请求已合并: {url}",
    "mf_found_already": "已找到: {url}",
    "mf_url_recorded": "已记录 URL {key} -> {url}",
    "mf_playlist_owned": "播放列表 {url} 属于已找到的流 {owner}",
    "mf_new_manifest": "新清单 {kind}: {url}",
    "mf_segment_before_manifest": "清单之前的片段 ({dir}): {url}",
    # 质量过滤 (spec 5.2 p.3)
    "mf_quality_unknown": "未知",
    "mf_quality_mp3": "MP3",
    "mf_quality_no_audio": "找到没有音频轨的流: 跳过",
    "mf_quality_video_skipped": "视频流: 跳过 (仅音频模式)",
    "mf_quality_no_heights": "找到没有 {target}p 的流: 已跳过 (无法确定分辨率)",
    "mf_quality_available": "找到没有 {target}p 的流: 已跳过 (可用: {listed})",
    "mf_quality_debug": "质量不符合 ({url}): {message}",
    # 检测流程的控制台消息 (spec 5.2)
    "mf_manifest_captured": "清单取自拦截的响应: {url}",
    "mf_manifest_not_fetched": "未能获取清单: {url}",
    "mf_manifest_not_parsed": "清单解析失败: {error}",
    "mf_parse_failed_debug": "清单解析失败 ({url}): {error}",
    "mf_live_skipped": "直播流: 已跳过 ({url})",
    "mf_drm_message": "内容受 DRM 保护, 无法下载",
    "mf_drm_detected": "{message} ({system})",
    "mf_found_mp4": "找到 MP4 {quality}: {url}",
    "mf_found_audio": "找到音频: {url}",
    "mf_found_dash": "找到 DASH 流 {height}p: {url}",
    "mf_found_hls_unknown": "找到 HLS 流 (分辨率未知): {url}",
    "mf_found_hls": "找到 HLS 流 {height}p: {url}",
    "mf_found_hls_deferred": "找到 HLS 流 {height}p: {url} (变体将在下载时请求)",
    "mf_variant_not_fetched": "变体 {height}p 未获取, 将在下载时请求: {url}",
    "mf_variant_not_parsed_debug": "变体解析失败 ({url}): {error}",
    "mf_nested_master_debug": "变体 {url} 是嵌套的主播放列表",
    "mf_master_debug": "主播放列表 {url}: 选择 {height}p, 变体 {variant} (已记录: {recorded})",
    "mf_yes": "是",
    "mf_no": "否",
    # HLS 与 DASH 解析器 (spec 5.1)
    "mf_empty_response": "清单响应为空",
    "hls_unclosed_quote": "属性中未闭合的引号: {text!r}",
    "hls_no_extm3u": "没有 #EXTM3U 标记 - 这不是 HLS 播放列表",
    "dash_parse_failed": "MPD 解析失败: {error}",
    "dash_root_not_mpd": "根元素不是 MPD",
    "dash_timeline_no_time": "SegmentTimeline 没有 @t, 也没有前一个值",
    # YouTube 来源
    "yt_reason_login_required": "YouTube 需要登录账号",
    "yt_reason_unplayable": "视频无法播放",
    "yt_reason_error": "YouTube 播放错误",
    "yt_reason_empty": "播放器响应为空",
    "yt_reason_malformed": "无法解析播放器响应",
    "yt_reason_parse_error": "无法解析播放器响应",
    "yt_reason_status": "YouTube: {status}",
    "yt_plan_error": "YouTube: {reason}",
    "yt_plan_live": "直播流: 已跳过",
    "yt_plan_no_video": "YouTube: 没有可用的视频格式",
}
