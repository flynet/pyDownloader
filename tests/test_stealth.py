"""Anti-bot stealth of the launch (spec 7.2): flags, user agent, init script."""

from __future__ import annotations

from pathlib import Path

from pydownloader.browser.stealth import (
    IGNORED_DEFAULT_ARGS,
    STEALTH_ARGS,
    browser_version,
    chrome_user_agent,
    launch_args,
    locale_of,
    stealth_kwargs,
    stealth_script,
)


def test_the_automation_marker_is_turned_off():
    args = launch_args(["--no-first-run"], None, True)
    # navigator.webdriver is true for a driver: this flag is the way to hide it.
    assert "--disable-blink-features=AutomationControlled" in args
    assert all(flag in args for flag in STEALTH_ARGS)


def test_the_flags_a_driver_leaves_are_dropped_from_the_defaults():
    # --disable-extensions is why Chrome ignores --load-extension of the blocker.
    assert "--disable-extensions" in IGNORED_DEFAULT_ARGS
    assert "--metrics-recording-only" in IGNORED_DEFAULT_ARGS


def test_the_banners_a_person_never_sees_are_hidden():
    # Chrome for Testing writes "this build is for automated testing" under the
    # address bar, Chrome and Edge write "you are using an unsupported
    # command-line flag". --disable-infobars stays in the defaults (only the
    # Chrome of Testing answers to it), --test-type is the flag Chrome honours.
    args = launch_args([], None, True)
    assert "--test-type" in args
    assert "--disable-infobars" not in IGNORED_DEFAULT_ARGS


def test_stealth_off_keeps_the_flags_of_playwright():
    assert launch_args(["--no-first-run"], None, False) == ["--no-first-run"]


def test_extension_flags_come_after_the_stealth_args():
    args = launch_args(["--start-maximized"], Path("uBlock"), True)
    marker = args.index("--disable-blink-features=AutomationControlled")
    load = args.index("--load-extension=uBlock")
    assert load > marker
    assert "--disable-extensions-except=uBlock" in args


def test_chrome_user_agent_of_the_chromium_version():
    agent = chrome_user_agent("Chromium 156.0.3304.0")
    # The word Chromium in the string is the second signal a detector reads.
    assert "Chrome/156.0.0.0" in agent
    assert "Chromium" not in agent
    assert agent.startswith("Mozilla/5.0 (Windows NT 10.0")


def test_a_version_that_is_not_a_number_falls_back_to_the_masked_form():
    assert "Chrome/110.0.0.0" in chrome_user_agent("Chromium dev build")


def test_the_locale_is_the_language_of_the_interface():
    assert locale_of("en") == "en-US"
    assert locale_of("ru") == "ru-RU"
    assert locale_of("zh") == "zh-CN"
    assert locale_of("uk") == "uk-UA"
    # An unknown language: the browser answers in English, as the interface does.
    assert locale_of("zz") == "en-US"


def test_the_sandbox_flag_of_a_driver_is_taken_out():
    kwargs = stealth_kwargs(True, "ru-RU")
    assert kwargs["chromium_sandbox"] is True
    assert kwargs["locale"] == "ru-RU"
    assert "--disable-extensions" in kwargs["ignore_default_args"]


def test_stealth_off_leaves_the_defaults_of_playwright():
    assert stealth_kwargs(False, "en-US") == {"locale": "en-US", "chromium_sandbox": True}


def test_the_script_hides_the_markers_a_detector_reads():
    script = stealth_script("Mozilla/5.0 Chrome/156.0.0.0", "ru-RU")
    assert "navigator" in script
    assert "webdriver" in script
    assert "window.chrome" in script
    # The templates are filled in with the version of the user agent.
    assert "%PLUGINS%" not in script
    assert "%MAJOR%" not in script
    assert "Chrome PDF Plugin" in script
    assert "156" in script
    # The locale of the interface is the first language the detector reads.
    assert '"ru-RU"' in script
    assert '"ru"' in script
    assert "%LOCALE%" not in script
    assert "%PRIMARY%" not in script


def test_the_version_of_a_file_that_is_not_a_browser(tmp_path: Path):
    fake = tmp_path / "chrome.exe"
    fake.write_bytes(b"MZ")
    # A browser that cannot be started: the user agent stays the default one.
    assert browser_version(fake) == ""
