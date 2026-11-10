# PyDownloader

A Windows application for downloading video from the browser: it opens a controlled
browser, intercepts network requests, finds HLS (`.m3u8`), MPEG-DASH (`.mpd`),
direct MP4 and YouTube streams, and joins the downloaded segments with FFmpeg into
one `.mp4`. The interface is dark by default; light and system themes are available
in the settings.

## Screenshots

![Main window: cards of found videos and the console](assets/screenshots/window.png)

![Settings dialog](assets/screenshots/settings.png)

The screenshots are rendered by the `tools/make_screenshots.py` script (`uv run python
tools/make_screenshots.py`): it fills the cards and the console with demo data, and
the script has no browser and no downloads, so the screenshots are reproducible. The
windows are never shown on the desktop — the snapshot is taken with `QWidget.grab()`
on the offscreen Qt platform.

## How it works

1. Launch → pick the downloads folder (first run only).
2. A browser and a window of two sections open: found videos (top) and console
   (bottom). The browser already has the uBlock ad blocker enabled (see below).
3. The user visits the site and starts the video himself — the application intercepts
   manifests and shows what it found as cards. If the site signs every URL separately
   (e.g. phncdn), the download uses the exact signed URLs from the browser traffic.
   If the playlist is requested inside the page and only segments are visible, three
   GET requests from one directory form an HLS card.
4. Downloading starts **only after pressing "Download"**; downloads run strictly
   sequentially, segments use up to 6 threads.
5. Segments (decrypted with AES-128 when required) are joined by FFmpeg
   (`-c copy`) into the finished `.mp4`, and the task's temporary folder is deleted.
6. YouTube: the page itself requests the inner-tube player API (VISIONOS client),
   so the classic signed URLs are available. Video and audio are downloaded in 8 MB
   range blocks and muxed without re-encoding.

Live streams, DRM-protected content (Widevine / PlayReady / FairPlay) and streams
without a 1080p variant are skipped; the reason is written to the console. DRM
bypass (including Widevine) is not supported.

## Card states

`Found` → `Queued` → `Downloading` (progress, speed, segments X of Y, stage,
"Cancel") → `Done` ("Open file" — plays the downloaded video in the default player)
/ `Error` ("Retry").

Above the list of found videos there are two buttons: **"Clear all"** removes the
whole list, **"Clear downloaded"** — only the cards whose files are already
downloaded and lie on disk. An active download is not cancelled when clearing and
continues in the background.

## Logging

The program writes a diagnostic log to `<install folder>\logs\app.log` (if the
install folder is not writable — to `%LOCALAPPDATA%\PyDownloader\logs\app.log`;
rotation: 5 MB × 3 files). Everything goes into the file: every intercepted
browser response, manifest and segment requests with response codes, cookies,
quality decisions, the selected variant, the task plan, the FFmpeg command and
errors. The window console shows only the important lines (INFO and above), so
the window does not slow down on long segment lists.

If a stream is not found or a download fails — press "Open log file" in the window
(the log path is also printed to the console at startup) and send the file: the
log shows which URLs the player requested and what the server answered.

## Settings

Settings are stored in `%APPDATA%\PyDownloader\settings.json`: downloads folder,
number of threads, theme, resolution, minimum MP4 size, update check, window size
and position. The downloads folder is asked only on the first run; on later runs
the program takes it from the settings and creates it if it was deleted. The
folder can be changed in "Settings" → "Downloads folder" — the value is saved
right after pressing "Save". The settings dialog takes 80% of the main window's
width and height, can be resized manually, and a long path is fully visible (and
in the tooltip on hover).

## Languages

The interface and the log lines are in English, Russian, Ukrainian, Chinese,
French and German; English is the default. The language is chosen in
Settings → Language; the native names shown in the combo are English, Русский,
Українська, 中文, Français, Deutsch. The choice is stored in
`%APPDATA%\PyDownloader\settings.json` as `"language"` and is applied after the
program restarts — the Settings dialog shows a hint and a Restart button.

## Ad blocker and browser profile

Next to the program lies `uBlock.crx` (uBlock Origin Lite). At startup it is
unpacked into `<install folder>\extensions` and attached to Chromium from
Playwright. Modern Chrome and Edge ignore extensions passed from the command
line, so for the blocker the program offers to download Chromium once (it lands
in `<install folder>\browsers`); without it the browser opens with no blocker.
Chromium downloaded by a previous version into
`%LOCALAPPDATA%\PyDownloader\browsers` is found and reused — it is not
downloaded again.

The browser profile lives in the program folder — `<install folder>\profile` —
and contains cookies, account logins and site settings. It persists between
program runs and updates. The profile of a previous version from
`%LOCALAPPDATA%\PyDownloader\profile` is moved there automatically on the first
run. If the program folder is not writable (e.g. `Program Files` without
administrator rights), the profile, logs, Chromium and the unpacked blocker stay
in `%LOCALAPPDATA%\PyDownloader`. In "Settings" you can instead keep the profile
in `<downloads folder>\.profile`.

## Where the data lives

| What | Where |
| --- | --- |
| Program, `bin\ffmpeg.exe`, `uBlock.crx` | install folder |
| Browser profile (cookies, sessions) | `<install folder>\profile` |
| Chromium from Playwright | `<install folder>\browsers` |
| Unpacked ad blocker | `<install folder>\extensions` |
| Log file | `<install folder>\logs` |
| Settings | `%APPDATA%\PyDownloader\settings.json` |

Everything except the settings lives in the install folder: deleting it deletes
the profile, the downloaded browser, the blocker and the logs too. The settings
stay in `%APPDATA%` to survive a reinstall. If the install folder is not
writable, these folders are created in `%LOCALAPPDATA%\PyDownloader`.

## Requirements

- Windows 10/11 x64; Chrome or Edge, or Chromium from Playwright (the
  application offers to download it on first run). The ad blocker requires
  Chromium specifically.
- Python 3.12 only for building; the installed application runs without Python.

## Running from source

Double-click `run.bat` in the repository root (or run `run.bat` from the
console). The script sets `PYTHONPATH=src` and runs `python -m pydownloader`
from `.venv`, so the current code always works — no rebuild is needed. If
`.venv` is absent, `uv run` is used. The console window stays open on an
error, so the traceback is visible.

## Build

```powershell
uv sync --extra dev
winget install -e --id JRSoftware.InnoSetup   # needed for the installer
.\build.ps1                                    # version, PyInstaller, ISCC, SHA-256
```

Result: `dist/PyDownloader/PyDownloader.exe` (the program folder, FFmpeg inside
`bin`), `dist/install/PyDownloader-Setup-<version>.exe` and the `.sha256` file.
`uBlock.crx` lies in the repository, is copied into `dist/PyDownloader` and
lands in the installer — the GitHub Actions build also contains the blocker.
The version is taken from `git describe --tags` (`0.0.0-dev` in development).

## Installation

`PyDownloader-Setup-<version>.exe` installs the program to
`Program Files\PyDownloader`, creates shortcuts and offers to run it. Silent
install:
`PyDownloader-Setup-<version>.exe /SILENT /SUPPRESSMSGBOXES /CLOSEAPPLICATIONS`.
Uninstallation deletes the install folder with all its data (browser profile,
downloaded Chromium, unpacked blocker, logs). The settings
(`%APPDATA%`) and the data in `%LOCALAPPDATA%` are deleted only after
confirmation in the dialog.

## Updates

The application checks `GitHub Releases` of the `flynet/pyDownloader` repository,
shows the release notes, downloads the installer, verifies SHA-256 and runs it
with `/SILENT /CLOSEAPPLICATIONS`. The automatic check is disabled in the
settings.

## Structure

```
src/pydownloader/
  i18n.py   language of the interface and of the log lines, ``tr`` lookup
  locales/  catalog of texts: English, Russian, Chinese, French, German
  hls/      .m3u8 parser and model
  dash/     .mpd parser and model
  manifest/ candidate detection, DRM, 1080p quality, source registry
  util/     URLs, file names, ranges, logging
  config/   settings, paths, repository constants
  browser/  browser launch and network interception
  download/ queue, segments, AES-128, direct MP4
  youtube/  inner-tube player API, format parsing, range plan
  ffmpeg/   locating ffmpeg.exe and running the join
  update/   release checks and installer launch
  ui/       window, cards, console, settings, themes
tests/      pytest + sample playlists and MPDs
```

## Tests

```powershell
ruff check src tests
mypy src
pytest
```

## Licenses

Third-party components and their licenses are listed in the `NOTICE` file. The
technical specification is in `docs/TZ_HLS_Grabber_Python.md`.
