"""게임 창 위치 찾기와 캡처 (Windows)."""
from __future__ import annotations

import sys

import mss
import numpy as np


def find_window(title: str) -> tuple[int, int, int, int] | None:
    """창 제목에 title이 포함된 창의 클라이언트 영역 (left, top, width, height)."""
    if sys.platform != "win32":
        return None
    import win32gui

    found: list[int] = []

    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and title in win32gui.GetWindowText(hwnd):
            found.append(hwnd)

    win32gui.EnumWindows(cb, None)
    if not found:
        return None
    hwnd = found[0]
    l, t, r, b = win32gui.GetClientRect(hwnd)
    left, top = win32gui.ClientToScreen(hwnd, (l, t))
    return left, top, r - l, b - t


class Capturer:
    def __init__(self) -> None:
        self._sct = mss.mss()

    def grab(self, rect: tuple[int, int, int, int]) -> np.ndarray:
        left, top, w, h = rect
        img = np.asarray(self._sct.grab({"left": left, "top": top, "width": w, "height": h}))
        return img[..., :3].copy()  # BGRA -> BGR
