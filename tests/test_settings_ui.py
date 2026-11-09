"""설정 창 저장 왕복 테스트 (Qt를 띄울 수 없는 환경이면 건너뜀)."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from stronghold_overlay import config, i18n  # noqa: E402
from stronghold_overlay.gamedata import GameData  # noqa: E402


@pytest.fixture
def tmp_user(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "USER_FILE", tmp_path / "user_settings.json")
    return tmp_path / "user_settings.json"


def test_save_roundtrip(tmp_user):
    from stronghold_overlay.settings_ui import SettingsDialog
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])  # noqa: F841
    s = config.load_settings()
    d = SettingsDialog(s, GameData.load())
    d.ops.set_checked(["忍冬", "Sharp"])
    d.als.set_checked(["炎"])
    d.lang.setCurrentIndex(d.lang.findData("zh"))
    d.strat.setCurrentIndex(d.strat.findData("歌利亚"))
    d.p_ops.set_checked(["复奏"])
    d.p_note.setText("tank")
    d.boss.setCurrentText("矩兽")
    d.boss_note.setPlainText("note")
    d._save()

    s2 = config.load_settings()
    assert s2.language == "zh" and i18n.tr.lang == "zh"
    assert set(s2.base_operators) == {"忍冬", "Sharp"} and s2.base_alliances == ["炎"]
    assert s2.presets["歌利亚"].operators == ["复奏"] and s2.presets["歌利亚"].note == "tank"
    assert "阿米娅" in s2.presets                     # 기존 프리셋 유지
    assert s2.enemy_notes == {"矩兽": "note"}
    ops, _, note = s2.preferred("歌利亚")
    assert ops == {"忍冬", "Sharp", "复奏"} and note == "tank"
    i18n.set_language("ko")


def test_all_strings_translated():
    for key, entry in i18n._S.items():
        assert set(entry) == set(i18n.LANGUAGES), key
