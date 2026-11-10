"""en texts of the manifest group: the keys come from manifest_en.py.

Keys of the classifier, the registry and the quality filter (spec 5.1/5.2),
the console lines of the pipeline, the HLS and DASH parsers (spec 5.1) and
the YouTube source. Placeholders are filled by ``tr`` with keyword arguments.
"""

TEXTS: dict[str, str] = {
    # --- classification and registry (spec 5.1) -----------------------------
    "mf_reason_fragment": "fragment of an already found manifest",
    "mf_reason_playlist": "playlist of an already found stream",
    "mf_reason_small_file": "file below the threshold, not a video",
    "mf_reason_with_url": "{reason}: {url}",
    "mf_range_merged": "Already found, Range request merged: {url}",
    "mf_found_already": "Already found: {url}",
    "mf_url_recorded": "Recorded URL {key} -> {url}",
    "mf_playlist_owned": "Playlist {url} belongs to the stream already found {owner}",
    "mf_new_manifest": "New manifest {kind}: {url}",
    "mf_segment_before_manifest": "Segment before the manifest ({dir}): {url}",
    # --- quality filter (spec 5.2 p.3) --------------------------------------
    "mf_quality_unknown": "unknown",
    "mf_quality_mp3": "MP3",
    "mf_quality_no_audio": "Found a stream without an audio track: skipped",
    "mf_quality_video_skipped": "Video stream: skipped (audio only mode)",
    "mf_quality_no_heights": "Found a stream without {target}p: skipped (resolution is unknown)",
    "mf_quality_available": "Found a stream without {target}p: skipped (available: {listed})",
    "mf_quality_debug": "Quality does not fit ({url}): {message}",
    # --- pipeline console lines (spec 5.2) ----------------------------------
    "mf_manifest_captured": "Manifest taken from the intercepted response: {url}",
    "mf_manifest_not_fetched": "Manifest is not fetched: {url}",
    "mf_manifest_not_parsed": "Manifest is not parsed: {error}",
    "mf_parse_failed_debug": "Manifest is not parsed ({url}): {error}",
    "mf_live_skipped": "Live stream: skipped ({url})",
    "mf_drm_message": "Content is protected by DRM, downloading is not possible",
    "mf_drm_detected": "{message} ({system})",
    "mf_found_mp4": "Found MP4 {quality}: {url}",
    "mf_found_audio": "Found audio: {url}",
    "mf_found_dash": "Found DASH stream {height}p: {url}",
    "mf_found_hls_unknown": "Found HLS stream (resolution unknown): {url}",
    "mf_found_hls": "Found HLS stream {height}p: {url}",
    "mf_found_hls_deferred": "Found HLS stream {height}p: {url} (variant fetched on download)",
    "mf_variant_not_fetched": "Variant {height}p is not fetched, requested on download: {url}",
    "mf_variant_not_parsed_debug": "Variant is not parsed ({url}): {error}",
    "mf_nested_master_debug": "Variant {url} is a nested master playlist",
    "mf_master_debug": "Master {url}: chosen {height}p, variant {variant} (recorded: {recorded})",
    "mf_yes": "yes",
    "mf_no": "no",
    # --- HLS and DASH parsers (spec 5.1) ------------------------------------
    "mf_empty_response": "Empty manifest response",
    "hls_unclosed_quote": "Unclosed quote in the attributes: {text!r}",
    "hls_no_extm3u": "No #EXTM3U marker - this is not an HLS playlist",
    "dash_parse_failed": "MPD is not parsed: {error}",
    "dash_root_not_mpd": "The root element is not MPD",
    "dash_timeline_no_time": "SegmentTimeline without @t and without a previous value",
    # --- YouTube source -----------------------------------------------------
    "yt_reason_login_required": "YouTube requires signing in",
    "yt_reason_unplayable": "video is not playable",
    "yt_reason_error": "YouTube playback error",
    "yt_reason_empty": "empty player response",
    "yt_reason_malformed": "cannot parse the player response",
    "yt_reason_parse_error": "cannot parse the player response",
    "yt_reason_status": "YouTube: {status}",
    "yt_plan_error": "YouTube: {reason}",
    "yt_plan_live": "Live stream: skipped",
    "yt_plan_no_video": "YouTube: no video format is available",
}
