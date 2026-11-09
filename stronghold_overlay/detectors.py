"""OCR 결과(TextBox 목록)와 프레임 이미지로 게임 상태를 판별한다.

좌표 상수는 1353x761(16:9) 스크린샷 기준 비율이다. 16:9면 해상도가 달라도 그대로 맞는다.
"""
from __future__ import annotations

import numpy as np

from .gamedata import GameData
from .models import GameState, MatchInfo, Screen, ShopCard, TextBox

# 상점 카드 6칸
SHOP_X0, SHOP_STEP, SHOP_W = 0.187, 0.1155, 0.112
SHOP_Y_TOP = 0.74
SHOP_NAME_Y = 0.92           # 이 아래 텍스트 = 오퍼레이터 이름
SHOP_SLOTS = 6

# 화면별로 읽을 영역 (x0, y0, x1, y1) — 전체 화면을 읽지 않아 빠르다
REGION_TITLE = (0.25, 0.0, 0.80, 0.09)        # "1/3 确认本局信息", "2/3 选择策略"
REGION_BUTTONS = (0.76, 0.62, 1.0, 0.72)      # 전투: "冻结", "刷新"
REGION_STRATEGY = (0.75, 0.40, 1.0, 0.62)     # 전략 상세: "初始生命值", 발기인 이름
REGION_ALLIANCES = (0.04, 0.28, 0.68, 0.97)   # 본국 정보: 맹약 이름들

STRATEGY_PANEL_X = 0.75
INFO_LEFT_PANEL_MAX_X = 0.68
ICON_OFFSET_Y = 0.075
ICON_RADIUS = 0.025

def classify_screen(boxes: list[TextBox]) -> Screen:
    texts = " ".join(b.text for b in boxes)
    # 글자 하나 정도 잘못 읽어도 되도록 일부만 맞춰 본다 (예: 选择策略 → 选择策路)
    if any(k in texts for k in ("确认本局", "本局信息")) or ("核心盟约" in texts and "附加盟约" in texts):
        return Screen.MATCH_INFO
    if any(k in texts for k in ("选择策", "择策略", "2/3")):
        return Screen.STRATEGY_SELECT
    if "刷新" in texts and any(k in texts for k in ("冻结", "升级", "剩余可放置", "准备就绪")):
        return Screen.BATTLE
    return Screen.UNKNOWN


# ---------- 1/3 본국 정보 ----------
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


def parse_match_info(boxes: list[TextBox], frame: np.ndarray | None, gd: GameData) -> MatchInfo:
    info = MatchInfo()
    for b in boxes:
        if b.x < INFO_LEFT_PANEL_MAX_X and b.y > 0.3 and len(b.text.strip()) <= 6:
            name = gd.alliance(b.text)
            if name:
                target = info.active_alliances if icon_is_active(frame, b) else info.banned_alliances
                if name not in target:
                    target.append(name)
    return info


# ---------- 2/3 전략 선택 ----------
def detect_strategy(boxes: list[TextBox]) -> str | None:
    """오른쪽 상세 패널에서 '初始生命值' 바로 아래 줄 = 전략 발기인(리더) 이름."""
    anchor = next((b for b in boxes if "初始生命值" in b.text), None)
    if not anchor:
        return None
    cands = [b for b in boxes if b.x > STRATEGY_PANEL_X and 0.02 < b.cy - anchor.cy < 0.12
             and not b.text.startswith(("【", "[")) and not b.text.strip().isdigit()]
    return min(cands, key=lambda b: b.cy).text.strip() if cands else None


# ---------- 전투/상점 ----------
def card_name(slot: int, text: str, gd: GameData) -> ShopCard | None:
    text = text.strip()
    if not text or text.isdigit():
        return None
    return ShopCard(slot=slot, operator=gd.operator_name(text) or text)


def parse_shop(boxes: list[TextBox], gd: GameData) -> list[ShopCard]:
    """전체 화면 OCR 결과에서 상점 카드 하단의 오퍼레이터 이름만 읽는다."""
    cards: dict[int, ShopCard] = {}
    for b in boxes:
        if b.cy < SHOP_NAME_Y:
            continue
        slot = int((b.cx - SHOP_X0) // SHOP_STEP)
        if 0 <= slot < SHOP_SLOTS and (b.cx - SHOP_X0) - slot * SHOP_STEP <= SHOP_W:
            card = card_name(slot, b.text, gd)
            if card:
                cards[slot] = card
    return [c for _, c in sorted(cards.items())]


def update_state(state: GameState, boxes: list[TextBox], frame: np.ndarray | None,
                 gd: GameData) -> GameState:
    screen = classify_screen(boxes)
    state.screen = screen
    if screen is Screen.MATCH_INFO:
        state.match = parse_match_info(boxes, frame, gd)
        state.strategy = None  # 새 게임
    elif screen is Screen.STRATEGY_SELECT:
        found = detect_strategy(boxes)  # 화면을 떠나기 전 마지막 값 = 확정 전략
        if found:
            state.strategy = found
    if screen is Screen.BATTLE:
        state.shop = parse_shop(boxes, gd)
    else:
        state.shop = []       # 상점이 안 보이면 표시도 지움
    return state
