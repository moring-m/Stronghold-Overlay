"""선호 설정 GUI."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPlainTextEdit, QPushButton, QSpinBox, QTabWidget, QVBoxLayout,
                               QWidget)

from . import config
from .config import Preset
from .gamedata import GameData
from .i18n import LANGUAGES, set_language, tr


class CheckList(QWidget):
    """검색 가능한 체크박스 목록."""
    changed = Signal()

    def __init__(self, items: list[tuple[str, str, str]], hint: str = "") -> None:
        """items: (키, 표시 문자열, 검색용 추가 문자열)"""
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        if hint:
            h = QLabel(hint)
            h.setWordWrap(True)
            lay.addWidget(h)
        top = QHBoxLayout()
        self.search = QLineEdit(placeholderText=tr("search"))
        self.search.setClearButtonEnabled(True)
        self.only = QCheckBox(tr("only_checked"))
        top.addWidget(self.search, 1)
        top.addWidget(self.only)
        lay.addLayout(top)
        self.list = QListWidget()
        for key, label, extra in items:
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, key)
            it.setData(Qt.UserRole + 1, f"{label} {extra}".lower())
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            self.list.addItem(it)
        lay.addWidget(self.list, 1)
        bottom = QHBoxLayout()
        self.count = QLabel()
        clear = QPushButton(tr("clear"))
        bottom.addWidget(self.count, 1)
        bottom.addWidget(clear)
        lay.addLayout(bottom)

        self.search.textChanged.connect(self._filter)
        self.only.toggled.connect(self._filter)
        self.list.itemChanged.connect(self._on_change)
        clear.clicked.connect(lambda: self.set_checked([]))
        self._on_change()

    def _items(self):
        return (self.list.item(i) for i in range(self.list.count()))

    def _filter(self) -> None:
        q = self.search.text().strip().lower()
        for it in self._items():
            hide = (q and q not in it.data(Qt.UserRole + 1)) or (
                self.only.isChecked() and it.checkState() != Qt.Checked)
            it.setHidden(bool(hide))

    def _on_change(self, *_):
        self.count.setText(tr("selected_n", n=len(self.checked())))
        self.changed.emit()

    def checked(self) -> list[str]:
        return [it.data(Qt.UserRole) for it in self._items() if it.checkState() == Qt.Checked]

    def set_checked(self, keys) -> None:
        keys = set(keys)
        self.list.blockSignals(True)
        for it in self._items():
            it.setCheckState(Qt.Checked if it.data(Qt.UserRole) in keys else Qt.Unchecked)
        self.list.blockSignals(False)
        self._on_change()
        self._filter()


def operator_items(gd: GameData) -> list[tuple[str, str, str]]:
    order = {t: i for i, t in enumerate("ⅠⅡⅢⅣⅤⅥ")}
    ops = sorted(gd.operators.items(), key=lambda kv: (order.get(kv[1]["tier"], 9), kv[0]))
    items = [(n, f"{n}   [{o['tier']}] {' / '.join(o['alliances'])}", o.get("prototype", ""))
             for n, o in ops]
    items += [(p, f"{p}   ({tr('prototype')})", "prototype 原型")
              for p in sorted(gd.prototypes)]
    return items


def alliance_items(gd: GameData) -> list[tuple[str, str, str]]:
    return [(n, f"{n}   [{tr(a['type'])}]  ({len(a['operators'])})", " ".join(a["operators"]))
            for n, a in gd.alliances.items()]


class SettingsDialog(QDialog):
    def __init__(self, settings: config.Settings, gd: GameData, parent=None) -> None:
        super().__init__(parent)
        self.settings, self.gd = settings, gd
        self.setWindowTitle(tr("settings_title"))
        self.resize(620, 640)
        # 프리셋은 편집용 사본에서 작업하고 저장 시 반영
        self.presets = {k: Preset(k, list(p.operators), list(p.alliances), p.note)
                        for k, p in settings.presets.items()}
        self.notes = dict(settings.enemy_notes)

        tabs = QTabWidget()
        tabs.addTab(self._general(), tr("tab_general"))
        self.ops = CheckList(operator_items(gd), tr("ops_hint"))
        self.ops.set_checked(settings.base_operators)
        tabs.addTab(self.ops, tr("tab_operators"))
        self.als = CheckList(alliance_items(gd), tr("alliances_hint"))
        self.als.set_checked(settings.base_alliances)
        tabs.addTab(self.als, tr("tab_alliances"))
        tabs.addTab(self._presets(), tr("tab_presets"))
        tabs.addTab(self._notes(), tr("tab_notes"))

        bb = QDialogButtonBox()
        bb.addButton(tr("save"), QDialogButtonBox.AcceptRole)
        bb.addButton(tr("cancel"), QDialogButtonBox.RejectRole)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        lay.addWidget(bb)

    # ---- 탭 ----
    def _general(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        self.lang = QComboBox()
        for code, name in LANGUAGES.items():
            self.lang.addItem(name, code)
        self.lang.setCurrentIndex(list(LANGUAGES).index(self.settings.language)
                                  if self.settings.language in LANGUAGES else 0)
        self.title = QLineEdit(self.settings.window_title)
        self.interval = QSpinBox(minimum=100, maximum=5000, singleStep=100, suffix=tr("ms"))
        self.interval.setValue(self.settings.interval_ms)
        f.addRow(tr("language"), self.lang)
        f.addRow(tr("window_title"), self.title)
        f.addRow(tr("interval"), self.interval)
        return w

    def _presets(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("preset_strategy")))
        self.strat = QComboBox()
        self.strat.setEditable(True)               # 입력해서 찾기
        self.strat.setInsertPolicy(QComboBox.NoInsert)
        for s in self.gd.raw["strategies"]:
            self.strat.addItem(f"{s['leader']} 【{s['name']}】", s["leader"])
        row.addWidget(self.strat, 1)
        lay.addLayout(row)
        hint = QLabel(tr("preset_hint"))
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.strat_effect = QLabel()
        self.strat_effect.setWordWrap(True)
        self.strat_effect.setStyleSheet("color: #2a9d8f;")
        lay.addWidget(self.strat_effect)
        sub = QTabWidget()
        self.p_ops = CheckList(operator_items(self.gd))
        self.p_als = CheckList(alliance_items(self.gd))
        sub.addTab(self.p_ops, tr("tab_operators"))
        sub.addTab(self.p_als, tr("tab_alliances"))
        lay.addWidget(sub, 1)
        nrow = QHBoxLayout()
        nrow.addWidget(QLabel(tr("note")))
        self.p_note = QLineEdit()
        nrow.addWidget(self.p_note, 1)
        lay.addLayout(nrow)

        self._cur: str | None = None
        self.strat.currentIndexChanged.connect(self._load_preset)
        for sig in (self.p_ops.changed, self.p_als.changed, self.p_note.textChanged):
            sig.connect(self._store_preset)
        self._mark_presets()
        self._load_preset(self.strat.currentIndex())
        return w

    def _preset_key(self, leader: str) -> str:
        """기존 설정이 전략 이름으로 저장돼 있으면 그 키를 유지."""
        s = self.gd.strategy(leader)
        for k in (leader, s and s["name"]):
            if k and k in self.presets:
                return k
        return leader

    def _load_preset(self, idx: int) -> None:
        leader = self.strat.itemData(idx)
        if leader is None:
            return
        self._cur = None  # 로딩 중 저장 방지
        p = self.presets.get(self._preset_key(leader))
        self.p_ops.set_checked(p.operators if p else [])
        self.p_als.set_checked(p.alliances if p else [])
        self.p_note.setText(p.note if p else "")
        s = self.gd.strategy(leader)
        self.strat_effect.setText(s["effect"] if s else "")
        self._cur = leader

    def _store_preset(self, *_):
        if not self._cur:
            return
        key = self._preset_key(self._cur)
        ops, als, note = self.p_ops.checked(), self.p_als.checked(), self.p_note.text().strip()
        if ops or als or note:
            self.presets[key] = Preset(key, ops, als, note)
        else:
            self.presets.pop(key, None)
        self._mark_presets()

    def _mark_presets(self) -> None:
        """프리셋이 있는 전략 앞에 ● 표시."""
        for i in range(self.strat.count()):
            leader = self.strat.itemData(i)
            s = self.gd.strategy(leader)
            label = f"{leader} 【{s['name']}】" if s else leader
            if self._preset_key(leader) in self.presets:
                label = "● " + label
            if self.strat.itemText(i) != label:
                self.strat.setItemText(i, label)

    def _notes(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("boss")))
        self.boss = QComboBox()
        self.boss.addItems(self.gd.raw["bosses"])
        row.addWidget(self.boss, 1)
        lay.addLayout(row)
        self.boss_note = QPlainTextEdit()
        lay.addWidget(self.boss_note, 1)
        self._boss_cur = None
        self.boss.currentTextChanged.connect(self._load_note)
        self.boss_note.textChanged.connect(self._store_note)
        self._load_note(self.boss.currentText())
        return w

    def _load_note(self, name: str) -> None:
        self._boss_cur = None
        self.boss_note.setPlainText(config.lookup_note(self.notes, name))
        self._boss_cur = name

    def _store_note(self) -> None:
        if self._boss_cur:
            t = self.boss_note.toPlainText().strip()
            if t:
                self.notes[self._boss_cur] = t
            else:
                self.notes.pop(self._boss_cur, None)

    # ---- 저장 ----
    def _save(self) -> None:
        s = self.settings
        s.language = self.lang.currentData()
        s.window_title = self.title.text().strip() or "明日方舟"
        s.interval_ms = self.interval.value()
        s.base_operators = self.ops.checked()
        s.base_alliances = self.als.checked()
        s.presets = self.presets
        s.enemy_notes = self.notes
        config.save_user_settings(s)
        set_language(s.language)
        self.accept()
