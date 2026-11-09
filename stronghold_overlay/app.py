from __future__ import annotations

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
from .i18n import set_language, tr
from .models import GameState, Screen
from .settings_ui import SettingsDialog
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
            lines.append(tr("ov_strategy", l=st["leader"], n=st["name"], hp=st["hp"]))
            lines.append("  " + st["effect"].replace("被动效果：", "")[:60])
        elif s.strategy:
            lines.append(tr("ov_strategy_unknown", l=s.strategy))
        if note:
            lines.append(tr("ov_note", t=note))

        m = s.match
        if m.banned_alliances:
            lines.append(tr("ov_banned", x=", ".join(m.banned_alliances)))
            hit = sorted(alliances & set(m.banned_alliances))
            if hit:
                lines.append(tr("ov_banned_pref", x=", ".join(hit)))
            banned_ops = sorted(o for o in ops
                                if set(self.gd.operators.get(o, {}).get("alliances", [])) & set(m.banned_alliances))
            if banned_ops:
                lines.append(tr("ov_banned_ops", x=", ".join(banned_ops)))
        if m.boss:
            bosses = self.gd.boss_candidates(m.boss)
            if len(bosses) == 1:
                lines.append(tr("ov_boss", b=bosses[0], n=config.lookup_note(self.settings.enemy_notes, bosses[0])))
            else:
                lines.append(tr("ov_boss_multi", b=m.boss, c="、".join(bosses)))
        for e in m.special_enemies:
            g = self.gd.special_group(e)
            if g:
                lines.append(tr("ov_special", g=g[0], e="、".join(g[1][:6]) + (tr("ov_more") if len(g[1]) > 6 else "")))
            else:
                lines.append(tr("ov_special", g="?", e=e))
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
    """조작 창: 상태 표시, 전략 수동 지정, 설정 열기."""

    def __init__(self, overlay: Overlay, settings: config.Settings, gd: GameData) -> None:
        super().__init__(None, Qt.WindowStaysOnTopHint)
        self.overlay, self.settings, self.gd = overlay, settings, gd
        self._state: GameState | None = None
        lay = QVBoxLayout(self)
        self.status = QLabel()
        self.pick_label = QLabel()
        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.setInsertPolicy(QComboBox.NoInsert)
        self.settings_btn = QPushButton()
        self.data_label = QLabel()
        self.data_label.setStyleSheet("color: gray;")
        for wdg in (self.status, self.pick_label, self.combo, self.settings_btn, self.data_label):
            lay.addWidget(wdg)
        self.combo.currentIndexChanged.connect(self._pick)
        self.settings_btn.clicked.connect(self._open_settings)
        self.retranslate()

    def retranslate(self) -> None:
        self.setWindowTitle(tr("app_title"))
        self.pick_label.setText(tr("strategy_pick"))
        self.settings_btn.setText(tr("open_settings"))
        self.data_label.setText(tr("data_date", d=self.gd.raw.get("fetched", "-")))
        cur = self.combo.currentData()
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem(tr("auto_detect"), None)
        for s in self.gd.raw["strategies"]:
            self.combo.addItem(f"{s['leader']} 【{s['name']}】", s["leader"])
        self.combo.setCurrentIndex(max(0, self.combo.findData(cur)))
        self.combo.blockSignals(False)
        self.on_update(self._state, None)

    def on_update(self, state: GameState | None, _rect) -> None:
        self._state = state
        if state is None:
            self.status.setText(tr("status_wait", t=self.settings.window_title))
        else:
            self.status.setText(tr("status_ok", s=tr("screen_" + state.screen.value)))

    def _pick(self, idx: int) -> None:
        self.overlay.manual_strategy = self.combo.itemData(idx)
        self.overlay.update()

    def _open_settings(self) -> None:
        if SettingsDialog(self.settings, self.gd, self).exec():
            self.retranslate()
            self.overlay.update()


def main() -> None:
    app = QApplication(sys.argv)
    settings = config.load_settings()
    set_language(settings.language)
    gd = GameData.load()
    overlay = Overlay(settings, gd)
    control = Control(overlay, settings, gd)
    control.show()

    worker = Worker(settings, gd)
    worker.updated.connect(overlay.on_update)
    worker.updated.connect(control.on_update)
    threading.Thread(target=worker.run, daemon=True).start()
    app.aboutToQuit.connect(worker.stop)
    sys.exit(app.exec())
