"""설정 패널 — 게임 창 위에 반투명으로 뜨고, 바꾸는 즉시 저장·반영된다."""
from __future__ import annotations

import copy

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFormLayout, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPushButton, QSlider, QStackedWidget, QVBoxLayout, QWidget)

from . import autostart, config, theme
from .config import Preset, new_id
from .gamedata import GameData
from .i18n import LANGUAGES, tr
from .pickers import AlliancePicker, CardPicker, ConfirmButton


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
        p.setCompositionMode(QPainter.CompositionMode_Source)   # 이전 프레임을 지우고 다시 칠함 (잔상 방지)
        p.fillRect(self.rect(), bg)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
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
        body = QHBoxLayout()
        lay.addLayout(body, 1)

        # 왼쪽: 프리셋 목록 + 관리 버튼
        left = QVBoxLayout()
        self.p_list = QListWidget(objectName="PresetList")
        self.p_list.setFixedWidth(220)
        left.addWidget(self.p_list, 1)
        grid = QGridLayout()
        grid.setSpacing(4)
        self.p_btns = {}
        specs = (("p_new", self._preset_new), ("p_dup", self._preset_dup),
                 ("p_save", self._preset_save), ("p_rename", self._preset_rename),
                 ("p_export", self._preset_export), ("p_import", self._preset_import))
        for i, (key, fn) in enumerate(specs):
            b = QPushButton(tr(key))
            b.clicked.connect(fn)
            grid.addWidget(b, i // 2, i % 2)
            self.p_btns[key] = b
        delete = ConfirmButton(tr("p_delete"))
        delete.confirmed.connect(self._preset_delete)
        grid.addWidget(delete, 3, 0, 1, 2)
        self.p_btns["p_delete"] = delete
        left.addLayout(grid)

        # 코드 내보내기/가져오기 줄 (대화상자 대신 패널 안에서)
        self.code_box = QWidget(objectName="CodeBox")
        cb = QVBoxLayout(self.code_box)
        cb.setContentsMargins(0, 4, 0, 0)
        self.code_msg = QLabel(objectName="Hint")
        self.code_msg.setWordWrap(True)
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText(tr("p_import_label"))
        self.code_edit.returnPressed.connect(self._code_go)
        row = QHBoxLayout()
        self.code_go = QPushButton(tr("p_import_go"), objectName="Primary")
        self.code_go.clicked.connect(self._code_go)
        close = QPushButton(tr("close"))
        close.clicked.connect(lambda: self.code_box.hide())
        row.addWidget(self.code_go)
        row.addWidget(close)
        cb.addWidget(self.code_msg)
        cb.addWidget(self.code_edit)
        cb.addLayout(row)
        self.code_box.hide()
        left.addWidget(self.code_box)
        body.addLayout(left)

        # 오른쪽: 선택한 프리셋 편집
        self.p_editor = QWidget()
        ed = QVBoxLayout(self.p_editor)
        ed.setContentsMargins(8, 0, 0, 0)
        nrow = QHBoxLayout()
        nrow.addWidget(QLabel(tr("p_name")))
        self.p_name = QLineEdit()
        self.p_name.setMaxLength(40)
        self.p_name.textEdited.connect(self._preset_renamed)
        nrow.addWidget(self.p_name, 1)
        ed.addLayout(nrow)
        srow = QHBoxLayout()
        srow.addWidget(QLabel(tr("p_strategies")))
        self.p_strat_add = QComboBox()
        self.p_strat_add.setEditable(True)
        self.p_strat_add.setInsertPolicy(QComboBox.NoInsert)
        self.p_strat_add.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.p_strat_add.setMinimumContentsLength(12)
        self.p_strat_add.lineEdit().setPlaceholderText(tr("strategy_search"))
        self.p_strat_add.addItem("", None)
        for st in self.gd.raw["strategies"]:
            t = self.gd.strategy_label(st)
            self.p_strat_add.addItem(f"{t['leader']} 【{t['name']}】", st["leader"])
        self.p_strat_add.activated.connect(self._preset_link)
        srow.addWidget(self.p_strat_add, 1)
        ed.addLayout(srow)
        self.p_chips = QHBoxLayout()
        self.p_chips.setSpacing(4)
        chips_w = QWidget()
        chips_w.setLayout(self.p_chips)
        ed.addWidget(chips_w)

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
        ed.addLayout(tabs)
        self.p_stack = QStackedWidget()
        self.p_ops = CardPicker(self.gd, "operator", compact=True)
        self.p_items = CardPicker(self.gd, "equipment", compact=True)
        self.p_als = AlliancePicker(self.gd)
        for wdg in (self.p_ops, self.p_items, self.p_als):
            self.p_stack.addWidget(wdg)
        self.p_tab.idClicked.connect(self.p_stack.setCurrentIndex)
        self.p_tab.button(0).setChecked(True)
        ed.addWidget(self.p_stack, 1)
        body.addWidget(self.p_editor, 1)
        self.p_empty = QLabel(tr("p_empty"), objectName="Muted", alignment=Qt.AlignCenter)
        self.p_empty.setWordWrap(True)
        body.addWidget(self.p_empty, 1)

        self._loading = False
        self.p_list.currentRowChanged.connect(self._preset_load)
        for sig in (self.p_ops.changed, self.p_items.changed, self.p_als.changed, self.p_note.textChanged):
            sig.connect(self._preset_store)
        self._preset_refresh()
        return w

    # ---------- 프리셋 ----------
    def _cur_preset(self) -> Preset | None:
        it = self.p_list.currentItem()
        return self.settings.presets.get(it.data(Qt.UserRole)) if it else None

    def _preset_refresh(self, select: str | None = None) -> None:
        cur = select or (self.p_list.currentItem().data(Qt.UserRole) if self.p_list.currentItem() else None)
        self.p_list.blockSignals(True)
        self.p_list.clear()
        for p in self.settings.presets.values():
            it = QListWidgetItem(self._list_text(p))
            it.setData(Qt.UserRole, p.id)
            self.p_list.addItem(it)
            if p.id == cur:
                self.p_list.setCurrentItem(it)
        if self.p_list.currentRow() < 0 and self.p_list.count():
            self.p_list.setCurrentRow(0)
        self.p_list.blockSignals(False)
        self._preset_load()

    def _preset_load(self, *_):
        p = self._cur_preset()
        # 숨길 것을 먼저 숨긴다 (둘이 잠깐 같이 보이면 창이 그 폭만큼 커짐)
        if p is None:
            self.p_editor.hide()
            self.p_empty.show()
        else:
            self.p_empty.hide()
            self.p_editor.show()
        for k in ("p_dup", "p_rename", "p_delete", "p_export"):
            self.p_btns[k].setEnabled(p is not None)
        if not p:
            return
        self._loading = True
        self.p_ops.set_checked(p.operators)
        self.p_items.set_checked(p.equipment)
        self.p_als.set_checked(p.alliances)
        self.p_note.setText(p.note)
        self.p_name.setText(p.name)
        self._preset_chips(p)
        self._loading = False

    def _preset_chips(self, p: Preset) -> None:
        while self.p_chips.count():
            item = self.p_chips.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not p.strategies:
            self.p_chips.addWidget(QLabel(tr("p_no_strategy"), objectName="Muted"))
        for leader in p.strategies:
            st = self.gd.strategy(leader)
            t = self.gd.strategy_label(st) if st else {"leader": leader, "name": ""}
            b = QPushButton(f"{t['leader']} 【{t['name']}】  ✕", objectName="ChipButton")
            b.setToolTip(tr("p_unlink"))
            b.clicked.connect(lambda _=False, lv=leader: self._preset_unlink(lv))
            self.p_chips.addWidget(b)
        self.p_chips.addStretch(1)

    def _preset_store(self, *_):
        p = self._cur_preset()
        if not p or self._loading:
            return
        p.operators, p.equipment = self.p_ops.checked(), self.p_items.checked()
        p.alliances, p.note = self.p_als.checked(), self.p_note.text().strip()
        self.p_list.currentItem().setText(self._list_text(p))
        self._changed()

    def _preset_link(self, idx: int) -> None:
        p, leader = self._cur_preset(), self.p_strat_add.itemData(idx)
        self.p_strat_add.setCurrentIndex(0)
        if p and leader and leader not in p.strategies:
            p.strategies.append(leader)
            self._preset_chips(p)
            self._preset_refresh(p.id)
            self._changed()

    def _preset_unlink(self, leader: str) -> None:
        p = self._cur_preset()
        if p and leader in p.strategies:
            p.strategies.remove(leader)
            self._preset_refresh(p.id)
            self._changed()

    def _list_text(self, p: Preset) -> str:
        return f"{p.name}\n{tr('p_summary', n=len(p.operators) + len(p.equipment), s=len(p.strategies))}"

    def _add_preset(self, p: Preset) -> None:
        self.settings.presets[p.id] = p
        self._preset_refresh(p.id)
        self._changed()

    def _preset_new(self) -> None:
        """기본 이름으로 바로 만들고, 이름 칸을 선택해 바로 고칠 수 있게."""
        n = len(self.settings.presets) + 1
        names = {p.name for p in self.settings.presets.values()}
        while tr("p_default_name", n=n) in names:
            n += 1
        self._add_preset(Preset(id=new_id(), name=tr("p_default_name", n=n)))
        self._preset_rename()

    def _preset_rename(self) -> None:
        if self._cur_preset():
            self.p_name.setFocus()
            self.p_name.selectAll()

    def _preset_renamed(self, text: str) -> None:
        p = self._cur_preset()
        if p and text.strip():
            p.name = text.strip()
            self.p_list.currentItem().setText(self._list_text(p))
            self._changed()

    def _preset_save(self) -> None:
        self._save()   # 자동 저장되지만 눌러서도 저장

    def _preset_dup(self) -> None:
        p = self._cur_preset()
        if p:
            q = copy.deepcopy(p)
            q.id, q.name = new_id(), tr("p_copy_name", n=p.name)[:40]
            self._add_preset(q)

    def _preset_delete(self) -> None:
        p = self._cur_preset()
        if p:
            del self.settings.presets[p.id]
            if self.settings.active_preset == p.id:
                self.settings.active_preset = None
            self._preset_refresh()
            self._changed()

    def _preset_export(self) -> None:
        p = self._cur_preset()
        if not p:
            return
        code = config.export_code(p)
        QGuiApplication.clipboard().setText(code)
        self._code_mode = "export"
        self.code_msg.setText(tr("p_export_done"))
        self.code_edit.setReadOnly(True)
        self.code_edit.setText(code)
        self.code_go.hide()
        self.code_box.show()
        self.code_edit.setFocus()
        self.code_edit.selectAll()

    def _preset_import(self) -> None:
        self._code_mode = "import"
        self.code_msg.setText(tr("p_import_label"))
        self.code_edit.setReadOnly(False)
        clip = QGuiApplication.clipboard().text().strip()
        self.code_edit.setText(clip if clip.startswith(config.CODE_PREFIX) else "")
        self.code_go.show()
        self.code_box.show()
        self.code_edit.setFocus()

    def _code_go(self) -> None:
        if getattr(self, "_code_mode", "") != "import":
            return
        valid = {"operators": set(self.gd.operators) | self.gd.prototypes, "equipment": set(self.gd.equipment),
                 "alliances": set(self.gd.alliances),
                 "strategies": {st["leader"] for st in self.gd.raw["strategies"]}}
        try:
            p = config.import_code(self.code_edit.text(), valid)
        except ValueError:
            self.code_msg.setText("⚠ " + tr("p_import_bad"))
            return
        self._add_preset(p)
        self.code_box.hide()

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
        self.manual.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.manual.addItem(tr("auto_detect"), None)
        for s in self.gd.raw["strategies"]:
            t = self.gd.strategy_label(s)
            self.manual.addItem(f"{t['leader']} 【{t['name']}】", s["leader"])
        self.manual.setCurrentIndex(max(0, self.manual.findData(current_manual)))
        self.manual.currentIndexChanged.connect(lambda i: self.manual_strategy.emit(self.manual.itemData(i)))
        f.addRow(tr("strategy_pick"), self.manual)

        self.active = QComboBox()
        self.active.addItem(tr("p_auto"), None)
        for p in self.settings.presets.values():
            self.active.addItem(p.name, p.id)
        self.active.setCurrentIndex(max(0, self.active.findData(self.settings.active_preset)))
        self.active.currentIndexChanged.connect(lambda i: self._set("active_preset", self.active.itemData(i)))
        f.addRow(tr("p_active"), self.active)

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
