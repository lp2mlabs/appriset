# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('release/third-party-licenses', 'third-party-licenses')],
    hiddenimports=['PIL.AvifImagePlugin', 'PIL.WebPImagePlugin'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtNetwork', 'PySide6.QtOpenGL'],
    noarchive=False,
    optimize=0,
)
# Qt uses the ICU API supplied by Windows 10/11. A developer machine may have
# unrelated Poppler/libheif DLLs on PATH; never ship those as Windows runtimes.
from pathlib import PureWindowsPath
a.binaries = [entry for entry in a.binaries
              if not (PureWindowsPath(entry[0]).name.lower().startswith(('api-ms-', 'ext-ms-', 'icudt'))
                      or PureWindowsPath(entry[0]).name.lower() in {'icuuc.dll', 'ucrtbase.dll'})]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='WebImage Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/webimage.ico'],
)
