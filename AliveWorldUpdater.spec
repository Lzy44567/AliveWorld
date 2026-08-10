# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project = Path(SPECPATH)
icon = project / "assets" / "aliveworld.ico"
if not icon.is_file():
    raise SystemExit("Windows icon is missing. Run tools/build_windows_icon.py before PyInstaller.")

a = Analysis(
    ["updater_main.py"],
    pathex=[str(project)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AliveWorldUpdater",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(icon),
)
