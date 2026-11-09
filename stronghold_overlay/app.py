from __future__ import annotations

import os
import sys
import threading
import time

from PySide6.QtCore import QObject, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QComboBox, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

from . import config
from .capture import Capturer, find_window
from .detectors import SHOP_STEP, SHOP_W, SHOP_X0, SHOP_Y_TOP, update_state
from .gamedata import GameData
from .models import GameState, Screen

MANUAL_AUTO = "(자동 감지)"
YELLOW = QColor(255, 210, 0)


class Worker(QObject):
    """백그라운드에서 캡처 → OCR → 상태 갱신."""
    updated = Signal(object, object)  # GameState, rect

    def __init__(self, settings: config.Settings, gd: GameData) -> None:
        super().__init__()
        self.settings, self.gd = settings, gd
        self.state = GameState()
        self._stop = False

    def run(self) -> None:
        from .ocr import Ocr
        ocr, cap = Ocr(), Capturer()
        tick = 0
        while not self._stop:
            tick += 1
            rect = find_window(self.settings.window_title)
            if rect and rect[2] > 100:
                frame = cap.grab(rect)
                # 상점 단계: 카드 영역만 빠르게 읽는다. 5회에 1번은 전체 화면으로 화면 전환 확인.
                shop = (ocr.read_shop(frame, self.gd)
                        if self.state.screen is Screen.BATTLE and tick % 5 else None)
                if shop:
                    self.state.shop = shop
                else:
                    update_state(self.state, ocr.read(frame), frame, self.gd)
                self.updated.emit(self.state, rect)
            time.sleep(self.settings.interval_ms / 1000)

    def stop(self) -> None:
        self._stop = True


class Overlay(QWidget):
    """게임 창 위에 겹치는 투명·클릭 통과 창."""

    def __init__(self, settings: config.Settings, gd: GameData) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.settings, self.gd = settings, gd
        self.state = GameState()
        self.manual_strategy: str | None = None

    @property
    def strategy(self) -> dict | None:
        return self.gd.strategy(self.manual_strategy or self.state.strategy)

    def preferred(self) -> tuple[set[str], set[str], str]:
        s = self.strategy
        keys = [k for k in (s and s["leader"], s and s["name"], self.state.strategy) if k]
        return self.settings.preferred(next((k for k in keys if k in self.settings.presets), None))

    def on_update(self, state: GameState, rect) -> None:
        self.state = state
        self.setGeometry(QRect(*rect))
        self.show()
        self.update()

    def info_lines(self) -> list[str]:
        ops, alliances, note = self.preferred()
        s, st = self.state, self.strategy
        lines = []
        if st:
            lines.append(f"전략: {st['leader']} 【{st['name']}】 HP {st['hp']}")
            lines.append("  " + st["effect"].replace("被动效果：", "")[:60])
        elif s.strategy:
            lines.append(f"전략: {s.strategy} (PRTS 데이터에 없음)")
        if note:
            lines.append(f"  메모: {note}")

        m = s.match
        if m.banned_alliances:
            lines.append("밴(이번 판 미등장): " + ", ".join(m.banned_alliances))
            hit = sorted(alliances & set(m.banned_alliances))
            if hit:
                lines.append("⚠ 선호 맹약 밴됨: " + ", ".join(hit))
            banned_ops = sorted(o for o in ops
                                if set(self.gd.operators.get(o, {}).get("alliances", [])) & set(m.banned_alliances))
            if banned_ops:
                lines.append("⚠ 밴 맹약 소속 선호 오퍼레이터: " + ", ".join(banned_ops))
        if m.boss:
            bosses = self.gd.boss_candidates(m.boss)
            if len(bosses) == 1:
                lines.append(f"보스: {bosses[0]}  {config.lookup_note(self.settings.enemy_notes, bosses[0])}")
            else:
                lines.append(f"보스: {m.boss}? (후보: {'、'.join(bosses)})")
        for e in m.special_enemies:
            g = self.gd.special_group(e)
            if g:
                lines.append(f"특훈[{g[0]}]: " + "、".join(g[1][:6]) + (" 외" if len(g[1]) > 6 else ""))
            else:
                lines.append(f"특훈: {e}")
        return lines

    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        ops, _, _ = self.preferred()

        if self.state.screen is Screen.BATTLE:
            p.setPen(QPen(YELLOW, 4))
            for c in self.state.shop:
                if c.operator not in ops:
                    continue
                x = int((SHOP_X0 + c.slot * SHOP_STEP) * w)
                p.drawRect(x, int(SHOP_Y_TOP * h), int(SHOP_W * w), int((0.99 - SHOP_Y_TOP) * h))

        lines = self.info_lines()
        if not lines:
            return
        p.setFont(QFont("Microsoft YaHei", 10))
        lh = 20
        box = QRect(10, int(h * 0.12), int(w * 0.34), lh * len(lines) + 12)
        p.fillRect(box, QColor(0, 0, 0, 170))
        p.setPen(QColor(230, 255, 240))
        for i, line in enumerate(lines):
            p.drawText(box.x() + 8, box.y() + 18 + i * lh, line)


class Control(QWidget):
    """작은 조작 창: 전략 수동 지정, 설정 파일 열기."""

    def __init__(self, overlay: Overlay, settings: config.Settings, gd: GameData) -> None:
        super().__init__(None, Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Stronghold Overlay")
        self.overlay, self.settings = overlay, settings
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("전략 (자동 감지 실패 시 수동 선택)"))
        self.combo = QComboBox()
        self.combo.addItem(MANUAL_AUTO)
        for s in gd.raw["strategies"]:
            self.combo.addItem(f"{s['leader']} 【{s['name']}】", s["leader"])
        self.combo.currentIndexChanged.connect(self._pick)
        lay.addWidget(self.combo)
        btn = QPushButton("설정 파일 열기")
        btn.clicked.connect(self._open)
        lay.addWidget(btn)
        src = gd.raw.get("fetched", "없음")
        lay.addWidget(QLabel(f"PRTS 데이터: {src}"))

    def _pick(self, idx: int) -> None:
        self.overlay.manual_strategy = self.combo.itemData(idx) if idx > 0 else None
        self.overlay.update()

    def _open(self) -> None:
        if not config.USER_FILE.exists():
            config.save_user_settings(self.settings)
        if sys.platform == "win32":
            os.startfile(config.USER_FILE)  # 저장 후 프로그램 재시작 시 반영


def main() -> None:
    app = QApplication(sys.argv)
    settings = config.load_settings()
    gd = GameData.load()
    overlay = Overlay(settings, gd)
    control = Control(overlay, settings, gd)
    control.show()

    worker = Worker(settings, gd)
    worker.updated.connect(overlay.on_update)
    threading.Thread(target=worker.run, daemon=True).start()
    app.aboutToQuit.connect(worker.stop)
    sys.exit(app.exec())
