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


def test_preset_roundtrip(panel):
    panel.strat.setCurrentIndex(panel.strat.findData("歌利亚"))
    click_card(panel.p_ops, "复奏")
    panel.p_note.setText("tank")
    assert panel.settings.presets["歌利亚"].operators == ["复奏"]
    assert panel.strat.currentText().startswith("● ")
    panel._save()
    ops, _, note = config.load_settings().preferred("歌利亚")
    assert "复奏" in ops and note == "tank"


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
