"""시스템 트레이에서 실행되는 오버레이 앱."""
from __future__ import annotations

import copy
import logging
import sys
import threading
import time
import traceback

from PySide6.QtCore import QObject, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QGuiApplication, QIcon, QPainter, QPen
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QPushButton, QSystemTrayIcon, QWidget

from . import capture, config, theme
from .detectors import SHOP_STEP, SHOP_W, SHOP_X0, SHOP_Y_TOP
from .gamedata import GameData
from .hotkeys import Hotkeys
from .inputwatch import InputWatcher
from .i18n import LANGUAGES, set_language, tr
from .models import GameState, Screen
from .settings_ui import SettingsPanel

log = logging.getLogger("stronghold_overlay")
YELLOW = QColor(255, 210, 0)
INSTANCE_KEY = "StrongholdOverlay-single-instance"


def setup_logging() -> None:
    path = config.USER_FILE.parent / "overlay.log"
    logging.basicConfig(filename=path, level=logging.INFO, encoding="utf-8",
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    def hook(t, v, tb):
        log.error("처리되지 않은 오류:\n%s", "".join(traceback.format_exception(t, v, tb)))
    sys.excepthook = hook


def app_icon() -> QIcon:
    return QIcon(str(config.ROOT / "assets" / "icon.png"))


def to_logical(rect: tuple[int, int, int, int]) -> QRect:
    """Win32 물리 픽셀 → Qt 논리 좌표 (Windows 배율 125% 등에서 위치가 어긋나지 않게)."""
    x, y, w, h = rect
    for s in QGuiApplication.screens():
        g, dpr = s.geometry(), s.devicePixelRatio()
        native = QRect(g.x(), g.y(), int(g.width() * dpr), int(g.height() * dpr))
        if native.contains(QPoint(x + w // 2, y + h // 2)):
            return QRect(g.x() + round((x - g.x()) / dpr), g.y() + round((y - g.y()) / dpr),
                         round(w / dpr), round(h / dpr))
    return QRect(x, y, w, h)


CONFIRM_AFTER = 0.5   # 입력으로 인식한 뒤, 애니메이션이 끝난 화면을 한 번 더 확인


def next_reason(now: float, last_input: float, last_run: float, delay: float, interval: float,
                confirm_at: float | None) -> str | None:
    """지금 인식할지와 그 이유. 'input' | 'confirm' | 'periodic' | None"""
    if last_input > last_run and now - last_input >= delay:
        return "input"          # 마지막 클릭/키 입력 후 delay초 (연속 입력이면 마지막 기준)
    if confirm_at is not None and now >= confirm_at:
        return "confirm"
    if now - last_run >= interval:
        return "periodic"       # 입력 없이 바뀌는 화면 대비
    return None


class Worker(QObject):
    """백그라운드: 입력 직후(기본 0.2초) 또는 주기적으로 캡처 → OCR → 상태 갱신."""
    updated = Signal(object)  # GameState

    def __init__(self, settings: config.Settings, gd: GameData, inputs) -> None:
        super().__init__()
        self.settings, self.gd, self.inputs = settings, gd, inputs
        self.state = GameState()
        self.rect: tuple[int, int, int, int] | None = None   # GUI 쪽 추적 타이머가 갱신
        self.focused = False                                  # 게임 창이 앞에 있을 때만 입력을 셈
        self.paused = False
        self._stop = False

    def run(self) -> None:
        try:
            from .ocr import Ocr
            ocr, cap = Ocr(), capture.Capturer()
        except Exception:
            log.exception("OCR 초기화 실패")
            return
        last_run, confirm_at, tick = 0.0, None, 0
        while not self._stop:
            time.sleep(0.02)
            rect = self.rect
            if not rect or self.paused:
                continue
            now = time.monotonic()
            last_input = self.inputs.last_input if self.focused else 0.0
            reason = next_reason(now, last_input, last_run, self.settings.input_delay_ms / 1000,
                                 self.settings.interval_ms / 1000, confirm_at)
            if not reason:
                continue
            last_run = now
            confirm_at = now + CONFIRM_AFTER if reason == "input" else None
            tick += 1
            try:
                frame = cap.grab(rect)
                t = time.perf_counter()
                ocr.scan(frame, self.state, self.gd)   # 화면별 필요한 영역만 읽음
                log.debug("인식 %s %.0fms %s", reason, (time.perf_counter() - t) * 1000, self.state.screen.value)
                self.updated.emit(copy.deepcopy(self.state))
            except Exception:
                log.exception("인식 중 오류")

    def stop(self) -> None:
        self._stop = True


class Overlay(QWidget):
    """게임 창 위의 투명·클릭 통과 층: 상점의 선호 카드에 노란 테두리만 그린다."""

    def __init__(self, settings: config.Settings, gd: GameData) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.settings, self.gd = settings, gd
        self.state = GameState()
        self.manual_strategy: str | None = None

    @property
    def strategy(self) -> dict | None:
        return self.gd.strategy(self.manual_strategy or self.state.strategy)

    def preferred(self):
        """(강조 이름, 선호 맹약, 적용된 프리셋 목록)."""
        s = self.strategy
        return self.settings.preferred(s["leader"] if s else None)

    def highlighted(self) -> list[int]:
        """노란 테두리를 그릴 상점 칸 번호."""
        if self.state.screen is not Screen.BATTLE:
            return []
        names, _, _ = self.preferred()
        return [c.slot for c in self.state.shop if c.operator in names]

    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.setPen(QPen(YELLOW, max(3, w // 400)))
        for slot in self.highlighted():
            x = int((SHOP_X0 + slot * SHOP_STEP) * w)
            p.drawRect(x, int(SHOP_Y_TOP * h), int(SHOP_W * w), int((0.99 - SHOP_Y_TOP) * h))


class Toast(QLabel):
    """게임 창 위쪽 가운데에 잠깐 뜨는 알림."""

    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet(f"QLabel {{ background: rgba(8,21,25,225); color: {theme.INK}; border: 1px solid "
                           f"{theme.RULE}; border-left: 3px solid {theme.ACCENT}; padding: 8px 16px; "
                           f"font-size: 14px; }}")
        self._timer = QTimer(self, singleShot=True, timeout=self.hide)

    def show_message(self, text: str, game: QRect | None, warn: bool = False) -> None:
        self.setText(("⚠ " if warn else "") + text)
        self.adjustSize()
        area = game or QGuiApplication.primaryScreen().availableGeometry()
        self.move(area.x() + (area.width() - self.width()) // 2, area.y() + int(area.height() * 0.08))
        self.show()
        self._timer.start(3500)


class GearButton(QPushButton):
    """게임 창 오른쪽 가장자리의 작은 설정 버튼 (오버레이는 클릭이 통과하므로 별도 창)."""

    def __init__(self) -> None:
        super().__init__("⚙", None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(30, 30)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"QPushButton {{ background: rgba(13,32,35,200); color: {theme.ACCENT}; border: 1px solid "
                           f"{theme.RULE}; font-size: 16px; padding: 0; }} QPushButton:hover {{ border-color: "
                           f"{theme.ACCENT}; background: {theme.PANEL}; }}")

    def place(self, r: QRect) -> None:
        self.move(r.right() - self.width() - 4, r.top() + int(r.height() * 0.40))


class App(QObject):
    def __init__(self, qapp: QApplication) -> None:
        super().__init__()
        self.qapp = qapp
        self.settings = config.load_settings()
        set_language(self.settings.language)
        self.gd = GameData.load()
        self.hwnd: int | None = None
        self.game: QRect | None = None
        self.panel: SettingsPanel | None = None
        self.enabled = True
        self._last_strategy = None
        self._last_bans: tuple = ()

        self.overlay = Overlay(self.settings, self.gd)
        self.gear = GearButton()
        self.gear.setToolTip(tr("gear_tip"))
        self.gear.clicked.connect(self.open_settings)
        self.toast = Toast()

        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.activated.connect(self._tray_activated)
        self._build_menu()
        self.tray.show()
        self.tray.showMessage(tr("app_title"), tr("tray_started", s=self.settings.hotkey_settings),
                              app_icon(), 4000)

        self.hotkeys = Hotkeys({"settings": self.settings.hotkey_settings, "toggle": self.settings.hotkey_toggle})
        self.hotkeys.triggered.connect(self._hotkey)

        self.inputs = InputWatcher()
        self.worker = Worker(self.settings, self.gd, self.inputs)
        self.worker.updated.connect(self.on_state)
        threading.Thread(target=self.worker.run, daemon=True).start()

        # 창 위치/포커스는 OCR과 따로 자주 확인 (창을 옮겨도 바로 따라가게)
        self.tracker = QTimer(self, interval=150, timeout=self._track)
        self.tracker.start()
        qapp.aboutToQuit.connect(self._shutdown)

    # ---- 트레이 ----
    def _build_menu(self) -> None:
        m = QMenu()
        m.addAction(f"{tr('tray_settings')}\t{self.settings.hotkey_settings}", self.open_settings)
        self.show_act = QAction(f"{tr('tray_overlay')}\t{self.settings.hotkey_toggle}", m,
                                checkable=True, checked=self.enabled)
        self.show_act.toggled.connect(self.set_enabled)
        m.addAction(self.show_act)
        lang_menu = m.addMenu(tr("tray_language"))
        grp = QActionGroup(lang_menu)
        for code, name in LANGUAGES.items():
            a = QAction(name, lang_menu, checkable=True, checked=code == self.settings.language)
            a.triggered.connect(lambda _=False, c=code: self.set_language(c))
            grp.addAction(a)
            lang_menu.addAction(a)
        m.addAction(tr("tray_log"), self._open_log)
        m.addSeparator()
        m.addAction(tr("tray_quit"), self.qapp.quit)
        self.tray.setContextMenu(m)
        self._menu = m
        self._update_tooltip()

    def _tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.open_settings()

    def _update_tooltip(self) -> None:
        if not self.enabled:
            status = tr("status_paused")
        elif not self.hwnd:
            status = tr("status_wait", t=self.settings.window_title)
        else:
            status = tr("status_ok", s=tr("screen_" + self.overlay.state.screen.value))
        self.tray.setToolTip(f"{tr('app_title')}\n{status}")

    def _open_log(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(config.USER_FILE.parent)))

    def _hotkey(self, name: str) -> None:
        if name == "settings":
            if self.panel and self.panel.isVisible():
                self.panel.close()
            else:
                self.open_settings()
        elif name == "toggle":
            self.show_act.setChecked(not self.show_act.isChecked())

    def set_enabled(self, on: bool) -> None:
        self.enabled = on
        self.worker.paused = not on      # 숨기면 인식도 멈춰 CPU 절약
        self._track()

    # ---- 창 추적 ----
    def _track(self) -> None:
        if not capture.is_alive(self.hwnd):
            self.hwnd = capture.find_window(self.settings.window_title)
        rect = capture.client_rect(self.hwnd) if self.hwnd else None
        self.worker.rect = rect
        game = to_logical(rect) if rect else None
        self._follow_panel(self.game, game)
        self.game = game
        focused = bool(self.hwnd) and capture.is_foreground(self.hwnd)
        self.worker.focused = focused
        visible = bool(self.game) and self.enabled and focused
        if visible:
            if self.overlay.geometry() != self.game:
                self.overlay.setGeometry(self.game)
            if not self.overlay.isVisible():
                self.overlay.show()
            self.gear.place(self.game)
            if not self.gear.isVisible():
                self.gear.show()
        else:
            self.overlay.hide()
            self.gear.hide()
            self.toast.hide()
        self._update_tooltip()

    def _follow_panel(self, old: QRect | None, new: QRect | None) -> None:
        """설정 창이 게임 창을 따라 움직이게 (게임 창 기준 상대 위치 유지)."""
        if not (self.panel and self.panel.isVisible() and old and new) or old == new:
            return
        pos = self.panel.pos() - old.topLeft() + new.topLeft()
        # 게임 창 크기가 바뀌어도 패널이 게임 창 밖으로 크게 벗어나지 않게
        pos.setX(max(new.left(), min(pos.x(), new.right() - self.panel.width())))
        pos.setY(max(new.top(), min(pos.y(), new.bottom() - self.panel.height())))
        self.panel.move(pos)

    # ---- 인식 결과 ----
    def on_state(self, state: GameState) -> None:
        self.overlay.state = state
        self.overlay.update()
        if not self.settings.notify:
            return
        _, alliances, active = self.overlay.preferred()
        if state.strategy and state.strategy != self._last_strategy:
            self._last_strategy = state.strategy
            linked = [p.name for p in active if p.id != self.settings.active_preset]
            if linked:
                self.toast.show_message(tr("toast_preset", n=", ".join(linked)), self.game)
        bans = tuple(sorted(alliances & set(state.match.banned_alliances)))
        if bans and bans != self._last_bans:
            self.toast.show_message(tr("toast_banned", x=", ".join(self.gd.alliance_label(a) for a in bans)),
                                    self.game, warn=True)
        self._last_bans = bans
        if state.screen is Screen.MATCH_INFO:
            self._last_strategy = None   # 새 판

    # ---- 설정 패널 ----
    def open_settings(self) -> None:
        if self.panel is None:
            self.panel = SettingsPanel(self.settings, self.gd, self.overlay.manual_strategy)
            self.panel.applied.connect(self.overlay.update)
            self.panel.manual_strategy.connect(self._set_manual)
            self.panel.language_changed.connect(lambda: self.set_language(self.settings.language))
            panel = self.panel
            panel.destroyed.connect(lambda *_: self.panel is panel and setattr(self, "panel", None))
            panel.setAttribute(Qt.WA_DeleteOnClose)
            self._place_panel()
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()

    def _place_panel(self) -> None:
        area = self.game or QGuiApplication.primaryScreen().availableGeometry()
        pw = min(1040, max(760, int(area.width() * 0.86)))
        ph = min(700, max(520, int(area.height() * 0.88)))
        self.panel.setGeometry(area.x() + (area.width() - pw) // 2, area.y() + (area.height() - ph) // 2, pw, ph)

    def _set_manual(self, leader) -> None:
        self.overlay.manual_strategy = leader
        self.overlay.update()

    def set_language(self, code: str) -> None:
        self.settings.language = code
        set_language(code)
        config.save_user_settings(self.settings)
        self._build_menu()
        self.gear.setToolTip(tr("gear_tip"))
        if self.panel is not None:   # 새 언어로 다시 만든다 (위치 유지)
            geo = self.panel.geometry()
            self.panel.close()
            self.panel = None
            self.open_settings()
            self.panel.setGeometry(geo)

    def _shutdown(self) -> None:
        self.worker.stop()
        self.hotkeys.stop()
        self.inputs.stop()
        self.tray.hide()


def selftest() -> int:
    """패키징 확인용: 데이터, 번역, 이미지, OCR 모델이 실제로 로드되는지 검사하고 종료."""
    import numpy as np
    from .ocr import Ocr
    gd = GameData.load()
    problems = []
    if len(gd.operators) < 100 or len(gd.equipment) < 50:
        problems.append(f"operators={len(gd.operators)} equipment={len(gd.equipment)}")
    if not gd.names.get("ko"):
        problems.append("i18n missing")
    miss_av = [n for n in gd.operators if not gd.avatar(n)]
    miss_it = [n for n in gd.equipment if not gd.item_icon(n)]
    if miss_av or miss_it:
        problems.append(f"images missing={len(miss_av) + len(miss_it)}")
    if not all(gd.tier_icon(t) for t in "ⅠⅡⅢⅣⅤⅥ") or not all(gd.alliance_icon(a) for a in gd.alliances):
        problems.append("tier/alliance icons missing")
    if not (config.ROOT / "assets" / "icon.png").exists():
        problems.append("icon missing")
    from .models import GameState
    Ocr().scan(np.zeros((720, 1280, 3), np.uint8), GameState(), gd)
    result = "selftest: " + ("OK" if not problems else "FAIL " + ", ".join(problems))
    from pathlib import Path
    Path("selftest.txt").write_text(result, "utf-8")   # 창 모드 exe에는 stdout이 없음
    if sys.stdout:
        print(result)
    return 1 if problems else 0


def main() -> None:
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    setup_logging()
    qapp = QApplication(sys.argv)
    qapp.setApplicationName("Stronghold Overlay")
    qapp.setQuitOnLastWindowClosed(False)   # 설정 창을 닫아도 트레이에 남음
    qapp.setWindowIcon(app_icon())
    qapp.setStyleSheet(theme.stylesheet())

    # 이미 실행 중이면 그쪽 설정 창을 띄우고 종료
    sock = QLocalSocket()
    sock.connectToServer(INSTANCE_KEY)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.waitForBytesWritten(300)
        return
    QLocalServer.removeServer(INSTANCE_KEY)
    server = QLocalServer()
    server.listen(INSTANCE_KEY)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        log.warning("시스템 트레이를 사용할 수 없음")
    app = App(qapp)
    server.newConnection.connect(lambda: (server.nextPendingConnection(), app.open_settings()))
    qapp.main_app, qapp.instance_server = app, server   # 참조 유지
    log.info("시작")
    sys.exit(qapp.exec())
