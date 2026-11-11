# Technical Specification (version 5): PyDownloader in Python with a modern UI, an Inno Setup 6 installer and updates via GitHub Releases

This is a revision of version 4 (Java). The application's functionality stays the
same (sections 5 and 6 are carried over unchanged in meaning); the stack,
interface, packaging, installation and update flow change.

---

## 1. Goal

A Windows application in Python that is installed into the system through an
installer (Inno Setup 6), has a modern interface and can check for new versions
on GitHub Releases on its own.

How the program works:

1. The user launches the program and picks the downloads folder.
2. The main window of two sections opens: found videos (top) and console
   (bottom). **The browser is not launched at startup** — the user opens it with
   the "Open browser" button. "Hide console" gives the whole window to the list
   of cards, "Show console" brings the panel back.
3. The user visits the site and starts the video.
4. The application intercepts the browser's network requests and finds HLS
   (`.m3u8`), MPEG-DASH (`.mpd`), direct MP4 and audio-only sources (SoundCloud,
   radio).
5. What is found appears as a row in the top section. Downloading starts
   **only after pressing "Download"** on a specific video.
6. Segments are downloaded into a temporary folder and joined by FFmpeg into
   one `.mp4`. A source that contains sound only is written as `.mp3`.
7. Closing the window with "X" hides it to the Windows tray: the downloads keep
   running and the browser stays open; "Exit" in the tray menu is the only way to
   quit, and the tray icon shows the state of the queue.

The principle: the browser already receives and decrypts (AES-128) the stream, so
the program does the same with the same URLs and keys. DRM (Widevine / PlayReady /
FairPlay) is not supported: such videos are skipped.

---

## 2. Technology stack

| Component | Solution |
|---|---|
| Language | Python 3.12 (64-bit), dependency manager `uv` or `pip` + `requirements.txt`, project config `pyproject.toml` |
| Interface | **PySide6 (Qt 6)** with a modern dark and light theme (following the system), rounded cards, a single QSS style. Allowed alternative: `PySide6-Fluent-Widgets`, if the agent finds it reliable. No Tkinter |
| Network interception | **Playwright for Python** (`playwright`), interception at `context` level (`request` / `response`) to see all tabs and popups |
| Browser | Order of attempts: `channel="chrome"` → `channel="msedge"` → Chromium from Playwright; the order is a setting (Automatic / Chrome / Edge / Chromium). Headed mode, maximised, real user agent, stealth flags, persistent context with a profile in `<install folder>\profile` (the first option by default) |
| HTTP | `httpx` (with HTTP/2 support and streaming downloads) |
| Encryption | `cryptography` (AES-128-CBC for HLS) |
| HLS | Custom parser (the `m3u8` library is allowed if it covers EXT-X-MAP, BYTERANGE, KEY) |
| DASH | `xml.etree.ElementTree` or `lxml` |
| FFmpeg | The `ffmpeg.exe` binary goes **inside the installed application** (`{app}\bin\ffmpeg.exe`). Source: the `imageio-ffmpeg` package (the binary is taken at build time) or a static build (gyan.dev / BtbN), the choice is up to the agent. `NOTICE` states the build license. Launched via `subprocess` with no console window (`CREATE_NO_WINDOW`) |
| Logs | standard `logging`: file `<install folder>\logs\app.log` (`%LOCALAPPDATA%\PyDownloader\logs\app.log` if the install folder is not writable; rotation) and a `QtLogHandler` that writes records into the window console |
| Tests | `pytest`, `pytest-qt` for basic GUI checks |
| Code quality | `ruff`, `mypy` (soft mode), `pre-commit` |
| Packaging | **PyInstaller** in `--onedir` mode (not `--onefile`: faster startup, fewer antivirus false positives), `--windowed`, `.ico` icon, version metadata |
| Installer | **Inno Setup 6** (`installer/pydownloader.iss`), built via `ISCC.exe` |
| Versioning | SemVer, Git tags like `v1.2.3`, releases on GitHub Releases (section 8) |

---

## 3. Work scenario

1. Program startup. The downloads-folder picker dialog (native Qt `QFileDialog`,
   the last used folder by default). Cancelling terminates the program.
2. The main window opens. **The browser is not launched by the program**: the
   user opens it with the "Open browser" button when he wants to look for a
   video. `.tmp\<task id>\` is created in the chosen folder for segments.
   Finished files lie in the root of the chosen folder.
3. The user opens the browser, visits the site and starts the video.
   `NetworkSniffer` analyzes the traffic (it runs in the browser thread, so it
   sees the requests only while the browser is open). Sources that pass the
   filters (section 5) appear as cards in the top section.
4. The user presses "Download" on the needed card. The task is queued, progress
   is shown inside that card.
5. Downloads are **strictly sequential** (one worker). If "Download" was pressed
   for several videos, they run one after another.
6. After the join, the task's temporary folder is deleted and the card moves to
   the "Done" state. On error, temporary files are kept, the reason is written
   to the log and the console.
7. Closing the window with "X" hides it to the tray (the downloads keep running,
   the browser stays open); "Exit" in the tray menu is the way to quit. If a
   download is running, "Exit" asks for confirmation, cancels the download,
   closes the browser and terminates the program. If the user closed the browser
   window, the console writes a message and the current download continues to the
   end (the program downloads the segments itself, not through the browser).
8. "Open browser" shows the browser window on the page where the user was last;
   "Close browser" closes it.

---

## 4. Interface (PySide6, one window of two sections)

The window is split into two parts by a `QSplitter` (vertical, about 40% top and
60% bottom by default, the splitter moves). Style: modern, with margins, rounded
corners, an accent color, dark and light themes per the system settings. Minimum
window size 900×600, size and position are remembered.

### 4.1. Top section: found videos

- At startup the list is empty. A gray hint in the middle: "No videos found yet.
  Open a site in the browser and start the video".
- When a suitable source is detected, a card (`SourceCard`) is added. The list is
  scrollable (`QScrollArea`), new cards are added at the bottom. The card section
  has a minimum height, so cards are never squeezed: when the window is small the
  console shrinks first.
- Each card contains:
  - a type badge (HLS / DASH / MP4 / YOUTUBE / **MP3** for an audio source);
  - a title (the page title on which the source was found);
  - a link (truncated by width, full in a tooltip, context menu "Copy link");
  - the quality preset (1080p / 720p / 480p), resolution and duration, or size,
    if known;
  - a **"Download"** button on the right.
- Card states:
  - **Found**: active "Download" button.
  - **Queued**: button disabled, caption "Queued".
  - **Downloading**: instead of the button, a progress bar with speed,
    percentage, "segments X of Y", stage (downloading / decrypting / joining)
    and a "Cancel" button.
  - **Done**: caption "Done" and an "Open file" button (plays the downloaded
    video in the default player).
  - **Error**: red caption and a "Retry" button, details in the console.
- Pressing "Download" only queues the task.
- In the section header there are five buttons:
  - **"Open browser"** — shows the browser window, maximised, on the page where
    the user was last (starts the browser if it is not open). The program does
    not open the browser on its own: the window is opened by this button;
  - **"Close browser"** — closes the browser window. An active download is not
    cancelled and continues in the background.
  - **"Clear all"** — removes all cards;
  - **"Clear downloaded"** — removes only the cards whose files are already
    downloaded and lie on disk;
  - **"Settings"** — the settings dialog.
  An active download is not cancelled when clearing and continues in the
  background.
- Under the list of cards there is the row of the console panel: **"Show
  console"** / **"Hide console"** (the label changes with the state), **"Clear"**
  (the text of the console), **"Open downloads folder"**, **"Open log file"**.
  The row stays on the screen when the console is hidden, so pressing "Show
  console" brings the panel back; the same command is in the tray menu.
- There is no separate shared progress bar between the sections: progress lives
  inside the card.

### 4.2. Bottom section: console

- Read-only `QPlainTextEdit`, monospace font, color highlighting of levels
  (INFO / WARNING / ERROR).
- Autoscroll down (disabled when the user scrolls up, re-enabled when scrolling
  to the end).
- Buffer limited to ~5000 lines (`setMaximumBlockCount`).
- The whole log goes here: browser launch, the stealth settings, found manifests
  (live, DRM, no preset of the chosen quality), segments, retries, FFmpeg
  calls, update checks, errors.
- Line format: `[12:34:56] INFO  Found HLS stream 1080p: https://...`
- Above the console, small buttons: "Show console" / "Hide console", "Clear",
  "Open downloads folder", "Open log file".
- **"Hide console"** takes the panel away and gives the whole window to the list
  of cards; **"Show console"** brings it back with the room it had. The state is
  stored in the settings, so the window opens the way the user left it, and the
  row of buttons is the way to open the panel from the tray menu.

### 4.3. Extras

- Status bar at the bottom of the window: application version, current downloads
  folder, update icon and status (section 8).
- Gear button "Settings" (a dialog): downloads folder, number of threads for
  segments (default 6), **quality (1080p / 720p / 480p)**, **MP3 bitrate
  (128 / 192 / 320 kbps)**, **Audio only (MP3)** mode, minimum MP4 size,
  **browser (Automatic / Chrome / Edge / Chromium)**, **anti-bot**, ad blocker,
  **language** (English, Русский, Українська, 中文, Français, Deutsch; English
  by default, applied after a restart), tray icon and hide-to-tray rows, the
  console panel row ("Show the console panel below the list"), automatic update
  checks
  (enabled by default), theme (system / light / dark). The dialog takes 80% of
  the main window's width and height and can be resized; a long folder path is
  fully visible (and in the tooltip on hover).
- **Tray (Windows notification area).** Pressing "X" hides the window to the tray
  and the downloads keep running; "Exit" in the tray menu is the only way to
  quit (it asks for confirmation when a download is running). The tray menu: show
  the window, open browser, close browser, show the console, check for updates,
  open downloads folder, exit. A single click or a double click on the icon shows
  the window, the browser items of the menu follow the state of the browser
  window; the first time the window is hidden a balloon hint explains the menu
  (shown once, the flag is stored).
- **The icon shows the state of the queue:** a **green arrow** with a jumping
  animation (the frames of a timer) while a download is running, a **blue
  arrow** when the queue is empty. When the last download is finished, a Windows
  balloon appears next to the icon ("All downloads are finished: N saved") and
  the system notification sound is played — this is the report for the user who
  works with the window hidden.
- If the system has no notification area (Windows Server, RDP, the offscreen CI
  of the tests), the tray icon is not created: "X" closes the program as before,
  the sound is not played, and the finished downloads are reported in the window
  console only.
- Window title: "PyDownloader `<version>` — `<downloads folder>`".

### 4.4. Threads and responsiveness

- Playwright runs in **its own thread** with its own event loop. Request and
  response handlers only put events into a queue and return quickly.
- Downloading and FFmpeg run in a separate worker (`QThread` or
  `ThreadPoolExecutor` with one worker for the queue, plus a thread pool for
  segments).
- Data reaches the GUI only through Qt signals (`Signal` / `Slot`). Direct
  widget calls from foreign threads are forbidden.

---

## 5. Source detection and filtering

### 5.1. Candidates

**HLS / DASH.** A request is a candidate if:
- the URL contains `.m3u8` or `.mpd`, **or**
- Content-Type is one of: `application/vnd.apple.mpegurl`,
  `application/x-mpegURL`, `audio/mpegurl`, `application/dash+xml`.

The response body is read and parsed.

**Direct MP4.** Content-Type `video/mp4` or the URL ends with `.mp4` (before
the query).
- Browsers often request such files in chunks via `Range`, so requests with the
  same normalized URL are merged into one entry.
- The full size is taken from `Content-Range` (`bytes 0-1/12345678`) or
  `Content-Length`.
- Files smaller than ~1 MB (configurable) are discarded as not video.
- Fragments of fMP4 segments (`.m4s`, `.mp4` belonging to an already found
  HLS/DASH manifest) do not get into the list.

**Audio.** Audio-only sources are separated from video: Content-Type
(`audio/mpeg`, `audio/mp3`, `audio/mp4`, `audio/aac`, `audio/x-m4a`,
`audio/ogg`, `audio/opus`, `audio/flac`, `audio/wav`, `audio/x-wav`,
`audio/x-aiff`), the URL extension (`.mp3`, `.ogg`, `.opus`, `.flac`, `.wav`,
`.aac`), an HLS master whose `CODECS` list is audio only (`mp4a`/`aac`, `ac-3`,
`ec-3`, `opus`, `mp3`, `flac`, `alac`) with no `RESOLUTION`, a DASH manifest with
an audio track and no video representation, and the FFmpeg probe of an
`.m3u8`/`.mpd`/file that has audio and no video. An audio source is shown as a
card with an `MP3` badge and is saved as `.mp3`; audio is never muxed into a
black video file.

### 5.2. Filters (in order of application)

1. **Live.** HLS without `#EXT-X-ENDLIST` and DASH with `type="dynamic"` are
   skipped, the reason goes to the log.
2. **DRM.** Skipped if:
   - `#EXT-X-KEY` with a method other than `NONE` and `AES-128` (SAMPLE-AES
     and the like);
   - the MPD has `ContentProtection` with Widevine, PlayReady or FairPlay.

   Console message: "Content is DRM-protected, downloading is impossible".
3. **Quality presets: 1080p / 720p / 480p.** The preset is a setting (1080 by
   default).
   - For a master playlist and an MPD, the source is shown only if there is a
     variant with the preset height, **exactly** (a 1440p source is taken as
     1080p, a 1080p source is never taken for the 720p preset). Among the
     variants of the preset height the one with the maximum bandwidth is picked,
     plus the best audio track.
   - If there is no variant of the preset, the source is not shown and the
     console writes: "Found a stream without 1080p: skipped (available: 720p,
     480p)".
   - A media playlist without variants is shown if its resolution matches the
     preset or cannot be determined (the card shows "unknown").
   - A playlist that is audio only passes without a preset.
   - For direct MP4 the resolution is determined via `ffprobe`/`ffmpeg -i`
     (with headers when possible). On failure the card shows "unknown" and the
     file stays in the list.
   - "Audio only (MP3)" mode takes only the audio part and writes `.mp3`; it
     does not require a video preset.
4. **Duplicates.** By normalized URL (without query tokens when they obviously
   change, otherwise by the full URL).

---

## 6. Downloading

### 6.1. General
- **Headers.** For manifests, segments and keys: `Referer`, `Origin`,
  `User-Agent` from the intercepted request and `Cookie` from
  `context.cookies(url)`.
- **URLs.** Relative paths are resolved against the manifest URL
  (`urllib.parse.urljoin`). Query parameters (tokens, signatures) are
  preserved.
- **Parallelism inside one download:** up to 6 threads for segments
  (setting).
- **Retries:** 3 attempts with exponential backoff. Already downloaded segments
  are skipped on retry (resumable download).
- **File name:** `<page title>.mp4` for video, `<page title>.mp3` for an audio
  source. Forbidden Windows characters are replaced, the length is truncated
  (with the path limit in mind). On a name conflict the suffix ` (1)`, ` (2)`
  and so on is added.
- **Cancellation:** pressing "Cancel" interrupts the download, active HTTP
  requests and the FFmpeg process are stopped, the task's temporary files are
  deleted.

### 6.2. HLS
- Master and media playlists.
- `#EXT-X-MAP` (the fMP4 init segment) is downloaded first.
- `#EXT-X-BYTERANGE`.
- `#EXT-X-MEDIA` (a separate audio track is downloaded and muxed; subtitles
  are optional).
- **AES-128** (`#EXT-X-KEY:METHOD=AES-128`): download the key, decrypt segments
  with `cryptography` (AES-CBC, PKCS7). The IV comes from the `IV` attribute
  or is computed from the media sequence number of the segment.

### 6.3. DASH
- `SegmentTemplate` (`$Number$`, `$Time$`, `$RepresentationID$`,
  `$Bandwidth$`), `SegmentTimeline`, `SegmentList`, `SegmentBase`, `BaseURL`,
  several Periods.
- The best Representation is chosen for video and audio (video under the
  preset condition). A manifest with audio and no video representation is an
  audio source and is written as `.mp3`.
- The init segment + segments are joined in order, then video and audio are
  muxed with FFmpeg.

### 6.4. Direct MP4
- Single-threaded download. With `Accept-Ranges` support, resume from the
  break point.
- No join needed: after completion the `.part` file is renamed to the final
  name.

### 6.5. Joining (FFmpeg)
- No re-encoding: `-c copy`.
- Video and audio as separate tracks via `-map`.
- `-bsf:a aac_adtstoasc` when needed.
- **Audio-only task:** `-vn -c:a libmp3lame -b:a <bitrate>k -f mp3` (the
  bitrate is a setting: 128 / 192 / 320). A direct `.mp3` download is renamed,
  not re-encoded.
- The method (concat list of local files or a local m3u8) is up to the agent,
  the main thing is that it works reliably.
- FFmpeg output is parsed for progress (the "joining" stage) and written to
  the log.

---

## 7. Installation and packaging

### 7.1. Application build (PyInstaller)
- `--onedir` mode, `--windowed`, icon `assets/app.ico`.
- Included in the build: PySide6, the Playwright driver
  (`collect_all("playwright")`, `node.exe` inside it), `ffmpeg.exe` (in
  `bin\`), resources (icons, QSS).
- Build script `build.ps1` (or `build.py`): cleanup, PyInstaller build,
  generation of the version file from the Git tag, call of `ISCC.exe`.

### 7.2. Playwright browser (fallback)
- Main path: an installed Chrome or Edge, nothing to download; the engine is a
  setting (Automatic / Chrome / Edge / Chromium), Chromium is downloaded when
  the ad blocker is wanted or Chromium is chosen.
- If neither exists, on first run the program offers to download Chromium (a
  consent dialog), runs the Playwright driver installation with
  `PLAYWRIGHT_BROWSERS_PATH=<install folder>\browsers`
  (`%LOCALAPPDATA%\PyDownloader\browsers` when the install folder is not
  writable) and shows progress in the console. Chromium is not bundled into
  the installer to avoid bloat. Chromium from a previous version lying in
  `%LOCALAPPDATA%\PyDownloader\browsers` is reused: it is not downloaded again.
- Warning in the console: Chromium from Playwright may not play H.264/AAC on
  some sites.

### 7.3. Inno Setup 6 installer (`installer/pydownloader.iss`)
- A constant `AppId` (GUID) is set once and never changes between versions, so
  that the update installs over the existing installation.
- `AppVersion` and the output file name come from the `/DAppVersion=...`
  parameter that `ISCC` receives from the build script. Output file name:
  `PyDownloader-Setup-<version>.exe`.
- Default install to `{autopf}\PyDownloader`. Mode
  `PrivilegesRequiredOverridesAllowed=dialog` (the user can choose a
  per-user install without administrator rights, or for all users).
- Files: contents of the PyInstaller folder `dist\PyDownloader\*` with
  `recursesubdirs`.
- Shortcuts: Start menu and an optional desktop shortcut (`desktopicon` task).
- Uninstaller: removes the application cleanly together with the data in the
  install folder (`profile`, `browsers`, `extensions`, `logs`); user data
  (`%APPDATA%`, `%LOCALAPPDATA%`) is deleted only if the user confirmed
  removal in the dialog.
- Modern wizard look: `WizardStyle=modern`, custom `WizardImageFile` and
  `WizardSmallImageFile`, Russian and English localizations (`Languages`).
- Running-application check: `CloseApplications=yes`,
  `RestartApplications=no`, so the installer closes the program correctly on
  update.
- Silent keys for auto-update: `/SILENT` or `/VERYSILENT`,
  `/SUPPRESSMSGBOXES`, `/CLOSEAPPLICATIONS`. After installation, the "Run
  PyDownloader" option.
- Code signing (`signtool`) is foreseen as an optional step in the build
  script (to reduce SmartScreen warnings); the installer must also build
  without signing.

### 7.4. Data layout
- Everything the program creates lives in the install folder: `{app}\profile`
  (browser profile), `{app}\browsers` (Chromium), `{app}\extensions` (the
  unpacked blocker), `{app}\logs` (logs). Deleting the install folder deletes
  this data too.
- Settings: `%APPDATA%\PyDownloader\settings.json` — survive a reinstall.
- When the install folder is not writable (`Program Files` without
  administrator rights), all the folders listed above are created in
  `%LOCALAPPDATA%\PyDownloader`.
- Chromium, downloaded by a previous version into
  `%LOCALAPPDATA%\PyDownloader\browsers`, is found and reused: no re-download.

### 7.5. Anti-bot (sites that block automation)

Google, SoundCloud and similar sites answer "JavaScript disabled / cookies
blocked" when they see an automation tool. The requirements:
- the browser must look like a normal user's browser: a real user agent taken
  from the installed browser (`chrome.exe --version`), matching platform and
  locale hints (`en-US`, `ru-RU`, `uk-UA` from the interface language), no
  `navigator.webdriver` (the `AutomationControlled` Blink feature is disabled
  and the Playwright automation switches are dropped), a stealth init script
  that fixes the usual automation leaks (`navigator.plugins`, the languages,
  `hardwareConcurrency`, `deviceMemory`, `window.chrome`, the notification
  permission, the brands of `navigator.userAgentData`), a normal maximised
  window, autoplay allowed;
- the banners a driver provokes are hidden: Chrome for Testing (the Chromium
  Playwright ships) prints "this build is for automated testing" with a proposal
  to install a regular Chrome, and Chrome, Edge and that same build print "you
  are using an unsupported command-line flag" under the address bar. The launch
  keeps `--disable-infobars` in the defaults (only the build of Testing answers
  to it) and adds `--test-type` (the switch the installed Chrome and Edge
  answer to), so the browser window shows no strip a person never sees;
- the browser is a full browser with a **persistent profile** (`{app}\profile`)
  that stores cookies, local storage, logins, extensions and site settings; the
  profile is fully saved when the program exits and is used again on the next
  start, so a Google login stays valid between runs;
- "Anti-bot" is a setting (on by default); the log records the launch
  arguments, the user agent, the locale, the stealth script result, the
  extension state and the profile path.
- out of scope: a full anti-detection suite (CDP isolation, a patched browser,
  fingerprint tools); a site that checks the DevTools protocol can still see
  the automation.

---

## 8. Versions, Git and updates via GitHub Releases

### 8.1. Versioning
- SemVer format (`MAJOR.MINOR.PATCH`), Git tags like `v1.2.3`.
- The single source of version in the code: `src/pydownloader/_version.py`. The
  file **is generated at build time** from the tag (`git describe --tags`),
  the development default is `0.0.0-dev`.
- The version is shown in the window title, the status bar, the `.exe`
  properties (PyInstaller version resource) and the installer.
- `CHANGELOG.md` follows the Keep a Changelog format, release notes are taken
  from it.

### 8.2. Release build (GitHub Actions)
- Workflow `.github/workflows/release.yml` runs on push of a `v*` tag on
  `windows-latest`.
- Steps: checkout (with tags) → Python 3.12 → install dependencies →
  `pytest` → PyInstaller build → `ISCC.exe` (Inno Setup 6 is available on the
  runner, if absent it is installed via `choco install innosetup`) → compute
  the installer's SHA-256 → publish the release with attached files:
  - `PyDownloader-Setup-<version>.exe`;
  - `PyDownloader-Setup-<version>.exe.sha256`.
- A separate workflow `ci.yml` on every push and pull request: `ruff`, `mypy`,
  `pytest`.
- Branches: `main` (stable), work via feature branches and pull requests. A
  release is a tag on `main`.

### 8.3. Update check and install inside the application
- At startup (in the background, not blocking the window) and via the "Check
  for updates" button in settings, the application requests
  `GET https://api.github.com/repos/<OWNER>/<REPO>/releases/latest`. The owner
  and the repository name are a constant in `config.py`.
- The release version (`tag_name`) is compared with the current one by SemVer
  (`packaging.version`). Prereleases (`prerelease: true`) and drafts are
  ignored.
- If there is a new version, a message appears in the status bar and the
  console, plus a dialog: version, release notes from `body`, buttons
  "Update", "Later", "Skip this version".
- On consent:
  1. The asset `PyDownloader-Setup-*.exe` is downloaded into a temporary folder
     (progress visible in the dialog).
  2. SHA-256 is checked against the `.sha256` file from the same release. On
     a mismatch the install is cancelled with an error message.
  3. If a video download is running, the user is asked to wait for it to
     finish.
  4. The installer is launched with the keys `/SILENT /CLOSEAPPLICATIONS` (as
     a separate process) and the current program terminates. After
     installation the user starts the application himself or via the
     installer's option.
- GitHub API rate limits: cache the check result (no more often than once every
  few hours), handle network errors and limits gracefully (a warning in the
  console, no pop-up errors).
- An option to disable automatic checks in settings. No network: the
  application works as usual.
- Private repositories are not covered by the spec (a public repository needs
  no token).

---

## 9. Project structure

```
pydownloader/
 ├─ pyproject.toml
 ├─ run.bat                     run the current source (no build)
 ├─ README.md
 ├─ CHANGELOG.md
 ├─ NOTICE                      licenses of third-party components (FFmpeg, Qt, Playwright)
 ├─ build.ps1                   build: PyInstaller + ISCC
 ├─ pydownloader.spec            PyInstaller config
 ├─ installer/
 │   ├─ pydownloader.iss
 │   └─ assets/                 wizard images, icons
 ├─ assets/                     app.ico, tray icon, screenshots
 ├─ tools/                      make_icon.py, make_screenshots.py, list_strings.py,
 │                              make_locales.py
 ├─ docs/                       TZ_HLS_Grabber_Python.md
 ├─ .github/workflows/
 │   ├─ ci.yml
 │   └─ release.yml
 ├─ src/pydownloader/
 │   ├─ __main__.py             entry point
 │   ├─ _version.py             generated at build time
 │   ├─ i18n.py                 language literal, SUPPORTED_LANGUAGES, tr()
 │   ├─ locales/                per-language catalogs (en, ru, uk, zh, fr, de)
 │   ├─ ui/                     app.py, main_window.py, card.py, console.py,
 │   │                          settings_panel.py, theme.py, tray.py
 │   ├─ browser/                launcher.py, sniffer.py, stealth.py, extensions.py,
 │   │                          events.py, chromium_installer.py
 │   ├─ manifest/               detector.py, drm.py, quality.py, pipeline.py,
 │   │                          registry.py
 │   ├─ hls/                    parser.py, models.py
 │   ├─ dash/                   parser.py, models.py, segments.py
 │   ├─ youtube/                api.py, player.py, downloader.py
 │   ├─ download/               plan.py, engine.py, http.py, runner.py, worker.py,
 │   │                          aes.py
 │   ├─ ffmpeg/                 mux.py, probe.py, locate.py
 │   ├─ update/                 checker.py, ui.py
 │   ├─ config/                 settings.py, paths.py, constants.py
 │   └─ util/                   urls.py, filenames.py, ranges.py, logging_setup.py
 └─ tests/
     ├─ test_hls_parser.py, test_dash_parser.py, test_drm.py, test_quality.py,
     ├─ test_pipeline.py, test_mp4_ranges.py, test_filenames.py, test_ffmpeg.py,
     ├─ test_stealth.py, test_i18n.py, test_settings.py, test_runner.py,
     ├─ test_worker.py, test_ui.py, test_tray.py, test_main_window.py,
     ├─ test_update_checker.py, test_updater.py, test_chromium_installer.py
     └─ data/                   sample playlists, MPDs, ffprobe output
```

---

## 10. Out of scope (do not do)

- Bypassing DRM and any content protections.
- Live streams.
- Automatic login, captcha and subscription bypass (the user does everything
  manually in the browser).
- A web interface.
- Parallel downloads of several videos (sequential queue only).
- macOS and Linux support (Windows 10/11 x64 only).
- Private repositories and token-based updates.

---

## 11. Acceptance criteria

**Application**
- After startup and the folder picker, the window opens: the top section is
  empty with a hint, the bottom section shows the console, and no browser is
  launched — the browser appears only after the user presses "Open browser".
- On opened test HLS, DASH and direct MP4, the source automatically appears as
  a card with a title, a link and a "Download" button.
- Downloading starts only after pressing the button. The card shows progress.
  The result is a playable `.mp4`.
- Live, DRM and streams without a preset of the chosen quality (1080p / 720p /
  480p) are skipped with a clear entry in the console.
- Several pressed "Download"s run strictly one after another. "Cancel"
  correctly stops the download and cleans up temporary files.
- "Open browser" shows the browser on the page where the user was last,
  "Close browser" closes it; an active download is not interrupted by closing
  the browser window.
- The browser window has no strip a person never sees: no "this build is for
  automated testing" with a proposal to install a regular Chrome, no "you are
  using an unsupported command-line flag", and no console window flashes on the
  desktop while a page is sniffed.
- "X" hides the window to the tray and the download keeps running; the program
  exits only through the tray menu ("Exit"), where the window, the browser, the
  console panel, the update check and the downloads folder are also available.
- While a download runs, the tray icon is a green arrow with the jumping
  animation; when the queue is empty it is a blue arrow, and the finished
  downloads are reported by a Windows balloon and the notification sound.
- "Show console" / "Hide console" take the console panel away and back; hidden,
  the list of cards fills the window, and the state is remembered for the next
  start.
- An audio source (SoundCloud, an audio-only playlist) is recognized, shown with
  an `MP3` badge, and saved as `.mp3` at the chosen bitrate; audio is never
  muxed into a black video file.
- Google and SoundCloud open the browser as a normal user's browser: no
  "JavaScript disabled / cookies blocked" message, and a Google login stays
  logged in after the program restarts (the profile is kept in the program's
  folder).
- The interface renders correctly in the light and dark themes and at Windows
  scaling 125% and 150%, in English, Russian, Ukrainian, Chinese, French and
  German.

**Installation and updates**
- `build.ps1` on a clean machine with Python 3.12 and Inno Setup 6 builds
  `PyDownloader-Setup-<version>.exe`.
- The installer installs the application onto a clean Windows 10/11 without
  Python, creates shortcuts, the program launches and works (FFmpeg is found
  in `{app}\bin`).
- Running the installer of a newer version again updates the installation in
  place (same `AppId`), settings are preserved.
- Removal via "Apps & features" removes the application, user data is deleted
  only with consent.
- Pushing a `vX.Y.Z` tag triggers GitHub Actions and publishes a release with
  the installer and the `.sha256` file.
- An old-version application detects the new release, shows the release notes,
  downloads the installer, verifies SHA-256 and runs the update.
- With no network and on GitHub API errors the application keeps working, a
  warning goes to the console.

**Tests (`pytest`)**
- HLS: master, media, AES-128, fMP4 (`EXT-X-MAP`), byterange, relative URLs.
- DASH: SegmentTemplate, SegmentTimeline, BaseURL.
- DrmDetector, QualityFilter.
- Merging MP4 Range requests.
- Name sanitization and name conflicts.
- Version comparison and GitHub API response parsing (on mocks), SHA-256
  verification.

---

## 12. Agent workflow

1. Repository skeleton: `pyproject.toml`, package structure, `ruff`,
   `pre-commit`, `ci.yml`.
2. HLS and DASH parsers, `QualityFilter`, `DrmDetector` + tests.
3. `BrowserLauncher` and `NetworkSniffer` (Playwright thread, MP4 detection and
   merging), on-demand Chromium installation.
4. Downloaders, decryption, queue, cancellation.
5. `FfmpegRunner` and locating `ffmpeg.exe` (in development and as installed).
6. PySide6 interface: window, cards, console, theme, settings.
7. Update module (`update/`) and the update dialog.
8. PyInstaller build and the `installer/pydownloader.iss` script, `build.ps1`.
9. Workflow `release.yml`, `CHANGELOG.md`, `README.md`, `NOTICE`.
10. Verification on a clean Windows (install, update from an old version,
    removal).

---

## 13. Accepted assumptions (can be changed)

- Interface on **PySide6**, not CustomTkinter or Flet: it works better with
  threads and gives a modern look, but the installer ends up heavier (about
  100–150 MB).
- The repository is **public**, updates are taken from `releases/latest`
  without a token.
- FFmpeg is included in the installer, Chromium from Playwright is downloaded
  on demand: when Chrome and Edge are absent, when Chromium is chosen in the
  settings, and because the ad blocker works only with Chromium (Chrome and
  Edge 157 ignore extensions passed from the command line).
- Streams without a variant of the chosen preset (1080p / 720p / 480p) are
  hidden from the list (written only to the console); audio-only sources are
  shown without a preset.
- Closing the window hides it to the tray; exit is only from the tray menu. On
  a system without a notification area, "X" closes the program.
- Anti-bot is on by default (stealth flags, real user agent, persistent
  profile). A full anti-detection suite (a CDP leak, a patched browser,
  fingerprint tools) is not covered.
- MP3 is made by re-encoding with `libmp3lame`; a direct `.mp3` download is
  renamed without re-encoding.
- Download progress is shown inside the video card, the downloading card has a
  "Cancel" button.
- The update is applied by running the installer with `/SILENT`, not by
  replacing files on the fly.
- Before starting, the agent must be given the repository's `OWNER/REPO` and
  a GUID for `AppId` must be generated once.
