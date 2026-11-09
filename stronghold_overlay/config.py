from __future__ import annotations

import base64
import json
import zlib
import os
import sys
import uuid
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
    """이름이 있는 선호 묶음. 연결한 전략을 게임에서 고르면 자동 적용."""
    id: str
    name: str
    operators: list[str] = field(default_factory=list)
    equipment: list[str] = field(default_factory=list)
    alliances: list[str] = field(default_factory=list)
    strategies: list[str] = field(default_factory=list)   # 연결된 전략 발기인(중국어)
    note: str = ""


def new_id() -> str:
    return uuid.uuid4().hex[:8]


@dataclass
class Settings:
    language: str = "ko"
    window_title: str = "明日方舟"
    interval_ms: int = 700
    base_operators: list[str] = field(default_factory=list)
    base_equipment: list[str] = field(default_factory=list)
    base_alliances: list[str] = field(default_factory=list)
    presets: dict[str, Preset] = field(default_factory=dict)   # id → Preset (순서 유지)
    active_preset: str | None = None    # 수동으로 항상 쓸 프리셋 (None = 전략 연결로 자동)
    notify: bool = True                 # 프리셋 적용/선호 맹약 밴 알림
    panel_opacity: int = 88             # 설정 창 배경 불투명도(%)
    hotkey_settings: str = "Ctrl+Alt+S"
    hotkey_toggle: str = "Ctrl+Alt+O"

    def active_presets(self, strategy: str | None) -> list[Preset]:
        """지금 적용되는 프리셋: 수동 지정 프리셋 + 현재 전략에 연결된 프리셋."""
        out = []
        for p in self.presets.values():
            if p.id == self.active_preset or (strategy and strategy in p.strategies):
                out.append(p)
        return out

    def preferred(self, strategy: str | None) -> tuple[set[str], set[str], list[Preset]]:
        """(강조할 오퍼레이터+장비 이름, 선호 맹약, 적용된 프리셋)."""
        names = set(self.base_operators) | set(self.base_equipment)
        al = set(self.base_alliances)
        active = self.active_presets(strategy)
        for p in active:
            names |= set(p.operators) | set(p.equipment)
            al |= set(p.alliances)
        return names, al, active


_FIELDS = set(Settings.__dataclass_fields__) - {"presets"}
_PRESET_FIELDS = set(Preset.__dataclass_fields__)


def load_settings() -> Settings:
    raw = json.loads(PRESETS_FILE.read_text("utf-8"))
    if USER_FILE.exists():  # 사용자 파일이 기본값을 덮어씀
        try:
            raw.update(json.loads(USER_FILE.read_text("utf-8")))
        except (OSError, ValueError):
            pass            # 깨진 설정 파일은 무시하고 기본값으로
    presets: dict[str, Preset] = {}
    raw_presets = raw.get("presets", {})
    items = raw_presets if isinstance(raw_presets, list) else list(raw_presets.items())
    for entry in items:
        if isinstance(entry, tuple):          # 이전 형식: {"전략 이름": {...}} → 전략에 연결된 프리셋
            key, v = entry
            v = {**v, "name": v.get("name") or key, "strategies": v.get("strategies") or [key]}
        else:
            v = entry
        p = Preset(**{f: v[f] for f in _PRESET_FIELDS if f in v and f not in ("id", "name")},
                   id=v.get("id") or new_id(), name=v.get("name") or "Preset")
        presets[p.id] = p
    return Settings(presets=presets, **{k: v for k, v in raw.items() if k in _FIELDS})


def save_user_settings(s: Settings) -> None:
    data = {k: getattr(s, k) for k in sorted(_FIELDS)}
    data["presets"] = [{f: getattr(p, f) for f in sorted(_PRESET_FIELDS)} for p in s.presets.values()]
    tmp = USER_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    tmp.replace(USER_FILE)  # 저장 중 종료돼도 파일이 깨지지 않게


# ---------- 프리셋 공유 코드 (한 줄) ----------
CODE_PREFIX = "SHP1."


def export_code(p: Preset) -> str:
    """프리셋 → 'SHP1.xxxx' 한 줄 코드 (압축 + base64url)."""
    data = {"n": p.name, "o": p.operators, "e": p.equipment, "a": p.alliances, "s": p.strategies, "m": p.note}
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return CODE_PREFIX + base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii").rstrip("=")


def import_code(code: str, valid: dict[str, set[str]] | None = None) -> Preset:
    """코드 → 새 프리셋. valid가 있으면 데이터에 없는 이름은 버린다. 형식이 틀리면 ValueError."""
    code = "".join(code.split())
    if not code.startswith(CODE_PREFIX):
        raise ValueError("not a preset code")
    body = code[len(CODE_PREFIX):]
    try:
        data = json.loads(zlib.decompress(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))))
    except Exception as e:
        raise ValueError("broken preset code") from e

    def keep(key: str, kind: str) -> list[str]:
        vals = [str(x) for x in data.get(key, []) if isinstance(x, str)]
        return [x for x in vals if valid is None or x in valid.get(kind, set())]

    return Preset(id=new_id(), name=str(data.get("n") or "Preset")[:40],
                  operators=keep("o", "operators"), equipment=keep("e", "equipment"),
                  alliances=keep("a", "alliances"), strategies=keep("s", "strategies"),
                  note=str(data.get("m", ""))[:200])
