"""선호 선택 위젯: 카드 그리드(오퍼레이터/장비), 맹약 토글, 정보 팝업.

카드: [초상화/아이콘] 이름 · 단계 / 맹약 칩(오퍼레이터) 또는 가격(장비) · 오른쪽 위 ⓘ
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QListView, QListWidget, QListWidgetItem, QPushButton,
                               QStyle, QStyledItemDelegate, QVBoxLayout, QWidget)

from . import theme
from .gamedata import TIERS, GameData
from .i18n import tr

CARD = QSize(232, 78)          # 가로형 카드 (참고: stronghold-protocol-web 战前准备)
PORTRAIT = 56
KEY, SEARCH, CHECKED = Qt.UserRole, Qt.UserRole + 1, Qt.UserRole + 2


def tier_text(tier: str) -> str:
    return tr("tier_n", n=TIERS.index(tier) + 1) if tier in TIERS else ""


def info_rect(r: QRect) -> QRect:
    """카드 오른쪽 위 ⓘ 버튼 영역 (그리기와 클릭 판정에 같이 씀)."""
    return QRect(r.right() - 26, r.top() + 6, 20, 20)


def load_pixmap(path, size: int) -> QPixmap | None:
    if not path:
        return None
    pm = QPixmap(str(path))
    if pm.isNull():
        return None
    return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


_ICONS: dict[tuple, QPixmap | None] = {}


def icon(path, size: int) -> QPixmap | None:
    key = (str(path), size)
    if key not in _ICONS:
        _ICONS[key] = load_pixmap(path, size)
    return _ICONS[key]


class ConfirmButton(QPushButton):
    """대화상자 없이 확인: 처음 누르면 '한 번 더 눌러 확인'으로 바뀌고, 3초 안에 다시 누르면 confirmed."""
    confirmed = Signal()

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self._text = text
        self._armed = False
        self._timer = QTimer(self, singleShot=True, interval=3000, timeout=self._reset)
        self.clicked.connect(self._click)

    def _click(self) -> None:
        if self._armed:
            self._reset()
            self.confirmed.emit()
        else:
            self._armed = True
            self.setText(tr("confirm_again"))
            self.setObjectName("Danger")
            self.style().unpolish(self)
            self.style().polish(self)
            self._timer.start()

    def _reset(self) -> None:
        self._armed = False
        self.setText(self._text)
        self.setObjectName("")
        self.style().unpolish(self)
        self.style().polish(self)


class CardDelegate(QStyledItemDelegate):
    info_clicked = Signal(str)

    def __init__(self, gd: GameData, kind: str, parent=None) -> None:
        super().__init__(parent)
        self.gd, self.kind = gd, kind
        self._pix: dict[str, QPixmap | None] = {}

    def sizeHint(self, opt, index):
        grid = self.parent().gridSize() if self.parent() else CARD
        return grid if grid.isValid() else CARD

    def pixmap(self, zh: str) -> QPixmap | None:
        if zh not in self._pix:
            path = self.gd.avatar(zh) if self.kind == "operator" else self.gd.item_icon(zh)
            self._pix[zh] = load_pixmap(path, PORTRAIT)
        return self._pix[zh]

    def editorEvent(self, event, model, opt, index):
        # ⓘ 클릭은 선택 토글 대신 정보 창
        if event.type() == QEvent.MouseButtonRelease and info_rect(opt.rect.adjusted(4, 4, -4, -4)).contains(
                event.position().toPoint()):
            self.info_clicked.emit(index.data(KEY))
            return True
        return False

    def paint(self, p: QPainter, opt, index) -> None:
        zh = index.data(KEY)
        is_op = self.kind == "operator"
        info = (self.gd.operators if is_op else self.gd.equipment).get(zh, {})
        checked = bool(index.data(CHECKED))
        hover = bool(opt.state & QStyle.State_MouseOver)
        r = opt.rect.adjusted(4, 4, -4, -4)
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        p.fillRect(r, QColor(theme.RAISED) if checked else QColor(theme.PANEL))
        border = QColor(theme.ACCENT if (checked or hover) else theme.RULE)
        if hover and not checked:
            border.setAlpha(140)
        p.setPen(QPen(border, 2 if checked else 1))
        p.drawRect(r.adjusted(0, 0, -1, -1))
        p.fillRect(QRect(r.left(), r.top(), 34, 2), QColor(theme.ACCENT))

        pr = QRect(r.left() + 8, r.top() + (r.height() - PORTRAIT) // 2, PORTRAIT, PORTRAIT)
        pm = self.pixmap(zh)
        if pm:
            p.drawPixmap(pr.topLeft() + QPoint((PORTRAIT - pm.width()) // 2, (PORTRAIT - pm.height()) // 2), pm)
        tier_pm = icon(self.gd.tier_icon(info.get("tier", "")), 20)
        if tier_pm:   # 등급 아이콘: 초상화 왼쪽 아래
            p.drawPixmap(pr.left() - 3, pr.bottom() - 17, tier_pm)
        if checked:   # 초상화 왼쪽 위 체크
            cr = QRect(pr.left() - 2, pr.top() - 2, 16, 16)
            p.fillRect(cr, QColor(theme.ACCENT))
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setPen(QPen(QColor(theme.PAGE), 2))
            p.drawLine(cr.left() + 3, cr.center().y(), cr.center().x() - 1, cr.bottom() - 3)
            p.drawLine(cr.center().x() - 1, cr.bottom() - 3, cr.right() - 3, cr.top() + 4)
            p.setRenderHint(QPainter.Antialiasing, False)

        x = pr.right() + 10
        ir = info_rect(r)
        right = ir.left() - 4
        nf = QFont(p.font())
        nf.setPixelSize(14)
        nf.setBold(True)
        top = r.top() + 12
        label = self.gd.op_label(zh) if is_op else self.gd.item_label(zh)
        p.setFont(nf)
        p.setPen(QColor(theme.INK))
        p.drawText(QRect(x, top, right - x, 20), Qt.AlignLeft | Qt.AlignVCenter,
                   QFontMetrics(nf).elidedText(label, Qt.ElideRight, right - x))

        # 둘째 줄: 맹약 아이콘 (핵심 = 금색 테두리) / 장비 가격
        cy, size = top + 25, 24
        cx = x
        sf = QFont(p.font())
        sf.setPixelSize(11)
        p.setFont(sf)
        if is_op:
            if not info:
                p.setPen(QColor(theme.MUTED))
                p.drawText(QRect(cx, cy, r.right() - cx, size), Qt.AlignLeft | Qt.AlignVCenter, tr("prototype"))
            for a in info.get("alliances", []):
                core = self.gd.alliances.get(a, {}).get("type") == "core"
                box = QRect(cx, cy, size, size)
                p.fillRect(box, QColor(0, 0, 0, 120))
                p.setPen(QPen(QColor(theme.SIGNAL if core else theme.RULE), 1))
                p.drawRect(box.adjusted(0, 0, -1, -1))
                apm = icon(self.gd.alliance_icon(a), size - 4)
                if apm:
                    p.drawPixmap(box.left() + 2, box.top() + 2, apm)
                cx += size + 4
        elif info.get("price"):
            p.setPen(QColor(theme.SIGNAL))
            p.drawText(QRect(cx, cy, r.right() - cx, size), Qt.AlignLeft | Qt.AlignVCenter,
                       tr("price_n", n=info["price"]))

        # ⓘ
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(QColor(theme.ACCENT if hover else theme.MUTED), 1.2))
        p.drawEllipse(ir.adjusted(2, 2, -2, -2))
        f = QFont(p.font())
        f.setPixelSize(11)
        f.setBold(True)
        p.setFont(f)
        p.drawText(ir, Qt.AlignCenter, "i")
        p.restore()


class CardGrid(QListWidget):
    """창 폭에 맞춰 카드 너비를 늘려 오른쪽 빈 공간이 생기지 않게."""

    def _fit(self) -> None:
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


class CardPicker(QWidget):
    """카드 그리드 + 검색 + 필터.  kind: 'operator' | 'equipment'"""
    changed = Signal(list)

    def __init__(self, gd: GameData, kind: str = "operator", compact: bool = False) -> None:
        """compact: 좁은 곳(프리셋 편집)용 — 필터를 두 줄로."""
        super().__init__()
        self.gd, self.kind = gd, kind
        is_op = kind == "operator"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.search = QLineEdit(placeholderText=tr("search_ops" if is_op else "search_items"))
        self.search.setClearButtonEnabled(True)
        self.only = QPushButton(tr("only_checked_short"), checkable=True)
        self.only.setToolTip(tr("only_checked"))
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
        self.delegate = CardDelegate(gd, kind, self.list)
        self.delegate.info_clicked.connect(self.show_info)
        self.list.setItemDelegate(self.delegate)
        self.empty = QLabel(tr("no_result"), objectName="Muted", alignment=Qt.AlignCenter)
        self.empty.hide()

        order = {t: i for i, t in enumerate(TIERS)}
        src = gd.operators if is_op else gd.equipment
        keys = sorted(src, key=lambda n: (order.get(src[n].get("tier"), 9), n))
        if is_op:
            keys += sorted(gd.prototypes)
        for zh in keys:
            it = QListWidgetItem()
            it.setData(KEY, zh)
            it.setData(CHECKED, False)
            it.setData(SEARCH, self._search_text(zh))
            it.setToolTip(self._tooltip(zh))
            self.list.addItem(it)
        lay.addWidget(self.list, 1)
        lay.addWidget(self.empty)

        bar = QWidget(objectName="FilterBar")
        bar_rows = QVBoxLayout(bar)
        bar_rows.setContentsMargins(10, 8, 10, 8)
        bar_rows.setSpacing(6)
        bl = QHBoxLayout()
        bar_rows.addLayout(bl)
        row2 = QHBoxLayout() if compact else bl
        bl.setSpacing(4)
        bl.addWidget(QLabel(tr("tier")))
        self.tier_group = QButtonGroup(self)
        for i, label in enumerate([*"123456", tr("all")]):
            pm = icon(gd.tier_icon(TIERS[i]), 22) if i < 6 else None
            b = QPushButton("" if pm else label, checkable=True, objectName="Seg")
            if pm:
                b.setIcon(QIcon(pm))
                b.setIconSize(QSize(22, 22))
                b.setToolTip(tier_text(TIERS[i]))
            else:
                b.setMinimumWidth(52)
            self.tier_group.addButton(b, i)
            bl.addWidget(b)
        self.tier_group.button(6).setChecked(True)
        self.core = self.extra = None
        if is_op:
            if compact:
                bl.addStretch(1)
                bar_rows.addLayout(row2)
            else:
                bl.addSpacing(6)
            self.core = self._alliance_combo("core")
            self.extra = self._alliance_combo("extra")
            row2.addWidget(QLabel(tr("core")))
            row2.addWidget(self.core, 1)
            row2.addWidget(QLabel(tr("extra")))
            row2.addWidget(self.extra, 1)
            self.core.currentIndexChanged.connect(self._filter)
            self.extra.currentIndexChanged.connect(self._filter)
        else:
            bl.addStretch(1)
        row2.addSpacing(8)
        row2.addWidget(self.only)
        self.clear_btn = ConfirmButton(tr("clear"))
        row2.addWidget(self.clear_btn)
        lay.addWidget(bar)

        self.list.itemClicked.connect(self._toggle)
        self.search.textChanged.connect(self._filter)
        self.only.toggled.connect(self._filter)
        self.tier_group.idClicked.connect(self._filter)
        self.clear_btn.confirmed.connect(self._clear)
        self._update_count()

    def _alliance_combo(self, kind: str) -> QComboBox:
        c = QComboBox()
        # 좁은 화면(프리셋 편집 등)에서도 줄어들 수 있게
        c.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        c.setMinimumContentsLength(5)
        c.addItem(tr("all_" + kind), None)
        for zh, a in self.gd.alliances.items():
            if a["type"] == kind:
                pm = icon(self.gd.alliance_icon(zh), 18)
                c.addItem(QIcon(pm) if pm else QIcon(), self.gd.alliance_label(zh), zh)
        return c

    def _search_text(self, zh: str) -> str:
        """중/한/영 이름 어느 것으로도 검색되게."""
        kind = "operators" if self.kind == "operator" else "equipment"
        parts = [zh] + [self.gd.names.get(lang, {}).get(kind, {}).get(zh, "") for lang in ("ko", "en")]
        for a in self.gd.operators.get(zh, {}).get("alliances", []) if self.kind == "operator" else []:
            parts += [a] + [self.gd.names.get(lang, {}).get("alliances", {}).get(a, "") for lang in ("ko", "en")]
        return " ".join(parts).lower()

    def _tooltip(self, zh: str) -> str:
        if self.kind == "operator":
            info = self.gd.operators.get(zh)
            label = self.gd.op_label(zh)
            if not info:
                return label
            return f"{label} · {tier_text(info['tier'])}\n" + " / ".join(
                self.gd.alliance_label(a) for a in info["alliances"])
        info = self.gd.equipment.get(zh, {})
        return f"{self.gd.item_label(zh)} · {tier_text(info.get('tier', ''))}"

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
        core = self.core.currentData() if self.core else None
        extra = self.extra.currentData() if self.extra else None
        src = self.gd.operators if self.kind == "operator" else self.gd.equipment
        shown = 0
        for it in self.items():
            info = src.get(it.data(KEY), {})
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
        if self.checked():
            self.set_checked([])
            self.changed.emit([])

    def show_info(self, zh: str) -> None:
        InfoPopup(self.gd, self.kind, zh, self).popup_near(self.list)

    def checked(self) -> list[str]:
        return [it.data(KEY) for it in self.items() if it.data(CHECKED)]

    def set_checked(self, keys) -> None:
        keys = set(keys)
        for it in self.items():
            it.setData(CHECKED, it.data(KEY) in keys)
        self._update_count()
        self._filter()
        self.list.viewport().update()


OperatorPicker = CardPicker  # 이전 이름 호환


class InfoPopup(QWidget):
    """ⓘ 정보 창: 오퍼레이터 특질 / 장비 효과. 바깥을 누르거나 Esc로 닫힘."""

    def __init__(self, gd: GameData, kind: str, zh: str, parent=None) -> None:
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        body = QWidget(objectName="Popup")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(8)
        is_op = kind == "operator"
        info = (gd.operators if is_op else gd.equipment).get(zh, {})

        head = QHBoxLayout()
        portrait = QLabel()
        pm = load_pixmap(gd.avatar(zh) if is_op else gd.item_icon(zh), 72)
        if pm:
            portrait.setPixmap(pm)
        portrait.setFixedSize(76, 76)
        head.addWidget(portrait)
        title = QVBoxLayout()
        name = gd.op_label(zh) if is_op else gd.item_label(zh)
        title.addWidget(QLabel(name, objectName="Title"))
        tpm = icon(gd.tier_icon(info.get("tier", "")), 22)
        if tpm:
            tier_lbl = QLabel()
            tier_lbl.setPixmap(tpm)
            tier_lbl.setToolTip(tier_text(info.get("tier", "")))
            head.addWidget(tier_lbl, 0, Qt.AlignTop)
        sub = " · ".join(x for x in (zh if zh != name else "",
                                     tr("price_n", n=info["price"]) if info.get("price") else "") if x)
        title.addWidget(QLabel(sub, objectName="Muted"))
        if is_op and info.get("alliances"):
            chips = QHBoxLayout()
            for a in info["alliances"]:
                core = gd.alliances.get(a, {}).get("type") == "core"
                pm = icon(gd.alliance_icon(a), 18)
                if pm:
                    ic = QLabel()
                    ic.setPixmap(pm)
                    chips.addWidget(ic)
                chips.addWidget(QLabel(gd.alliance_label(a), objectName="ChipCore" if core else "Chip"))
            chips.addStretch(1)
            title.addLayout(chips)
        head.addLayout(title, 1)
        lay.addLayout(head)

        def section(label: str, text: str) -> None:
            if not text:
                return
            lay.addWidget(QLabel(label, objectName="Section"))
            t = QLabel(text)
            t.setWordWrap(True)
            t.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lay.addWidget(t)

        if is_op:
            if not info:
                section(tr("trait"), tr("prototype_desc"))
            else:
                ttype = gd._label("trait_types", info.get("trait_type", ""))
                section(tr("trait") + (f" · {ttype}" if ttype else ""),
                        gd.trait_text(zh))
        else:
            section(tr("effect"), gd.item_effect(zh))
            if info.get("desc"):
                d = QLabel(info["desc"], objectName="Muted")
                d.setWordWrap(True)
                lay.addWidget(d)
        self.setFixedWidth(400)

    def popup_near(self, anchor: QWidget) -> None:
        self.adjustSize()
        from PySide6.QtGui import QCursor
        pos = QCursor.pos() + QPoint(12, 12)
        scr = anchor.screen().availableGeometry()
        pos.setX(min(pos.x(), scr.right() - self.width()))
        pos.setY(min(pos.y(), scr.bottom() - self.height()))
        self.move(pos)
        self.show()


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
                b = QPushButton(gd.alliance_label(zh), checkable=True)
                pm = icon(gd.alliance_icon(zh), 22)
                if pm:
                    b.setIcon(QIcon(pm))
                    b.setIconSize(QSize(22, 22))
                b.setToolTip(f"{zh} · {tr('members_n', n=len(a['operators']))}")
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
