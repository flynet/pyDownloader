# Changelog

The format is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning is [SemVer](https://semver.org/). A release is a `vX.Y.Z` tag
on `main`.

## [Unreleased]

## [0.4.3] - 2026-11-11

### Added
- The console panel is collapsible: **«Hide console»** in the row under the list of
  cards takes the panel away and gives the whole window to the list of found videos
  (the panel was half the window, which is the room a person picking a video needs),
  **«Show console»** brings it back with the room it had. The row of buttons stays on
  the screen, so the panel is opened back with the same button and from the tray menu
  (the menu has the item «Show console» as well). The state is stored in the settings
  and there is a row in the settings dialog, so the window opens the way the user
  left it.
- The tray icon shows the state of the queue: a **green arrow** with a jumping
  animation (the frames of a `QTimer`: the arrow flips between the down and the up
  drawing, which reads as the icon moving up and down in the notification area) while
  a download runs, a **blue arrow** when the queue is empty.
- When the last download of the queue is finished, the icon goes back to blue, a
  Windows balloon appears next to it ("All downloads are finished: N saved") and the
  system notification sound is played (`winsound`, async; a platform without it plays
  nothing).

### Changed
- The balloon that explains the tray is shown at startup (the first run with the
  tray on), not only when the window is hidden: the tray is where the window is
  brought back and where the program is quit. "X" in the title bar still hides the
  window to the tray, the downloads keep running, and "Exit" in the tray menu is
  the only way to quit.

### Tests
- The console panel (hidden state, splitter sizes, settings round-trip, the text of
  the button), the tray menu with the console item, the colour of the tray icon and
  the frames of the animation, and the balloon + sound of the finished downloads are
  covered.

### Changed
- The browser is not launched when the program starts: the program opens its own
  window only, and the browser window appears when the user presses «Open
  browser». The console says it at startup, in the language of the interface.

### Fixed
- The banners a driver provokes are hidden in the browser window. Chrome for
  Testing (the Chromium Playwright ships) wrote "this build is for automated
  testing" with a proposal to install a regular Chrome, and Chrome and Edge
  wrote "you are using an unsupported command-line flag:
  --disable-blink-features=AutomationControlled" under the address bar.
  `--disable-infobars` stays in the Playwright defaults (the Chrome of Testing
  is the only one that reads it) and `--test-type` is added to the launch
  (the switch the installed Chrome and Edge read), so neither strip is shown.

### Tests
- The flags that hide the banners are checked, and the startup path is checked
  to leave the browser closed.

## [0.4.1] - 2026-11-11

### Fixed
- MP3 of an audio source (SoundCloud and other audio-only HLS): the AAC
  bitstream filter `-bsf:a aac_adtstoasc` is no longer applied to the MP3
  stream. The filter converts the ADTS header of a stream that is *copied* into
  MP4, and FFmpeg applies it to the stream of the output file, so the MP3
  encode ended with "Codec 'mp3' is not supported by the bitstream filter",
  exit code `-22` and an empty output file. The MP3 path is its own method now:
  the merged stream is decoded with `libmp3lame` at the bitrate of the settings,
  the input format of the merged stream is told from the extensions of the
  segments (`mp4` for `.m4s`/`.m4a`, `mpegts` for `.ts`), and a direct `.mp3`
  download is copied without re-encode.
- An audio-only source has no video files, and `all()` of an empty list is true:
  the empty video list was read as MPEG-TS, which is what added the filter to
  the audio task. An empty list is no longer TS, and the format of the stream
  comes from the segments that are merged.
- The console window of the child processes is hidden: `CREATE_NO_WINDOW` is the
  flag `0x08000000` in every run, not `0`. The FFmpeg probe runs on every
  request a page makes, so on a page that plays many audio files the program
  flashed a console window for each of them, and the same happened to the
  Chromium installer and to the update commands.
- The command of a failed FFmpeg run is written to `app.log`, so an
  "Invalid argument" report shows the input format that did not fit the stream.
- Tests: the MP3 commands and the hidden console flag are checked, and a new
  integration file runs the real FFmpeg binary on an audio-only HLS of
  fragmented MP4 and of MPEG-TS segments, and the result is a playable MP3 with
  audio and no video. The file is skipped when no FFmpeg binary is available.

## [0.4.0] - 2026-11-11

### Added
- «Open browser» and «Close browser» in the top panel and in the tray menu: the
  browser window is no longer tied to the program. Closing it stops the sniffer
  thread and the running downloads continue; «Open browser» starts the same
  browser on the page the user was on last, so the profile, the cookies and the
  login are read back from disk and the page can be played again.
- The program lives in the Windows notification area: closing the window with «X»
  hides it to the tray, the downloads keep running, and «Exit» in the tray menu
  is the only way to quit. The menu shows the window, opens and closes the
  browser, checks for an update and opens the download folder; a double click on
  the icon shows the window, and the first minimize shows a balloon that explains
  the tray. The tray and the «X» behaviour are settings, and a platform without a
  notification area (Windows Server, the offscreen CI) runs without the icon.
- Anti-bot stealth of the launched browser (spec 7.2): the flags Playwright adds
  for a driver are dropped (`--disable-extensions`, `--disable-sync`,
  `--metrics-recording-only`, `--force-color-profile=srgb`, ...), the sandbox
  flag is taken out, `--disable-blink-features=AutomationControlled` is added so
  `navigator.webdriver` is not true, and an init script fixes the markers a
  detector reads on its first check: `navigator.webdriver`, the list of
  languages, `navigator.plugins`, `hardwareConcurrency`, `deviceMemory`,
  `window.chrome`, the notification permission and the brands of
  `navigator.userAgentData`. The bundled Chromium sends the Chrome user agent of
  the same major version, and the locale of the browser is the language of the
  interface, so `Accept-Language` matches the user's machine. Stealth is a
  setting; the launch flags, the user agent, `navigator.webdriver` and the
  extensions of the page are written to `app.log`, so a report of
  "JavaScript is disabled" can be analysed after a user test.
- Settings: the browser to launch is chosen (Auto = Chrome → Edge → Chromium,
  Chrome, Edge, Chromium of Playwright), a browser that is not installed falls
  back to the Auto order, so a choice cannot stop the program; the Chromium of
  Playwright is the only browser that loads the bundled ad blocker, and the
  blocker can be switched off. A User agent field imitates another device, an
  empty field takes the Chrome string of the version that is launched.
- Audio sources are saved as `.mp3` (spec 5.2 p.4): a source is recognised as
  audio by the content type (`audio/mpeg`, `audio/aac`, ...), by the extension
  of the URL (`.mp3`, `.ogg`, `.flac`, ...), by the `CODECS` list of an HLS
  master with no `RESOLUTION`, by the FFmpeg probe of a playlist that sees an
  audio stream without a video stream, and by a DASH manifest of audio
  representations only. The card shows an MP3 badge, the console line names the
  source as sound, the file is written as `.mp3`: a direct MP3 is copied, a
  stream of segments is re-encoded with `libmp3lame` at the bitrate chosen in
  the settings (128, 192, 320 kbit/s, 192 is the default). The mode
  «Audio only (MP3)» hides video sources, so a music site gives only the sound.
- Settings: the quality is a dropdown of the three presets of the spec,
  1080p / 720p / 480p, the match is exact; a resolution saved in an edited
  `settings.json` gets its own entry, so saving the dialog does not change the
  value the user had.
- The interface and the log lines are localized in Ukrainian (spec 4.3): the
  language is chosen in Settings → Language as «Українська», the texts of the
  cards, the console, the tray, the settings dialog, the update dialog and the
  log messages follow the choice, the browser gets the `uk-UA` locale for
  `Accept-Language`, and a key missing in one language falls back to English.

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
