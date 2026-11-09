"""전역 단축키 (Windows RegisterHotKey). 게임에 포커스가 있어도 동작한다."""
from __future__ import annotations

import logging
import sys
import threading

from PySide6.QtCore import QObject, Signal

log = logging.getLogger(__name__)
MODS = {"ctrl": 0x0002, "alt": 0x0001, "shift": 0x0004, "win": 0x0008}
MOD_NOREPEAT = 0x4000
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012


def parse(seq: str) -> tuple[int, int] | None:
    """'Ctrl+Alt+S' → (modifiers, virtual key)."""
    mods, vk = 0, None
    for part in (p.strip().lower() for p in seq.split("+")):
        if part in MODS:
            mods |= MODS[part]
        elif len(part) == 1 and part.isalnum():
            vk = ord(part.upper())
        elif part.startswith("f") and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            vk = 0x70 + int(part[1:]) - 1
    return (mods | MOD_NOREPEAT, vk) if vk else None


class Hotkeys(QObject):
    triggered = Signal(str)   # 이름

    def __init__(self, bindings: dict[str, str]) -> None:
        super().__init__()
        self.bindings = bindings
        self._tid = None
        if sys.platform == "win32":
            threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self) -> None:
        import ctypes
        from ctypes import wintypes
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        self._tid = kernel32.GetCurrentThreadId()
        names = {}
        for i, (name, seq) in enumerate(self.bindings.items(), start=1):
            parsed = parse(seq)
            if parsed and user32.RegisterHotKey(None, i, parsed[0], parsed[1]):
                names[i] = name
            else:
                log.warning("단축키 등록 실패: %s (%s) — 다른 프로그램이 사용 중일 수 있음", name, seq)
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam in names:
                self.triggered.emit(names[msg.wParam])
        for i in names:
            user32.UnregisterHotKey(None, i)

    def stop(self) -> None:
        if self._tid:
            import ctypes
            ctypes.windll.user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
