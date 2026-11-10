# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification of PyDownloader (spec 7.3).

One directory build: ``dist/PyDownloader/PyDownloader.exe`` with ``_internal``
and the bundled ``bin/ffmpeg.exe`` (copied there by ``build.ps1``). The
Playwright driver (``node.exe`` and the npm package) is collected so the browser
sniffing works without a system install; Chromium itself is downloaded on the
first run by the program.
"""

import os

from PyInstaller.utils.hooks import collect_all

app_dir = os.path.abspath(SPECPATH)
src_dir = os.path.join(app_dir, "src")

datas: list = []
binaries: list = []
hiddenimports: list = []

# Playwright: node.exe, the driver package and the Python bindings.
pd_playwright, pd_binaries, pd_imports = collect_all("playwright")
datas += pd_playwright
binaries += pd_binaries
hiddenimports += pd_imports

for pkg in ("lxml", "cryptography", "httpx"):
    extra_data, extra_binaries, extra_imports = collect_all(pkg)
    datas += extra_data
    binaries += extra_binaries
    hiddenimports += extra_imports

# The pure-Python part of imageio-ffmpeg is the fallback of locate_ffmpeg();
# its own 100 MB ffmpeg binary is not shipped, build.ps1 puts one in bin.
hiddenimports.append("imageio_ffmpeg")

icon_path = os.path.join(app_dir, "assets", "icon.ico")
icon = icon_path if os.path.exists(icon_path) else None
# build.ps1 fills the placeholders of version_info.template.txt into this file.
version_file = os.path.join(app_dir, "build", "version_info.txt")

a = Analysis(
    [os.path.join(src_dir, "pydownloader", "__main__.py")],
    pathex=[src_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Qt modules the program does not use; keeping them would double the size.
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore"],
    noarchive=False,
)

# The hook of imageio-ffmpeg ships its own 100 MB binary; FFmpeg comes from
# bin\ffmpeg.exe, so the copy inside the package is dropped (build.ps1 step 3b).
def _is_packaged_ffmpeg(entry) -> bool:
    return entry[0].replace("\\", "/").startswith("imageio_ffmpeg/binaries")


a.datas = [item for item in a.datas if not _is_packaged_ffmpeg(item)]
a.binaries = [item for item in a.binaries if not _is_packaged_ffmpeg(item)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PyDownloader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_injection=True,
    icon=icon,
    version=version_file if os.path.exists(version_file) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PyDownloader",
)
