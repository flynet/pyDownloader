"""Language of the interface and of the log lines (spec 4.3, 8.1).

Every user-facing text is a key of the catalog in ``locales``, so the program
can run in English, Russian, Chinese, French and German. The language comes
from the settings and is applied once at startup: the text of a widget is
written when the widget is built, so changing the language needs a restart.

``tr("card_download")`` returns the text in the current language; the
placeholders of the template are filled with the keyword arguments:
``tr("quality_fallback", target=1080, chosen=720)``.
"""

from __future__ import annotations

from typing import Literal

from pydownloader.locales import CATALOG

Language = Literal["en", "ru", "zh", "fr", "de"]

#: English is the default, the rest follow it in the order of the settings combo.
DEFAULT_LANGUAGE: Language = "en"
SUPPORTED_LANGUAGES: tuple[Language, ...] = ("en", "ru", "zh", "fr", "de")
#: The name of a language is always written in its own language, so the combo
#: is readable whatever the current language is.
LANGUAGE_NAMES: dict[Language, str] = {
    "en": "English",
    "ru": "Русский",
    "zh": "中文",
    "fr": "Français",
    "de": "Deutsch",
}

#: The language of the running program; the settings apply it at startup.
_current: Language = DEFAULT_LANGUAGE


def set_language(language: Language) -> Language:
    """Switch the language of the texts; the old language is returned."""
    global _current
    previous = _current
    _current = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    return previous


def current_language() -> Language:
    return _current


def tr(key: str, /, **params: object) -> str:
    """The text of ``key`` in the current language, with the parameters filled in.

    ``key`` is positional-only, so a template may take a parameter named ``key``.

    A missing translation falls back to English, so a new string is readable in
    every language before it is translated.
    """
    texts = CATALOG[_current]
    template = texts.get(key)
    if template is None:
        template = CATALOG[DEFAULT_LANGUAGE][key]
    if params:
        template = template.format(**params)
    return template


__all__ = [
    "DEFAULT_LANGUAGE",
    "LANGUAGE_NAMES",
    "SUPPORTED_LANGUAGES",
    "Language",
    "current_language",
    "set_language",
    "tr",
]
