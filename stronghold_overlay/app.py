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
from .detectors import lookup_note, SHOP_STEP, SHOP_W, SHOP_X0, SHOP_Y_TOP, update_state
from .models import GameState, Screen

MANUAL_AUTO = "(자동 감지)"


class Worker(QObject):
    """백그라운드에서 캡처 → OCR → 상태 갱신."""
    updated = Signal(object, object)  # GameState, rect

    def __init__(self, settings: config.Settings) -> None:
        super().__init__()
        self.settings = settings
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
                # 5회에 1번은 전체 화면으로 다시 판별 (상점 화면을 벗어났는지 확인)
                if self.state.screen is Screen.BATTLE and tick % 5:
                    # 상점 단계: 이름 칸만 빠르게 읽고, 이름이 안 보이면 전체 화면 판별로 복귀
                    shop = ocr.read_shop(frame)
                    if shop:
                        self.state.shop = shop
                        self.updated.emit(self.state, rect)
                        time.sleep(self.settings.interval_ms / 1000)
                        continue
                boxes = ocr.read(frame)
                update_state(self.state, boxes, frame)
                self.updated.emit(self.state, rect)
            time.sleep(self.settings.interval_ms / 1000)

    def stop(self) -> None:
        self._stop = True


class Overlay(QWidget):
    """게임 창 위에 겹치는 투명·클릭 통과 창."""

    def __init__(self, settings: config.Settings) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.settings = settings
        self.state = GameState()
        self.manual_strategy: str | None = None

    @property
    def strategy(self) -> str | None:
        return self.manual_strategy or self.state.strategy

    def on_update(self, state: GameState, rect) -> None:
        self.state = state
        self.setGeometry(QRect(*rect))
        self.show()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        ops, alliances, note = self.settings.preferred(self.strategy)
        s = self.state

        # 상점 단계: 선호 오퍼레이터 카드에 노란 테두리
        if s.screen is Screen.BATTLE:
            p.setPen(QPen(QColor(255, 210, 0), 4))
            for c in s.shop:
                if c.operator in ops:
                    x = int((SHOP_X0 + c.slot * SHOP_STEP) * w)
                    p.drawRect(x, int(SHOP_Y_TOP * h), int(SHOP_W * w), int((0.99 - SHOP_Y_TOP) * h))

        # 정보 패널
        lines = [f"전략: {self.strategy or '-'}" + ("" if self.strategy in self.settings.presets or not self.strategy
                                                  else " (프리셋 없음)")]
        if note:
            lines.append(f"  {note}")
        m = s.match
        if m.banned_alliances:
            lines.append("밴(이번 판 미등장): " + ", ".join(m.banned_alliances))
            banned_pref = alliances & set(m.banned_alliances)
            if banned_pref:
                lines.append("⚠ 선호 맹약 밴됨: " + ", ".join(sorted(banned_pref)))
        if m.boss:
            lines.append(f"보스: {m.boss}  {lookup_note(self.settings.enemy_notes, m.boss)}")
        for e in m.special_enemies:
            lines.append(f"적: {e}  {lookup_note(self.settings.enemy_notes, e)}")

        p.setFont(QFont("Microsoft YaHei", 10))
        lh = 20
        box = QRect(10, int(h * 0.12), int(w * 0.30), lh * len(lines) + 12)
        p.fillRect(box, QColor(0, 0, 0, 170))
        p.setPen(QColor(230, 255, 240))
        for i, line in enumerate(lines):
            p.drawText(box.x() + 8, box.y() + 18 + i * lh, line)


class Control(QWidget):
    """작은 조작 창: 전략 수동 지정, 설정 파일 열기."""

    def __init__(self, overlay: Overlay, settings: config.Settings) -> None:
        super().__init__(None, Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Stronghold Overlay")
        self.overlay, self.settings = overlay, settings
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("전략 (자동 감지 실패 시 수동 선택)"))
        self.combo = QComboBox()
        self.combo.addItems([MANUAL_AUTO, *settings.presets.keys()])
        self.combo.currentTextChanged.connect(self._pick)
        lay.addWidget(self.combo)
        btn = QPushButton("설정 파일 열기")
        btn.clicked.connect(self._open)
        lay.addWidget(btn)

    def _pick(self, text: str) -> None:
        self.overlay.manual_strategy = None if text == MANUAL_AUTO else text
        self.overlay.update()

    def _open(self) -> None:
        if not config.USER_FILE.exists():
            config.save_user_settings(self.settings)
        if sys.platform == "win32":
            os.startfile(config.USER_FILE)  # 저장 후 프로그램 재시작 시 반영


def main() -> None:
    app = QApplication(sys.argv)
    settings = config.load_settings()
    overlay = Overlay(settings)
    control = Control(overlay, settings)
    control.show()

    worker = Worker(settings)
    worker.updated.connect(overlay.on_update)
    threading.Thread(target=worker.run, daemon=True).start()
    app.aboutToQuit.connect(worker.stop)
    sys.exit(app.exec())
