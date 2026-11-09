"""위수 협의: 규정 데이터 (PRTS + 번역).

갱신: python tools/sync_prts.py && python tools/sync_i18n.py
"""
from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_FILE = DATA_DIR / "prts_stronghold.json"
I18N_FILE = DATA_DIR / "i18n_names.json"
AVATAR_DIR = DATA_DIR / "avatars"
ITEM_DIR = DATA_DIR / "items"
TIERS = "ⅠⅡⅢⅣⅤⅥ"


@dataclass
class GameData:
    raw: dict

    @classmethod
    def load(cls, path: Path = DATA_FILE) -> "GameData":
        if not path.exists():
            return cls({"alliances": {}, "strategies": [], "operators": {}, "equipment": {}})
        return cls(json.loads(path.read_text("utf-8")))

    # ---- 기본 데이터 (키는 중국어 이름) ----
    @property
    def alliances(self) -> dict[str, dict]:
        return self.raw["alliances"]

    @property
    def operators(self) -> dict[str, dict]:
        return self.raw["operators"]

    @property
    def equipment(self) -> dict[str, dict]:
        return self.raw.get("equipment", {})

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

    # ---- UI 언어 표기 ----
    @cached_property
    def names(self) -> dict:
        return json.loads(I18N_FILE.read_text("utf-8")) if I18N_FILE.exists() else {}

    def _label(self, kind: str, zh: str) -> str:
        from .i18n import tr
        return self.names.get(tr.lang, {}).get(kind, {}).get(zh) or zh

    def op_label(self, zh: str) -> str:
        return self._label("operators", zh)

    def alliance_label(self, zh: str) -> str:
        return self._label("alliances", zh)

    def item_label(self, zh: str) -> str:
        return self._label("equipment", zh)

    def strategy_label(self, s: dict) -> dict:
        from .i18n import tr
        t = self.names.get(tr.lang, {}).get("strategies", {}).get(s["leader"], {})
        return {"leader": t.get("leader") or s["leader"], "name": t.get("name") or s["name"],
                "effect": t.get("effect") or s["effect"].replace("被动效果：", "")}

    def trait_text(self, zh: str) -> str:
        """특질 설명 (한국어는 '기본(진급)' 한 줄, 그 외는 중국어 기본/진급)."""
        from .i18n import tr
        ko = self.names.get(tr.lang, {}).get("traits", {}).get(zh)
        if ko:
            return ko
        o = self.operators.get(zh, {})
        return "\n".join(x for x in (o.get("trait", ""), o.get("trait_adv", "") and "▲ " + o["trait_adv"]) if x)

    def item_effect(self, zh: str) -> str:
        from .i18n import tr
        ko = self.names.get(tr.lang, {}).get("equipment_effects", {}).get(zh)
        if ko:
            return ko
        e = self.equipment.get(zh, {})
        return "\n".join(x for x in (e.get("effect", ""), e.get("effect_adv", "") and "▲ " + e["effect_adv"]) if x)

    def avatar(self, zh: str) -> Path | None:
        p = AVATAR_DIR / f"{zh}.png"
        return p if p.exists() else None

    def item_icon(self, zh: str) -> Path | None:
        p = ITEM_DIR / f"{zh}.png"
        return p if p.exists() else None

    # ---- OCR 보정 ----
    @staticmethod
    def _closest(text: str, choices, cutoff: float) -> str | None:
        text = text.strip()
        if not text:
            return None
        if text in choices:
            return text
        hits = [c for c in choices if c in text]   # 아이콘이 글자로 붙는 경우
        if hits:
            return max(hits, key=len)
        m = difflib.get_close_matches(text, list(choices), n=1, cutoff=cutoff)
        return m[0] if m else None

    def alliance(self, text: str) -> str | None:
        return self._closest(text, self.alliances, 0.67)

    @cached_property
    def _card_names(self) -> set[str]:
        return set(self.operators) | self.prototypes | set(self.equipment)

    def operator_name(self, text: str) -> str | None:
        """상점 카드 이름 칸(오퍼레이터 또는 장비)의 OCR 오타 보정."""
        return self._closest(text, self._card_names, 0.6)

    def strategy(self, text: str | None) -> dict | None:
        if not text:
            return None
        key = self._closest(text, self._strategy_index, 0.6)
        return self._strategy_index.get(key) if key else None
