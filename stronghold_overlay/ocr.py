from __future__ import annotations

import numpy as np

from .detectors import (SHOP_NAME_Y, SHOP_SLOTS, SHOP_STEP, SHOP_TAG_Y, SHOP_W, SHOP_X0,
                        build_card, read_tier)
from .gamedata import GameData
from .models import ShopCard, TextBox


class Ocr:
    """RapidOCR(PaddleOCR 모델의 ONNX 버전, 중국어 기본) 래퍼."""

    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR
        self._engine = RapidOCR()

    def read(self, frame: np.ndarray, min_score: float = 0.5) -> list[TextBox]:
        h, w = frame.shape[:2]
        result, _ = self._engine(frame)
        boxes: list[TextBox] = []
        for pts, text, score in result or []:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            if float(score) < min_score:
                continue
            boxes.append(TextBox(text, min(xs) / w, min(ys) / h,
                                 (max(xs) - min(xs)) / w, (max(ys) - min(ys)) / h, float(score)))
        return boxes

    def read_shop(self, frame: np.ndarray, gd: GameData) -> list[ShopCard]:
        """상점 6칸의 태그+이름 영역만 잘라 세로로 쌓아 한 번에 OCR.

        가로로 납작한 띠는 텍스트 검출이 실패하므로 칸별로 세로로 쌓는다.
        """
        h, w = frame.shape[:2]
        y0, y1 = int(SHOP_TAG_Y * h), int(0.98 * h)
        cw = int(SHOP_W * w)
        rows = [frame[y0:y1, int((SHOP_X0 + i * SHOP_STEP) * w):][:, :cw] for i in range(SHOP_SLOTS)]
        rh = y1 - y0
        result, _ = self._engine(np.ascontiguousarray(np.vstack(rows)))
        lines: dict[int, list[TextBox]] = {}
        for pts, text, score in result or []:
            cy = (pts[0][1] + pts[2][1]) / 2
            slot = int(cy // rh)
            if float(score) >= 0.5 and 0 <= slot < SHOP_SLOTS:
                # 칸 안의 세로 위치만 쓰므로 비율 좌표로 환산
                lines.setdefault(slot, []).append(TextBox(text, 0, (y0 + cy - slot * rh) / h, 0, 0))
        cards = []
        for slot, ls in sorted(lines.items()):
            if any(b.cy >= SHOP_NAME_Y for b in ls):
                card = build_card(slot, ls, read_tier(frame, slot), gd)
                if card:
                    cards.append(card)
        return cards
