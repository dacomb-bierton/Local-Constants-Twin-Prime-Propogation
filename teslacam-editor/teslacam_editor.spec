# PyInstaller spec: build a single-folder Windows distribution with the bundled ffmpeg.
#   pip install pyinstaller
#   pyinstaller teslacam_editor.spec
# Output: dist/TeslaCamEditor/TeslaCamEditor.exe
import os
from PyInstaller.utils.hooks import collect_data_files

datas = [("teslacam_editor/static", "teslacam_editor/static")]
datas += collect_data_files("imageio_ffmpeg", includes=["binaries/*"])

a = Analysis(
    ["launcher.py"],
    pathex=[os.path.abspath(".")],
    binaries=[],
    datas=datas,
    hiddenimports=["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto", "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on", "multipart", "PIL.ImageFont", "PIL.ImageDraw"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TeslaCamEditor",
    debug=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="TeslaCamEditor")
