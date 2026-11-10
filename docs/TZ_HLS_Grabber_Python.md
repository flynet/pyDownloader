# Technical Specification (version 5): HLS Grabber in Python with a modern UI, an Inno Setup 6 installer and updates via GitHub Releases

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
2. A managed browser and the main window of two sections open: found videos
   (top) and console (bottom).
3. The user visits the site and starts the video.
4. The application intercepts the browser's network requests and finds HLS
   (`.m3u8`), MPEG-DASH (`.mpd`) and direct MP4.
5. What is found appears as a row in the top section. Downloading starts
   **only after pressing "Download"** on a specific video.
6. Segments are downloaded into a temporary folder and joined by FFmpeg into
   one `.mp4`.

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
| Browser | Order of attempts: `channel="chrome"` → `channel="msedge"` → Chromium from Playwright. Headed mode, persistent context with a profile in `<install folder>\profile` or `<downloads folder>\.profile` (choice in settings, the first option by default) |
| HTTP | `httpx` (with HTTP/2 support and streaming downloads) |
| Encryption | `cryptography` (AES-128-CBC for HLS) |
| HLS | Custom parser (the `m3u8` library is allowed if it covers EXT-X-MAP, BYTERANGE, KEY) |
| DASH | `xml.etree.ElementTree` or `lxml` |
| FFmpeg | The `ffmpeg.exe` binary goes **inside the installed application** (`{app}\bin\ffmpeg.exe`). Source: the `imageio-ffmpeg` package (the binary is taken at build time) or a static build (gyan.dev / BtbN), the choice is up to the agent. `NOTICE` states the build license. Launched via `subprocess` with no console window (`CREATE_NO_WINDOW`) |
| Logs | standard `logging`: file `<install folder>\logs\app.log` (`%LOCALAPPDATA%\HLSGrabber\logs\app.log` if the install folder is not writable; rotation) and a `QtLogHandler` that writes records into the window console |
| Tests | `pytest`, `pytest-qt` for basic GUI checks |
| Code quality | `ruff`, `mypy` (soft mode), `pre-commit` |
| Packaging | **PyInstaller** in `--onedir` mode (not `--onefile`: faster startup, fewer antivirus false positives), `--windowed`, `.ico` icon, version metadata |
| Installer | **Inno Setup 6** (`installer/hlsgrabber.iss`), built via `ISCC.exe` |
| Versioning | SemVer, Git tags like `v1.2.3`, releases on GitHub Releases (section 8) |

---

## 3. Work scenario

1. Program startup. The downloads-folder picker dialog (native Qt `QFileDialog`,
   the last used folder by default). Cancelling terminates the program.
2. The main window opens and the browser opens in parallel. `.tmp\<task id>\` is
   created in the chosen folder for segments. Finished files lie in the root of
   the chosen folder.
3. The user visits the site and starts the video. `NetworkSniffer` analyzes the
   traffic. Sources that pass the filters (section 5) appear as cards in the top
   section.
4. The user presses "Download" on the needed card. The task is queued, progress
   is shown inside that card.
5. Downloads are **strictly sequential** (one worker). If "Download" was pressed
   for several videos, they run one after another.
6. After the join, the task's temporary folder is deleted and the card moves to
   the "Done" state. On error, temporary files are kept, the reason is written
   to the log and the console.
7. Closing the window: if a download is running, ask for confirmation. After
   consent, cancel the download, close the browser, terminate the program. If
   the user closed the browser, the console writes a message and the current
   download continues to the end (or the user can cancel it).

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
  scrollable (`QScrollArea`), new cards are added at the bottom.
- Each card contains:
  - a type badge (HLS / DASH / MP4);
  - a title (the page title on which the video was found);
  - a link (truncated by width, full in a tooltip, context menu "Copy link");
  - resolution and duration, or size, if known;
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
- In the section header there are two list-clearing buttons:
  - **"Clear all"** — removes all cards;
  - **"Clear downloaded"** — removes only the cards whose files are already
    downloaded and lie on disk.
  An active download is not cancelled when clearing and continues in the
  background.
- There is no separate shared progress bar between the sections: progress lives
  inside the card.

### 4.2. Bottom section: console

- Read-only `QPlainTextEdit`, monospace font, color highlighting of levels
  (INFO / WARNING / ERROR).
- Autoscroll down (disabled when the user scrolls up, re-enabled when scrolling
  to the end).
- Buffer limited to ~5000 lines (`setMaximumBlockCount`).
- The whole log goes here: browser launch, found manifests, skip reasons (live,
  DRM, no 1080p), segments, retries, FFmpeg calls, update checks, errors.
- Line format: `[12:34:56] INFO  Found HLS stream 1080p: https://...`
- Above the console, small buttons: "Clear", "Open downloads folder", "Open log
  file".

### 4.3. Extras

- Status bar at the bottom of the window: application version, current downloads
  folder, update icon and status (section 8).
- Menu or gear button "Settings" (a dialog): downloads folder, number of
  threads for segments (default 6), automatic update checks (enabled by
  default), theme (system / light / dark). The dialog takes 80% of the main
  window's width and height and can be resized; a long folder path is fully
  visible (and in the tooltip on hover).
- Window title: "HLS Grabber `<version>` — `<downloads folder>`".

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

### 5.2. Filters (in order of application)

1. **Live.** HLS without `#EXT-X-ENDLIST` and DASH with `type="dynamic"` are
   skipped, the reason goes to the log.
2. **DRM.** Skipped if:
   - `#EXT-X-KEY` with a method other than `NONE` and `AES-128` (SAMPLE-AES
     and the like);
   - the MPD has `ContentProtection` with Widevine, PlayReady or FairPlay.

   Console message: "Content is DRM-protected, downloading is impossible".
3. **1080p quality.** We only care about a height of 1080.
   - For a master playlist and an MPD, the source is shown only if there is a
     variant with `height == 1080`. Among 1080p variants the one with the
     maximum bandwidth is picked, plus the best audio track.
   - If there is no 1080p, the source is not shown and the console writes:
     "Found a stream without 1080p: skipped (available: 720p, 480p)".
   - A media playlist without variants is shown if its resolution is 1080 or
     cannot be determined (the card shows "unknown").
   - For direct MP4 the resolution is determined via `ffprobe`/`ffmpeg -i`
     (with headers when possible). On failure the card shows "unknown" and the
     file stays in the list.
   - The threshold is a setting (`target_height`, default 1080), no UI for it.
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
- **File name:** `<page title>.mp4`. Forbidden Windows characters are replaced,
  the length is truncated (with the path limit in mind). On a name conflict the
  suffix ` (1)`, ` (2)` and so on is added.
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
- The best Representation is chosen for video and audio (video under the 1080p
  condition).
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
- Main path: an installed Chrome or Edge, nothing to download.
- If neither exists, on first run the program offers to download Chromium (a
  consent dialog), runs the Playwright driver installation with
  `PLAYWRIGHT_BROWSERS_PATH=<install folder>\browsers`
  (`%LOCALAPPDATA%\HLSGrabber\browsers` when the install folder is not
  writable) and shows progress in the console. Chromium is not bundled into
  the installer to avoid bloat. Chromium from a previous version lying in
  `%LOCALAPPDATA%\HLSGrabber\browsers` is reused: it is not downloaded again.
- Warning in the console: Chromium from Playwright may not play H.264/AAC on
  some sites.

### 7.3. Inno Setup 6 installer (`installer/hlsgrabber.iss`)
- A constant `AppId` (GUID) is set once and never changes between versions, so
  that the update installs over the existing installation.
- `AppVersion` and the output file name come from the `/DAppVersion=...`
  parameter that `ISCC` receives from the build script. Output file name:
  `HLSGrabber-Setup-<version>.exe`.
- Default install to `{autopf}\HLS Grabber`. Mode
  `PrivilegesRequiredOverridesAllowed=dialog` (the user can choose a
  per-user install without administrator rights, or for all users).
- Files: contents of the PyInstaller folder `dist\HLSGrabber\*` with
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
  `/SUPPRESSMSGBOXES`, `/CLOSEAPPLICATIONS`. After installation, the "Run HLS
  Grabber" option.
- Code signing (`signtool`) is foreseen as an optional step in the build
  script (to reduce SmartScreen warnings); the installer must also build
  without signing.

### 7.4. Data layout
- Everything the program creates lives in the install folder: `{app}\profile`
  (browser profile), `{app}\browsers` (Chromium), `{app}\extensions` (the
  unpacked blocker), `{app}\logs` (logs). Deleting the install folder deletes
  this data too.
- Settings: `%APPDATA%\HLSGrabber\settings.json` — survive a reinstall.
- When the install folder is not writable (`Program Files` without
  administrator rights), all the folders listed above are created in
  `%LOCALAPPDATA%\HLSGrabber`.
- Chromium, downloaded by a previous version into
  `%LOCALAPPDATA%\HLSGrabber\browsers`, is found and reused: no re-download.

---

## 8. Versions, Git and updates via GitHub Releases

### 8.1. Versioning
- SemVer format (`MAJOR.MINOR.PATCH`), Git tags like `v1.2.3`.
- The single source of version in the code: `src/hlsgrabber/_version.py`. The
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
  - `HLSGrabber-Setup-<version>.exe`;
  - `HLSGrabber-Setup-<version>.exe.sha256`.
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
  1. The asset `HLSGrabber-Setup-*.exe` is downloaded into a temporary folder
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
hls-grabber/
 ├─ pyproject.toml
 ├─ requirements.txt
 ├─ README.md
 ├─ CHANGELOG.md
 ├─ NOTICE                      licenses of third-party components (FFmpeg, Qt, Playwright)
 ├─ build.ps1                   build: PyInstaller + ISCC
 ├─ hlsgrabber.spec             PyInstaller config
 ├─ installer/
 │   ├─ hlsgrabber.iss
 │   └─ assets/                 wizard images, icons
 ├─ assets/                     app.ico, interface icons, QSS styles
 ├─ .github/workflows/
 │   ├─ ci.yml
 │   └─ release.yml
 ├─ src/hlsgrabber/
 │   ├─ __main__.py             entry point
 │   ├─ _version.py             generated at build time
 │   ├─ app.py                  Qt initialization, folder picker
 │   ├─ ui/                     main_window.py, source_card.py, source_list.py,
 │   │                          console_panel.py, settings_dialog.py,
 │   │                          update_dialog.py, theme.py
 │   ├─ browser/                launcher.py, sniffer.py, chromium_installer.py
 │   ├─ manifest/               detector.py, drm.py, quality.py, registry.py
 │   ├─ hls/                    parser.py, models.py
 │   ├─ dash/                   parser.py, models.py, segments.py
 │   ├─ download/               queue.py, segments.py, direct.py, decrypt.py, retry.py
 │   ├─ ffmpeg/                 runner.py, locate.py
 │   ├─ update/                 checker.py, installer_runner.py, semver.py
 │   ├─ config/                 settings.py, paths.py
 │   └─ util/                   urls.py, filenames.py, logging_setup.py
 └─ tests/
     ├─ test_hls_parser.py
     ├─ test_dash_parser.py
     ├─ test_drm.py
     ├─ test_quality.py
     ├─ test_mp4_ranges.py
     ├─ test_filenames.py
     ├─ test_update_checker.py
     └─ data/                   sample playlists and MPDs
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
  empty with a hint, the bottom section shows the console, and the browser
  opens in parallel.
- On opened test HLS, DASH and direct MP4, the source automatically appears as
  a card with a title, a link and a "Download" button.
- Downloading starts only after pressing the button. The card shows progress.
  The result is a playable `.mp4`.
- Live, DRM and streams without 1080p are skipped with a clear entry in the
  console.
- Several pressed "Download"s run strictly one after another. "Cancel"
  correctly stops the download and cleans up temporary files.
- The window does not freeze during a download.
- The interface renders correctly in the light and dark themes and at Windows
  scaling 125% and 150%.

**Installation and updates**
- `build.ps1` on a clean machine with Python 3.12 and Inno Setup 6 builds
  `HLSGrabber-Setup-<version>.exe`.
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
8. PyInstaller build and the `installer/hlsgrabber.iss` script, `build.ps1`.
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
  on demand, only when Chrome and Edge are absent.
- Streams without a 1080p variant are hidden from the list (written only to
  the console).
- Download progress is shown inside the video card, the downloading card has a
  "Cancel" button.
- The update is applied by running the installer with `/SILENT`, not by
  replacing files on the fly.
- Before starting, the agent must be given the repository's `OWNER/REPO` and
  a GUID for `AppId` must be generated once.
