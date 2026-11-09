"""OCR 결과(TextBox 목록)와 프레임 이미지로 게임 상태를 판별한다.

좌표 상수는 1353x761(16:9) 스크린샷 기준 비율이다. 해상도가 달라도 16:9면 그대로 맞는다.
"""
from __future__ import annotations

import numpy as np

from .models import GameState, MatchInfo, Screen, ShopCard, TextBox

# 상점 카드 6칸: 첫 카드 왼쪽 x, 카드 간격, 카드 폭(비율)
SHOP_X0, SHOP_STEP, SHOP_W = 0.187, 0.1155, 0.112
SHOP_Y_TOP = 0.74
SHOP_NAME_Y = 0.92          # 이 아래 텍스트 = 오퍼레이터 이름
SHOP_SLOTS = 6

# OCR이 태그 앞 아이콘을 글자로 오인하는 경우(예: '本精准')를 정리하기 위한 알려진 태그
KNOWN_TAGS = [
    "炎", "谢拉格", "叙拉古", "伊比利亚", "萨尔贡", "维多利亚", "莱塔尼亚", "乌萨斯", "阿戈尔", "卡西米尔",
    "坚守", "远见", "奇迹", "投资人", "突袭", "不屈", "调和", "协防干员", "独行", "绝技",
    "精准", "灵巧", "迅捷",
]

STRATEGY_PANEL_X = 0.75
INFO_LEFT_PANEL_MAX_X = 0.68   # 맹약 패널 오른쪽 끝
ICON_OFFSET_Y = 0.075          # 라벨 위 아이콘 중심까지 거리
ICON_RADIUS = 0.025


def classify_screen(boxes: list[TextBox]) -> Screen:
    texts = " ".join(b.text for b in boxes)
    if "确认本局信息" in texts or ("核心盟约" in texts and "附加盟约" in texts):
        return Screen.MATCH_INFO
    if "选择策略" in texts:
        return Screen.STRATEGY_SELECT
    if "刷新" in texts and any(k in texts for k in ("冻结", "升级", "剩余可放置", "准备就绪")):
        return Screen.BATTLE
    return Screen.UNKNOWN


def icon_is_active(frame: np.ndarray | None, label: TextBox) -> bool:
    """라벨 위 아이콘이 청록색(활성)인지 회색(비활성/밴)인지. frame은 BGR."""
    if frame is None:
        return True
    h, w = frame.shape[:2]
    cx, cy = int(label.cx * w), int((label.cy - ICON_OFFSET_Y) * h)
    r = max(2, int(ICON_RADIUS * h))
    patch = frame[max(0, cy - r):cy + r, max(0, cx - r):cx + r]
    if patch.size == 0:
        return True
    b, g, rch = (patch[..., i].astype(int) for i in range(3))
    teal = (g > 150) & (b > 120) & (g - rch > 60)
    return teal.mean() > 0.12


def _is_alliance_label(b: TextBox) -> bool:
    t = b.text.strip()
    return (
        b.x < INFO_LEFT_PANEL_MAX_X
        and 1 <= len(t) <= 5
        and "盟约" not in t
        and not any(ch.isdigit() for ch in t)
        and b.y > 0.3
    )


def parse_match_info(boxes: list[TextBox], frame: np.ndarray | None) -> MatchInfo:
    info = MatchInfo()
    for b in boxes:
        if _is_alliance_label(b):
            (info.active_alliances if icon_is_active(frame, b) else info.banned_alliances).append(b.text.strip())
        if "特训敌人" in b.text:
            info.special_enemies.append(b.text.strip())

    leader = next((b for b in boxes if "敌方领袖" in b.text), None)
    if leader:
        cands = [b for b in boxes if b is not leader and b.y > leader.y and b.y - leader.y < 0.1
                 and b.x >= leader.x - 0.03]
        if cands:
            info.boss = min(cands, key=lambda b: b.y).text.strip()
    return info


def normalize_tag(text: str) -> str:
    t = text.strip()
    hits = [k for k in KNOWN_TAGS if k in t]
    return max(hits, key=len) if hits else t


def lookup_note(notes: dict[str, str], name: str) -> str:
    """OCR이 희귀 한자를 놓쳐도(예: '假想敌：铳' -> '假想敌：') 메모를 찾는다."""
    if name in notes:
        return notes[name]
    for k, v in notes.items():
        if name and (k.startswith(name) or name.startswith(k)):
            return v
    return ""


def lookup_note(notes: dict[str, str], name: str) -> str:
    """OCR이 희귀 한자를 놓쳐도(예: '假想敌：铳' -> '假想敌：') 메모를 찾는다."""
    if name in notes:
        return notes[name]
    for k, v in notes.items():
        if name and (k.startswith(name) or name.startswith(k)):
            return v
    return ""


def parse_shop(boxes: list[TextBox]) -> list[ShopCard]:
    """상점 카드 하단의 오퍼레이터 이름만 읽는다."""
    cards: dict[int, ShopCard] = {}
    for b in boxes:
        if b.cy < SHOP_NAME_Y or b.text.strip().isdigit():
            continue
        slot = int((b.cx - SHOP_X0) // SHOP_STEP)
        if 0 <= slot < SHOP_SLOTS and (b.cx - SHOP_X0) - slot * SHOP_STEP <= SHOP_W:
            cards[slot] = ShopCard(slot=slot, operator=b.text.strip())
    return [c for _, c in sorted(cards.items())]


def detect_strategy(boxes: list[TextBox]) -> str | None:
    """선택 화면 오른쪽 상세 패널에서 '初始生命值' 바로 아래 줄 = 전략(리더) 이름."""
    anchor = next((b for b in boxes if "初始生命值" in b.text), None)
    if not anchor:
        return None
    cands = [b for b in boxes if b.x > STRATEGY_PANEL_X and 0.02 < b.cy - anchor.cy < 0.12
             and not b.text.startswith(("【", "[")) and not b.text.strip().isdigit()]
    return min(cands, key=lambda b: b.cy).text.strip() if cands else None


def update_state(state: GameState, boxes: list[TextBox], frame: np.ndarray | None) -> GameState:
    screen = classify_screen(boxes)
    state.screen = screen
    if screen is Screen.MATCH_INFO:
        state.match = parse_match_info(boxes, frame)
        state.strategy = None  # 새 게임 시작
    elif screen is Screen.STRATEGY_SELECT:
        found = detect_strategy(boxes)  # 화면을 떠나기 전 마지막 값 = 확정 전략
        if found:
            state.strategy = found
    elif screen is Screen.BATTLE:
        state.shop = parse_shop(boxes)
    return state
