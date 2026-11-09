"""PRTS 위키에서 동기화한 위수 협의 데이터 (data/prts_stronghold.json).

갱신: python tools/sync_prts.py
"""
from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "prts_stronghold.json"
BOSS_DIR = DATA_FILE.parent / "bosses"


@dataclass
class GameData:
    raw: dict

    @classmethod
    def load(cls, path: Path = DATA_FILE) -> "GameData":
        if not path.exists():
            return cls({"alliances": {}, "strategies": [], "bosses": [], "special_enemies": {}, "operators": {}})
        return cls(json.loads(path.read_text("utf-8")))

    @property
    def alliances(self) -> dict[str, dict]:
        return self.raw["alliances"]

    @property
    def operators(self) -> dict[str, dict]:
        return self.raw["operators"]

    @cached_property
    def prototypes(self) -> set[str]:
        return {o["prototype"] for o in self.operators.values() if o.get("prototype")}

    @cached_property
    def _strategy_index(self) -> dict[str, dict]:
        idx = {}
        for s in self.raw["strategies"]:
            for key in (s["leader"], s["leader_icon"], s["name"]):
                if key:
                    idx.setdefault(key, s)
        return idx

    # ---- OCR 보정 ----
    @staticmethod
    def _closest(text: str, choices, cutoff: float) -> str | None:
        text = text.strip()
        if not text:
            return None
        if text in choices:
            return text
        hits = [c for c in choices if c in text]  # 아이콘이 글자로 붙는 경우: '茶灵巧' -> '灵巧'
        if hits:
            return max(hits, key=len)
        m = difflib.get_close_matches(text, list(choices), n=1, cutoff=cutoff)
        return m[0] if m else None

    def alliance(self, text: str) -> str | None:
        return self._closest(text, self.alliances, 0.67)

    def operator_name(self, text: str) -> str | None:
        """상점 이름 칸의 OCR 오타 보정 (원형 카드 이름 Sharp 등도 그대로 허용)."""
        return self._closest(text, self.operators.keys() | self.prototypes, 0.6)

    def strategy(self, text: str | None) -> dict | None:
        if not text:
            return None
        key = self._closest(text, self._strategy_index, 0.6)
        return self._strategy_index.get(key) if key else None

    def boss_candidates(self, text: str | None) -> list[str]:
        """'假想敌：' 처럼 끝 글자를 놓쳐도 후보를 돌려준다."""
        if not text:
            return []
        bosses = self.raw["bosses"]
        if text in bosses:
            return [text]
        pref = [b for b in bosses if b.startswith(text)]
        if pref:
            return pref
        m = difflib.get_close_matches(text, bosses, n=1, cutoff=0.6)
        return m or [text]

    @cached_property
    def boss_portraits(self) -> dict[str, "np.ndarray"]:
        """PRTS 보스 초상화 (BGRA). 한글/특수문자 경로 때문에 imdecode 사용."""
        import cv2
        import numpy as np
        out = {}
        if BOSS_DIR.exists():
            for p in BOSS_DIR.glob("*.png"):
                img = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_UNCHANGED)
                if img is not None and img.ndim == 3 and img.shape[2] == 4:
                    out[p.stem] = img
        return out

    def special_group(self, text: str) -> tuple[str, list[str]] | None:
        """'特训敌人·飞行' -> ('飞行', [적 목록])"""
        for g, enemies in self.raw["special_enemies"].items():
            if g in text:
                return g, enemies
        return None
