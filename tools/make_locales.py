"""Creates the skeleton files of the locale catalog: one file per group and language.

Run once: ``uv run python tools/make_locales.py``. Every file defines
``TEXTS``; the translators fill the dictionaries, the keys of ``<group>_en.py``
are the reference.
"""

from __future__ import annotations

import sys
from pathlib import Path

GROUPS = ("ui", "browser", "download", "manifest", "update")
LANGUAGES = ("en", "ru", "zh", "fr", "de")
OUT = Path("src") / "pydownloader" / "locales"


def skeleton(group: str, lang: str) -> str:
    return (
        f'"""{lang} texts of the {group} group: the keys come from {group}_en.py.\n\n'
        "TEXTS: dict[str, str] = {}\n"
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    created = 0
    for group in GROUPS:
        for lang in LANGUAGES:
            path = OUT / f"{group}_{lang}.py"
            if not path.exists():
                path.write_text(skeleton(group, lang), "utf-8")
                created += 1
    print(f"created {created} files in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
