# Changelog

The format is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning is [SemVer](https://semver.org/). A release is a `vX.Y.Z` tag
on `main`.

## [0.4.9] - 2026-11-12

### Added
- **A video card shows the still of the video** (spec 4.1): the picture stands on
  the left of the text, so a found video is recognized by its frame before its name
  is read. The address of the still is read from the page itself — the `og:image` of
  the markup, the structured data of the page, the picture of a tweet card, the
  `poster` of the player, the frame the player shows right now — so the card shows
  the frame the person saw in the browser; every frame of the page is searched,
  because a player often lives in an iframe, and a YouTube video takes the cover of
  its id. The bytes are fetched by Qt's network manager with the `Referer`, the
  `User-Agent`, the language and the cookies of the page, the window is never
  blocked, and the card is added only after the picture has arrived and has been
  decoded: the list never shows a card with an empty frame. The request names only
  the picture formats Qt reads (AVIF is left out on purpose: a host that sees it
  switches to AVIF, which this Qt cannot decode, and the frame would stay empty). A picture that did not
  arrive in time or is not an image is skipped — the card is added without it, a
  found source is never lost to a preview. An audio source (MP3) has no still: its
  card starts with the name of what is downloaded.

### Fixed
- **The program no longer stops with «entry point OPENSSL_LH_set_thunks not found»**
  on a machine with Miniconda or Anaconda (spec 4.1): folders that hold an OpenSSL of
  another build are kept out of the DLL search, so Qt cannot load it next to the
  copy of Python, a DLL that still fails to load no longer shows a system message
  box, and Qt uses Schannel, the TLS of Windows. Video stills load on such a machine
  instead of breaking the start with a dialog.

## [0.4.8] - 2026-11-11

### Added
- **A long title of a card is broken into lines** (spec 4.1 p.1): the card is as wide
  as the list of cards, and the list is as wide as the window, so a long page title
  takes the lines of its words the card can hold (two of them), the letters that do
  not fit are marked by the sign of elision, the whole title is read in the tooltip,
  and the card grows by height, never by width. The same rule keeps the link, the
  quality line and the path of a saved file inside the card: a link and a path are
  one word, so the middle of the line is kept for them and the end of the file name
  stays on the card. Making the window narrow builds the lines of every card again
  for the new width, so the list of cards never gets a horizontal scrollbar.
- **The tooltip of the tray icon keeps the percent of every task** (spec 4.2 p.7):
  Windows keeps the tooltip of the icon in a buffer of 128 characters, so a long name
  of a downloading file is shortened — the budget of the text is spent on the report
  of a line (the percent, the speed, the time left) first, the names take the rest by
  the same share, the cut is marked by the sign of elision, and the lines of a long
  queue that still do not fit go from the end, so the tooltip of the icon ends with
  the percent of a task, not with the tail of a name.
- The ampersand of a title is a letter of the name: the label of the title of a card
  is written with no flag of a mnemonic, so "Rock & Roll" keeps its `&` and the
  letter after it is not underlined.

### Changed
- The whole path of a saved file is read in the tooltip of its card.

## [0.4.7] - 2026-11-11

### Added
- **Three theme palettes in the theme row of the settings** (spec 4.3 p.3): «Cartoons»,
  «Neon» and «Pink», named by their style, standing between the dark and the light
  themes and the system one. Every color of a theme is a key of its palette, so the
  new themes color the same parts of the interface as the two themes that were
  before: the wall of the window and the wall of the cards, the frames of the cards
  and of the fields, the main text and the secondary text, the buttons, the yellow
  of "Clear downloaded", the red of "Clear all", the bar of a running file and the
  bar of a finished file, the badges of HLS, DASH, MP4, YouTube and MP3, the console
  panel and its text, the fields, the lists, the check boxes, the menus, the scroll
  bars, the tabs and the status bar. The names of the themes are translated into the
  six languages of the catalog.
- **The letters of a theme are checked by the ratio of contrast**: the text on the
  wall of the window, the letters of the buttons, the letters of a badge and the log
  on the wall of the console are at least 4.0 apart (WCAG AA), so the accent of a
  bright palette is taken to the darker edge of its family and the letters stay
  readable.

### Changed
- The theme is applied to the window **without a restart**: the marks of the buttons
  and of the cards, the badge of a card and the bar of a finished card are painted
  once, so they are drawn again with the colors of the theme the user picks in the
  settings; the wall behind the cards, the console panel, the fields and the menus
  take the new palette at the same moment. The marks of the tray menu are repainted
  as well: the menu is built once, with the theme the program started with
  (spec 4.3 p.4).

## [0.4.6] - 2026-11-11

### Changed
- **«Open browser» and «Close browser» are one button** (spec 4.1 p.7, 4.3): the
  button in the header says the action it does, so its text, its tip and its mark
  follow the browser thread — "Open browser" with the arrow of the window while
  the browser is down, "Close browser" with the cross in the title bar while it
  runs. The button is clickable in both states, and it is disabled only while the
  browser is being resolved and launched (the first launch can download Chromium
  and ask the question in a dialog box), so a second press cannot start a second
  thread of Playwright; during the launch the tip says the browser is starting.
  One item of the tray menu is the same button: its text changes with the state.
- The old pair of buttons and the pair of tray items are gone: the messages "the
  browser is already open" and "the browser is not running" stay as the safety net
  of the actions.
- **The console section is one block that appears with its row** (spec 4.2 p.5):
  the row of the buttons and the panel of the log are one widget, so hidden the
  window shows neither the row nor the panel, the list of cards fills the window
  and there is no divider between the sections at all — the handle of the splitter
  is 0 px. "Show console" / "Hide console" is **one button of the top row** with
  the same rule as the browser button: its text, its tip and its mark follow the
  state, and the window opens with the button saying "Hide console" when the panel
  was left on the screen.
- "Show console" and "Open download folder" move to the header of the window, next
  to "Settings": the row of the console is on the screen only with the panel, and
  both commands are needed while the console is hidden. "Open log file" goes to the
  row of the console, with "Clear": the log and the text of the panel belong to the
  console, so the two buttons appear with the panel and go away with it. The row of
  the console has two buttons.
- **"Clear downloaded" and "Clear all" take the colors of the theme** and stand in the
  **right corner of the top row** of the window: "Clear downloaded" is **yellow**
  (`warn`), "Clear all" is **red** (`danger`), so the two commands of the list are told
  apart by the color in the dark theme, the light theme and the screenshots, and the
  mark of a button takes the color of its text. The commands of the window — the
  browser, the console, the folder, the settings — stand in the **left corner** of the
  same row, where the row of the label "Found videos" used to be; the clears are not
  the console, so they stay on the screen while the console is hidden.
- **The main buttons of the settings dialog are in the right lower corner**: "Save"
  and "Cancel" stand at the right end of the bottom row ("Save" is the button of
  Enter, "Cancel" is the last button of the row), and the secondary commands "Check
  updates" and "Restart" stand on the left. Before, "Save" and "Cancel" were on the
  left, where a person does not look for the buttons that finish a dialog. The four
  buttons are attributes of the dialog (`save_button`, `cancel_button`,
  `update_check_button`, `restart_button`), each with its painted mark.
- **The settings dialog cannot be squeezed under the height its rows need**: every
  field, select, checkbox and button gets the minimum height of its own `sizeHint`
  (the height its font and text ask for), the layout gets the minimum height of all
  the rows, and the smallest dialog shows every row readable. A squeezed row showed
  15 px of a 26 px field, so the text was visible only in half. `MIN_DIALOG_HEIGHT`
  (420 px) stays the least height the dialog gets, and the floor of the rows raises
  it when the rows need more.

### Added
- **The marks of the buttons are painted** (`ui/button_icons.py`, spec 4.1 p.1,
  4.3 p.2): every button of the window, of the cards and of the settings dialog
  carries a 16 px picture drawn with `QPainter` — the browser window with the
  globe, the list with the cross, the list with the check, the gear of the
  settings, the chevron of "Hide console", the terminal of "Show console", the
  folder, the page of the log, the arrow to the disk, the triangle of a player,
  the arc of "Retry" and the check of "Save". The characters "⚙" and "✕" are not
  in the UI font of Windows, so the label "⚙ Settings" showed a box; the painted
  mark is the same picture in the dark theme, the light theme, the system theme,
  in every language and in the screenshots of the README. The color is the color
  of the text of the button: white on the accent, white on the red of "Clear all",
  the dark of the theme on the yellow of "Clear downloaded", the text color of the
  theme on a button of the panel background and in the tray menu, the text color of
  the palette when the theme is the system one. The "✕" of a card and the cross of
  "Cancel" are the same drawing, the cross of the card is moved out of `ui/card.py`
  to the new module.
- The buttons of a card keep their text next to the mark (`ToolButtonTextBesideIcon`):
  a `QToolButton` shows the icon only by default, and the labels of "Cancel",
  "Open file" and "Retry" would disappear. A button with no text is left as the icon
  only, and the "✕" on the right of a card is a fixed square of 26 px (the icon of
  16 px, the padding of 4 px, the border of 1 px), so the box is not stretched into
  a rectangle with the mark shifted to the left of it.
- **The window carries the address of the video** (`url_input` and `go_button`, spec
  4.2 p.4): the link is pasted in the second row of the header, and "Go" — or Enter in
  the field — opens the browser on that page. With the browser down, the thread is
  launched on the address of the field (`start_browser` takes the `url` argument, the
  browser button shows "Close browser" when the window is up); with the browser
  running, `SnifferThread.go(url)` puts the address in the queue of the pump loop
  (`NavigateRequest` in `browser/events.py`), which owns the page object and opens the
  page there, so the response listener reads the manifests of the new site the same way
  it reads any page. A bare domain gets `https://`, a long link is read in the tooltip
  of the field, the page is remembered for "Open browser", an empty field answers that
  the field is empty, and a link equal to the page the browser is on does not reload
  it. The row has its own painted mark: the arrow going into a frame (`go_icon`).

### Fixed
- **The test suite no longer rewrites the settings of the user** (spec 7.4): a
  window saves its settings on every toggle of the console, on the Apply of the
  dialog and on the close, and the file it writes is
  `%APPDATA%/PyDownloader/settings.json` — the file of the user. A window of the
  UI tests is built with `Settings(download_dir=tmp_path)`, so every run of the
  suite left the downloads folder of the developer as the temp folder of one test,
  and the installed program started with that temp path after a reinstall. The
  suite now runs with its own `%APPDATA%`, `%LOCALAPPDATA%` and temp folder (the
  session fixture of `conftest.py`), so it writes only in the test tree: the
  settings, the browser profile, the logs and Chromium of the tests never touch
  the folders of the user. The tool of the screenshots does the same (`isolate_app_data`
  of `config/paths.py`, the rule of the tests and of the tool is one function), so a
  run of `tools/make_screenshots.py` cannot rewrite the file of the user either.
- **The settings are written atomically and a damaged file is read from the
  backup** (spec 7.4): the program writes `settings.json` on every start, so a
  start that cannot read the file loses the theme, the language, the state of the
  console panel and the folder of the videos, and the next start writes the
  defaults back. `save_settings` now writes `settings.json.new` in the same folder,
  moves it in one call and keeps the file that was there as `settings.json.bak`;
  `load_settings` reads the backup when the main file is missing or damaged.
- **The whole window follows the chosen theme** (spec 4.3): a widget with no rule of
  its own paints the palette, and the palette Qt reads from Windows is the palette of
  the system dark mode, not the theme of the program. The wall behind the list of
  cards stayed dark in the light theme on a machine with the dark mode of Windows.
  `apply_palette` now sets the palette of the application to the colors of the chosen
  theme (window, base, button, text, accent), and the container of the cards gets its
  own rule in the stylesheet (`#cardArea`), so the list of cards, the console panel,
  the status bar and every widget that paints the palette are light in the light theme
  and dark in the dark theme. The `system` choice keeps the palette of the style.
- **The balloon and the sound report the end of a batch of downloads** (spec 4.2
  p.7): the report is sent once, when the queue is empty and every task of the
  batch is finished, and a batch is at least two files (`MIN_BATCH`). A single
  download gives no balloon and no sound, the queue does not report after every
  file of a batch, and removing a card, cancelling a task, clearing the list and a
  task that ends with an error are not finished downloads at all — the icon of the
  tray only goes back to the white arrow. The counter is the counter of one batch:
  it is reset when the queue was empty before the next download, so a row of single
  downloads never becomes the report of a finished batch.

### Tests
- The one browser button is a toggle: it emits the request of the action in both
  states, the text, the tip and the icon follow the thread, the button is disabled
  for the time of the launch and gets back its own tip, the state of the window is
  kept across the launch; `toggle_browser` closes a running thread and opens the
  browser of the last page, and the launch records the disable of the button.
- Every button of the window, of a card and of the settings dialog carries a
  painted mark: the icon is not empty, and the picture covers pixels; the
  `QToolButton` of a card keeps the text beside the icon. The two states of the
  browser button are one window: the frame, the title bar and the globe are the
  same picture, the marks follow the theme (white on the accent, the text color on
  the panel). A `QToolButton` with no text is left as the icon only, so the "✕" of
  a card is a square with the mark in the middle, and "Cancel" keeps its text.
- The catalog has no character the UI font lacks, the tip of the launch is in the
  six languages, the tray has no pair of browser keys, the menu has six items.
- The console section is tested as one block: hidden, the row, the panel, "Clear"
  and "Open log file" are all off the screen, the sizes of the splitter are
  `[1000, 0]` and the handle is 0 px; shown, the row and the panel come back
  together and the handle gets its 6 px. "Show console" / "Hide console" and
  "Open download folder" are children of the header widget, "Open log file" is a
  child of the console section, and the top button says "Hide console" from the
  first frame when the settings open the window with the panel.
- The header has two rows: the top row is the browser, the console, the folder and
  the settings in the left corner, and "Clear downloaded" on the left and "Clear all"
  on the right in the right corner of the same row; the row is on the screen while the
  console is hidden, and the first button of the row starts at the left edge of the
  window. The object names are `clearDownloaded` and `clearAll`, the yellow and the
  red are keys of both themes in the stylesheet, the mark of the yellow takes the
  dark text color of the theme and the mark of the red takes white.
- The row under the commands is the field of the address and the "Go" button: the
  field is under the row, the button is at its right end, the placeholder is the text
  of the locale, and a long link is read in the tooltip. "Go" sends the address to the
  running browser (`FakeSniffer.go` records the list of navigated pages) and remembers
  it as the page of the browser; the same link as the page of the browser answers with
  the message and does not reload; with the browser down the signal carries the
  address, and a bare domain comes with `https://`; an empty field says the field is
  empty and the browser is not asked.
- The pump loop of the sniffer thread opens the page of the queue: `go(url)` puts the
  address in the queue, and a run of `_drain` with a fake context opens the page of the
  browser on that address and keeps it as `last_url` (the page object belongs to the
  event loop of the thread, so the GUI thread never touches it).
- The launch with the address of the field: `launch_sniffer` gets the address as the
  start page, the address is written as the last page of the window, the browser button
  is disabled for the launch (`[True, False]`), and the line of the page goes to the
  console.
- The settings a window writes stay in the tree of the tests: the file is inside
  the redirected app data of the session, and the folder it records is the folder
  of the test. A settings file with a temp folder asks the dialog again, starting
  at the downloads of the user, and does not create that temp folder.
- The settings survive a damaged file: a corrupt `settings.json` is read from
  `settings.json.bak`, the backup is the file of the previous save, the write leaves
  no `settings.json.new` behind, and the file a start writes back keeps the theme,
  the language, the state of the console panel and the folder of the videos.
- The balloon and the sound follow the batch: two finished downloads give one
  balloon for the whole batch, the first of the two gives nothing; a single
  download gives no balloon and no sound, and neither does a row of single
  downloads; removing the cards of a list, clearing the list and a task that
  failed give no balloon and no sound. In every one of these cases the arrow of the
  tray goes back to white.
- The palette of the application is the palette of the theme: `Window`/`Base`/`Button`
  are the colors of the theme in the light theme and in the dark theme, and the
  `system` choice gets the palette of the style. The wall behind an empty list of
  cards is the background of the theme in both themes, checked by the pixels of the
  widget.
- The rule of the isolation is one: `isolate_app_data` puts the settings, the data
  folders, the Chromium folders and the temp folder of a run inside one temp tree,
  so the tool of the screenshots and the suite cannot write the folders of the user.
- The bottom row of the settings dialog is tested by the geometry of its buttons:
  "Save" and "Cancel" are in the same row and to the right of "Check updates" and
  "Restart", "Save" is the button of Enter, "Cancel" is the last button of the row.
- The dialog cannot be squeezed: the minimum height of a field, a select and a button
  is the height of its `sizeHint`, the minimum height of the dialog is at least the
  height of its rows, and after a request for a smaller dialog every row keeps the
  height the font asks for.

## [0.4.5] - 2026-11-11

### Added
- **The tray icon is the icon of the program**: the dark rounded square, the arrow
  pointing down, the line of the tray under it. The same drawing (`ui/app_icon.py`)
  makes `assets/icon.ico`, the pictures of the setup wizard and the icon of the
  title bar, so the desktop, the installer and the notification area are one style
  (spec 7.3). Only the colour of the arrow marks the state: **white** when the
  queue is empty, **green** while a download runs, and the arrow jumps up and down
  over the line of the tray (the frames of a timer).
- **The tooltip of the tray icon is the queue of the program** (spec 4.2 p.7):
  hovering over the icon, without clicking, shows the files that are downloading
  with the name, the percent, the speed, the time left, and the number of the
  tasks waiting in the queue. The text is rewritten at most once a second (the
  tooltip of Windows is a heavy call), the start and the end of a task at once; a
  source of unknown size shows the percent only.
- The progress bar of a card turns **green** when the file is on the disk, so the
  end of a download is seen at a glance (spec 4.1 p.3); a running download keeps
  the accent colour of the theme.

### Tests
- The tray icon is the picture of the program icon (pixel by pixel), only the
  colour of the arrow changes, the line of the tray does not move while the arrow
  jumps, the white arrow is back when the queue is empty.
- The tooltip of the tray lists the running files with the percent, the speed and
  the time left, the queued count, and the file is taken out of the tooltip when
  the card cross cancels it.
- The bar of a finished card is green, the bar of a running and of a cancelled one
  is not.

## [0.4.4] - 2026-11-11

### Added
- Every card has a **«✕»** on the right, in every state: it takes this one entry
  out of the list. A queued or running task is cancelled first and its card goes
  with it, a finished card is removed and the file on the disk stays, a found
  card is simply taken away. The line is written to the console ("Cancelled and
  removed from the list: {title}", "Removed from the list: {title}"), so the
  console and the tray report what happened while the window was hidden. The
  cross is painted by hand: the text glyph «✕» (U+2715) is not in the UI font of
  Windows, so a label shows a box. The cross works on one card, "Clear all" and
  "Clear downloaded" work on the whole list.

### Changed
- The console panel is **hidden at startup**: from the first start the list of
  found videos gets the whole window, and the row of buttons shows «Show
  console».
- The «Clear» button of the console text is shown only while the console panel
  is on the screen: there is nothing to clear while the panel is hidden.

### Tests
- The card cross (a found entry, a running task cancelled, a finished file kept,
  the painted icon), the console panel hidden at startup and the «Clear» button
  with the panel are covered.

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
- The browser is not launched when the program starts: the program opens its own
  window only, and the browser window appears when the user presses «Open
  browser». The console says it at startup, in the language of the interface.
- The balloon that explains the tray is shown at startup (the first run with the
  tray on), not only when the window is hidden: the tray is where the window is
  brought back and where the program is quit. "X" in the title bar hides the
  window to the tray, the downloads keep running, and "Exit" in the tray menu is
  the only way to quit.

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
- The console panel (hidden state, splitter sizes, settings round-trip, the text
  of the button), the tray menu with the console item, the colour of the tray icon
  and the frames of the animation, and the balloon + sound of the finished
  downloads are covered. The flags that hide the banners are checked, and the
  startup path is checked to leave the browser closed.

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
