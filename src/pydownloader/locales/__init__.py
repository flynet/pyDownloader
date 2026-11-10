"""The catalog of texts: group per module, file per language.

The keys of ``<group>_en.py`` are the reference; a key missing in another
language falls back to English (see ``pydownloader.i18n``). The test
``test_i18n.py`` checks that every language has every key.
"""

from pydownloader.locales.browser_de import TEXTS as BROWSER_DE
from pydownloader.locales.browser_en import TEXTS as BROWSER_EN
from pydownloader.locales.browser_fr import TEXTS as BROWSER_FR
from pydownloader.locales.browser_ru import TEXTS as BROWSER_RU
from pydownloader.locales.browser_uk import TEXTS as BROWSER_UK
from pydownloader.locales.browser_zh import TEXTS as BROWSER_ZH
from pydownloader.locales.download_de import TEXTS as DOWNLOAD_DE
from pydownloader.locales.download_en import TEXTS as DOWNLOAD_EN
from pydownloader.locales.download_fr import TEXTS as DOWNLOAD_FR
from pydownloader.locales.download_ru import TEXTS as DOWNLOAD_RU
from pydownloader.locales.download_uk import TEXTS as DOWNLOAD_UK
from pydownloader.locales.download_zh import TEXTS as DOWNLOAD_ZH
from pydownloader.locales.manifest_de import TEXTS as MANIFEST_DE
from pydownloader.locales.manifest_en import TEXTS as MANIFEST_EN
from pydownloader.locales.manifest_fr import TEXTS as MANIFEST_FR
from pydownloader.locales.manifest_ru import TEXTS as MANIFEST_RU
from pydownloader.locales.manifest_uk import TEXTS as MANIFEST_UK
from pydownloader.locales.manifest_zh import TEXTS as MANIFEST_ZH
from pydownloader.locales.ui_de import TEXTS as UI_DE
from pydownloader.locales.ui_en import TEXTS as UI_EN
from pydownloader.locales.ui_fr import TEXTS as UI_FR
from pydownloader.locales.ui_ru import TEXTS as UI_RU
from pydownloader.locales.ui_uk import TEXTS as UI_UK
from pydownloader.locales.ui_zh import TEXTS as UI_ZH
from pydownloader.locales.update_de import TEXTS as UPDATE_DE
from pydownloader.locales.update_en import TEXTS as UPDATE_EN
from pydownloader.locales.update_fr import TEXTS as UPDATE_FR
from pydownloader.locales.update_ru import TEXTS as UPDATE_RU
from pydownloader.locales.update_uk import TEXTS as UPDATE_UK
from pydownloader.locales.update_zh import TEXTS as UPDATE_ZH

#: Language -> key -> text.
CATALOG: dict[str, dict[str, str]] = {
    "en": {**UI_EN, **BROWSER_EN, **DOWNLOAD_EN, **MANIFEST_EN, **UPDATE_EN},
    "ru": {**UI_RU, **BROWSER_RU, **DOWNLOAD_RU, **MANIFEST_RU, **UPDATE_RU},
    "uk": {**UI_UK, **BROWSER_UK, **DOWNLOAD_UK, **MANIFEST_UK, **UPDATE_UK},
    "zh": {**UI_ZH, **BROWSER_ZH, **DOWNLOAD_ZH, **MANIFEST_ZH, **UPDATE_ZH},
    "fr": {**UI_FR, **BROWSER_FR, **DOWNLOAD_FR, **MANIFEST_FR, **UPDATE_FR},
    "de": {**UI_DE, **BROWSER_DE, **DOWNLOAD_DE, **MANIFEST_DE, **UPDATE_DE},
}

__all__ = ["CATALOG"]
