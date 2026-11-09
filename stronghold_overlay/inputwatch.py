"""마우스 클릭/키 입력 감지 (Windows 저수준 훅). 입력 시각만 기록하고 즉시 돌려준다.

게임 입력을 막거나 바꾸지 않는다 (항상 CallNextHookEx로 그대로 넘김).
"""
from __future__ import annotations

import logging
import sys
import threading
import time

log = logging.getLogger(__name__)

WH_KEYBOARD_LL, WH_MOUSE_LL = 13, 14
# 버튼을 뗀 순간(클릭 완료)과 휠, 키를 뗀 순간만 센다
MOUSE_EVENTS = {0x0202, 0x0205, 0x0208, 0x020A}   # L/R/M BUTTONUP, WHEEL
KEY_EVENTS = {0x0101, 0x0105}                      # KEYUP, SYSKEYUP
WM_QUIT = 0x0012


class InputWatcher:
    def __init__(self) -> None:
        self.last_input = 0.0      # time.monotonic() 기준
        self._tid = None
        if sys.platform == "win32":
            threading.Thread(target=self._loop, daemon=True).start()

    def mark(self) -> None:
        self.last_input = time.monotonic()

    def _loop(self) -> None:
        import ctypes
        from ctypes import wintypes
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        self._tid = kernel32.GetCurrentThreadId()
        LRESULT = ctypes.c_ssize_t
        HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user32.CallNextHookEx.restype = LRESULT
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
        user32.SetWindowsHookExW.restype = wintypes.HHOOK

        def make(events):
            def proc(code, wparam, lparam):
                if code >= 0 and wparam in events:
                    self.last_input = time.monotonic()
                return user32.CallNextHookEx(None, code, wparam, lparam)
            return HOOKPROC(proc)

        self._procs = (make(MOUSE_EVENTS), make(KEY_EVENTS))   # 참조 유지 (GC 방지)
        hooks = [user32.SetWindowsHookExW(WH_MOUSE_LL, self._procs[0], None, 0),
                 user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._procs[1], None, 0)]
        if not all(hooks):
            log.warning("입력 감지 훅 설치 실패 — 주기 인식만 사용")
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            pass
        for h in hooks:
            if h:
                user32.UnhookWindowsHookEx(h)

    def stop(self) -> None:
        if self._tid:
            import ctypes
            ctypes.windll.user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
