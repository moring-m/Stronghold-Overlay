from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PRESETS_FILE = DATA / "presets.json"
USER_FILE = DATA / "user_settings.json"


@dataclass
class Preset:
    """전략(策略) 하나에 연동되는 선호 설정."""
    strategy: str
    operators: list[str] = field(default_factory=list)
    alliances: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class Settings:
    window_title: str = "明日方舟"
    interval_ms: int = 700
    base_operators: list[str] = field(default_factory=list)
    base_alliances: list[str] = field(default_factory=list)
    presets: dict[str, Preset] = field(default_factory=dict)
    enemy_notes: dict[str, str] = field(default_factory=dict)

    def preferred(self, strategy: str | None) -> tuple[set[str], set[str], str]:
        """현재 전략을 반영한 (오퍼레이터, 맹약, 메모)."""
        ops, al, note = set(self.base_operators), set(self.base_alliances), ""
        p = self.presets.get(strategy) if strategy else None
        if p:
            ops |= set(p.operators)
            al |= set(p.alliances)
            note = p.note
        return ops, al, note


def load_settings() -> Settings:
    raw = json.loads(PRESETS_FILE.read_text("utf-8"))
    if USER_FILE.exists():  # 사용자 파일이 기본값을 덮어씀
        raw.update(json.loads(USER_FILE.read_text("utf-8")))
    presets = {k: Preset(strategy=k, **v) for k, v in raw.pop("presets", {}).items()}
    return Settings(presets=presets, **raw)


def save_user_settings(s: Settings) -> None:
    data = {
        "window_title": s.window_title,
        "interval_ms": s.interval_ms,
        "base_operators": s.base_operators,
        "base_alliances": s.base_alliances,
        "presets": {k: {"operators": p.operators, "alliances": p.alliances, "note": p.note}
                    for k, p in s.presets.items()},
        "enemy_notes": s.enemy_notes,
    }
    USER_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
