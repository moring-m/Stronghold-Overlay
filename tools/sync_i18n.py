"""번역(ko/en)과 오퍼레이터 초상화를 받아 저장.

- ko: arknights1234.github.io (위수 협의: 규정 / act3autochess) — 오퍼레이터, 특질, 맹약, 전략, 장비
      없는 이름은 공식 한국 서버 character_table 로 보충
- en: 공식 글로벌 서버 character_table (ArknightsGameData_YoStar)
      글로벌 미출시 오퍼레이터는 PRTS '干员外文名'(라틴 문자일 때만)
      맹약 영어 이름은 이 파일의 표 (국가명은 공식 표기, 나머지는 비공식 번역)
      장비/특질의 영어 공식 번역은 없어 중국어로 표시
- 초상화: PRTS 头像_<이름>.png → data/avatars/<이름>.png (96px)
- 등급/맹약 아이콘: arknights1234 images/stage*.webp, oaths/*.webp → data/icons

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
    s = re.sub(r"</?[a-zA-Z][^>]*>", "", s)   # HTML 태그만 (<获得时> 같은 조건 표기는 유지)
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
    ko_ops, ko_traits, ko_trait_types = {}, {}, {}
    for o in ak["operators"]:
        m = re.search(r"头像_(.+)\.webp", o.get("img", ""))
        if m:
            ko_ops[m.group(1)] = o["name"]
            ko_traits[m.group(1)] = strip_html(o.get("traitDescription", ""))
            zh_type = prts["operators"].get(m.group(1), {}).get("trait_type")
            if zh_type and o.get("class"):
                ko_trait_types[zh_type] = o["class"]   # 예: 持续叠加 → 지속 중첩

    # 장비: PRTS와 같은 순서 (단계로 검증)
    zh_items = list(prts.get("equipment", {}))
    ko_items, ko_item_eff = {}, {}
    if len(ak.get("tools", [])) == len(zh_items):
        for z, t in zip(zh_items, ak["tools"]):
            if "ⅠⅡⅢⅣⅤⅥ"[int(t["stage"]) - 1] != prts["equipment"][z]["tier"]:
                raise SystemExit(f"장비 순서 불일치: {z} / {t['name']}")
            ko_items[z] = t["name"]
            ko_item_eff[z] = strip_html(t.get("effect", ""))
    else:
        print("경고: 장비 개수가 PRTS와 달라 한국어 장비 이름을 건너뜁니다")
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
            "traits": ko_traits,
            "trait_types": ko_trait_types,
            "equipment": ko_items,
            "equipment_effects": ko_item_eff,
        },
        "en": {
            "operators": en_ops,
            "alliances": ALLIANCE_EN,
            "strategies": en_strat,
        },
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf-8")
    for lang in ("ko", "en"):
        miss = [n for n in names if n not in out[lang]["operators"]]
        print(f"{lang}: 오퍼레이터 {len(out[lang]['operators'])}/{len(names)} (없음: {', '.join(miss) or '-'})")

    sync_icons(ak, zh_alliances)
    sync_avatars(names)


def sync_icons(ak: dict, zh_alliances: list[str]) -> None:
    """arknights1234의 등급 아이콘(stage1~6)과 맹약 아이콘 → data/icons (PNG)."""
    from PIL import Image
    base = AK1234.rsplit("/js/", 1)[0] + "/"
    icons = DATA / "icons"
    (icons / "alliances").mkdir(parents=True, exist_ok=True)
    jobs = [(f"images/stage{n}.webp", icons / f"tier{n}.png", 48) for n in range(1, 7)]
    jobs += [(o["img"], icons / "alliances" / f"{z}.png", 48) for z, o in zip(zh_alliances, ak["oaths"])]
    for src, dest, size in jobs:
        if dest.exists():
            continue
        img = Image.open(io.BytesIO(fetch(base + src))).convert("RGBA")
        img.thumbnail((size, size), Image.LANCZOS)
        img.save(dest, optimize=True)
    print(f"아이콘 {len(jobs)}개")


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
    if "--icons" in sys.argv:     # 등급/맹약 아이콘만
        prts = json.loads((DATA / "prts_stronghold.json").read_text("utf-8"))
        sync_icons(parse_js_object(fetch(AK1234).decode("utf-8")), list(prts["alliances"]))
    elif "--avatars" in sys.argv:   # 초상화만 다시 받기
        prts = json.loads((DATA / "prts_stronghold.json").read_text("utf-8"))
        protos = sorted({o["prototype"] for o in prts["operators"].values() if o.get("prototype")})
        sync_avatars(list(prts["operators"]) + protos)
    else:
        main()
