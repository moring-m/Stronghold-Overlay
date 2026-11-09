"""선호 선택 위젯: 초상화 카드 그리드(오퍼레이터), 맹약 토글 그리드.

카드에는 초상화 위에 등급, 이름, 맹약만 표시한다.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QListView, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
                               QStyle, QStyledItemDelegate, QVBoxLayout, QWidget)

from . import theme
from .gamedata import GameData
from .i18n import tr

TIERS = "ⅠⅡⅢⅣⅤⅥ"
CARD = QSize(232, 78)          # 가로형 카드 (참고: stronghold-protocol-web 战前准备)
PORTRAIT = 56
KEY, SEARCH, CHECKED = Qt.UserRole, Qt.UserRole + 1, Qt.UserRole + 2


def tier_text(tier: str) -> str:
    n = TIERS.index(tier) + 1 if tier in TIERS else 0
    return tr("tier_n", n=n) if n else ""


class CardDelegate(QStyledItemDelegate):
    """[초상화] 이름 · N단계 / 맹약 칩.  선택 시 민트 테두리와 체크."""

    def __init__(self, gd: GameData, parent=None) -> None:
        super().__init__(parent)
        self.gd = gd
        self._pix: dict[str, QPixmap] = {}

    def sizeHint(self, opt, index):
        grid = self.parent().gridSize() if self.parent() else CARD
        return grid if grid.isValid() else CARD

    def pixmap(self, zh: str) -> QPixmap | None:
        if zh not in self._pix:
            p = self.gd.avatar(zh)
            pm = QPixmap(str(p)) if p else QPixmap()
            if not pm.isNull():
                pm = pm.scaled(PORTRAIT, PORTRAIT, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._pix[zh] = pm
        pm = self._pix[zh]
        return None if pm.isNull() else pm

    def paint(self, p: QPainter, opt, index) -> None:
        zh = index.data(KEY)
        info = self.gd.operators.get(zh, {})
        checked = bool(index.data(CHECKED))
        hover = bool(opt.state & QStyle.State_MouseOver)
        r = opt.rect.adjusted(4, 4, -4, -4)
        p.save()
        p.setRenderHint(QPainter.Antialiasing, False)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        # 카드 배경/테두리
        p.fillRect(r, QColor(theme.RAISED) if checked else QColor(theme.PANEL))
        border = QColor(theme.ACCENT) if checked else QColor(theme.ACCENT if hover else theme.RULE)
        if hover and not checked:
            border.setAlpha(140)
        p.setPen(QPen(border, 2 if checked else 1))
        p.drawRect(r.adjusted(0, 0, -1, -1))
        p.fillRect(QRect(r.left(), r.top(), 34, 2), QColor(theme.ACCENT))   # 좌상단 강조선

        # 초상화
        pr = QRect(r.left() + 8, r.top() + (r.height() - PORTRAIT) // 2, PORTRAIT, PORTRAIT)
        pm = self.pixmap(zh)
        if pm:
            p.drawPixmap(pr.topLeft() + QPoint((PORTRAIT - pm.width()) // 2, (PORTRAIT - pm.height()) // 2), pm)
        x = pr.right() + 10
        right = r.right() - 8

        # 이름 + 단계
        nf = QFont(p.font())
        nf.setPixelSize(14)
        nf.setBold(True)
        tf = QFont(p.font())
        tf.setPixelSize(11)
        tier = tier_text(info.get("tier", ""))
        tw = QFontMetrics(tf).horizontalAdvance(tier) + 6 if tier else 0
        nfm = QFontMetrics(nf)
        name = nfm.elidedText(self.gd.op_label(zh), Qt.ElideRight, right - x - tw - (18 if checked else 0))
        p.setFont(nf)
        p.setPen(QColor(theme.INK))
        top = r.top() + 12
        p.drawText(QRect(x, top, right - x, 20), Qt.AlignLeft | Qt.AlignVCenter, name)
        if tier:
            p.setFont(tf)
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRect(x + nfm.horizontalAdvance(name) + 6, top, tw, 20), Qt.AlignLeft | Qt.AlignVCenter, tier)

        # 맹약 칩 (핵심 = 금색, 부가 = 청록)
        cf = QFont(p.font())
        cf.setPixelSize(11)
        cfm = QFontMetrics(cf)
        p.setFont(cf)
        cx, cy, ch = x, top + 26, cfm.height() + 4
        chips = info.get("alliances", []) or []
        if not info:
            chips = []
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRect(x, cy, right - x, ch), Qt.AlignLeft | Qt.AlignVCenter, tr("prototype"))
        for a in chips:
            label = self.gd.alliance_label(a)
            w = cfm.horizontalAdvance(label) + 10
            if cx + w > right:
                break
            core = self.gd.alliances.get(a, {}).get("type") == "core"
            col = QColor(theme.SIGNAL if core else theme.MUTED)
            rect = QRect(cx, cy, w, ch)
            fill = QColor(col)
            fill.setAlpha(28)
            p.fillRect(rect, fill)
            p.setPen(QPen(col, 1))
            p.drawRect(rect.adjusted(0, 0, -1, -1))
            p.drawText(rect, Qt.AlignCenter, label)
            cx += w + 4

        # 선택 체크
        if checked:
            cr = QRect(right - 14, r.top() + 10, 14, 14)
            p.fillRect(cr, QColor(theme.ACCENT))
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setPen(QPen(QColor(theme.PAGE), 2))
            p.drawLine(cr.left() + 3, cr.center().y(), cr.center().x() - 1, cr.bottom() - 3)
            p.drawLine(cr.center().x() - 1, cr.bottom() - 3, cr.right() - 2, cr.top() + 3)
        p.restore()


class CardGrid(QListWidget):
    """창 폭에 맞춰 카드 너비를 늘려 오른쪽 빈 공간이 생기지 않게."""

    def _fit(self) -> None:
        # 스크롤바 표시 여부와 상관없이 같은 폭을 쓰도록 항상 스크롤바 폭을 뺀다
        vw = self.width() - self.verticalScrollBar().sizeHint().width() - 2 * self.frameWidth() - 2
        cols = max(1, vw // CARD.width())
        size = QSize(vw // cols, CARD.height())
        if size != self.gridSize():
            self.setGridSize(size)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit()

    def showEvent(self, e):
        super().showEvent(e)
        self._fit()


class OperatorPicker(QWidget):
    """초상화 카드 그리드 + 검색 + 필터(등급, 핵심/부가 맹약, 선택만)."""
    changed = Signal(list)

    def __init__(self, gd: GameData) -> None:
        super().__init__()
        self.gd = gd
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.search = QLineEdit(placeholderText=tr("search_ops"))
        self.search.setClearButtonEnabled(True)
        self.only = QPushButton(tr("only_checked"), checkable=True)
        self.count = QLabel(objectName="Counter")   # 페이지 머리 오른쪽에 붙임
        lay.addWidget(self.search)

        self.list = CardGrid()
        self.list.setViewMode(QListView.IconMode)
        self.list.setResizeMode(QListView.Adjust)
        self.list.setMovement(QListView.Static)
        self.list.setUniformItemSizes(True)
        self.list.setGridSize(CARD)
        self.list.setSpacing(0)
        self.list.setVerticalScrollMode(QListView.ScrollPerPixel)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.list.setMouseTracking(True)
        self.list.setSelectionMode(QListWidget.NoSelection)
        self.list.setStyleSheet("QListWidget { background: transparent; border: none; }")
        self.list.setItemDelegate(CardDelegate(gd, self.list))
        self.empty = QLabel(tr("no_result"), objectName="Muted", alignment=Qt.AlignCenter)
        self.empty.hide()
        order = {t: i for i, t in enumerate(TIERS)}
        prototypes = sorted(gd.prototypes)
        ops = sorted(gd.operators, key=lambda n: (order.get(gd.operators[n]["tier"], 9), n))
        for zh in ops + prototypes:
            it = QListWidgetItem()
            it.setData(KEY, zh)
            it.setData(CHECKED, False)
            it.setData(SEARCH, self._search_text(zh))
            it.setToolTip(self._tooltip(zh))
            self.list.addItem(it)
        lay.addWidget(self.list, 1)
        lay.addWidget(self.empty)

        # 하단 필터 바
        bar = QWidget(objectName="FilterBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(10, 8, 10, 8)
        bl.addWidget(QLabel(tr("tier")))
        self.tier_group = QButtonGroup(self)
        for i, label in enumerate([*"123456", tr("all")]):
            b = QPushButton(label, checkable=True, objectName="Seg")
            if i == 6:
                b.setMinimumWidth(52)
            self.tier_group.addButton(b, i)
            bl.addWidget(b)
        self.tier_group.button(6).setChecked(True)
        bl.addSpacing(12)
        self.core = self._alliance_combo("core")
        self.extra = self._alliance_combo("extra")
        bl.addWidget(QLabel(tr("core")))
        bl.addWidget(self.core, 1)
        bl.addWidget(QLabel(tr("extra")))
        bl.addWidget(self.extra, 1)
        bl.addSpacing(8)
        bl.addWidget(self.only)
        self.clear_btn = QPushButton(tr("clear"))
        bl.addWidget(self.clear_btn)
        lay.addWidget(bar)

        self.list.itemClicked.connect(self._toggle)
        self.search.textChanged.connect(self._filter)
        self.only.toggled.connect(self._filter)
        self.tier_group.idClicked.connect(self._filter)
        self.core.currentIndexChanged.connect(self._filter)
        self.extra.currentIndexChanged.connect(self._filter)
        self.clear_btn.clicked.connect(self._clear)
        self._update_count()

    def _alliance_combo(self, kind: str) -> QComboBox:
        c = QComboBox()
        c.addItem(tr("all_" + kind), None)
        for zh, a in self.gd.alliances.items():
            if a["type"] == kind:
                c.addItem(self.gd.alliance_label(zh), zh)
        return c

    def _search_text(self, zh: str) -> str:
        """현재 언어뿐 아니라 중/한/영 이름 모두로 검색되게."""
        parts = [zh] + [self.gd.names.get(l, {}).get("operators", {}).get(zh, "") for l in ("ko", "en")]
        for a in self.gd.operators.get(zh, {}).get("alliances", []):
            parts += [a] + [self.gd.names.get(l, {}).get("alliances", {}).get(a, "") for l in ("ko", "en")]
        return " ".join(parts).lower()

    def _tooltip(self, zh: str) -> str:
        info = self.gd.operators.get(zh)
        if not info:
            return f"{self.gd.op_label(zh)}\n{tr('prototype')}"
        return f"{self.gd.op_label(zh)} ({zh}) · {info['tier']}\n" + " / ".join(
            self.gd.alliance_label(a) for a in info["alliances"])

    def items(self):
        return (self.list.item(i) for i in range(self.list.count()))

    def _toggle(self, it: QListWidgetItem) -> None:
        it.setData(CHECKED, not it.data(CHECKED))
        self._update_count()
        if self.only.isChecked():
            self._filter()
        self.changed.emit(self.checked())

    def _filter(self, *_):
        q = self.search.text().strip().lower()
        tier_id = self.tier_group.checkedId()
        tier = TIERS[tier_id] if 0 <= tier_id < 6 else None
        core, extra = self.core.currentData(), self.extra.currentData()
        shown = 0
        for it in self.items():
            zh = it.data(KEY)
            info = self.gd.operators.get(zh, {})
            al = info.get("alliances", [])
            hide = ((q and q not in it.data(SEARCH))
                    or (self.only.isChecked() and not it.data(CHECKED))
                    or (tier and info.get("tier") != tier)
                    or (core and core not in al) or (extra and extra not in al))
            it.setHidden(bool(hide))
            shown += not hide
        self.empty.setVisible(shown == 0)

    def _update_count(self):
        self.count.setText(f"<span style='font-size:22px;font-weight:700;color:{theme.ACCENT}'>"
                           f"{len(self.checked())}</span><span style='color:{theme.MUTED}'>"
                           f"&nbsp;/ {self.list.count()} {tr('selected')}</span>")

    def _clear(self):
        if not self.checked():
            return
        if QMessageBox.question(self, tr("clear"), tr("clear_confirm")) == QMessageBox.Yes:
            self.set_checked([])
            self.changed.emit([])

    def checked(self) -> list[str]:
        return [it.data(KEY) for it in self.items() if it.data(CHECKED)]

    def set_checked(self, keys) -> None:
        keys = set(keys)
        for it in self.items():
            it.setData(CHECKED, it.data(KEY) in keys)
        self._update_count()
        self._filter()
        self.list.viewport().update()


class AlliancePicker(QWidget):
    """맹약 토글 버튼 그리드 (핵심 / 부가 구역)."""
    changed = Signal(list)

    def __init__(self, gd: GameData) -> None:
        super().__init__()
        self.gd = gd
        self.buttons: dict[str, QPushButton] = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        for kind in ("core", "extra"):
            lay.addWidget(QLabel(tr(kind + "_alliances"), objectName="Section"))
            grid = QGridLayout()
            grid.setSpacing(6)
            items = [(zh, a) for zh, a in gd.alliances.items() if a["type"] == kind]
            for i, (zh, a) in enumerate(items):
                b = QPushButton(f"{gd.alliance_label(zh)}", checkable=True)
                b.setToolTip(f"{zh} · {tr('members_n', n=len(a['operators']))}\n{a['effect'][:200]}")
                b.setMinimumHeight(34)
                b.toggled.connect(lambda *_: self.changed.emit(self.checked()))
                grid.addWidget(b, i // 5, i % 5)
                self.buttons[zh] = b
            lay.addLayout(grid)
        lay.addStretch(1)

    def checked(self) -> list[str]:
        return [zh for zh, b in self.buttons.items() if b.isChecked()]

    def set_checked(self, keys) -> None:
        keys = set(keys)
        for zh, b in self.buttons.items():
            b.blockSignals(True)
            b.setChecked(zh in keys)
            b.blockSignals(False)
