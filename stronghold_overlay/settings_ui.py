"""설정 패널 — 게임 창 위에 반투명으로 뜨고, 바꾸는 즉시 저장·반영된다."""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QSlider, QStackedWidget, QVBoxLayout,
                               QWidget)

from . import autostart, config, theme
from .config import Preset
from .gamedata import GameData
from .i18n import LANGUAGES, tr
from .pickers import AlliancePicker, CardPicker


def rule() -> QFrame:
    f = QFrame(objectName="Rule")
    f.setFrameShape(QFrame.HLine)
    return f


class SettingsPanel(QWidget):
    """상단 탭 + 페이지. 저장 버튼 없이 변경 즉시 자동 저장."""
    applied = Signal()             # 설정이 바뀜 → 오버레이 다시 그리기
    language_changed = Signal()    # 언어 변경 → 패널 다시 만들기
    manual_strategy = Signal(object)

    PAGES = ("tab_operators", "tab_equipment", "tab_alliances", "tab_presets", "tab_general")

    def __init__(self, settings: config.Settings, gd: GameData, current_manual: str | None = None) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.settings, self.gd = settings, gd
        self.setAttribute(Qt.WA_TranslucentBackground)   # 배경은 paintEvent에서 반투명으로
        self.resize(1000, 660)
        self._drag: QPoint | None = None
        self._save_timer = QTimer(self, singleShot=True, interval=300, timeout=self._save)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 12, 18, 16)
        head = QHBoxLayout()
        head.addWidget(QLabel(tr("settings_title"), objectName="Title"))
        head.addStretch(1)
        self.saved = QLabel("", objectName="Muted")
        head.addWidget(self.saved)
        close = QPushButton("✕", objectName="Close")
        close.setToolTip(tr("close_hint"))
        close.clicked.connect(self.close)
        head.addWidget(close)
        root.addLayout(head)
        root.addWidget(rule())

        tabs = QHBoxLayout()
        tabs.setSpacing(0)
        self.nav = QButtonGroup(self)
        self.stack = QStackedWidget()
        builders = (self._page_operators, self._page_equipment, self._page_alliances,
                    self._page_presets, lambda: self._page_general(current_manual))
        for i, (key, build) in enumerate(zip(self.PAGES, builders)):
            b = QPushButton(tr(key), objectName="Tab", checkable=True)
            self.nav.addButton(b, i)
            tabs.addWidget(b)
            self.stack.addWidget(build())
        tabs.addStretch(1)
        tabs.addWidget(QLabel(tr("data_date", d=gd.raw.get("fetched", "-")), objectName="Muted"))
        self.nav.idClicked.connect(self.stack.setCurrentIndex)
        self.nav.button(0).setChecked(True)
        root.addSpacing(6)
        root.addLayout(tabs)
        root.addWidget(rule())
        root.addSpacing(8)
        root.addWidget(self.stack, 1)

        QShortcut(QKeySequence(Qt.Key_Escape), self, self.close)

    # ---------- 반투명 배경 ----------
    def paintEvent(self, _):
        p = QPainter(self)
        bg = QColor(theme.PAGE)
        bg.setAlpha(int(255 * self.settings.panel_opacity / 100))
        p.fillRect(self.rect(), bg)
        p.setPen(QPen(QColor(theme.RULE), 1))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))

    # ---------- 페이지 ----------
    def _page(self, hint: str, counter: QWidget | None = None) -> tuple[QWidget, QVBoxLayout]:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        head = QHBoxLayout()
        h = QLabel(hint, objectName="Hint")
        h.setWordWrap(True)
        head.addWidget(h, 1)
        if counter is not None:
            head.addWidget(counter, 0, Qt.AlignBottom)
        lay.addLayout(head)
        return w, lay

    def _page_operators(self) -> QWidget:
        self.ops = CardPicker(self.gd, "operator")
        self.ops.set_checked(self.settings.base_operators)
        self.ops.changed.connect(lambda v: self._set("base_operators", v))
        w, lay = self._page(tr("ops_hint"), self.ops.count)
        lay.addWidget(self.ops, 1)
        return w

    def _page_equipment(self) -> QWidget:
        self.items = CardPicker(self.gd, "equipment")
        self.items.set_checked(self.settings.base_equipment)
        self.items.changed.connect(lambda v: self._set("base_equipment", v))
        w, lay = self._page(tr("items_hint"), self.items.count)
        lay.addWidget(self.items, 1)
        return w

    def _page_alliances(self) -> QWidget:
        w, lay = self._page(tr("alliances_hint"))
        self.als = AlliancePicker(self.gd)
        self.als.set_checked(self.settings.base_alliances)
        self.als.changed.connect(lambda v: self._set("base_alliances", v))
        lay.addWidget(self.als, 1)
        return w

    def _page_presets(self) -> QWidget:
        w, lay = self._page(tr("preset_hint"))
        self.strat = QComboBox()
        self.strat.setEditable(True)            # 입력해서 찾기
        self.strat.setInsertPolicy(QComboBox.NoInsert)
        self.strat.lineEdit().setPlaceholderText(tr("strategy_search"))
        for s in self.gd.raw["strategies"]:
            self.strat.addItem("", s["leader"])
        lay.addWidget(self.strat)
        self.strat_effect = QLabel(objectName="Hint")
        self.strat_effect.setWordWrap(True)
        lay.addWidget(self.strat_effect)

        tabs = QHBoxLayout()
        self.p_tab = QButtonGroup(self)
        for i, key in enumerate(("operators", "equipment", "alliances")):
            b = QPushButton(tr(key), checkable=True)
            self.p_tab.addButton(b, i)
            tabs.addWidget(b)
        tabs.addStretch(1)
        tabs.addWidget(QLabel(tr("note")))
        self.p_note = QLineEdit()
        self.p_note.setPlaceholderText(tr("note_placeholder"))
        tabs.addWidget(self.p_note, 2)
        lay.addLayout(tabs)
        self.p_stack = QStackedWidget()
        self.p_ops = CardPicker(self.gd, "operator")
        self.p_items = CardPicker(self.gd, "equipment")
        self.p_als = AlliancePicker(self.gd)
        for wdg in (self.p_ops, self.p_items, self.p_als):
            self.p_stack.addWidget(wdg)
        self.p_tab.idClicked.connect(self.p_stack.setCurrentIndex)
        self.p_tab.button(0).setChecked(True)
        lay.addWidget(self.p_stack, 1)

        self._cur: str | None = None
        self.strat.currentIndexChanged.connect(self._load_preset)
        for sig in (self.p_ops.changed, self.p_items.changed, self.p_als.changed, self.p_note.textChanged):
            sig.connect(self._store_preset)
        self._label_strategies()
        self._load_preset(0)
        return w

    def _page_general(self, current_manual: str | None) -> QWidget:
        w, lay = self._page("")
        f = QFormLayout()
        f.setLabelAlignment(Qt.AlignLeft)
        f.setSpacing(12)
        self.lang = QComboBox()
        for code, name in LANGUAGES.items():
            self.lang.addItem(name, code)
        self.lang.setCurrentIndex(max(0, self.lang.findData(self.settings.language)))
        self.lang.currentIndexChanged.connect(self._lang_changed)
        f.addRow(tr("language"), self.lang)

        self.manual = QComboBox()
        self.manual.addItem(tr("auto_detect"), None)
        for s in self.gd.raw["strategies"]:
            t = self.gd.strategy_label(s)
            self.manual.addItem(f"{t['leader']} 【{t['name']}】", s["leader"])
        self.manual.setCurrentIndex(max(0, self.manual.findData(current_manual)))
        self.manual.currentIndexChanged.connect(lambda i: self.manual_strategy.emit(self.manual.itemData(i)))
        f.addRow(tr("strategy_pick"), self.manual)

        self.opacity = QSlider(Qt.Horizontal, minimum=50, maximum=100, value=self.settings.panel_opacity)
        self.opacity.valueChanged.connect(self._opacity_changed)
        f.addRow(tr("opacity"), self.opacity)

        self.notify = QCheckBox(tr("notify_desc"))
        self.notify.setChecked(self.settings.notify)
        self.notify.toggled.connect(lambda v: self._set("notify", v))
        f.addRow(tr("notify"), self.notify)

        self.autostart = QCheckBox(tr("autostart_desc"))
        self.autostart.setEnabled(autostart.supported())
        self.autostart.setChecked(autostart.is_enabled())
        self.autostart.toggled.connect(autostart.set_enabled)
        f.addRow(tr("autostart"), self.autostart)

        f.addRow(tr("hotkeys"), QLabel(tr("hotkeys_desc", s=self.settings.hotkey_settings,
                                          o=self.settings.hotkey_toggle), objectName="Muted"))

        self.interval = QComboBox()
        for ms, key in ((400, "speed_fast"), (700, "speed_normal"), (1200, "speed_slow")):
            self.interval.addItem(tr(key, ms=ms), ms)
        cur = self.interval.findData(self.settings.interval_ms)
        if cur < 0:
            self.interval.addItem(f"{self.settings.interval_ms} ms", self.settings.interval_ms)
            cur = self.interval.count() - 1
        self.interval.setCurrentIndex(cur)
        self.interval.currentIndexChanged.connect(lambda i: self._set("interval_ms", self.interval.itemData(i)))
        f.addRow(tr("interval"), self.interval)

        self.title = QLineEdit(self.settings.window_title)
        self.title.textChanged.connect(lambda t: self._set("window_title", t.strip() or "明日方舟"))
        f.addRow(tr("window_title"), self.title)
        lay.addLayout(f)
        lay.addStretch(1)
        return w

    # ---------- 프리셋 ----------
    def _preset_key(self, leader: str) -> str:
        s = self.gd.strategy(leader)
        for k in (leader, s and s["name"]):
            if k and k in self.settings.presets:
                return k
        return leader

    def _label_strategies(self) -> None:
        """프리셋이 있는 전략 앞에 ● 표시."""
        for i in range(self.strat.count()):
            s = self.gd.strategy(self.strat.itemData(i))
            t = self.gd.strategy_label(s)
            mark = "● " if self._preset_key(s["leader"]) in self.settings.presets else ""
            label = f"{mark}{t['leader']} 【{t['name']}】"
            if self.strat.itemText(i) != label:
                self.strat.setItemText(i, label)

    def _load_preset(self, idx: int) -> None:
        leader = self.strat.itemData(idx)
        if leader is None:
            return
        self._cur = None
        p = self.settings.presets.get(self._preset_key(leader))
        self.p_ops.set_checked(p.operators if p else [])
        self.p_items.set_checked(p.equipment if p else [])
        self.p_als.set_checked(p.alliances if p else [])
        self.p_note.setText(p.note if p else "")
        self.strat_effect.setText(self.gd.strategy_label(self.gd.strategy(leader))["effect"])
        self._cur = leader

    def _store_preset(self, *_):
        if not self._cur:
            return
        key = self._preset_key(self._cur)
        ops, items, als = self.p_ops.checked(), self.p_items.checked(), self.p_als.checked()
        note = self.p_note.text().strip()
        if ops or items or als or note:
            self.settings.presets[key] = Preset(key, ops, items, als, note)
        else:
            self.settings.presets.pop(key, None)
        self._label_strategies()
        self._changed()

    # ---------- 저장 ----------
    def _set(self, attr: str, value) -> None:
        setattr(self.settings, attr, value)
        self._changed()

    def _opacity_changed(self, v: int) -> None:
        self.settings.panel_opacity = v
        self.update()
        self._changed()

    def _changed(self) -> None:
        self.applied.emit()            # 오버레이에는 바로 반영
        self._save_timer.start()       # 파일 저장은 잠깐 모았다가

    def _save(self) -> None:
        config.save_user_settings(self.settings)
        self.saved.setText(tr("saved"))
        QTimer.singleShot(1500, lambda: self.saved.setText(""))

    def _lang_changed(self, idx: int) -> None:
        self.settings.language = self.lang.itemData(idx)
        self._save()
        self.language_changed.emit()

    def closeEvent(self, e):
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._save()
        super().closeEvent(e)

    # ---------- 헤더 드래그 ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and e.position().y() < 50:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None
