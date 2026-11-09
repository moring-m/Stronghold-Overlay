# PyInstaller 빌드 설정:  pyinstaller --noconfirm StrongholdOverlay.spec
from PyInstaller.utils.hooks import collect_data_files

datas = [("data", "data"), ("assets", "assets")]
datas += collect_data_files("rapidocr_onnxruntime")   # OCR 모델/설정

a = Analysis(
    ["launcher.py"],
    datas=datas,
    hiddenimports=["win32gui"],
    excludes=["tkinter", "matplotlib", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore", "PySide6.QtQuick"],
)
# 개인 설정 파일은 넣지 않음
a.datas = [d for d in a.datas if not d[0].replace("\\\\", "/").endswith("data/user_settings.json")]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="StrongholdOverlay",
          icon="assets/icon.ico", console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="StrongholdOverlay", upx=False)
