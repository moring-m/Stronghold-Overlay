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
SHOP_TAG_Y = 0.85            # 태그+이름 영역 시작
SHOP_NAME_Y = 0.92           # 이 아래 텍스트 = 이름
SHOP_SLOTS = 6
TIER_BOX = (0.748, 0.785, 0.05)   # 등급 배지: y0, y1, 폭

STRATEGY_PANEL_X = 0.75
INFO_LEFT_PANEL_MAX_X = 0.68
ICON_OFFSET_Y = 0.075
ICON_RADIUS = 0.025
BOSS_PORTRAIT = (0.69, 0.40, 0.785, 0.57)   # x0, y0, x1, y1 (敌方领袖 왼쪽 초상화)
BOSS_MATCH_MIN = 0.97

ROMAN = {"I": "Ⅰ", "II": "Ⅱ", "III": "Ⅲ", "IV": "Ⅳ", "V": "Ⅴ", "VI": "Ⅵ"}


def classify_screen(boxes: list[TextBox]) -> Screen:
    texts = " ".join(b.text for b in boxes)
    if "确认本局信息" in texts or ("核心盟约" in texts and "附加盟约" in texts):
        return Screen.MATCH_INFO
    if "选择策略" in texts:
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
        if "特训敌人" in b.text:
            info.special_enemies.append(b.text.strip())

    leader = next((b for b in boxes if "敌方领袖" in b.text), None)
    if leader:
        cands = [b for b in boxes if b is not leader and 0 < b.y - leader.y < 0.1
                 and b.x >= leader.x - 0.03]
        if cands:
            info.boss = min(cands, key=lambda b: b.y).text.strip()
    if frame is not None and gd.boss_portraits:
        m = match_boss(frame, gd)
        if m and m[1] >= BOSS_MATCH_MIN:
            info.boss = m[0]
    return info


def match_boss(frame: np.ndarray, gd: GameData) -> tuple[str, float] | None:
    """보스 초상화를 PRTS 이미지와 템플릿 매칭 (OCR이 '铳' 같은 글자를 못 읽어서)."""
    import cv2
    h, w = frame.shape[:2]
    x0, y0, x1, y1 = BOSS_PORTRAIT
    region = cv2.cvtColor(frame[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)], cv2.COLOR_BGR2GRAY)
    side = min(region.shape)
    best: tuple[str, float] | None = None
    for name, img in gd.boss_portraits.items():
        # 초상화는 영역 높이의 약 47~78% 크기 → 여러 크기로 시도
        for size in range(int(side * 0.47), int(side * 0.78), max(2, side // 32)):
            t = cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)
            tg = cv2.cvtColor(t[..., :3], cv2.COLOR_BGR2GRAY)
            mask = (t[..., 3] > 128).astype(np.uint8)
            score = float(np.nanmax(cv2.matchTemplate(region, tg, cv2.TM_CCORR_NORMED, mask=mask)))
            if best is None or score > best[1]:
                best = (name, score)
    return best


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
def read_tier(frame: np.ndarray, slot: int) -> str | None:
    """카드 좌상단 로마 숫자 배지를 획 모양으로 판별 (OCR로는 읽히지 않음).

    밝은 픽셀의 세로 열 덩어리: 좁으면 I, 넓으면 V.
    """
    h, w = frame.shape[:2]
    y0, y1, bw = TIER_BOX
    x0 = int((SHOP_X0 + slot * SHOP_STEP) * w)
    badge = frame[int(y0 * h):int(y1 * h), x0:x0 + int(bw * w)]
    if badge.size == 0:
        return None
    bh = badge.shape[0]
    mask = badge.min(axis=2) > 190
    cols = mask.sum(axis=0) > 0
    seq, start = "", None
    for x, on in enumerate([*cols, False]):
        if on and start is None:
            start = x
        elif not on and start is not None:
            width = x - start
            if mask[:, start:x].sum() >= bh * 0.7:  # 잡티 제외
                seq += "V" if width > bh * 0.45 else "I"
            start = None
    return ROMAN.get(seq)


def build_card(slot: int, lines: list[TextBox], tier: str | None, gd: GameData) -> ShopCard | None:
    """한 칸의 텍스트 줄들(위→아래) → 카드. 맨 아래 줄이 이름."""
    lines = [b for b in sorted(lines, key=lambda b: b.cy) if not b.text.strip().isdigit()]
    if not lines:
        return None
    raw_name = lines[-1].text.strip()
    name = gd.operator_name(raw_name) or raw_name
    tags = [t for t in (gd.alliance(b.text) for b in lines[:-1]) if t]
    card = ShopCard(slot=slot, operator=name, tags=tags, tier=tier)
    card.candidates = gd.resolve(name, tags, tier)
    return card


def slot_of(b: TextBox) -> int | None:
    slot = int((b.cx - SHOP_X0) // SHOP_STEP)
    if 0 <= slot < SHOP_SLOTS and (b.cx - SHOP_X0) - slot * SHOP_STEP <= SHOP_W:
        return slot
    return None


def parse_shop(boxes: list[TextBox], frame: np.ndarray | None, gd: GameData) -> list[ShopCard]:
    """전체 화면 OCR 결과에서 상점 카드를 읽는다."""
    by_slot: dict[int, list[TextBox]] = {}
    for b in boxes:
        s = slot_of(b) if b.cy >= SHOP_TAG_Y else None
        if s is not None:
            by_slot.setdefault(s, []).append(b)
    cards = []
    for s, lines in sorted(by_slot.items()):
        if not any(b.cy >= SHOP_NAME_Y for b in lines):
            continue
        card = build_card(s, lines, read_tier(frame, s) if frame is not None else None, gd)
        if card:
            cards.append(card)
    return cards


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
    elif screen is Screen.BATTLE:
        state.shop = parse_shop(boxes, frame, gd)
    return state
