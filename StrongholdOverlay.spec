# PyInstaller 빌드 설정:  pyinstaller --noconfirm StrongholdOverlay.spec
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [("data", "data"), ("assets", "assets")]
# OCR: 검출/인식 모델과 설정만 (글자 방향 판별 모델은 쓰지 않음)
datas += [d for d in collect_data_files("rapidocr_onnxruntime") if "cls_infer" not in d[0]]

a = Analysis(
    ["launcher.py"],
    datas=datas,
    hiddenimports=["win32gui", "win32process"] + [
        m for m in collect_submodules("rapidocr_onnxruntime") if "cls" not in m],
    excludes=[
        "tkinter", "matplotlib", "scipy", "pandas", "IPython", "pytest",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtPdf", "PySide6.QtOpenGL",
        "PySide6.QtWebEngineCore", "PySide6.Qt3DCore", "PySide6.QtMultimedia",
    ],
)

# 쓰지 않는 큰 파일 제외 (경로에 아래 문자열이 들어가면 뺀다)
DROP = [
    "opengl32sw",                         # Qt 소프트웨어 OpenGL (약 20MB)
    "Qt6Pdf", "Qt6Qml", "Qt6Quick", "Qt6VirtualKeyboard", "Qt6OpenGL", "Qt6Wayland",
    "libQt6Pdf", "libQt6Qml", "libQt6Quick", "libQt6VirtualKeyboard", "libQt6OpenGL", "libQt6Wayland",
    "libQt6EglFS", "libQt6WlShell",
    "/translations/",                     # Qt 번역 (UI 문구는 앱 자체 번역 사용)
    "platforminputcontexts", "virtualkeyboard", "wayland-", "egldeviceintegrations",
    "imageformats/qpdf", "imageformats/qgif", "imageformats/qtiff", "imageformats/qwebp",
    "imageformats/qicns", "imageformats/qtga", "imageformats/qwbmp", "imageformats/qjpeg",
    "networkinformation", "/tls/", "generic/",
    "opencv_videoio_ffmpeg",              # OpenCV 동영상 코덱 (약 25MB)
    "cls_infer.onnx", "data/user_settings.json",
]


def keep(entry):
    path = entry[0].replace("\\", "/")
    return not any(d in path for d in DROP)


a.binaries = [b for b in a.binaries if keep(b)]
a.datas = [d for d in a.datas if keep(d)]

pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="StrongholdOverlay",
          icon="assets/icon.ico", console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="StrongholdOverlay", upx=False)
