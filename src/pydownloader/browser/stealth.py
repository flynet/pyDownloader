"""Making the browser look like a browser of a person (spec 7.2).

Playwright starts the browser with a long list of flags that no person uses,
and its Chromium reports ``Chromium`` in the user agent. Sites that watch for a
bot (Google, SoundCloud) read those signals and answer "JavaScript is disabled",
so the flags of a driver are dropped, the automation marker is hidden, and the
user agent is taken from the Chrome that is installed on the machine.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydownloader.i18n import Language

#: Flags Playwright adds for its own automation: they tell a site that a script
#: drives the browser, and the first of them is why Chrome ignores
#: ``--load-extension`` of the ad blocker. They are taken out of the defaults.
IGNORED_DEFAULT_ARGS = [
    "--disable-extensions",
    "--disable-field-trial-config",
    "--disable-dev-shm-usage",
    "--disable-infobars",
    "--disable-stack-profiler",
    "--disable-sync",
    "--force-color-profile=srgb",
    "--metrics-recording-only",
    "--enable-unsafe-swiftshader",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-hang-monitor",
    "--disable-ipc-flooding-protection",
    "--disable-popup-blocking",
    "--disable-prompt-on-repost",
]
#: Flags of a browser a person opened: the automation marker is off, the page is
#: allowed to start playing without a click (the sniffer needs the first frame),
#: and no infobar about the automation is drawn.
STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--autoplay-policy=no-user-gesture-required",
    "--disable-features=AutomationControlled",
]
#: Language code of ``Accept-Language`` and of ``navigator.languages`` for each
#: language of the interface, in the BCP 47 form Chrome writes.
LOCALES: dict[str, str] = {
    "en": "en-US",
    "ru": "ru-RU",
    "zh": "zh-CN",
    "fr": "fr-FR",
    "de": "de-DE",
    "uk": "uk-UA",
}
#: Fallback of the list, used when the language of the interface is not known.
DEFAULT_LOCALE = "en-US"
#: ``navigator.plugins`` of a normal Chrome, in the order Chrome reports them.
CHROME_PLUGINS = [
    "Chrome PDF Plugin",
    "Chrome PDF Viewer",
    "Native Client",
]

#: Script of the automation markers. It runs before the page, so a detector sees
#: the values of a human browser on its first read.
STEALTH_SCRIPT = """
(() => {
  const hide = (object, key, value) => {
    try {
      Object.defineProperty(object, key, { get: () => value });
    } catch (error) {}
  };
  // ``navigator.webdriver`` is true for a browser Playwright started: it is the
  // first thing a bot detector reads, and the answer is "JavaScript is disabled".
  hide(navigator, "webdriver", undefined);
  // The list of languages of a person, not the single one a driver is given:
  // the locale of the interface is first, its base code and English follow.
  hide(navigator, "languages", ["%LOCALE%", "%PRIMARY%", "en-US"]);
  // A driver reports no plugin and no window.chrome object: Chrome has both.
  hide(navigator, "plugins", %PLUGINS%);
  hide(navigator, "hardwareConcurrency", 4);
  hide(navigator, "deviceMemory", 8);
  hide(navigator, "maxTouchPoints", 0);
  window.chrome = window.chrome || { runtime: {}, load: undefined };
  // The permissions of a headless browser answer "denied" for everything.
  const query = window.Permissions && window.Permissions.prototype.query;
  if (query) {
    window.Permissions.prototype.query = function (parameters) {
      const answer = query.call(this, parameters);
      if (parameters && parameters.name === "notifications") {
        return Promise.resolve({ state: "prompt", name: parameters.name });
      }
      return answer;
    };
  }
  // A driver adds a cdp flag on the command line of the browser.
  const flags = navigator.userAgentData ? navigator.userAgentData : null;
  if (flags) {
    hide(flags, "brands", [
      { brand: "Chromium", version: "%MAJOR%" },
      { brand: "Google Chrome", version: "%MAJOR%" },
      { brand: "Not-A.Brand", version: "99" },
    ]);
  }
})();
"""
#: Keys the script fills in, so the user agent and the locale of the run are used.
SCRIPT_KEYS = ("%PLUGINS%", "%MAJOR%", "%LOCALE%", "%PRIMARY%")

_PLUGIN_TEMPLATE = "[" + ", ".join(
    f'{{ name: {name!r}, filename: "", description: "", length: 0 }}' for name in CHROME_PLUGINS
)

#: Major number used when the user agent has no ``Chrome/<number>``: real Chrome
#: masks its build number as ``110.0.0.0``, the form it sends since version 110.
_MAJOR_TEMPLATE = "110"

#: Version of the browser the program ships, read from ``chrome.exe --version``.
_VERSION_PATTERN = re.compile(r"(\d+)")
#: The major number of a user agent, the part a detector compares with its list.
_UA_MAJOR_PATTERN = re.compile(r"Chrome/(\d+)")
#: Timeout of the version request, in seconds: the browser answers at once.
VERSION_TIMEOUT = 5.0
#: The form a user agent has on Windows, with the Chrome version filled in.
UA_TEMPLATE = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/{version} Safari/537.36"
)


def chrome_user_agent(version: str) -> str:
    """User agent of Chrome for the major version Playwright Chromium reports.

    The Chromium of Playwright says ``Chromium`` in its user agent, and Chrome
    masks its build number as ``x.0.0.0`` in the string it sends, so the same
    form is built here: a site sees a Chrome of the same major version.
    """
    match = _VERSION_PATTERN.search(version)
    major = match.group(1) if match else "110"
    return UA_TEMPLATE.format(version=f"{major}.0.0.0")


def browser_version(executable: Path | str) -> str:
    """Version line of the browser, ``""`` when it cannot be read.

    ``chrome.exe --version`` prints the version and exits, so the request is
    cheap and no window is shown (``CREATE_NO_WINDOW`` on Windows).
    """
    command = [str(executable), "--version"]
    flags = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=VERSION_TIMEOUT,
            creationflags=flags,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return (result.stdout or result.stderr).strip()


def locale_of(language: Language) -> str:
    """``Accept-Language`` code Chrome writes for a language of the interface."""
    return LOCALES.get(language, DEFAULT_LOCALE)


def stealth_script(user_agent: str, locale: str) -> str:
    """The init script of the run, filled in with the user agent and the locale.

    ``add_init_script`` runs before every page, so a bot detector reads
    ``navigator`` on a browser that already looks like a normal Chrome. The
    major number is taken from ``Chrome/<major>`` in the user agent, the base
    code from the locale, so the markers the script writes match the browser
    that is launched.
    """
    match = _UA_MAJOR_PATTERN.search(user_agent)
    version = match.group(1) if match else _MAJOR_TEMPLATE
    primary = locale.split("-")[0]
    return (
        STEALTH_SCRIPT.replace("%PLUGINS%", _PLUGIN_TEMPLATE)
        .replace("%MAJOR%", version)
        .replace("%LOCALE%", locale)
        .replace("%PRIMARY%", primary)
    )


def launch_args(extra: Sequence[str], extension: Path | None, anti_bot: bool) -> list[str]:
    """Arguments of the launch: the flags of a driver are added by the stealth.

    ``anti_bot`` is the switch of the whole feature: with it off the flags of
    Playwright are kept as they are, so the browser behaves exactly as before.
    """
    args = list(extra)
    if anti_bot:
        args.extend(STEALTH_ARGS)
    if extension is not None:
        args.append(f"--disable-extensions-except={extension}")
        args.append(f"--load-extension={extension}")
    return args


def stealth_kwargs(anti_bot: bool, locale: str) -> dict[str, Any]:
    """The keyword arguments of ``launch_persistent_context`` for the stealth.

    ``chromium_sandbox`` is turned on so Playwright drops ``--no-sandbox``, the
    flag a normal Chrome never has; the locale is the language of the interface,
    so ``Accept-Language`` and ``navigator.language`` match the user's machine.
    ``ignore_default_args`` is the list of the flags of a driver that Playwright
    adds for itself, taken out of the defaults (spec 7.2).
    """
    kwargs: dict[str, Any] = {"locale": locale, "chromium_sandbox": True}
    if anti_bot:
        kwargs["ignore_default_args"] = list(IGNORED_DEFAULT_ARGS)
    return kwargs


__all__ = [
    "CHROME_PLUGINS",
    "DEFAULT_LOCALE",
    "IGNORED_DEFAULT_ARGS",
    "LOCALES",
    "SCRIPT_KEYS",
    "STEALTH_ARGS",
    "STEALTH_SCRIPT",
    "UA_TEMPLATE",
    "VERSION_TIMEOUT",
    "browser_version",
    "chrome_user_agent",
    "launch_args",
    "locale_of",
    "stealth_kwargs",
    "stealth_script",
]
