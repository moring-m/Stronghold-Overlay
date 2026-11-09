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
    assert classify_screen([tb("2/3 选择策路请", 610, 30)]) is Screen.STRATEGY_SELECT   # 실제 오인식 사례
    assert classify_screen([tb("冻结", 1120, 505), tb("刷新", 1270, 505)]) is Screen.BATTLE


def test_match_info_banned_by_icon_color():
    frame = np.full((H, W, 3), 60, np.uint8)            # 회색 = 비활성
    frame[220:270, 160:215] = (170, 200, 40)            # 炎 아이콘 청록(BGR)
    boxes = [tb("核心盟约", 130, 132, 90), tb("炎", 178, 290, 20),
             tb("维多利亚", 565, 290, 70), tb("请选择一组", 200, 175, 300),
             ]
    m = parse_match_info(boxes, frame, GD)
    assert m.active_alliances == ["炎"]
    assert m.banned_alliances == ["维多利亚"]


def test_shop_names_only():
    boxes = [tb("茶灵巧", 610, 690), tb("Sharp", 630, 712),     # 태그 줄은 무시
             tb("叙拉古", 760, 670), tb("忍冬", 760, 712), tb("3", 735, 545, 15)]
    shop = parse_shop(boxes, GD)
    assert [(c.slot, c.operator) for c in shop] == [(2, "Sharp"), (3, "忍冬")]


def test_shop_equipment_and_hidden():
    from stronghold_overlay.detectors import update_state
    from stronghold_overlay.models import GameState
    st = GameState()
    battle = [tb("冻结", 1120, 505), tb("刷新", 1270, 505), tb("歌利亚头盔", 300, 712, 80)]
    update_state(st, battle, None, GD)
    assert [c.operator for c in st.shop] == ["歌利亚头盔"]       # 장비 이름도 인식
    update_state(st, [tb("休息一下", 660, 25)], None, GD)         # 상점이 사라지면
    assert st.shop == []                                          # 표시할 카드도 비움


def test_strategy_name():
    boxes = [tb("泛用型策略", 450, 125, 100), tb("初始生命值", 1140, 343, 100),
             tb("25", 1245, 343, 20), tb("阿米娅", 1080, 390, 60), tb("【众志合一】", 1075, 445, 100)]
    leader = detect_strategy(boxes)
    assert leader == "阿米娅"
    assert GD.strategy(leader)["name"] == "众志合一"


def test_scan_reads_only_regions():
    """scan()은 화면별 영역만 읽는다: 어떤 영역을 읽었는지 기록해서 확인."""
    import numpy as np
    from stronghold_overlay.detectors import REGION_ALLIANCES, REGION_BUTTONS, REGION_STRATEGY, REGION_TITLE
    from stronghold_overlay.models import GameState
    from stronghold_overlay.ocr import Ocr

    class FakeOcr(Ocr):
        def __init__(self, title, buttons=(), strategy=(), shop=()):
            self.calls, self.data = [], {REGION_TITLE: title, REGION_BUTTONS: buttons,
                                         REGION_STRATEGY: strategy, REGION_ALLIANCES: []}
            self.shop = list(shop)

        def read(self, frame, min_score=0.5, region=(0, 0, 1, 1)):
            self.calls.append(region)
            return list(self.data.get(region, []))

        def read_shop(self, frame, gd):
            self.calls.append("shop")
            return self.shop

    frame = np.zeros((10, 10, 3), np.uint8)
    o = FakeOcr([tb("2/3 选择策略", 610, 30)], strategy=[tb("初始生命值", 1140, 343, 100), tb("阿米娅", 1080, 390, 60)])
    st = o.scan(frame, GameState(), GD)
    assert st.strategy == "阿米娅" and o.calls == [REGION_TITLE, REGION_STRATEGY]

    from stronghold_overlay.models import Screen, ShopCard
    o = FakeOcr([], shop=[ShopCard(1, "复奏")])
    st = o.scan(frame, GameState(screen=Screen.BATTLE), GD)
    assert [c.operator for c in st.shop] == ["复奏"] and o.calls == ["shop"]     # 전투 중엔 상점 칸만
