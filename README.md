# PyDownloader

A Windows application for downloading video from the browser: the user opens a
controlled browser with the "Open browser" button, the program intercepts the
network requests of that browser, finds HLS (`.m3u8`), MPEG-DASH (`.mpd`),
direct MP4, YouTube streams and audio sources, and joins the downloaded segments
with FFmpeg into one `.mp4` (a source of sound only is written as `.mp3`). The
interface is dark by default; the light theme, the system theme and three theme
palettes — "Cartoons", "Neon", "Pink" — are available in the settings, the program
lives in the Windows tray, and the browser window can be opened and closed by the
user. The console panel starts hidden, so the list of found videos takes the whole
window: no divider, no console row, and the top row of the window has the button
that opens the panel back.

## Screenshots

![Main window: the cards of found videos with the cross on the right, the console
panel open with its row of buttons](assets/screenshots/window.png)

![Settings dialog: quality, browser, language, theme, the tray rows and the console
panel](assets/screenshots/settings.png)

The same window in the three theme palettes of the settings:

![Cartoons theme: the cream wall, the white cards, the dark navy outlines, the sky
blue of the buttons, the badges of the formats](assets/screenshots/window_cartoons.png)

![Neon theme: the dark wall of a game, the violet of the buttons, the cyan of the HLS
badge, the lime of a finished file](assets/screenshots/window_neon.png)

![Pink theme: pastel on a light base, the rose of the buttons, the lavender of the HLS
badge, the mint of a finished file](assets/screenshots/window_pink.png)

The screenshots are rendered by the `tools/make_screenshots.py` script (`uv run python
tools/make_screenshots.py`): it fills the cards and the console with demo data, and
the script has no browser and no downloads, so the screenshots are reproducible. The
main window is drawn four times — in the dark theme and in each of the three theme
palettes — because a card is painted once, when it is added to the window, so the
window is built fresh for every theme. The
windows are never shown on the desktop — the snapshot is taken with `QWidget.grab()`
on the offscreen Qt platform. The script runs with its own `%APPDATA%`,
`%LOCALAPPDATA%` and temp folder (`isolate_app_data` of `config/paths.py`, the same
rule the tests follow), so a run of the screenshots cannot rewrite the settings of
the user: a window saves its settings on the close and on the Apply of the dialog.

## How it works

1. Launch → pick the downloads folder (first run only). The main window opens with
   the **console section hidden**: the list of found videos takes the whole window,
   there is no divider between the sections, and the top row of the window shows
   **"Show console"**. Press it to see the log of the program — the row of the
   console appears with the panel, and the same top button now reads **"Hide
   console"**, which takes the whole section away and gives the room back to the
   cards. The state is stored, so the window opens the way the user left it. **The
   browser is not started automatically** — press "Open browser" when you want to
   look for a video.
2. The browser window opens maximised on the last page you visited, with the uBlock
   ad blocker enabled (see below). It carries no banners of a driver: neither
   "this build is for automated testing" nor the "unsupported command-line flag"
   strip under the address bar.
3. The user visits the site and starts the video himself — the application intercepts
   manifests and shows what it found as cards. If the site signs every URL separately
   (e.g. phncdn), the download uses the exact signed URLs from the browser traffic.
   If the playlist is requested inside the page and only segments are visible, three
   GET requests from one directory form an HLS card.
4. Downloading starts **only after pressing "Download"**; downloads run strictly
   sequentially, segments use up to 6 threads.
5. Segments (decrypted with AES-128 when required) are joined by FFmpeg
   (`-c copy`) into the finished `.mp4`, and the task's temporary folder is deleted.
   A source that is audio only (SoundCloud, a radio stream, an audio-only HLS
   playlist) is decoded with `libmp3lame` and written as `.mp3` at the bitrate
   chosen in the settings; audio is never muxed into a black video file.
6. YouTube: the page itself requests the inner-tube player API (VISIONOS client),
   so the classic signed URLs are available. Video and audio are downloaded in 8 MB
   range blocks and muxed without re-encoding.

Live streams, DRM-protected content (Widevine / PlayReady / FairPlay) and streams
without a variant of one of the presets **1080p, 720p, 480p** are skipped; the
reason is written to the console. An exact match is taken (a 1440p source is
downloaded as 1080p), an HLS playlist of sound only is accepted without a
preset. DRM bypass (including Widevine) is not supported.

## Card states

`Found` → `Queued` → `Downloading` (progress, speed, segments X of Y, stage,
"Cancel") → `Done` ("Open file" — plays the downloaded file in the default player)
/ `Error` ("Retry").

The progress bar keeps the accent colour of the theme while the file is
downloading and turns **green** when the file is on the disk, so the end of a
download is seen at a glance, without reading the text of the card.

Each card shows the source type badge: HLS, DASH, MP4, YOUTUBE, and **MP3** for
an audio source, plus the quality line: `1080p`, `720p`, `480p`, the resolution
when it is known, or `MP3`. A card with a source is never cut off: the list of
cards has its own scrollbar, and when the window is made small the card section
keeps its minimum height and the console shrinks.

On the right of every card there is a **"✕"** — a square box of 26 px with the mark
in the middle: the button has no text, so nothing is asked for next to the icon and
the box is not stretched into a rectangle with the mark to the left. It takes this
one entry out of the list. A queued or running task is **cancelled** first (the
card goes with it), a finished card is removed and the file on the disk stays, a
found card is simply taken away. "Clear all" and "Clear downloaded" work on the
whole list, the cross works on one card.

Above the list of found videos the window has **two rows** of buttons. The top row is
the commands of the window, in the **upper-left corner**:
- **"Open browser"** / **"Close browser"** — one button whose label is the action it
  does: while the browser window is down the button reads "Open browser" and shows
  the page where the user was last, once it runs the same button reads "Close
  browser" and stops the window. Downloads keep running in both cases.
- **"Show console"** / **"Hide console"** — one button with the same rule: the
  console section is a whole section (its row of buttons and the text of the log),
  so hidden it is not on the screen at all, the list of cards fills the window and
  there is no divider between the two sections. Pressed, the section comes back with
  the room it had, the button reads "Hide console" and gives the window to the cards
  again. The state is stored, so the window opens the way the user left it.
- **"Open download folder"** — the folder the finished files are written to. The
  button stands in the top row, not under the list: the row of the console is on the
  screen only while the console is open, and the folder is needed without it.
- **"Settings"** — the settings dialog.

The right end of the same row carries the two commands of the list, each in
its own color:
- **"Clear downloaded"** — **yellow**: remove only the cards whose files are on disk.
- **"Clear all"** — **red**: remove every card.
The colors are keys of the theme, so the yellow and the red are the same in the dark
theme, the light theme and the screenshots, and the mark of a button takes the color
of its text: the dark of the theme on the yellow, white on the red.

The second row is the address of the video: a field with the label *"Paste the link to
the video"* and the **"Go"** button at its right. A link is pasted into the window, and
"Go" — or Enter in the field — opens the browser on that page: with the browser down,
its thread is launched on the address of the field and the browser button of the window
changes to "Close browser" when the browser window is up; with the browser running, the
address goes to the pump loop of the thread, which opens the page in the window that is
already there, and the same listener that reads any page of the browser finds the
manifests of the new site. A domain pasted without the protocol gets `https://`, a link
longer than the field is read in the tooltip, and the page is remembered, so "Open
browser" opens the same site after the browser is restarted. The label "Found videos"
is gone: the row of the commands starts at the left edge of the window.

Every button carries a mark drawn by the program: the browser window with the globe,
the list with the cross, the list with the check, the terminal, the folder, the gear. The marks are painted
with `QPainter` in a 16 px grid, not typed: the font of the Windows buttons does not
carry the gear (it shows a box), so the same picture is drawn in every theme, in
every language and in the screenshots above, as the icon of the program and the cross
of a card are drawn.

The theme colors the whole window, not only the widgets with a rule of their own.
A plain widget paints the **palette** of the application, and the palette Qt reads
from Windows is the palette of the system dark mode, so on a machine with the dark
mode of Windows the light theme showed a dark wall behind the list of cards. The
palette of the application is set to the colors of the theme that is chosen in the
settings (window, base, button, text, accent), and the wall behind the cards has its
own rule in the stylesheet, so the list of cards, the console panel and the status
bar are light in the light theme and dark in the dark theme. The **system** choice
keeps the palette of Windows.

Six choices stand in the theme row of the settings: **Dark**, **Light**,
**Cartoons**, **Neon**, **Pink**, **System**. The three new palettes are named by
their style, not by the age of the person who uses them: "Cartoons" is a warm cream
wall with white cards and dark navy outlines, "Neon" is the wall of a game with the
violet of the buttons and the cyan of a badge, "Pink" is pastel on a light base. A
theme is a set of **keys**, not a set of colors picked widget by widget: the
background of the window, the panel of a card, the text, the secondary text, the
accent of the buttons, the yellow of "Clear downloaded", the red of "Clear all", the
green of a finished file, the color of each badge (HLS, DASH, MP4, YouTube, MP3), the
wall of the console and the color of the log. One key is one role, so the same
theme paints the main window, the console panel and the settings dialog, and a
theme chosen in the settings is applied to the window at once: the marks of the
buttons, the badge of a card and the bar of a finished card are drawn again with
the colors of the new theme, no restart is asked. The letters of a theme are
measured by the WCAG ratio of contrast: the text on the wall, the letters of a
button, the letters of a badge and the log on the wall of the console are at least
4.0 apart, so the accent of a bright palette is the darker edge of its family.

The console section is one block: the row of two buttons and the panel of the log,
and it is on the screen only while the console is open. Its buttons are **"Clear"**
(the text of the console) and **"Open log file"** (the diary of the run on disk):
both belong to the console, so hidden there is nothing to clear and no room for the
log. The commands of the window — the console itself and the downloads folder —
stand in the top row, so they are reachable while the section is away, and so is
"Show console" / "Hide console": one button that brings the section back and takes
it away. The console command is in the tray menu as well.

## Tray

The program lives in the Windows notification area. Pressing **X** in the window
title bar **hides the window to the tray**: the downloads keep running, the
browser window stays open, and the tray menu is the only way to quit — "Exit"
asks for confirmation when a download is running, cancels it, closes the browser
and terminates the program. The tray menu offers: show the window, the browser,
show the console, check for updates, open the downloads folder, exit — six items,
each with its painted mark. The item of the browser is the button of the window:
one item whose text is "Open browser" while the window is down and "Close browser"
while it runs. A single click or a double click on the tray icon shows the window.
The first time
the window is hidden, the tray icon shows a balloon explaining the menu (the hint
is shown once and stored in the settings).

The tray icon is the icon of the program: the dark square with the white arrow
pointing down and the line of the tray under it. The icon of the desktop, the
installer and the window title bar is the same picture, drawn by the same code.
Only the colour of the arrow marks the state: a **green arrow** while a download
is running, and the arrow jumps up and down (the frames of a timer); the white
arrow of the program when nothing is downloading. When a batch of downloads is
over — the queue is empty and every task of it is finished — the icon goes back to
white, a Windows balloon appears next to it ("All downloads are finished: N saved")
and the system notification sound is played: this is how the user who works with
the window hidden learns that the program is done. The report is the end of a
batch, so it comes once for the whole batch and not after every file, it is not
sent for a single download (a batch is at least two files), and it is not sent
when the user takes cards out of the list, cancels a task or a task ends with an
error: in all these cases the icon only goes back to white.

Putting the mouse over the icon (without clicking) shows the list of the files
that are downloading: the name, the percent, the speed, the time left, and the
number of the tasks waiting in the queue. The text is rewritten at most once a
second, and the start and the end of a task are written at once.

The tray settings are "Show the icon in the notification area" and "Hide the
window to the tray when closing" (both on by default). If the system has no
notification area (Windows Server, a remote desktop session, the offscreen CI of
the tests), the tray icon is not created: "X" works as a normal close, the sound
of the finished downloads is not played (the sound of the system is a Windows
one), and the finished downloads are reported in the window console only.

## Browser controls

The button "Open browser" shows the browser window on the last page the user
visited, maximised; the same button, reading "Close browser", closes it. The
program does not open the browser by itself: the first window of the run is the
window of the program, and the browser appears only after the user presses the
button, so nothing is launched in the background. Closing the browser window does
not stop an active download: the segments are downloaded by the program itself, not
by the browser, so the task finishes after the window is closed. When the browser
is closed, its thread is replaced by a new one (the Playwright objects of a closed
browser belong to the event loop of the old thread), and the user's profile is read
from disk again, so cookies, logins and site settings are the same as before the
closing. If the browser is not open, the button starts it with the program's
profile on the last page; when it is already open, the button closes the window.
The button is disabled while the browser is being resolved and launched (the first
launch can download Chromium and ask a question in a dialog box), so a second press
cannot start a second thread: during the launch the tip of the button says that the
browser is starting. Pressing "Close browser" when nothing runs writes the message
"the browser is not running" and keeps the window as it was.

## Logging

The program writes a diagnostic log to `<install folder>\logs\app.log` (if the
install folder is not writable — to `%LOCALAPPDATA%\PyDownloader\logs\app.log`;
rotation: 5 MB × 3 files). Everything goes into the file: every intercepted
browser response, manifest and segment requests with response codes, cookies,
quality decisions, the selected variant, the task plan, the FFmpeg command and
errors. The window console shows only the important lines (INFO and above), so
the window does not slow down on long segment lists.

If a stream is not found or a download fails — press "Show console" in the top row
of the window and then "Open log file" in the row of the console (the log path is
also printed to the console at startup) and send the file: the log shows which URLs
the player requested and what the server answered.

## Settings

Settings are stored in `%APPDATA%\PyDownloader\settings.json`: downloads folder,
number of threads, theme, quality preset, MP3 bitrate, audio-only mode,
minimum MP4 size, browser, anti-bot, ad blocker, language, tray icon, console
panel, update check, window size and position (and the state of the console
panel). The downloads folder is asked only on the first
run; on later runs the program takes it from the settings and creates it if it
was deleted. A settings file naming a folder inside the system temp folder is not
taken as the choice of the user — the program does not write videos there, so the
folder is asked again. The settings of the user are never written by the test suite:
the tests of the suite run with their own `%APPDATA%` and `%LOCALAPPDATA%`, so a
run of `pytest` cannot leave the temp folder of a test as the downloads folder of
the user. The folder can be changed in "Settings" → "Downloads folder" — the
value is saved right after pressing "Save". The settings dialog takes 80% of the
main window's width and height, can be resized manually, and a long path is
fully visible (and in the tooltip on hover). The row at the bottom has the two
main buttons — **"Save"** and **"Cancel"** — in the **right lower corner**, where
the buttons that finish a dialog are looked for; "Check updates" and "Restart"
stand on the left of that row. The dialog can be resized, but not under the height
its rows need: every field, select, checkbox and button keeps the height its own
font asks for, so the smallest dialog shows all the rows readable — no field is
squeezed to half a letter.

"Resolution (p)" is a combo with three presets: **1080p, 720p, 480p** (an
out-of-list height saved in an edited `settings.json` gets its own entry). "MP3
bitrate" is 128 / 192 / 320 kbps, "Audio only (MP3)" downloads only the sound
part, "User agent" imitates another device (an empty field takes the Chrome
string of the version launched), "Hide the flags a bot driver leaves (anti-bot)"
switches stealth on and off, "Load the bundled ad blocker" is on by default,
"Show the icon in the notification area" and "Hide the window to the tray when
closing" are the tray rows, "Show the console panel below the list" is the panel
of the window (off by default, so the list of cards gets the whole window). The
state of the panel is stored, so the window opens the way the user left it.

## Languages

The interface and the log lines are in English, Russian, Ukrainian, Chinese,
French and German; English is the default. The language is chosen in
Settings → Language; the native names shown in the combo are English, Русский,
Українська, 中文, Français, Deutsch. The choice is stored in
`%APPDATA%\PyDownloader\settings.json` as `"language"` and is applied after the
program restarts — the Settings dialog shows a hint and a Restart button.

## Anti-bot

Google and SoundCloud check the browser the page runs in and report "JavaScript
disabled / cookies blocked" when an automation tool opens it. The program makes
the browser look like an ordinary user's browser:
- the automation flags are removed: the "AutomationControlled" feature is
  disabled, so `navigator.webdriver` is undefined, a stealth script fixes the
  properties that bots usually leak (plugins, languages, `hardwareConcurrency`,
  `deviceMemory`, `window.chrome`, the notification permission, the brands of
  `navigator.userAgentData`), the sandbox switch is dropped;
- the user agent is taken from the real installed browser, not from
  Playwright's default one, with matching platform and locale hints
  (`en-US` / `ru-RU` / `uk-UA` from the language chosen in the settings);
- the browser runs with a **persistent profile** in the program's folder, so
  cookies, local storage, logins, extensions and site settings are kept between
  runs — after signing in to Google once the program is not asked to sign in
  again, and the same profile is sent to Google on every start;
- autoplay is allowed, the browser starts maximised, and the window looks like
  a normal browser window, not the stripped Playwright window;
- the banners a driver provokes are hidden: the Chrome for Testing that
  Playwright ships writes "this build is for automated testing" with a proposal
  to install a regular Chrome, and Chrome, Edge and that same build write "you
  are using an unsupported command-line flag" under the address bar. The launch
  keeps `--disable-infobars` in the defaults (the build of Testing answers to
  it) and adds `--test-type` (the switch the installed Chrome and Edge answer
  to), so none of these strips is shown.

"Anti-bot" is a setting (on by default); turning it off returns the plain
Playwright launch, which is useful to compare. The log records the launch
arguments, the user agent, the locale, the stealth script result and the profile
path, so a login problem can be diagnosed from `app.log`.

A site that checks the DevTools protocol (a CDP leak) can still tell that the
browser is driven by a program: a full anti-detection suite (a patched browser,
CDP isolation, fingerprint tools) is out of scope. The program is made for
sites that play video for a user who logs in himself, not for evading a
detection service.

## Ad blocker and browser choice

Next to the program lies `uBlock.crx` (uBlock Origin Lite). At startup it is
unpacked into `<install folder>\extensions` and attached to Chromium from
Playwright. Chrome 157 and Edge 157 ignore extensions passed from the command
line, so for the blocker the program offers to download Chromium once (it lands
in `<install folder>\browsers`); without it the browser opens with no blocker.
Chromium downloaded by a previous version into
`%LOCALAPPDATA%\PyDownloader\browsers` is found and reused — it is not
downloaded again.

Settings → "Browser" chooses the engine: **Automatic** (installed Chrome, then
Edge, then Chromium), **Google Chrome**, **Microsoft Edge**, **Chromium**. The
chosen engine is remembered; when it is not installed, the program falls back to
an installed one and Chromium, and asks to download Chromium when Chromium is
wanted.

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
| Settings of the previous save | `%APPDATA%\PyDownloader\settings.json.bak` |

Everything except the settings lives in the install folder: deleting it deletes
the profile, the downloaded browser, the blocker and the logs too. The settings
stay in `%APPDATA%` to survive a reinstall. If the install folder is not
writable, these folders are created in `%LOCALAPPDATA%\PyDownloader`.

The settings are written atomically: the file is written as `settings.json.new`
and moved in one call, and the file that was there is kept as `settings.json.bak`.
A `settings.json` that cannot be read (a start killed in the middle of a write)
is read from the backup, so the theme, the language, the state of the console
panel and the downloads folder come back on the next start instead of falling to
the defaults.

## Requirements

- Windows 10/11 x64; Chrome or Edge, or Chromium from Playwright (the
  application offers to download it on first run). The ad blocker requires
  Chromium specifically. The browser to launch is chosen in the settings.
- The tray icon needs the Windows notification area. On a system without it
  (Windows Server, a remote desktop session) the program works with the tray
  switched off, and the sound of the finished downloads is not played (the
  sound of the system is a Windows one).
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
  locales/  catalog of texts: English, Russian, Ukrainian, Chinese, French, German
  hls/      .m3u8 parser and model
  dash/     .mpd parser and model
  manifest/ candidate detection (audio/video), DRM, quality presets
            (1080p / 720p / 480p), source registry, probe pipeline
  util/     URLs, file names, ranges, logging
  config/   settings, paths, repository constants
  browser/  browser launch, stealth flags and user agent, ad blocker,
            network interception, Chromium download
  download/ queue, segments, AES-128, direct MP4, MP3 output
  youtube/  inner-tube player API, format parsing, range plan
  ffmpeg/   locating ffmpeg.exe, ffprobe media info, the join, MP3 encode
  update/   release checks and installer launch
  ui/       window, cards, console, settings, themes, tray
tests/      pytest + sample playlists, MPDs, ffprobe output
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
