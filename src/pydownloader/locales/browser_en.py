"""English texts of the browser group: the keys come from browser_en.py.

Keys of the launched browser (spec 5, 6.4), of the ad blocker extension
(spec 6.4), of the program data and of the browser profile (spec 7.2), and of
the FFmpeg search (spec 6.5).
"""

TEXTS: dict[str, str] = {
    # --- launched browser (spec 5, 6.4) -------------------------------------
    "browser_started": "Browser: {browser}, profile {profile}, extension {extension}",
    "browser_started_line": "Browser started: {browser}",
    "browser_closed_by_user": "Browser closed by the user",
    "browser_page": "Page: {url} — {title}",
    "browser_page_unavailable": "Page not available: {error}",
    "browser_no_browser": (
        "Chrome and Edge are not found, Chromium from Playwright is not installed. "
        "Install Chrome or Edge, or allow Chromium to be downloaded."
    ),
    "browser_codec_warning": (
        "Chromium from Playwright may not play H.264/AAC on some sites: "
        "the installed Chrome or Edge is a better choice"
    ),
    "browser_none": "none",
    "browser_placeholder": "-",
    "browser_cookies": "Cookies for {url}: {count}",
    "browser_response": "Response {status} {type} {length} bytes {url}",
    "browser_family": "Segment family: {url} ({count} files)",
    "browser_hls_group": "HLS segment group found ({count} files): {url}",
    "browser_youtube_error": "YouTube: {error}",
    "browser_youtube_reason": "YouTube: {reason}",
    "browser_youtube_updated": "YouTube: stream updated — {title}",
    "browser_youtube_found": "YouTube found ({quality}): {title}",
    "browser_quality_none": "unknown",
    "browser_manifest_request": "Manifest request {url} (cookies: {cookies})",
    "browser_manifest_failed": "Manifest not fetched: {url} ({error})",
    "browser_failed": "Browser: {error}",
    # --- Chromium download (spec 6.4) ---------------------------------------
    "chromium_installed": "Chromium is installed",
    "chromium_not_installed": "Chromium is not installed (code {code}): {tail}",
    "chromium_no_output": "no output",
    # --- ad blocker (spec 6.4) ---------------------------------------------
    "ext_unpacked": "Extension unpacked: {path}",
    "ext_not_crx": "the file is not a Chromium extension (.crx)",
    "ext_bad_header": "damaged CRX header",
    "ext_no_manifest": "the archive has no manifest.json",
    "ext_bad_zip": "the extension is damaged: the ZIP archive cannot be read",
    "ext_dir_unreadable": "Cannot read the program folder {path}: {error}",
    "ext_not_loaded": "Extension {path} is not loaded: {error}",
    "ext_unknown_version": "unknown CRX version: {value}",
    "ext_bad_path": "invalid path in the archive: {path}",
    "ext_connected": "Ad blocker connected",
    "ext_not_connected": "Ad blocker not connected",
    # --- program data and profile (spec 7.2) ------------------------------
    "profile_moved": "Browser profile moved: {src} -> {dst}",
    "profile_data_dir_writable": (
        "The program folder {dir} is not writable, the data stays in {fallback}"
    ),
    "profile_dir_taken": "The profile path is taken by a file: {path}",
    "profile_dir_writable": (
        "The program folder {dir} is not writable, the profile stays in {fallback}"
    ),
    "profile_move_failed": "Cannot move the profile {src} to {dst}: {error}",
    # --- FFmpeg (spec 6.5) -------------------------------------------------
    "ffmpeg_not_found": (
        "FFmpeg is not found. Put ffmpeg.exe in the bin folder next to the program, "
        "or add it to PATH"
    ),
    "ffmpeg_ready": "FFmpeg ready, output: {lines} lines",
    "ffmpeg_code": "FFmpeg code {code}: {output}",
    "ffmpeg_exit_code": "FFmpeg exited with code {code}",
    "ffmpeg_no_output": "no output",
    "ffmpeg_direct_mp4": "direct MP4",
}
