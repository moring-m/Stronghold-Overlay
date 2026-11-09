"""번역(ko/en)과 오퍼레이터 초상화를 받아 저장.

- ko: arknights1234.github.io (위수 협의: 규정 / act3autochess) — 오퍼레이터, 맹약, 전략
      없는 이름은 공식 한국 서버 character_table 로 보충
- en: 공식 글로벌 서버 character_table (ArknightsGameData_YoStar)
      글로벌 미출시 오퍼레이터는 PRTS '干员外文名'(라틴 문자일 때만)
      맹약/특훈 분류 영어 이름은 이 파일의 표 (국가명은 공식 표기, 나머지는 비공식 번역)
- 초상화: PRTS 头像_<이름>.png → data/avatars/<이름>.png (96px)

받아온 JS 파일은 실행하지 않고 텍스트로만 파싱한다.
"""
from __future__ import annotations

import io
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import prts_api  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
AVATARS = DATA / "avatars"
OUT = DATA / "i18n_names.json"

AK1234 = "https://arknights1234.github.io/js/act3autochess/data.js"
GAMEDATA = {
    "zh": "https://raw.githubusercontent.com/Kengxxiao/ArknightsGameData/master/zh_CN/gamedata/excel/character_table.json",
    "en": "https://raw.githubusercontent.com/Kengxxiao/ArknightsGameData_YoStar/main/en_US/gamedata/excel/character_table.json",
    "ko": "https://raw.githubusercontent.com/Kengxxiao/ArknightsGameData_YoStar/main/ko_KR/gamedata/excel/character_table.json",
}

ALLIANCE_EN = {
    "炎": "Yan", "萨尔贡": "Sargon", "维多利亚": "Victoria", "谢拉格": "Kjerag", "阿戈尔": "Aegir",
    "叙拉古": "Siracusa", "卡西米尔": "Kazimierz", "乌萨斯": "Ursus", "伊比利亚": "Iberia",
    "莱塔尼亚": "Leithanien",
    "精准": "Precision", "迅捷": "Swift", "灵巧": "Agile", "坚守": "Steadfast", "助力": "Assist",
    "远见": "Foresight", "奇迹": "Miracle", "投资人": "Investor", "突袭": "Raid", "不屈": "Unyielding",
    "调和": "Harmony", "协防干员": "Joint Defense", "独行": "Lone Wolf", "绝技": "Ultimate",
    "聚合": "Convergence", "奥术": "Arcane",
}
SPECIAL = {  # 특훈 적 분류
    "特异": ("특이", "Anomalous"), "飞行": ("비행", "Aerial"), "频次": ("빈도", "Hit-count"),
    "元素": ("원소", "Elemental"), "持续": ("지속", "Sustained"), "隐匿": ("은닉", "Stealth"),
    "折射": ("굴절", "Reflective"), "致命": ("치명", "Lethal"), "复苏": ("소생", "Revival"),
}


def fetch(url: str) -> bytes:
    last = None
    for i in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": prts_api.UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:  # PRTS/GitHub 연결 끊김 재시도
            last = e
            time.sleep(min(2 ** i, 20))
    raise RuntimeError(f"다운로드 실패: {url}") from last


def strip_html(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return s.replace("&lt;", "<").replace("&gt;", ">").strip()


def parse_js_object(text: str) -> dict:
    """`export const data = {...}` → dict (주석/후행 쉼표 제거, 실행하지 않음)."""
    text = re.sub(r"^\s*//.*$", "", text, flags=re.M)
    body = text[text.index("{"): text.rindex("}") + 1]
    return json.loads(re.sub(r",(\s*[}\]])", r"\1", body))


def latin(s: str) -> bool:
    return bool(s) and all(ord(c) < 0x250 for c in s)


def main() -> None:
    prts = json.loads((DATA / "prts_stronghold.json").read_text("utf-8"))
    ops = list(prts["operators"])
    protos = sorted({o["prototype"] for o in prts["operators"].values() if o.get("prototype")})
    names = ops + protos

    # ---- 공식 게임 데이터 (이름 ↔ charId) ----
    tables = {k: json.loads(fetch(u)) for k, u in GAMEDATA.items()}
    zh2id: dict[str, str] = {}
    for cid, c in tables["zh"].items():
        zh2id.setdefault(c["name"], cid)

    def official(lang: str, zh: str) -> str | None:
        cid = zh2id.get(zh)
        return tables[lang].get(cid, {}).get("name") if cid else None

    # ---- ko: arknights1234 ----
    ak = parse_js_object(fetch(AK1234).decode("utf-8"))
    ko_ops = {}
    for o in ak["operators"]:
        m = re.search(r"头像_(.+)\.webp", o.get("img", ""))
        if m:
            ko_ops[m.group(1)] = o["name"]
    zh_alliances = list(prts["alliances"])
    if len(ak["oaths"]) != len(zh_alliances):
        raise SystemExit("맹약 개수가 PRTS와 다릅니다 — 매핑 확인 필요")
    ko_alliances = {z: o["name"] for z, o in zip(zh_alliances, ak["oaths"])}

    ko_strat, en_strat = {}, {}
    for p, a in zip(prts["strategies"], ak["abilities"]):
        if str(p["hp"]) != str(a["hp"]):
            raise SystemExit(f"전략 순서 불일치: {p['leader']} / {a['name']}")
        eff = strip_html(a["effect"])
        m = re.match(r"\[([^\]]+)\]\s*", eff)
        ko_strat[p["leader"]] = {
            "leader": a["name"],
            "name": m.group(1) if m else "",
            "effect": re.sub(r"^패시브 효과\s*:\s*", "", eff[m.end():] if m else eff).strip(),
        }
        en_leader = official("en", p["leader_icon"]) or official("en", p["leader"])
        if en_leader:
            en_strat[p["leader"]] = {"leader": en_leader}

    # ---- en: 미출시 오퍼레이터는 PRTS 외문명(라틴 문자만) ----
    en_ops = {}
    for n in names:
        name = official("en", n)
        if not name:
            try:
                t = prts_api.wikitext(n)
                m = re.search(r"\|\s*干员外文名\s*=\s*([^\n|]*)", t)
                cand = m.group(1).strip().replace("/", " ") if m else ""
                name = cand if latin(cand) else None
            except Exception:
                name = None
        if name:
            en_ops[n] = name

    out = {
        "sources": {"ko": AK1234, "en": GAMEDATA["en"]},
        "ko": {
            "operators": {n: ko_ops.get(n) or official("ko", n) for n in names
                          if ko_ops.get(n) or official("ko", n)},
            "alliances": ko_alliances,
            "strategies": ko_strat,
            "special": {k: v[0] for k, v in SPECIAL.items()},
        },
        "en": {
            "operators": en_ops,
            "alliances": ALLIANCE_EN,
            "strategies": en_strat,
            "special": {k: v[1] for k, v in SPECIAL.items()},
        },
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf-8")
    for lang in ("ko", "en"):
        miss = [n for n in names if n not in out[lang]["operators"]]
        print(f"{lang}: 오퍼레이터 {len(out[lang]['operators'])}/{len(names)} (없음: {', '.join(miss) or '-'})")

    sync_avatars(names)


def sync_avatars(names: list[str], force: bool = False) -> None:
    """PRTS 초상화 → data/avatars (이미 있는 파일은 건너뜀)."""
    from PIL import Image
    AVATARS.mkdir(exist_ok=True)
    want = {}
    for n in names:
        want[f"头像_{n}(卫戍协议).png"] = n   # 원형 카드는 위수 협의 전용 이미지 우선
        want[f"头像_{n}.png"] = n
    urls = prts_api.image_urls(list(want))
    got = {}
    for fname, url in urls.items():
        n = want[fname]
        if n in got and "(卫戍协议)" not in fname:
            continue
        got[n] = url
    for n, url in got.items():
        if (AVATARS / f"{n}.png").exists() and not force:
            continue
        img = Image.open(io.BytesIO(fetch(url))).convert("RGBA")
        img.thumbnail((96, 96), Image.LANCZOS)
        img.save(AVATARS / f"{n}.png", optimize=True)
    print(f"초상화 {len(got)}/{len(names)}")


if __name__ == "__main__":
    if "--avatars" in sys.argv:   # 초상화만 다시 받기
        prts = json.loads((DATA / "prts_stronghold.json").read_text("utf-8"))
        protos = sorted({o["prototype"] for o in prts["operators"].values() if o.get("prototype")})
        sync_avatars(list(prts["operators"]) + protos)
    else:
        main()
