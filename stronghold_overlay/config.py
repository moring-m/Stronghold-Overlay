from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PRESETS_FILE = DATA / "presets.json"


def _user_dir() -> Path:
    """실행 파일(PyInstaller)로 실행 중이면 %APPDATA%\\StrongholdOverlay, 아니면 data/."""
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("APPDATA") or Path.home()) / "StrongholdOverlay"
        base.mkdir(parents=True, exist_ok=True)
        return base
    return DATA


USER_FILE = _user_dir() / "user_settings.json"


@dataclass
class Preset:
    """전략(策略) 하나에 연동되는 추가 선호."""
    strategy: str
    operators: list[str] = field(default_factory=list)
    equipment: list[str] = field(default_factory=list)
    alliances: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class Settings:
    language: str = "ko"
    window_title: str = "明日方舟"
    interval_ms: int = 700
    base_operators: list[str] = field(default_factory=list)
    base_equipment: list[str] = field(default_factory=list)
    base_alliances: list[str] = field(default_factory=list)
    presets: dict[str, Preset] = field(default_factory=dict)
    notify: bool = True                 # 전략 프리셋 적용/선호 맹약 밴 알림
    panel_opacity: int = 88             # 설정 창 배경 불투명도(%)
    hotkey_settings: str = "Ctrl+Alt+S"
    hotkey_toggle: str = "Ctrl+Alt+O"

    def preferred(self, strategy: str | None) -> tuple[set[str], set[str], str]:
        """현재 전략을 반영한 (오퍼레이터+장비 이름, 맹약, 메모)."""
        names = set(self.base_operators) | set(self.base_equipment)
        al, note = set(self.base_alliances), ""
        p = self.presets.get(strategy) if strategy else None
        if p:
            names |= set(p.operators) | set(p.equipment)
            al |= set(p.alliances)
            note = p.note
        return names, al, note


_FIELDS = set(Settings.__dataclass_fields__) - {"presets"}
_PRESET_FIELDS = set(Preset.__dataclass_fields__) - {"strategy"}


def load_settings() -> Settings:
    raw = json.loads(PRESETS_FILE.read_text("utf-8"))
    if USER_FILE.exists():  # 사용자 파일이 기본값을 덮어씀
        try:
            raw.update(json.loads(USER_FILE.read_text("utf-8")))
        except (OSError, ValueError):
            pass            # 깨진 설정 파일은 무시하고 기본값으로
    presets = {k: Preset(strategy=k, **{f: v[f] for f in _PRESET_FIELDS if f in v})
               for k, v in raw.get("presets", {}).items()}
    return Settings(presets=presets, **{k: v for k, v in raw.items() if k in _FIELDS})


def save_user_settings(s: Settings) -> None:
    data = {k: getattr(s, k) for k in sorted(_FIELDS)}
    data["presets"] = {k: {f: getattr(p, f) for f in sorted(_PRESET_FIELDS)} for k, p in s.presets.items()}
    tmp = USER_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    tmp.replace(USER_FILE)  # 저장 중 종료돼도 파일이 깨지지 않게
