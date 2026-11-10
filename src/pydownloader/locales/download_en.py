"""English texts of the download group: the queue, the engine, HTTP, AES, FFmpeg.

Keys of the worker queue and the plan of a task (spec 6.2), the segment engine
and AES-128 (spec 6.2, 6.3), the ``GET`` requests (spec 6.1), FFmpeg
(spec 6.4, 7.3) and the byte ranges (spec 5.1). Placeholders are filled by
``tr`` with keyword arguments.
"""

TEXTS: dict[str, str] = {
    # --- plan of a task (spec 6.2) -----------------------------------------
    "dl_source_not_parsed": "Source is not parsed: {url}",
    "dl_family_playlist_not_parsed": "Segment family playlist is not parsed: {error}",
    "dl_live_skipped": "Live stream: skipped",
    "dl_drm_detected": "{message} ({system})",
    "dl_manifest_not_fetched": "Manifest is not fetched: {url}",
    "dl_manifest_not_parsed": "Manifest is not parsed: {error}",
    "dl_manifest_fetch_failed": "Manifest is not fetched: {url} ({error})",
    "dl_manifest_recorded_url": "Manifest from the recorded URL: {url}",
    "dl_nested_master": "Nested master {url}: descending to {target}",
    "dl_nested_master_deep": "Manifest is not parsed: nested master playlist",
    "dl_no_variants": "The master playlist has no variants",
    "dl_no_video_track": "The manifest has no video",
    "dl_audio_not_fetched": "Audio track is not fetched: {url}",
    "dl_variant_fallback": "Variant {height}p is not available, downloading {fallback}p: {url}",
    "dl_variant_fallback_short": "Variant {height}p is not available, downloading {fallback}p",
    # --- queue of tasks (spec 6.2) -----------------------------------------
    "dl_task_queued": "Task {id} added to the queue: {url}",
    "dl_cancel_task": "Cancelling task {id}",
    "dl_queue_started": "Queue started, waiting for tasks",
    "dl_queue_stopped": "Queue stopped",
    "dl_task_start": "Task {id}: {title} ({kind}, {name})",
    "dl_task_ready": "Task {id} is ready: {path}",
    "dl_task_cancelled": "Task cancelled",
    "dl_task_cancelled_log": "Task {id} cancelled",
    "dl_task_failed": "Task {id} failed: {error}",
    "dl_task_error": "Task error {title}: {error}",
    "dl_task_crashed": "Task {id} crashed unexpectedly",
    "dl_cancelled_title": "Cancelled: {title}",
    "dl_cancelled": "cancelled",
    "dl_nothing_to_download": "Nothing to download",
    "dl_plan_of_task": "Plan of task {id}: {count} files, streams: {streams}",
    # --- signed URLs of the browser (spec 6.1, 6.2) ------------------------
    "dl_recorded_url_failed": "The recorded URL did not work ({error}): {url}",
    "dl_recorded_segment_failed": "Segment from the recorded URL is not fetched ({error}): {url}",
    "dl_try_recorded_playlist": "Trying the recorded playlist of the same folder: {url}",
    "dl_recorded_playlist_failed": "The recorded playlist did not work ({error}): {url}",
    "dl_waiting_recorded_url": "Waiting for the recorded URL ({seconds:.0f} s): {url}",
    # --- engine of segments (spec 6.2) --------------------------------------
    "dl_segments_incomplete": "Not all segments are downloaded",
    "dl_segment_not_downloaded": "Segment is not downloaded",
    "dl_segment_attempt_failed": "Segment not downloaded (attempt {attempt}): {url} ({error})",
    "dl_segment_failed_after": "Segment not downloaded after {attempts} attempts: {url} ({error})",
    "dl_segment_key_missing": "Segment is encrypted, no key is given: {url}",
    # --- HTTP (spec 6.1) ---------------------------------------------------
    "http_net_error": "Network error: {error}",
    "http_net_error_log": "GET {url}: network error {error}",
    "http_get_chars": "GET {url} -> {status} ({chars} chars)",
    "http_get_bytes": "GET {url} -> {status} ({size} bytes)",
    "http_status_for": "HTTP {status} for {url}",
    # --- AES-128 (spec 6.3) ------------------------------------------------
    "aes_key_size": "The key is {size} bytes, expected {expected}",
    "aes_key_must_be": "The key must be {size} bytes",
    "aes_iv_must_be": "The IV must be {size} bytes",
    "aes_data_not_aligned": "Segment data is not a multiple of the AES block size",
    "aes_bad_padding": "Broken PKCS#7 padding",
    # --- FFmpeg (spec 6.4, 7.3) --------------------------------------------
    "ffmpeg_not_found": (
        "FFmpeg is not found. Put ffmpeg.exe in the bin folder next to the program, "
        "or add it to PATH"
    ),
    "ffmpeg_no_output": "no output",
    "ffmpeg_exit_log": "FFmpeg code {code}: {tail}",
    "ffmpeg_failed": "FFmpeg exited with code {code}: {tail}",
    "ffmpeg_done_output": "FFmpeg finished, output: {lines} lines",
    "ffmpeg_direct_mp4": "direct MP4",
    # --- byte ranges (spec 5.1) --------------------------------------------
    "range_bad_byterange": "Invalid BYTERANGE: {value!r}",
    "range_no_offset": "BYTERANGE without an offset and without a previous range in the same file",
    "range_bad_length": "The BYTERANGE length must be positive: {value!r}",
}
