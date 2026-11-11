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
   (bottom). **The console section is hidden at startup**: its row of buttons and
   the panel of the log are one section, so hidden the list of cards takes the
   whole window and there is no divider between the two sections. **The browser is
   not launched at startup** — the user opens it with the "Open browser" button.
   "Show console" / "Hide console" is one button of the top row: it brings the
   section back with the room it had and takes it away, giving the whole window to
   the list of cards; the state is stored for the next start.
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
  - a title (the page title on which the source was found): the card is as wide as
    the list of cards, so a long title is broken into the lines of its words the card
    can hold (two at most), the letters that do not fit are marked by the sign of
    elision, and the whole title is read in the tooltip. The card grows by height,
    never by width, and the list of cards gets no horizontal scrollbar;
  - a link (truncated by width, full in a tooltip, context menu "Copy link"); the
    link and the path of a saved file are one word, so the middle of the line is
    kept for them and the end of the file name stays on the card;
  - the quality preset (1080p / 720p / 480p), resolution and duration, or size,
    if known;
  - a **"Download"** button on the right;
  - a **"✕"** at the far right, in every state: it takes this one entry out of
    the list. A queued or running task is cancelled first and its card goes with
    it; a finished card is removed and the file on the disk stays; a found card
    is simply taken away. The entry is reported in the console ("Cancelled and
    removed from the list", "Removed from the list").
  - The box of the "✕" is a square: a button with no text is left as the icon only
    (a square box 26 px, the mark in the middle), so the box is not stretched into a
    rectangle with the mark shifted to the left.
- Card states:
  - **Found**: active "Download" button.
  - **Queued**: button disabled, caption "Queued".
  - **Downloading**: instead of the button, a progress bar with speed,
    percentage, "segments X of Y", stage (downloading / decrypting / joining)
    and a "Cancel" button. The bar keeps the accent colour of the theme.
  - **Done**: caption "Done" and an "Open file" button (plays the downloaded
    video in the default player). The bar of the card turns **green**: the file is
    on the disk, and the end of the download is seen at a glance, without reading
    the text.
  - **Error**: red caption and a "Retry" button, details in the console.
- Pressing "Download" only queues the task.
- In the section header there are **two rows** of buttons: the top row is the
  commands of the window in the **upper-left corner** and the two commands of the
  list in its **right corner**; the second row is the field of the address with the
  "Go" button.
  - **"Open browser"** / **"Close browser"** — **one button** whose label is the
    action it does: while the browser window is down the button shows "Open
    browser" (maximised, on the page where the user was last; starts the browser
    if it is not open), once the window runs the same button shows "Close
    browser". The program does not open the browser on its own: the window is
    opened by this button. Closing does not cancel an active download, it
    continues in the background. The button is disabled while the browser is
    being resolved and launched (the first launch can download Chromium and ask
    the question in a dialog), so a second press cannot start a second thread;
    the tip of the button says the browser is starting;
  - **"Show console"** / **"Hide console"** — **one button** with the same rule.
    The console section (the row of its buttons and the panel of the log) is on
    the screen only when the user asks for it, so the command of the window stands
    in the header and the label follows the state. Pressed, the section comes back
    with the room it had (the row of the console, the panel, and the divider of the
    splitter), pressed again it goes away and the list of cards fills the window;
    hidden, there is no divider between the sections at all, the handle of the
    splitter is 0 px. The state is stored in the settings, so the window opens the
    way the user left it;
  - **"Open downloads folder"** — the folder the finished files are written to.
    The command stands in the header because the row of the console is on the
    screen only with the panel, and the folder is needed while the console is
    hidden;
  - **"Settings"** — the settings dialog.
  - The **right corner of the top row** carries the two commands of the list, each
    in its own color: **"Clear downloaded"** is **yellow** — removes only the cards
    whose files are already downloaded and lie on disk; **"Clear all"** is **red** —
    removes all cards. The colors are keys of the theme, so the yellow and the red
    are the same in the dark theme, the light theme and the screenshots, and the mark
    of a button takes the color of its text: the dark of the theme on the yellow,
    white on the red. The commands of the list are in the header row, so they stay on
    the screen while the console is hidden.
  - The second row is the address of the video: the field (the placeholder *"Paste
    the link to the video"*) and the **"Go"** button at its right. "Go", or Enter in
    the field, opens the browser on the page of the link: with the browser down, the
    thread is launched on that address, and the browser button of the window changes
    to "Close browser" when the browser window is up; with the browser running, the
    address goes to the queue of the pump loop of the thread and the page is opened
    in the window that is already up — the response listener finds the manifests of
    the new site the same way it finds them on any page. A domain pasted without the
    protocol gets `https://`, a link longer than the field is read in the tooltip, an
    empty field is answered with the message that the field is empty, a link equal to
    the page the browser is on does not reload the page, and the page is remembered,
    so "Open browser" opens the same site after a restart of the browser. The label
    *"Found videos"* is removed: the row of the commands starts at the left edge of
    the window.
  An active download is not cancelled when clearing and continues in the
  background.
- Every button of the window carries a mark drawn by the program (a 16 px picture
  painted with `QPainter`): the browser window with the globe, the list with the
  cross, the list with the check, the gear, the chevron and the terminal, the
  folder, the page of the log. The marks are not typed characters: the UI font of
  Windows has no gear glyph, so a label with "⚙" shows a box. The color of the mark
  is the color of the button: white on the accent of the theme, the text color of
  the theme on a button of the panel background and in the tray menu. The same
  drawing rule is used for the cross of a card (spec 4.1 p.1) and for the icon of
  the program (spec 7.3).
- The theme colors **the whole window**: a plain widget paints the palette of the
  application, and the palette Qt reads from Windows is the palette of the system
  dark mode. The palette of the application is set to the colors of the chosen theme
  (window, base, button, text, accent), and the wall behind the cards has its own
  rule in the stylesheet, so the list of cards, the console panel, the status bar and
  every widget that paints the palette are light in the light theme and dark in the
  dark theme, whatever Windows says. The "system" choice keeps the palette of the
  style.
- The console section is one block on the screen: the row of two buttons above the
  panel, **"Clear"** (the text of the console) and **"Open log file"** (the diary of
  the run on disk). Both belong to the console, so hidden there is nothing to clear
  and no room for the log: the row, the panel and the divider of the splitter go
  away together, and the list of cards fills the window.
- The commands of the window — "Show console" / "Hide console" and "Open downloads
  folder" — stand in the header of the top section, so they are reachable while the
  console is hidden. The same console command is in the tray menu.
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
- Above the console, the row of its section: **"Clear"** and **"Open log file"**.
  The row is on the screen only while the console is, and the commands of the
  window ("Show console" / "Hide console", "Open downloads folder") are in the
  header of the top section.
- **"Hide console"** takes the console section away and gives the whole window to
  the list of cards; **"Show console"** brings the section back with the room it
  had. The console is **hidden at startup**: the row, the panel and the divider of
  the splitter are not on the screen, so the list of cards gets the whole window
  from the first start. With the panel shown, the handle of the splitter gets its
  width back and the divider is the line between the two sections. The state is
  stored in the settings, so the window opens the way the user left it, and the
  console is opened from the tray menu as well.

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
  (enabled by default), theme (**dark** / **light** / **Cartoons** / **Neon** /
  **Pink** / system). The dialog takes 80% of
  the main window's width and height and can be resized; a long folder path is
  fully visible (and in the tooltip on hover).
- **The theme paints the whole interface, not only the widgets with a rule of their
  own:** the wall of the window and the wall of the cards, the frames of the cards
  and of the fields, the main text and the secondary text (links, size, duration,
  status), the buttons, the yellow of "Clear downloaded", the red of "Clear all",
  the bar of a running file and the bar of a finished file, the badges of HLS, DASH,
  MP4, YouTube and MP3, the console panel and its text, the fields, the lists, the
  check boxes, the menus, the scroll bars, the tabs and the status bar. Every color
  of a theme is a key of one palette, so one role is one color in the whole window.
- **Three theme palettes** ("Cartoons", "Neon", "Pink") are named by their style,
  not by the age or the sex of the person who chooses them: "Cartoons" is the cream
  wall with white cards, dark navy outlines and the sky blue of the buttons, "Neon"
  is the wall of a game with the violet of the buttons, the cyan of a badge and the
  lime of a finished file, "Pink" is pastel on a light base with the rose of the
  buttons. The names are translated into the six languages of the catalog.
- **The letters of a theme are measured by the WCAG ratio of contrast:** the text on
  the wall of the window, the letters of a button, the letters of a badge and the log
  on the wall of the console are at least **4.0** apart, so the accent of a bright
  palette is taken to the darker edge of its family and the white letters stay
  readable.
- **The theme is applied to the window without a restart:** the marks of the buttons
  and of the cards are painted once, when the window is built, and a card is painted
  once, when it is added, so the marks, the badge of a card, the bar of a finished
  card, the wall behind the cards, the console panel, the fields, the menus and the
  status bar are drawn again with the colors of the theme the user picks.
- **The dialog cannot be squeezed under the height its rows need:** every field,
  select, checkbox and button of the dialog has the minimum height of its own
  ``sizeHint`` (the height its font and its text ask for), so the layout gets the
  minimum height of all the rows and the smallest dialog shows every row readable.
  A field squeezed to half a letter is not readable, so the floor is the height of
  the rows, with 420 px as the least height the dialog gets.
- **The row of buttons at the bottom of the dialog:** the two main buttons —
  **"Save"** and **"Cancel"** — are in the **right lower corner**, where the buttons
  that finish a dialog are looked for ("Save" is the button of Enter, "Cancel" is
  the last button of the row). "Check updates" and "Restart" are the secondary
  commands of the dialog and stand on the **left** of the row. Every button carries
  its painted mark.
- **Tray (Windows notification area).** Pressing "X" hides the window to the tray
  and the downloads keep running; "Exit" in the tray menu is the only way to
  quit (it asks for confirmation when a download is running). The tray menu has
  six items, each with its painted mark: show the window, the browser, show the
  console, check for updates, open downloads folder, exit. The item of the
  browser is the button of the window: one item whose text is "Open browser"
  while the window is down and "Close browser" while it runs, with the same
  picture of the browser and its mark. A single click or a double click on the
  icon shows the window; the first time the window is hidden a balloon hint
  explains the menu (shown once, the flag is stored).
- **The icon is the icon of the program** (spec 7.3): the dark square with the
  arrow pointing down and the line of the tray under it, the same picture as on
  the desktop and in the installer. **Only the colour of the arrow marks the
  state:** a **green arrow** with a jumping animation (the frames of a timer)
  while a download is running, the **white arrow** of the program when the queue
  is empty. The report is the **end of a batch**: when the queue is empty and every
  task of the batch is finished, a Windows balloon appears next to the icon ("All
  downloads are finished: N saved") and the system notification sound is played —
  this is the report for the user who works with the window hidden. The balloon
  comes **once for the whole batch**, not after every file; a batch is at least two
  files, so a single download gives no balloon and no sound. Removing a card,
  cancelling a task, clearing the list and a task that ends with an error are not
  finished downloads: in these cases the icon only goes back to the white arrow,
  nothing is announced.
- **The tooltip of the icon is the queue** (the mouse is over it, no click): the
  files that are downloading with the name, the percent, the speed, the time left,
  and the number of the tasks waiting. The text is rewritten at most once a
  second, because the tooltip of Windows is a heavy call; the start and the end of
  a task are written at once. A source of unknown size shows the percent only. The
  tooltip is kept by Windows in a buffer of 128 characters, so a long name of a
  task is shortened: the budget of the text goes to the report of a line (percent,
  speed, time left) first, the names take the rest by the same share, the cut is
  marked by the sign of elision, and the lines that still do not fit go from the
  end, so the tooltip ends with the percent of a task, not with the tail of a name.
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
- The icon of the program (`assets/icon.ico`), the pictures of the wizard and the
  icon of the tray are drawn by one code (`ui/app_icon.py`): the dark rounded
  square, the arrow pointing down, the line of the tray under it. The tray draws
  the same picture with the colour of the arrow of the state, so the program looks
  the same on the desktop, in the installer, in the title bar and in the
  notification area.
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
- The settings are written atomically: the file is written as
  `settings.json.new` in the same folder and moved in one call, and the file that
  was there is kept as `settings.json.bak`. A `settings.json` that cannot be read
  (half-written, damaged by a killed start) is read from the backup, so a start
  that cannot read the settings does not fall to the defaults and lose the theme,
  the language, the state of the console panel and the downloads folder.
- A settings file naming a folder inside the system temp folder is not taken as
  the choice of the user: the program never writes the videos there, so the
  downloads folder is asked again (the temp folder is not created).
- Any script that builds a window of the program writes the settings of the user:
  a window saves `settings.json` on the console toggle, on the Apply of the dialog
  and on the close. The test suite and the tool of the screenshots run with their
  own `%APPDATA%`, `%LOCALAPPDATA%`, data folders and temp folder
  (`isolate_app_data` of `config/paths.py`), so a run of `pytest` or of
  `tools/make_screenshots.py` cannot leave the temp folder of a run as the downloads
  folder of the user, and the browser profile, the logs and Chromium of the run do
  not go to the real folders of the developer.
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
  empty with a hint and takes the whole window (the console section is hidden: no
  row, no panel, no divider), the top row has "Show console", "Open downloads
  folder" and "Settings", and no browser is launched — the browser appears only
  after the user presses "Open browser".
- On opened test HLS, DASH and direct MP4, the source automatically appears as
  a card with a title, a link, a "Download" button and a "✕" on the right.
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
- While a download runs, the tray icon is the icon of the program with a green
  arrow and the jumping animation; when the queue is empty the arrow is white, so
  only the colour of the arrow changes and the picture is the icon on the desktop.
  Hovering over the icon shows the files that are downloading: name, percent,
  speed, time left. The bar of a card is green when the file is on the disk, and
  the end of a batch of downloads is reported once by a Windows balloon and the
  notification sound: a single download, a removed card, a cancelled task and an
  error give no balloon and no sound, only the white arrow of the tray.
- "Show console" / "Hide console" is one button of the top row that takes the
  console section away and back; hidden, the list of cards fills the window, the
  row of the console with "Clear" and "Open log file" goes with the panel, the
  divider between the sections is not on the screen, and the state is remembered
  for the next start.
- The header has two rows: the top row has "Open browser" / "Close browser", the
  console toggle, "Open download folder" and "Settings" in the **upper-left corner**,
  and "Clear downloaded" in yellow with "Clear all" in red in the **right corner** of
  the same row; the row below is the field of the address and the "Go" button. "Go"
  (or Enter in the field) opens the browser on the page of the link: it starts the
  browser when the browser is down, and opens the page in the running browser when it
  is up, so the manifests of the new site are read by the same listener. The commands
  of the list are in the header row, so they stay on the screen while the console is
  hidden, and the label "Found videos" is gone: the row of the commands starts at the
  left edge of the window.
- "✕" on a card takes one entry out of the list: a queued or running task is
  cancelled and its card goes, a finished card is removed and the file on the
  disk stays, a found card is taken away. The box of the cross is a square with
  the painted mark in the middle, not a rectangle with the mark to the left.
- The settings dialog has its two main buttons, "Save" and "Cancel", in the right
  lower corner, and "Check updates" and "Restart" on the left of the same row. The
  dialog cannot be shrunk to the point where the fields, the selects and the buttons
  show half of a letter.
- An audio source (SoundCloud, an audio-only playlist) is recognized, shown with
  an `MP3` badge, and saved as `.mp3` at the chosen bitrate; audio is never
  muxed into a black video file.
- Google and SoundCloud open the browser as a normal user's browser: no
  "JavaScript disabled / cookies blocked" message, and a Google login stays
  logged in after the program restarts (the profile is kept in the program's
  folder).
- The interface renders correctly in the light and dark themes and at Windows
  scaling 125% and 150%, in English, Russian, Ukrainian, Chinese, French and
  German. The whole window follows the theme: on a machine with the dark mode of
  Windows the light theme is light everywhere — the wall behind the cards, the
  console panel and the status bar as much as the cards.

**Installation and updates**
- `build.ps1` on a clean machine with Python 3.12 and Inno Setup 6 builds
  `PyDownloader-Setup-<version>.exe`.
- The installer installs the application onto a clean Windows 10/11 without
  Python, creates shortcuts, the program launches and works (FFmpeg is found
  in `{app}\bin`).
- Running the installer of a newer version again updates the installation in
  place (same `AppId`), settings are preserved.
- A start that cannot read `settings.json` takes `settings.json.bak`, so the theme,
  the language, the state of the console panel and the downloads folder are not
  lost; every write is atomic, so a killed start cannot leave a half-written file.
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
- The console panel is hidden at startup (the list of cards gets the whole
  window), and "Clear" of the console text is on the screen only while the panel
  is. "✕" on a card cancels a running task of that card, and a finished file on
  the disk is never deleted by it.
- The update is applied by running the installer with `/SILENT`, not by
  replacing files on the fly.
- Before starting, the agent must be given the repository's `OWNER/REPO` and
  a GUID for `AppId` must be generated once.
