"""Entry point of ``python -m pydownloader`` and of ``PyDownloader.exe``."""

import sys

from pydownloader.ui.app import main

if __name__ == "__main__":  # pragma: no cover - the built program runs this
    raise SystemExit(main(sys.argv[1:]))
