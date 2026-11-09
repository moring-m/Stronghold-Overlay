"""PRTS 위키에서 위수 협의: 규정(卫戍协议·规程) 데이터를 받아 data/prts_stronghold.json 으로 저장.

    python tools/sync_prts.py [--page "卫戍协议·规程/PRTS盟约记录"]

시즌이 바뀌면 --page 로 새 시즌의 'PRTS盟约记录' 페이지를 지정하세요.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import prts_api  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "prts_stronghold.json"
ITEM_DIR = OUT.parent / "items"    # 장비 아이콘
DEFAULT_PAGE = "卫戍协议·规程/PRTS盟约记录"


# ---------- 위키텍스트 유틸 ----------
def templates(text: str, name: str) -> list[dict[str, str]]:
    """{{name|k=v|...}} 를 중첩 괄호를 고려해 찾아 파라미터 dict 목록으로 반환."""
    out = []
    pat = re.compile(r"\{\{\s*" + re.escape(name) + r"\s*\|")
    for m in pat.finditer(text):
        depth, i = 0, m.start()
        while i < len(text):
            if text.startswith("{{", i):
                depth += 1; i += 2
            elif text.startswith("}}", i):
                depth -= 1; i += 2
                if depth == 0:
                    break
            else:
                i += 1
        out.append(_params(text[m.end():i - 2]))
    return out


def _params(body: str) -> dict[str, str]:
    parts, depth, cur = [], 0, ""
    j = 0
    while j < len(body):
        two = body[j:j + 2]
        if two in ("{{", "[["):
            depth += 1; cur += two; j += 2; continue
        if two in ("}}", "]]"):
            depth -= 1; cur += two; j += 2; continue
        if body[j] == "|" and depth == 0:
            parts.append(cur); cur = ""
        else:
            cur += body[j]
        j += 1
    parts.append(cur)
    res = {}
    for n, p in enumerate(parts):
        k, eq, v = p.partition("=")
        res[k.strip() if eq else str(n + 1)] = (v if eq else p).strip()
    return res


def plain(s: str) -> str:
    """색상/아이콘 틀과 HTML 태그를 지운 읽기용 텍스트."""
    s = re.sub(r"\{\{color\|[^|{}]*\|([^{}]*)\}\}", r"\1", s)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</?[a-zA-Z][^>]*>", "", s)   # HTML 태그만 (<获得时> 같은 조건 표기는 유지)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    s = s.replace("'''", "")
    return s.strip()


def section(text: str, title: str) -> str:
    m = re.search(r"^(=+)\s*" + re.escape(title) + r"\s*\1\s*$", text, re.M)
    if not m:
        return ""
    level = len(m.group(1))
    nxt = re.compile(r"^={1,%d}[^=].*?=+\s*$" % level, re.M).search(text, m.end())
    return text[m.end(): nxt.start() if nxt else len(text)]


def heads(s: str, tpl: str) -> list[str]:
    return [p["1"] for p in templates(s, tpl)]


# ---------- 파서 ----------
def parse(text: str) -> dict:
    alliances = {}
    for kind, sec in (("core", "核心盟约"), ("extra", "附加盟约")):
        for t in templates(section(text, sec), "卫戍协议/盟约"):
            alliances[t["盟约"]] = {
                "type": kind,
                "count": int(t.get("人数", 0) or 0),
                "effect": plain(t.get("效果", "")),
                "operators": heads(t.get("干员", ""), "干员头像"),
            }

    strategies = []
    for t in templates(text, ":卫戍协议/策略"):
        strategies.append({
            "leader": t.get("发起人override") or t.get("发起人", ""),
            "leader_icon": t.get("发起人", ""),
            "name": t.get("策略", ""),
            "hp": t.get("血量", ""),
            "effect": plain(t.get("效果", "")),
            "unlock": plain(t.get("解锁条件", "")),
        })

    equipment = {}
    for t in templates(section(text, "装备数据库"), ":卫戍协议/道具"):
        if t.get("类型") != "装备" or not t.get("名称"):
            continue
        eff = plain(t.get("效果", ""))
        basic, _, adv = eff.partition("\n")
        equipment[t["名称"]] = {
            "tier": "ⅠⅡⅢⅣⅤⅥ"[int(t.get("等阶", 1)) - 1] if t.get("等阶", "").isdigit() else "",
            "price": t.get("售价", ""),
            "effect": basic.replace("【基础】", "").strip(),
            "effect_adv": adv.replace("【进阶】", "").strip(),
            "desc": plain(t.get("描述", "")),
        }

    operators = {}
    db = section(text, "干员数据库")
    tier = ""
    for line in db.splitlines():
        tm = re.search(r"([ⅠⅡⅢⅣⅤⅥ])\}\}阶干员", line)
        if tm:
            tier = tm.group(1)
        for t in templates(line, "卫戍协议/参战干员"):
            operators[t["干员"]] = {
                "tier": tier,
                # 미보유 시 상점에 대신 표시되는 원형 이름 (예: Sharp(卫戍协议) -> Sharp)
                "prototype": re.sub(r"\(卫戍协议\)$", "", t.get("原型", "")).strip(),
                "alliances": [t[k] for k in ("盟约1", "盟约2", "盟约3") if t.get(k)],
                "trait_type": t.get("特质类型", ""),
                "trait": plain(t.get("特质1", "")),
                "trait_adv": plain(t.get("特质2", "")),
            }

    return {"alliances": alliances, "strategies": strategies, "operators": operators,
            "equipment": equipment}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default=DEFAULT_PAGE)
    args = ap.parse_args()
    data = parse(prts_api.wikitext(args.page))
    data = {"source": f"https://prts.wiki/w/{args.page}", "fetched": date.today().isoformat(), **data}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")

    ITEM_DIR.mkdir(exist_ok=True)
    files = {f"卫戍协议 道具 {n}.png": n for n in data["equipment"]}
    for fname, url in prts_api.image_urls(list(files)).items():
        dest = ITEM_DIR / f"{files[fname]}.png"
        if not dest.exists():
            prts_api.download(url, dest)
    print(f"{OUT.name}: 맹약 {len(data['alliances'])}, 전략 {len(data['strategies'])}, "
          f"오퍼레이터 {len(data['operators'])}, 장비 {len(data['equipment'])}")


if __name__ == "__main__":
    main()
