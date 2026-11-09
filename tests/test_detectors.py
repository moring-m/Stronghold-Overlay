import numpy as np

from stronghold_overlay.detectors import (classify_screen, detect_strategy, parse_match_info,
                                          parse_shop)
from stronghold_overlay.gamedata import GameData
from stronghold_overlay.models import Screen, TextBox

W, H = 1353, 761
GD = GameData.load()


def tb(text, x, y, w=40, h=18):
    return TextBox(text, x / W, y / H, w / W, h / H)


def test_classify():
    assert classify_screen([tb("1/3", 0, 0), tb("确认本局信息", 470, 25)]) is Screen.MATCH_INFO
    assert classify_screen([tb("选择策略", 610, 30)]) is Screen.STRATEGY_SELECT
    assert classify_screen([tb("冻结", 1120, 505), tb("刷新", 1270, 505)]) is Screen.BATTLE


def test_match_info_banned_by_icon_color():
    frame = np.full((H, W, 3), 60, np.uint8)            # 회색 = 비활성
    frame[220:270, 160:215] = (170, 200, 40)            # 炎 아이콘 청록(BGR)
    boxes = [tb("核心盟约", 130, 132, 90), tb("炎", 178, 290, 20),
             tb("维多利亚", 565, 290, 70), tb("请选择一组", 200, 175, 300),
             tb("敌方领袖", 1055, 318, 80), tb("假想敌：", 1052, 348, 110),
             tb("特训敌人·飞行", 1058, 437, 120)]
    m = parse_match_info(boxes, frame, GD)
    assert m.active_alliances == ["炎"]
    assert m.banned_alliances == ["维多利亚"]
    assert m.boss == "假想敌："
    assert "假想敌：铳" in GD.boss_candidates(m.boss)
    assert GD.special_group(m.special_enemies[0])[0] == "飞行"


def test_shop_resolves_prototype():
    boxes = [tb("茶灵巧", 610, 690), tb("Sharp", 630, 712),     # 원형 카드
             tb("叙拉古", 760, 670), tb("多迅捷", 760, 690), tb("忍冬", 760, 712)]
    shop = parse_shop(boxes, None, GD)
    assert [(c.slot, c.operator) for c in shop] == [(2, "Sharp"), (3, "忍冬")]
    assert shop[0].tags == ["灵巧"]
    assert set(shop[0].candidates) == {"仇白", "佩佩", "隐德来希"}       # 등급 모르면 3명
    assert GD.resolve("Sharp", ["灵巧"], "Ⅳ") == ["仇白"]               # 등급까지 알면 확정
    assert shop[1].candidates == ["忍冬"] and shop[1].tags == ["叙拉古", "迅捷"]


def test_strategy_name():
    boxes = [tb("泛用型策略", 450, 125, 100), tb("初始生命值", 1140, 343, 100),
             tb("25", 1245, 343, 20), tb("阿米娅", 1080, 390, 60), tb("【众志合一】", 1075, 445, 100)]
    leader = detect_strategy(boxes)
    assert leader == "阿米娅"
    assert GD.strategy(leader)["name"] == "众志合一"
