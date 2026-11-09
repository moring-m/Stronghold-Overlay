"""언제 화면을 읽을지 (입력 후 0.2초 / 확인 판독 / 주기) 테스트."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")

from stronghold_overlay.app import CONFIRM_AFTER, next_reason  # noqa: E402

D, I = 0.2, 1.5   # 입력 후 대기, 주기


def test_waits_200ms_after_last_click():
    last_run = 10.0
    assert next_reason(10.10, 10.05, last_run, D, I, None) is None        # 클릭 0.05초 후: 대기
    assert next_reason(10.26, 10.05, last_run, D, I, None) == "input"     # 0.2초 지나면 인식


def test_rapid_clicks_use_the_last_one():
    # 10.05, 10.15, 10.30에 연속 클릭 → 마지막(10.30) + 0.2초 전에는 인식하지 않음
    assert next_reason(10.45, 10.30, 10.0, D, I, None) is None
    assert next_reason(10.51, 10.30, 10.0, D, I, None) == "input"


def test_input_during_recognition_triggers_again():
    # 인식(10.5 시작) 도중 10.6에 클릭 → 그 클릭 기준으로 다시 인식
    assert next_reason(10.81, 10.6, 10.5, D, I, None) == "input"


def test_confirm_pass_after_input():
    run = 10.5
    confirm = run + CONFIRM_AFTER
    assert next_reason(10.9, 10.3, run, D, I, confirm) is None             # 이미 처리한 입력
    assert next_reason(11.0, 10.3, run, D, I, confirm) == "confirm"


def test_periodic_without_input():
    assert next_reason(11.4, 0.0, 10.0, D, I, None) is None
    assert next_reason(11.5, 0.0, 10.0, D, I, None) == "periodic"
