"""Localization tests (spec 4.3, 8.1): the catalog, the language setting, restart."""

from __future__ import annotations

import json
from pathlib import Path
from string import Formatter

import pytest
from PySide6.QtWidgets import QLabel

from pydownloader.config.settings import (
    DEFAULT_MP3_BITRATE,
    Settings,
    load_settings,
    save_settings,
)
from pydownloader.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGE_NAMES,
    SUPPORTED_LANGUAGES,
    current_language,
    set_language,
    tr,
)
from pydownloader.locales import CATALOG
from pydownloader.ui.settings_panel import SettingsDialog

FIELDS = Formatter()


@pytest.fixture(autouse=True)
def english():
    """Each test runs in English and hands the language back to the suite."""
    previous = set_language(DEFAULT_LANGUAGE)
    yield
    set_language(previous)


def placeholders(template: str) -> set[str]:
    """Names of the ``{...}`` fields of a template; plain text is not a field."""
    return {name for _, name, _, _ in FIELDS.parse(template) if name}


def test_every_language_has_every_key():
    keys = set(CATALOG[DEFAULT_LANGUAGE])
    assert keys
    for language in SUPPORTED_LANGUAGES:
        missing = keys - set(CATALOG[language])
        assert not missing, f"{language}: {sorted(missing)}"


def test_placeholders_match_across_languages():
    for key, english in CATALOG[DEFAULT_LANGUAGE].items():
        expected = placeholders(english)
        for language in SUPPORTED_LANGUAGES:
            assert placeholders(CATALOG[language][key]) == expected, f"{key} in {language}"


def test_language_names_are_written_in_their_own_language():
    assert LANGUAGE_NAMES == {
        "en": "English",
        "ru": "Русский",
        "uk": "Українська",
        "zh": "中文",
        "fr": "Français",
        "de": "Deutsch",
    }
    assert set(LANGUAGE_NAMES) == set(SUPPORTED_LANGUAGES)


def test_tr_switches_the_language_and_returns_the_previous():
    assert tr("card_download") == "Download"
    assert set_language("de") == "en"
    assert current_language() == "de"
    assert tr("card_download") == CATALOG["de"]["card_download"]
    set_language("ru")
    assert tr("card_download") == "Скачать"


def test_unknown_language_falls_back_to_english():
    set_language("ru")
    assert set_language("zz") == "ru"
    assert current_language() == DEFAULT_LANGUAGE


def test_a_key_the_catalog_does_not_have_raises():
    with pytest.raises(KeyError):
        tr("no_such_key")


def test_tr_fills_named_parameters():
    set_language("en")
    assert tr("window_queued", title="Clip") == "Queued: Clip"
    # ``key`` is positional-only in tr, so a template can use a field named key
    assert tr("mf_url_recorded", key="/a/seg.ts", url="https://cdn/a/seg.ts?sign=1") == (
        "Recorded URL /a/seg.ts -> https://cdn/a/seg.ts?sign=1"
    )


def test_ukrainian_switches_the_texts():
    """The console, the tray and the settings read the Ukrainian catalog (spec 4.3)."""
    assert set_language("uk") == DEFAULT_LANGUAGE
    assert current_language() == "uk"
    assert tr("window_open_browser") == CATALOG["uk"]["window_open_browser"]
    assert tr("settings_audio_only") == CATALOG["uk"]["settings_audio_only"]
    assert tr("tray_quit") == CATALOG["uk"]["tray_quit"]
    set_language("ru")
    assert tr("window_open_browser") == CATALOG["ru"]["window_open_browser"]


def test_settings_store_the_language(tmp_path: Path):
    path = tmp_path / "settings.json"
    save_settings(Settings(language="fr"), path)
    assert load_settings(path).language == "fr"


def test_settings_fall_back_to_english(tmp_path: Path):
    path = tmp_path / "settings.json"
    save_settings(Settings(), path)
    body = json.loads(path.read_text(encoding="utf-8"))
    # an old file has no language at all
    body.pop("language")
    path.write_text(json.dumps(body), encoding="utf-8")
    assert load_settings(path).language == DEFAULT_LANGUAGE
    # an edited file has a value that is not a language
    body["language"] = "zz"
    path.write_text(json.dumps(body), encoding="utf-8")
    assert load_settings(path).language == DEFAULT_LANGUAGE
    body["language"] = 7
    path.write_text(json.dumps(body), encoding="utf-8")
    assert load_settings(path).language == DEFAULT_LANGUAGE
    assert load_settings(tmp_path / "absent.json").language == DEFAULT_LANGUAGE


def test_a_damaged_settings_file_is_read_from_the_backup(tmp_path: Path):
    """A settings file that cannot be read falls back to ``settings.json.bak`` (spec 7.4).

    Every start of the program writes the settings, so a start that cannot read
    them loses the theme, the language, the state of the console panel and the
    folder of the videos. The backup is the file the previous save kept.
    """
    path = tmp_path / "settings.json"
    save_settings(Settings(theme="dark", console_open=False, language="ru"), path)
    save_settings(Settings(theme="light", console_open=True, language="ru"), path)
    assert load_settings(path).theme == "light"
    # A half-written file: the settings of the last good save come back.
    path.write_text("{ not json", encoding="utf-8")
    back = load_settings(path)
    assert back.theme == "dark"
    assert back.console_open is False
    assert back.language == "ru"
    # A missing file with no backup is the first start: the defaults.
    path.unlink()
    assert load_settings(path).theme == "dark"


def test_the_save_leaves_no_temp_file(tmp_path: Path):
    """The settings are written in one move, so a killed start cannot leave a half file."""
    path = tmp_path / "settings.json"
    save_settings(Settings(theme="dark"), path)
    save_settings(Settings(theme="light"), path)
    assert not (tmp_path / "settings.json.new").exists()
    assert (tmp_path / "settings.json.bak").is_file()
    assert load_settings(path).theme == "light"
    # The backup is the file of the previous save, not the current one.
    kept = json.loads((tmp_path / "settings.json.bak").read_text(encoding="utf-8"))
    assert kept["theme"] == "dark"


def test_settings_keep_the_browser_choice(tmp_path: Path):
    path = tmp_path / "settings.json"
    save_settings(Settings(browser_name="chromium", user_agent="Dev 1.0", anti_bot=False), path)
    back = load_settings(path)
    # The browser, the user agent and the stealth are saved as the user set them.
    assert back.browser_name == "chromium"
    assert back.user_agent == "Dev 1.0"
    assert not back.anti_bot
    assert back.ad_blocker
    # an edited file names a browser that does not exist: launch the spec order
    body = json.loads(path.read_text(encoding="utf-8"))
    body["browser_name"] = "opera"
    path.write_text(json.dumps(body), encoding="utf-8")
    assert load_settings(path).browser_name == "auto"


def test_settings_keep_the_audio_mode(tmp_path: Path):
    path = tmp_path / "settings.json"
    save_settings(Settings(mp3_bitrate=128, audio_only=True, target_height=720), path)
    back = load_settings(path)
    # the audio mode, the bitrate and the quality preset are saved as the user set them
    assert back.mp3_bitrate == 128
    assert back.audio_only
    assert back.target_height == 720
    # an edited file names a bitrate FFmpeg does not accept: the middle choice
    body = json.loads(path.read_text(encoding="utf-8"))
    body["mp3_bitrate"] = 999
    path.write_text(json.dumps(body), encoding="utf-8")
    assert load_settings(path).mp3_bitrate == DEFAULT_MP3_BITRATE


def test_settings_dialog_shows_the_languages(qtbot):
    dialog = SettingsDialog(Settings())
    qtbot.addWidget(dialog)
    codes = [dialog.language_box.itemData(i) for i in range(dialog.language_box.count())]
    assert codes == list(SUPPORTED_LANGUAGES)
    names = [dialog.language_box.itemText(i) for i in range(dialog.language_box.count())]
    assert names == [LANGUAGE_NAMES[code] for code in SUPPORTED_LANGUAGES]
    hints = [label.text() for label in dialog.findChildren(QLabel)]
    assert tr("settings_restart_hint") in hints
    # a restart is needed only when the choice differs from the running language
    assert dialog.restart_button.isEnabled() is False
    dialog.language_box.setCurrentIndex(dialog.language_box.findData("ru"))
    assert dialog.restart_button.isEnabled() is True


def test_restart_button_saves_the_language_for_the_next_start(qtbot):
    settings = Settings()
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    dialog.language_box.setCurrentIndex(dialog.language_box.findData("de"))
    with qtbot.waitSignal(dialog.restart_requested):
        dialog._restart()
    assert settings.language == "de"
    assert current_language() == "en"  # applied only after the program restarts


def test_restart_command_runs_the_program_again():
    from pydownloader.ui.app import restart_command

    exe, args = restart_command()
    assert exe
    assert args in ([], ["-m", "pydownloader"])


def test_no_text_of_the_catalog_needs_a_glyph_the_ui_font_lacks():
    """The marks of the buttons are painted, not typed (spec 4.1 p.1, 4.3 p.2).

    The Windows font of the buttons does not carry the gear and the cross, so a
    label with these code points shows a box. The catalog has no such character,
    every mark is drawn by ``button_icons``.
    """
    missing_glyphs = "⚙✕✓▶"
    for language, catalog in CATALOG.items():
        for key, text in catalog.items():
            for char in missing_glyphs:
                assert char not in text, f"{key} in {language}: {char}"


def test_the_browser_starting_tip_is_in_every_language():
    # The one browser button is disabled while it launches, and says so (spec 4.3 p.2).
    for language in SUPPORTED_LANGUAGES:
        assert CATALOG[language]["window_browser_starting"]


def test_the_tray_has_one_item_for_the_browser_window():
    # The item of the menu is the button of the window: it changes its text, so the
    # menu does not carry the two keys of the old pair (spec 4.3).
    for language in SUPPORTED_LANGUAGES:
        assert "tray_open_browser" not in CATALOG[language]
        assert "tray_close_browser" not in CATALOG[language]
