"""시스템 트레이에서 실행되는 오버레이 앱."""
from __future__ import annotations

import sys
import threading
import time

from PySide6.QtCore import QObject, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QIcon, QPainter, QPen, QPixmap, QPolygon
from PySide6.QtWidgets import QApplication, QMenu, QPushButton, QSystemTrayIcon, QWidget

from . import config, theme
from .capture import Capturer, find_window
from .detectors import SHOP_STEP, SHOP_W, SHOP_X0, SHOP_Y_TOP, update_state
from .gamedata import GameData
from .i18n import LANGUAGES, set_language, tr
from .models import GameState, Screen
from .settings_ui import SettingsPanel

YELLOW = QColor(255, 210, 0)


def app_icon() -> QIcon:
    """assets/icon.png (없으면 직접 그림)."""
    path = config.ROOT / "assets" / "icon.png"
    if path.exists():
        return QIcon(str(path))
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(theme.PAGE))
    p.setPen(QPen(QColor(theme.ACCENT), 4))
    p.drawPolygon(QPolygon([QPoint(32, 4), QPoint(60, 32), QPoint(32, 60), QPoint(4, 32)]))
    p.setBrush(QColor(theme.ACCENT))
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygon([QPoint(32, 20), QPoint(44, 32), QPoint(32, 44), QPoint(20, 32)]))
    p.end()
    return QIcon(pm)


class Worker(QObject):
    """백그라운드: 캡처 → OCR → 상태 갱신."""
    updated = Signal(object, object)  # GameState, rect | None

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
                shop = (ocr.read_shop(frame, self.gd)
                        if self.state.screen is Screen.BATTLE and tick % 5 else None)
                if shop:
                    self.state.shop = shop
                else:
                    update_state(self.state, ocr.read(frame), frame, self.gd)
            self.updated.emit(self.state, rect if rect and rect[2] > 100 else None)
            time.sleep(self.settings.interval_ms / 1000)

    def stop(self) -> None:
        self._stop = True


class Overlay(QWidget):
    """게임 창 위의 투명·클릭 통과 표시층."""

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

    def info_lines(self) -> list[str]:
        gd = self.gd
        ops, alliances, note = self.preferred()
        s, st = self.state, self.strategy
        lines = []
        if st:
            t = gd.strategy_label(st)
            lines.append(tr("ov_strategy", l=t["leader"], n=t["name"], hp=st["hp"]))
            lines.append("  " + t["effect"].replace("\n", " ")[:70])
        elif s.strategy:
            lines.append(tr("ov_strategy_unknown", l=s.strategy))
        if note:
            lines.append(tr("ov_note", t=note))

        m = s.match
        al = gd.alliance_label
        if m.banned_alliances:
            lines.append(tr("ov_banned", x=", ".join(al(a) for a in m.banned_alliances)))
            hit = sorted(alliances & set(m.banned_alliances))
            if hit:
                lines.append(tr("ov_banned_pref", x=", ".join(al(a) for a in hit)))
            banned_ops = sorted(o for o in ops
                                if set(gd.operators.get(o, {}).get("alliances", [])) & set(m.banned_alliances))
            if banned_ops:
                lines.append(tr("ov_banned_ops", x=", ".join(gd.op_label(o) for o in banned_ops)))
        if m.boss:
            bosses = gd.boss_candidates(m.boss)
            if len(bosses) == 1:
                lines.append(tr("ov_boss", b=bosses[0], n=config.lookup_note(self.settings.enemy_notes, bosses[0])))
            else:
                lines.append(tr("ov_boss_multi", b=m.boss, c="、".join(bosses)))
        for e in m.special_enemies:
            g = gd.special_group(e)
            if g:
                lines.append(tr("ov_special", g=gd.special_label(g[0]),
                                e="、".join(g[1][:6]) + (tr("ov_more") if len(g[1]) > 6 else "")))
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
                if c.operator in ops:
                    x = int((SHOP_X0 + c.slot * SHOP_STEP) * w)
                    p.drawRect(x, int(SHOP_Y_TOP * h), int(SHOP_W * w), int((0.99 - SHOP_Y_TOP) * h))
        lines = self.info_lines()
        if not lines:
            return
        f = QFont()
        f.setPixelSize(13)
        p.setFont(f)
        lh = 20
        box = QRect(10, int(h * 0.12), int(w * 0.36), lh * len(lines) + 14)
        p.fillRect(box, QColor(8, 21, 25, 200))
        p.setPen(QPen(QColor(theme.RULE), 1))
        p.drawRect(box.adjusted(0, 0, -1, -1))
        p.fillRect(QRect(box.x(), box.y(), 3, box.height()), QColor(theme.ACCENT))
        p.setPen(QColor(theme.INK))
        for i, line in enumerate(lines):
            p.drawText(box.x() + 12, box.y() + 20 + i * lh, line)


class GearButton(QPushButton):
    """게임 창 오른쪽 아래 구석의 작은 설정 버튼 (오버레이는 클릭이 통과하므로 별도 창)."""

    def __init__(self) -> None:
        super().__init__("⚙", None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setFixedSize(30, 30)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"QPushButton {{ background: {theme.PANEL}; color: {theme.ACCENT}; border: 1px solid "
                           f"{theme.RULE}; font-size: 16px; padding: 0; }} QPushButton:hover {{ border-color: "
                           f"{theme.ACCENT}; }}")

    def place(self, rect) -> None:
        x, y, w, h = rect
        # 오른쪽 위 카운트다운/버튼과 겹치지 않도록 오른쪽 가장자리 세로 중앙보다 조금 위
        self.move(x + w - self.width() - 4, y + int(h * 0.40))


class App(QObject):
    def __init__(self, qapp: QApplication) -> None:
        super().__init__()
        self.qapp = qapp
        self.settings = config.load_settings()
        set_language(self.settings.language)
        self.gd = GameData.load()
        self.rect = None
        self.panel: SettingsPanel | None = None

        self.overlay = Overlay(self.settings, self.gd)
        self.gear = GearButton()
        self.gear.clicked.connect(self.open_settings)

        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.activated.connect(self._tray_activated)
        self._build_menu()
        self.tray.show()
        self.tray.showMessage(tr("app_title"), tr("tray_started"), app_icon(), 4000)

        self.worker = Worker(self.settings, self.gd)
        self.worker.updated.connect(self.on_update)
        threading.Thread(target=self.worker.run, daemon=True).start()
        qapp.aboutToQuit.connect(self.worker.stop)

    # ---- 트레이 ----
    def _build_menu(self) -> None:
        m = QMenu()
        m.addAction(tr("tray_settings"), self.open_settings)
        self.show_act = QAction(tr("tray_overlay"), m, checkable=True, checked=True)
        self.show_act.toggled.connect(lambda _: self.on_update(self.overlay.state, self.rect))
        m.addAction(self.show_act)
        lang_menu = m.addMenu(tr("tray_language"))
        grp = QActionGroup(lang_menu)
        for code, name in LANGUAGES.items():
            a = QAction(name, lang_menu, checkable=True, checked=code == self.settings.language)
            a.triggered.connect(lambda _=False, c=code: self.set_language(c))
            grp.addAction(a)
            lang_menu.addAction(a)
        m.addSeparator()
        m.addAction(tr("tray_quit"), self.qapp.quit)
        old = self.tray.contextMenu()
        self.tray.setContextMenu(m)
        self._menu = m  # 참조 유지
        if old:
            old.deleteLater()
        self.tray.setToolTip(tr("app_title"))

    def _tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.open_settings()

    # ---- 상태 갱신 ----
    def on_update(self, state: GameState, rect) -> None:
        self.rect = rect
        self.overlay.state = state
        visible = bool(rect) and self.show_act.isChecked()
        if visible:
            self.overlay.setGeometry(QRect(*rect))
            self.overlay.show()
            self.overlay.update()
            self.gear.place(rect)
            self.gear.show()
            self.gear.raise_()
        else:
            self.overlay.hide()
            self.gear.hide()
        screen = tr("screen_" + state.screen.value) if rect else tr("status_wait", t=self.settings.window_title)
        self.tray.setToolTip(f"{tr('app_title')}\n{screen}")

    # ---- 설정 패널 ----
    def open_settings(self) -> None:
        if self.panel is None:
            self.panel = SettingsPanel(self.settings, self.gd, self.overlay.manual_strategy)
            self.panel.applied.connect(self.overlay.update)
            self.panel.manual_strategy.connect(self._set_manual)
            self.panel.language_changed.connect(lambda: self.set_language(self.settings.language))
            panel = self.panel
            # 언어 변경으로 새 패널이 생긴 뒤 옛 패널의 destroyed가 와도 새 참조를 지우지 않게
            panel.destroyed.connect(lambda *_: self.panel is panel and setattr(self, "panel", None))
            self.panel.setAttribute(Qt.WA_DeleteOnClose)
            self._center_panel()
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()

    def _center_panel(self) -> None:
        if self.rect:      # 게임 창 가운데
            x, y, w, h = self.rect
            pw, ph = min(1000, max(760, int(w * 0.9))), min(660, max(520, int(h * 0.9)))
            self.panel.setGeometry(x + (w - pw) // 2, y + (h - ph) // 2, pw, ph)
        else:              # 게임이 없으면 화면 가운데
            g = self.qapp.primaryScreen().availableGeometry()
            self.panel.move(g.center() - self.panel.rect().center())

    def _set_manual(self, leader) -> None:
        self.overlay.manual_strategy = leader
        self.overlay.update()

    def set_language(self, code: str) -> None:
        self.settings.language = code
        set_language(code)
        config.save_user_settings(self.settings)
        self._build_menu()
        if self.panel is not None:   # 패널을 새 언어로 다시 만든다 (위치 유지)
            geo = self.panel.geometry()
            self.panel.close()
            self.panel = None
            self.open_settings()
            self.panel.setGeometry(geo)
        self.overlay.update()


def selftest() -> int:
    """패키징 확인용: 데이터, 번역, 초상화, OCR 모델이 실제로 로드되는지 검사하고 종료."""
    import numpy as np
    from .ocr import Ocr
    gd = GameData.load()
    problems = []
    if len(gd.operators) < 100:
        problems.append(f"operators={len(gd.operators)}")
    if not gd.names.get("ko"):
        problems.append("i18n missing")
    missing = [n for n in gd.operators if not gd.avatar(n)]
    if missing:
        problems.append(f"avatars missing={len(missing)}")
    if not gd.boss_portraits:
        problems.append("boss portraits missing")
    Ocr().read(np.zeros((90, 160, 3), np.uint8))
    result = "selftest: " + ("OK" if not problems else "FAIL " + ", ".join(problems))
    # 창 모드 exe에는 stdout이 없으므로 파일로도 남긴다
    from pathlib import Path
    Path("selftest.txt").write_text(result, "utf-8")
    if sys.stdout:
        print(result)
    return 1 if problems else 0


def main() -> None:
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    qapp = QApplication(sys.argv)
    qapp.setApplicationName("Stronghold Overlay")
    qapp.setQuitOnLastWindowClosed(False)   # 설정 창을 닫아도 트레이에 남음
    qapp.setWindowIcon(app_icon())
    qapp.setStyleSheet(theme.stylesheet())
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("System tray is not available.", file=sys.stderr)
    qapp.main_app = App(qapp)  # 참조 유지
    sys.exit(qapp.exec())
