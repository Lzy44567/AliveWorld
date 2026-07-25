# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import subprocess

from PyInstaller.utils.hooks import collect_submodules


project = Path(SPECPATH)
dist = project / "aliveworld-ui" / "dist"
icon = project / "assets" / "aliveworld.ico"
if not (dist / "index.html").is_file():
    raise SystemExit("Frontend dist is missing. Run npm run build before PyInstaller.")
if not icon.is_file():
    raise SystemExit("Windows icon is missing. Run tools/build_windows_icon.py before PyInstaller.")

tracked = subprocess.check_output(
    ["git", "-c", "core.quotepath=false", "ls-files", "-z", "--", "data"],
    cwd=project,
).decode("utf-8").split("\0")
template_data = []
for relative in tracked:
    if relative.endswith((".template.yml", ".template.yaml", ".template.json")):
        source = project / relative
        template_data.append((str(source), str(Path(relative).parent)))

datas = [
    (str(project / "VERSION"), "."),
    (str(project / "config.example.yml"), "."),
    (str(project / "system_prompts.yml"), "."),
    (str(dist), "aliveworld-ui/dist"),
    *template_data,
]
hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("openai")
    + collect_submodules("webview")
)

a = Analysis(
    ["desktop_launcher.py"],
    pathex=[str(project)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["torch", "sentence_transformers", "transformers", "PIL"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AliveWorld",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(icon),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="AliveWorld",
)
