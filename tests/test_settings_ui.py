"""설정 패널 테스트 (Qt를 띄울 수 없는 환경이면 건너뜀)."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import Qt  # noqa: E402

from stronghold_overlay import config, i18n  # noqa: E402
from stronghold_overlay.gamedata import GameData  # noqa: E402
from stronghold_overlay.pickers import CHECKED, KEY  # noqa: E402

GD = GameData.load()


@pytest.fixture
def panel(tmp_path, monkeypatch):
    from stronghold_overlay.settings_ui import SettingsPanel
    monkeypatch.setattr(config, "USER_FILE", tmp_path / "user_settings.json")
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    i18n.set_language("ko")
    p = SettingsPanel(config.load_settings(), GD)
    yield p
    i18n.set_language("ko")


def click_card(picker, zh):
    it = next(i for i in picker.items() if i.data(KEY) == zh)
    picker.list.itemClicked.emit(it)
    return it


def test_click_toggles_and_autosaves(panel):
    applied = []
    panel.applied.connect(lambda: applied.append(1))
    it = click_card(panel.ops, "仇白")
    assert it.data(CHECKED) and "仇白" in panel.settings.base_operators and applied
    panel._save()                                   # 타이머 대신 즉시 저장
    assert "仇白" in config.load_settings().base_operators
    click_card(panel.ops, "仇白")
    assert "仇白" not in panel.settings.base_operators


def test_filters(panel):
    ops = panel.ops
    ops.search.setText("thorns")                    # 영어 이름으로도 검색
    visible = [i.data(KEY) for i in ops.items() if not i.isHidden()]
    assert set(visible) == {"棘刺", "引星棘刺"}
    ops.search.setText("")
    ops.tier_group.button(3).click()                # Ⅳ
    ops.core.setCurrentIndex(ops.core.findData("炎"))
    visible = {i.data(KEY) for i in ops.items() if not i.isHidden()}
    assert visible and all(GD.operators[n]["tier"] == "Ⅳ" and "炎" in GD.operators[n]["alliances"]
                           for n in visible)
    ops.search.setText("존재하지않는이름")
    assert ops.empty.isVisibleTo(ops)


def test_preset_management(panel):
    panel._preset_new()                                                 # 대화상자 없이 바로 생성
    p = panel._cur_preset()
    assert p.name == "프리셋 1" and panel.p_name.text() == "프리셋 1"
    panel.p_name.setText("아미야 덱")
    panel.p_name.textEdited.emit("아미야 덱")                            # 이름 칸에서 바로 수정
    assert p.name == "아미야 덱" and panel.p_list.currentItem().text().startswith("아미야 덱")
    panel._preset_link(panel.p_strat_add.findData("阿米娅"))
    click_card(panel.p_ops, "复奏")
    click_card(panel.p_items, "歌利亚头盔")
    assert p.strategies == ["阿米娅"] and p.operators == ["复奏"] and p.equipment == ["歌利亚头盔"]

    names, _, active = panel.settings.preferred("阿米娅")
    assert {"复奏", "歌利亚头盔"} <= names and active == [p]
    assert panel.settings.preferred("歌利亚")[2] == []

    panel._preset_dup()
    q = panel._cur_preset()
    assert q.id != p.id and q.operators == p.operators and "사본" in q.name

    delete = panel.p_btns["p_delete"]
    delete.click()                                                      # 첫 클릭은 확인 대기
    assert q.id in panel.settings.presets and delete.text() == "한 번 더 눌러 확인"
    delete.click()                                                      # 두 번째 클릭에 삭제
    assert q.id not in panel.settings.presets and p.id in panel.settings.presets

    panel.p_list.setCurrentRow(0)
    panel._preset_export()                                              # 내보내기 → 패널 안에 코드 표시
    code = panel.code_edit.text()
    assert code.startswith("SHP1.") and not panel.code_box.isHidden()
    panel._preset_import()
    panel.code_edit.setText(code)
    panel._code_go()                                                    # 가져오기 → 새 프리셋
    assert len(panel.settings.presets) == 2 and panel._cur_preset().operators == ["复奏"]
    panel._preset_import()
    panel.code_edit.setText("이상한 코드")
    panel._code_go()
    assert "⚠" in panel.code_msg.text() and len(panel.settings.presets) == 2

    panel._save()
    loaded = config.load_settings().presets[p.id]
    assert loaded.name == "아미야 덱" and loaded.equipment == ["歌利亚头盔"]


def test_settings_panel_follows_game_window():
    from types import SimpleNamespace
    from PySide6.QtCore import QPoint, QRect
    from stronghold_overlay.app import App

    class FakePanel:
        def __init__(self):
            self.p = QPoint(300, 200)
        def isVisible(self): return True
        def pos(self): return self.p
        def width(self): return 800
        def height(self): return 500
        def move(self, p): self.p = p

    fake = SimpleNamespace(panel=FakePanel())
    App._follow_panel(fake, QRect(100, 100, 1353, 761), QRect(400, 250, 1353, 761))
    assert fake.panel.p == QPoint(600, 350)                             # 게임 창과 같이 이동


def test_preset_code_roundtrip():
    p = config.Preset(id="a", name="덱", operators=["仇白", "없는이름"], equipment=["歌利亚头盔"],
                      strategies=["阿米娅"], note="메모")
    code = config.export_code(p)
    assert code.startswith("SHP1.") and "\n" not in code and " " not in code   # 한 줄
    valid = {"operators": set(GD.operators), "equipment": set(GD.equipment), "alliances": set(GD.alliances),
             "strategies": {s["leader"] for s in GD.raw["strategies"]}}
    q = config.import_code(code, valid)
    assert q.id != p.id and q.name == "덱" and q.operators == ["仇白"]      # 없는 이름은 버림
    assert q.equipment == ["歌利亚头盔"] and q.strategies == ["阿米娅"] and q.note == "메모"
    with pytest.raises(ValueError):
        config.import_code("SHP1.깨진코드")


def test_equipment_and_info_popup(panel):
    from stronghold_overlay.pickers import InfoPopup
    it = click_card(panel.items, "歌利亚头盔")
    assert it.data(CHECKED) and panel.settings.base_equipment == ["歌利亚头盔"]
    names, _, _ = panel.settings.preferred(None)
    assert "歌利亚头盔" in names                      # 오버레이 강조 대상에 포함
    pop = InfoPopup(GD, "equipment", "歌利亚头盔")
    texts = " ".join(l.text() for l in pop.findChildren(QtWidgets.QLabel))
    assert "골리앗 투구" in texts and "HP" in texts
    pop = InfoPopup(GD, "operator", "仇白")
    texts = " ".join(l.text() for l in pop.findChildren(QtWidgets.QLabel))
    assert "획득 시" in texts                          # 한국어 특질


def test_info_button_does_not_toggle(panel):
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent
    from stronghold_overlay.pickers import info_rect
    lst = panel.ops.list
    panel.ops.resize(900, 500)
    lst._fit()
    idx = lst.model().index(0, 0)
    opt = QtWidgets.QStyleOptionViewItem()
    opt.rect = lst.visualRect(idx)
    seen = []
    panel.ops.delegate.info_clicked.connect(seen.append)
    pos = QPointF(info_rect(opt.rect.adjusted(4, 4, -4, -4)).center())
    ev = QMouseEvent(QEvent.MouseButtonRelease, pos, pos, Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
    assert panel.ops.delegate.editorEvent(ev, lst.model(), opt, idx) is True
    assert seen == [idx.data(KEY)]


def test_old_user_file_still_loads(tmp_path, monkeypatch):
    f = tmp_path / "u.json"
    f.write_text('{"enemy_notes": {"x": "y"}, "presets": {"阿米娅": {"operators": ["复奏"], "note": ""}}}', "utf-8")
    monkeypatch.setattr(config, "USER_FILE", f)
    s = config.load_settings()
    (p,) = s.presets.values()                         # 이전 형식은 전략에 연결된 프리셋으로 변환
    assert p.name == "阿米娅" and p.strategies == ["阿米娅"] and p.operators == ["复奏"]


def test_labels_follow_language(panel):
    i18n.set_language("en")
    assert GD.op_label("棘刺") == "Thorns" and GD.alliance_label("叙拉古") == "Siracusa"
    i18n.set_language("ko")
    assert GD.op_label("棘刺") == "쏜즈" and GD.alliance_label("叙拉古") == "시라쿠사"
    assert GD.strategy_label(GD.strategy("阿米娅"))["name"] == "일치단결"
    i18n.set_language("zh")
    assert GD.op_label("棘刺") == "棘刺"


def test_all_strings_translated():
    for key, entry in i18n._S.items():
        assert set(entry) == set(i18n.LANGUAGES), key
