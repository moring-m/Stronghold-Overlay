"""게임 창 찾기, 위치/포커스 확인, 캡처 (Windows)."""
from __future__ import annotations

import os
import sys

import mss
import numpy as np

WIN = sys.platform == "win32"


def find_window(title: str) -> int | None:
    """창 제목에 title이 포함된 보이는 창의 핸들."""
    if not WIN:
        return None
    import win32gui
    found: list[int] = []

    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and title in win32gui.GetWindowText(hwnd):
            found.append(hwnd)

    win32gui.EnumWindows(cb, None)
    return found[0] if found else None


def is_alive(hwnd: int | None) -> bool:
    if not (WIN and hwnd):
        return False
    import win32gui
    return bool(win32gui.IsWindow(hwnd))


def client_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """클라이언트 영역 (left, top, width, height) — 물리 픽셀. 최소화면 None."""
    import win32gui
    if win32gui.IsIconic(hwnd):
        return None
    l, t, r, b = win32gui.GetClientRect(hwnd)
    if r - l < 100 or b - t < 100:
        return None
    left, top = win32gui.ClientToScreen(hwnd, (l, t))
    return left, top, r - l, b - t


def is_foreground(hwnd: int) -> bool:
    """게임 창이나 이 프로그램의 창(설정 패널 등)이 앞에 있는지."""
    import win32gui
    import win32process
    fg = win32gui.GetForegroundWindow()
    if fg == hwnd:
        return True
    try:
        return win32process.GetWindowThreadProcessId(fg)[1] == os.getpid()
    except Exception:
        return False


class Capturer:
    def __init__(self) -> None:
        self._sct = mss.mss()

    def grab(self, rect: tuple[int, int, int, int]) -> np.ndarray:
        left, top, w, h = rect
        img = np.asarray(self._sct.grab({"left": left, "top": top, "width": w, "height": h}))
        return img[..., :3].copy()  # BGRA -> BGR
