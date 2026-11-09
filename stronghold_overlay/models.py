from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Screen(Enum):
    UNKNOWN = "unknown"
    MATCH_INFO = "match_info"        # 1/3 确认本局信息
    STRATEGY_SELECT = "strategy"     # 2/3 选择策略
    BATTLE = "battle"                # 준비/상점 단계 (刷新 / 冻结 버튼)


@dataclass
class TextBox:
    """OCR 결과 하나. 좌표는 창 크기 대비 0~1 비율."""
    text: str
    x: float
    y: float
    w: float
    h: float
    score: float = 1.0

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


@dataclass
class MatchInfo:
    active_alliances: list[str] = field(default_factory=list)
    banned_alliances: list[str] = field(default_factory=list)


@dataclass
class ShopCard:
    slot: int
    operator: str  # 카드에 표시된 이름 그대로 (PRTS 이름으로 오타만 보정)


@dataclass
class GameState:
    screen: Screen = Screen.UNKNOWN
    match: MatchInfo = field(default_factory=MatchInfo)
    strategy: str | None = None
    shop: list[ShopCard] = field(default_factory=list)
