from __future__ import annotations

import numpy as np

from .detectors import (REGION_ALLIANCES, REGION_BUTTONS, REGION_STRATEGY, REGION_TITLE, SHOP_SLOTS, SHOP_STEP,
                        SHOP_W, SHOP_X0, card_name, classify_screen, detect_strategy, parse_match_info)
from .gamedata import GameData
from .models import GameState, Screen, ShopCard, TextBox


class Ocr:
    """RapidOCR(PaddleOCR 모델의 ONNX 버전, 중국어 기본) 래퍼."""

    THREADS = 2   # 측정상 2개가 속도/CPU 균형이 가장 좋음 (1개: 느림, 4개: 이득 거의 없음)

    def __init__(self) -> None:
        self._engine = self._create_engine()
        # 기본값(짧은 변을 736px 이상으로 '확대')은 작은 영역에서 오히려 느리다.
        # 긴 변을 960px 이하로 '제한'하면 작은 영역은 그대로, 큰 화면(1080p 등)은 줄여서 빠르게 읽는다.
        try:
            resize = self._engine.text_detector.preprocess_op[0]
            resize.limit_type, resize.limit_side_len = "max", 960
        except (AttributeError, IndexError):
            pass

    @classmethod
    def _create_engine(cls):
        """RapidOCR을 처음부터 가볍게 만든다 (모델을 두 번 불러오지 않도록 생성 전에 설정을 바꿈).

        - 글자 방향 판별 모델은 불러오지 않음: 게임 글자는 회전되어 있지 않다.
          (RapidOCR은 호출 인자 use_cls를 무시하므로 설정 파일 값을 바꿔야 한다.)
        - onnxruntime 기본값은 코어 수만큼 스레드를 만들고 작업 뒤 '바쁜 대기(spinning)'를 해
          CPU를 많이 쓴다 → 스레드 2개, spinning 끔. (측정: 같은 속도에서 CPU 약 1/3)
        """
        import importlib
        import sys

        import onnxruntime as ort
        import rapidocr_onnxruntime.rapid_ocr_api as api
        import rapidocr_onnxruntime.utils as utils

        # RapidOCR은 내부 모듈을 'ch_ppocr_v3_det' 같은 최상위 이름으로 동적 import 한다.
        # exe(PyInstaller) 안에서는 같은 이름의 데이터 폴더가 대신 잡힐 수 있어 명시적으로 연결해 둔다.
        for name in ("ch_ppocr_v3_det", "ch_ppocr_v3_rec"):
            sys.modules[name] = importlib.import_module(f"rapidocr_onnxruntime.{name}")

        def tuned_options():
            opt = ort.SessionOptions()
            opt.intra_op_num_threads = cls.THREADS
            opt.inter_op_num_threads = 1
            opt.add_session_config_entry("session.intra_op.allow_spinning", "0")
            opt.add_session_config_entry("session.inter_op.allow_spinning", "0")
            return opt

        def light_config(path):
            config = orig_read_yaml(path)
            config["Global"]["use_angle_cls"] = False
            return config

        orig_opts, orig_read_yaml = utils.SessionOptions, api.read_yaml
        utils.SessionOptions, api.read_yaml = tuned_options, light_config
        try:
            return api.RapidOCR()
        finally:
            utils.SessionOptions, api.read_yaml = orig_opts, orig_read_yaml

    def _run(self, img: np.ndarray):
        result, _ = self._engine(np.ascontiguousarray(img))
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
