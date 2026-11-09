from __future__ import annotations

import numpy as np

from .detectors import SHOP_SLOTS, SHOP_STEP, SHOP_X0
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

    def read_shop(self, frame: np.ndarray) -> list[ShopCard]:
        """상점 6칸의 이름 영역만 잘라 세로로 쌓아 한 번에 OCR (전체 화면보다 빠름).

        가로로 납작한 띠는 텍스트 검출이 실패하므로 세로로 쌓는다.
        """
        h, w = frame.shape[:2]
        y0, y1 = int(0.915 * h), int(0.98 * h)
        cw = int(0.111 * w)
        rows = [frame[y0:y1, int((SHOP_X0 + i * SHOP_STEP) * w):][:, :cw] for i in range(SHOP_SLOTS)]
        rh = y1 - y0
        result, _ = self._engine(np.ascontiguousarray(np.vstack(rows)))
        cards: dict[int, ShopCard] = {}
        for pts, text, score in result or []:
            slot = int(((pts[0][1] + pts[2][1]) / 2) // rh)
            if float(score) >= 0.5 and 0 <= slot < SHOP_SLOTS and not text.strip().isdigit():
                cards[slot] = ShopCard(slot=slot, operator=text.strip())
        return [c for _, c in sorted(cards.items())]
