"""PRTS 위키(prts.wiki) MediaWiki API 최소 클라이언트."""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

API = "https://prts.wiki/api.php"
UA = "StrongholdOverlay/0.1 (data sync script)"


def _get(params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    last: Exception | None = None
    for i in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception as e:  # 연결 끊김이 잦아 재시도
            last = e
            time.sleep(2 ** i)
    raise RuntimeError(f"PRTS 요청 실패: {params}") from last


def wikitext(page: str) -> str:
    return _get({"action": "parse", "page": page, "prop": "wikitext"})["parse"]["wikitext"]["*"]


def expanded(page: str) -> str:
    """틀(template)을 펼친 결과 wikitext."""
    src = wikitext(page)
    return _get({"action": "expandtemplates", "text": src, "title": page,
                 "prop": "wikitext"})["expandtemplates"]["wikitext"]


def prefix_pages(prefix: str) -> list[str]:
    q = _get({"action": "query", "list": "allpages", "apprefix": prefix, "aplimit": 500})
    return [p["title"] for p in q["query"]["allpages"]]


def image_urls(files: list[str]) -> dict[str, str]:
    """'头像_敌人_xxx.png' 같은 파일 이름 → 다운로드 URL."""
    out: dict[str, str] = {}
    for i in range(0, len(files), 40):
        batch = files[i:i + 40]
        q = _get({"action": "query", "prop": "imageinfo", "iiprop": "url",
                  "titles": "|".join("文件:" + f for f in batch)})["query"]
        norm = {n["to"]: n["from"] for n in q.get("normalized", [])}
        for page in q["pages"].values():
            if "imageinfo" in page:
                src = norm.get(page["title"], page["title"])
                out[src.removeprefix("文件:")] = page["imageinfo"][0]["url"]
    return out


def download(url: str, dest) -> None:
    last = None
    for i in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                dest.write_bytes(r.read())
            return
        except Exception as e:
            last = e
            time.sleep(2 ** i)
    raise RuntimeError(f"다운로드 실패: {url}") from last
