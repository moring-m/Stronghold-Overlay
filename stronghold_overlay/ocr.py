from __future__ import annotations

import numpy as np

from .detectors import (REGION_ALLIANCES, REGION_BUTTONS, REGION_STRATEGY, REGION_TITLE, SHOP_SLOTS, SHOP_STEP,
                        SHOP_W, SHOP_X0, card_name, classify_screen, detect_strategy, parse_match_info)
from .gamedata import GameData
from .models import GameState, Screen, ShopCard, TextBox


class Ocr:
    """RapidOCR(PaddleOCR 모델의 ONNX 버전, 중국어 기본) 래퍼."""

    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR
        self._engine = RapidOCR()
        # 기본값(짧은 변을 736px 이상으로 '확대')은 작은 영역에서 오히려 느리다.
        # 긴 변을 960px 이하로 '제한'하면 작은 영역은 그대로, 큰 화면(1080p 등)은 줄여서 빠르게 읽는다.
        try:
            resize = self._engine.text_detector.preprocess_op[0]
            resize.limit_type, resize.limit_side_len = "max", 960
        except (AttributeError, IndexError):
            pass

    def _run(self, img: np.ndarray):
        # 게임 글자는 회전되어 있지 않으므로 방향 판별(cls)은 생략
        result, _ = self._engine(np.ascontiguousarray(img), use_cls=False)
        return result or []

    def read(self, frame: np.ndarray, min_score: float = 0.5,
             region: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)) -> list[TextBox]:
        """frame 중 region(비율)만 읽는다. 결과 좌표는 항상 전체 화면 비율."""
        h, w = frame.shape[:2]
        x0, y0 = int(region[0] * w), int(region[1] * h)
        crop = frame[y0:int(region[3] * h), x0:int(region[2] * w)]
        boxes: list[TextBox] = []
        for pts, text, score in self._run(crop):
            if float(score) < min_score:
                continue
            xs = [p[0] + x0 for p in pts]
            ys = [p[1] + y0 for p in pts]
            boxes.append(TextBox(text, min(xs) / w, min(ys) / h,
                                 (max(xs) - min(xs)) / w, (max(ys) - min(ys)) / h, float(score)))
        return boxes

    def scan(self, frame: np.ndarray, state: GameState, gd: GameData) -> GameState:
        """필요한 영역만 읽어 상태를 갱신한다.

        전투 중이면 상점 이름 칸부터 → 카드가 보이면 끝.
        아니면 제목 줄로 화면 판별 → 화면별 영역만 읽는다.
        """
        if state.screen is Screen.BATTLE:
            shop = self.read_shop(frame, gd)
            if shop:
                state.shop = shop
                return state
        screen = classify_screen(self.read(frame, region=REGION_TITLE))
        if screen is Screen.UNKNOWN:
            screen = classify_screen(self.read(frame, region=REGION_BUTTONS))
        state.screen = screen
        state.shop = []
        if screen is Screen.MATCH_INFO:
            state.match = parse_match_info(self.read(frame, region=REGION_ALLIANCES), frame, gd)
            state.strategy = None   # 새 판
        elif screen is Screen.STRATEGY_SELECT:
            found = detect_strategy(self.read(frame, region=REGION_STRATEGY))
            if found:
                state.strategy = found   # 화면을 떠나기 전 마지막 값 = 확정 전략
        elif screen is Screen.BATTLE:
            state.shop = self.read_shop(frame, gd)
        return state

    def read_shop(self, frame: np.ndarray, gd: GameData) -> list[ShopCard]:
        """상점 6칸의 이름 칸만 잘라 세로로 쌓아 한 번에 OCR (전체 화면보다 빠름).

        가로로 납작한 띠는 텍스트 검출이 실패하므로 칸별로 세로로 쌓는다.
        """
        h, w = frame.shape[:2]
        y0, y1 = int(0.915 * h), int(0.98 * h)
        cw = int(SHOP_W * w)
        rows = [frame[y0:y1, int((SHOP_X0 + i * SHOP_STEP) * w):][:, :cw] for i in range(SHOP_SLOTS)]
        rh = y1 - y0
        cards: dict[int, ShopCard] = {}
        for pts, text, score in self._run(np.vstack(rows)):
            slot = int(((pts[0][1] + pts[2][1]) / 2) // rh)
            if float(score) >= 0.5 and 0 <= slot < SHOP_SLOTS:
                card = card_name(slot, text, gd)
                if card:
                    cards[slot] = card
        return [c for _, c in sorted(cards.items())]
