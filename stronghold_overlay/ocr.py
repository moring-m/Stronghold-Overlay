from __future__ import annotations

import numpy as np

from .models import TextBox


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
