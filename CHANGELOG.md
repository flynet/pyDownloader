# Changelog

The format is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning is [SemVer](https://semver.org/). A release is a `vX.Y.Z` tag
on `main`.

## [Unreleased]

### Fixed
- `build.ps1` writes the `.sha256` file of the installer without a byte-order
  mark, so the file is plain text and hash verification tools read it directly.

## [0.3.0] - 2026-11-10

### Added
- Screenshots of the main window and of the settings dialog: they live in
  `assets/screenshots` and are shown in the README and in the release text. The
  screenshots are rendered by `tools/make_screenshots.py` with demo data (cards,
  console), without a browser and without downloads, so they are reproducible.
- The interface and the log messages are localized (English, Russian, Chinese,
  French, German), English is the default, the language is chosen in Settings and
  is applied after a restart.
- The installer wizard, the README, the changelog and the release notes are
  English only; the program itself switches the language in the settings.

### Fixed
- Cards keep their height in the list: a resizable scroll area resized its widget
  to the viewport, and the layout squeezed the cards to a few pixels, so the
  download button lost its text and the cards below the viewport were unreachable.
  The floors of the card layout and of the button are written into `minimumSize`,
  and the card list gets the floor of its cards, so the scroll area scrolls.

## [0.2.0] - 2026-11-10

### Added
- Dark theme by default; all themes use the Fusion style, so buttons and menus
  are drawn identically on Windows 10/11.
- Exact signed URLs: the registry remembers the URL of every manifest, segment
  and key from the browser traffic, and the downloader prefers them to the ones
  built from the playlist (a CDN that signs every path, e.g. phncdn).
- HLS "family" detection: three segments from one directory without a playlist
  form a card; the download plan is built from the recorded URLs, init first.
- YouTube: the inner-tube player API requested from the page itself (VISIONOS
  client), format selection up to 1080p, video and audio in 8 MB range blocks,
  FFmpeg muxing without re-encoding.
- Relative links inherit the query parameters of the manifest (CDN signatures
  and tokens).
- Diagnostic log (DEBUG, with logger names, rotation 5 MB × 3). Every
  intercepted response, manifest and segment requests with response codes,
  cookies, quality decisions, the selected variant, the task plan, the FFmpeg
  command and errors are written. The window console shows only INFO.
- The "Open log file" item and a line with the log path at startup.
- uBlock ad blocker: `uBlock.crx` lies next to the program, is unpacked into
  `<install folder>\extensions` (cache by hash) and loaded into Chromium from
  Playwright. Chrome and Edge do not accept extensions passed from the command
  line, so when `uBlock.crx` is present the program offers to download Chromium
  and runs exactly it. The file is in the repository, so the installer is built
  with the blocker in GitHub Actions too.
- Everything the program creates lives in the install folder: `profile` (the
  browser profile), `browsers` (Chromium), `extensions` (the unpacked blocker),
  `logs` — deleting the program folder deletes this data too. The settings stay
  in `%APPDATA%` to survive a reinstall. If the install folder is not writable
  (`Program Files` without administrator rights), these folders are created in
  `%LOCALAPPDATA%\PyDownloader`. The path to the profile and to the data is
  written to the log.
- Chromium from a previous version, downloaded into
  `%LOCALAPPDATA%\PyDownloader\browsers`, is found and reused: it is not
  downloaded again.
- The browser profile is stored in the program folder (`<app>\profile`), so
  sessions and cookies survive restarts and updates; the profile of a previous
  version is moved there once.
- The "Open file" button on a finished video card launches the downloaded file
  in the default player; if the file is already gone, the downloads folder
  opens.
- The "Clear all" and "Clear downloaded" buttons above the list of found
  videos: the second removes only the cards whose files lie on disk. Whether a
  download is running or not — it is not cancelled, the file finishes
  downloading.
- The settings dialog takes 80% of the main window's width and height and can
  be resized manually; the long downloads-folder path is fully visible and in
  the tooltip.

### Fixed
- The queue thread no longer exits on an empty queue: it waits for the next
  task (condition variable), so "Download" after launch really downloads.
- The "Download" button no longer shrinks to a few pixels when there are
  several cards: the card height comes from the layout, not from a fixed
  minimum.
- Page and CDN cookies are merged with the cookies intercepted from the
  request, instead of replacing them.
- A playlist in the directory of an already found stream (a second variant,
  an audio track) does not create a second card: its URL is remembered for the
  downloader.
- The manifest is taken from the already intercepted browser response, without
  a repeated request: a CDN that signs every path rejects the second request.
- If a variant from the master playlist is not fetched during discovery, the
  card does not disappear: the downloader requests the variant while
  downloading (the live/DRM/quality checks are done there too).
- The download plan descends into a nested master playlist (phncdn serves a
  separate master per quality).
- If the CDN signs every path and the player never requested the selected
  quality, the best quality whose URL the browser really requested is
  downloaded (the console shows "1080p variant unavailable, downloading 720p")
  instead of an HTTP 410 error.
- A variant playlist in a nested directory (`720P_.../master.m3u8`) counts as
  part of the already found stream and does not create a second card.
- The recorded signed URLs are shared across all lines of the page: downloading
  one card sees the files recorded for another.
- The downloads folder is asked only on the first run: afterwards it is taken
  from `settings.json` (and created if it was deleted). The dialog appears
  again only if the saved path is unavailable.
- A closed browser page stops the sniffer instead of burying the console in
  Playwright errors.

## [0.1.0] - 2026-11-10

### Added
- HLS parser: master/media, `EXT-X-MAP`, `EXT-X-BYTERANGE`, `EXT-X-KEY`
  (AES-128), `EXT-X-MEDIA`, the resolution and bandwidth of variants.
- DASH parser: `BaseURL` chains, several `Period`s, `SegmentTemplate`
  (`$Number$`, `$Time$`, `$RepresentationID$`, `$Bandwidth$`), `SegmentTimeline`,
  `SegmentList`, `SegmentBase`, `ContentProtection`.
- `QualityFilter` (1080p), `DrmDetector` (Widevine/PlayReady/FairPlay/CommonEncryption),
  candidate classification and the source registry (dedup by normalized URL,
  merging of MP4 Range requests, skipping segments of found manifests).
- Repository skeleton: `pyproject.toml`, ruff, mypy, pre-commit, `ci.yml`.
- Traffic interception via Playwright (Chrome → Edge → Chromium), streaming
  manifest parsing, the live → DRM → quality → dedup filter, segment downloads
  (up to 6 threads), AES-128, FFmpeg joining, a strict task queue.
- GUI on PySide6: cards of found sources with progress inside the card,
  console with skip reasons, settings, dark/light/system theme, memory of the
  window size and position.
- Update checks via GitHub Releases: cache, dialog with release notes,
  installer download, SHA-256 check, launch with `/SILENT /CLOSEAPPLICATIONS`.
- Build: `build.ps1` (version from the tag, PyInstaller, FFmpeg in `bin`,
  SHA-256), `pydownloader.spec`, Inno Setup 6 installer
  (`installer/pydownloader.iss`), `release.yml` publishing the installer and
  release notes from the CHANGELOG.

[Unreleased]: https://github.com/flynet/pyDownloader/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/flynet/pyDownloader/releases/tag/v0.3.0
[0.2.0]: https://github.com/flynet/pyDownloader/releases/tag/v0.2.0
[0.1.0]: https://github.com/flynet/pyDownloader/releases/tag/v0.1.0
