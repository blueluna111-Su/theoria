"""每日加值區塊：『今日一識』（跨界實用知識）＋『新鮮發現』（GitHub / Hacker News 上新鮮又實用的專案）。

  python scripts/extras.py                 # 產今天的（需 GOOGLE_API_KEY）
  python scripts/extras.py --date 2026-11-05 --force
  THEORIA_MOCK=1 python scripts/extras.py  # 離線佔位內容

輸出：data/extras/<date>.json（同日已存在就沿用，--force 才重生）。
『新鮮發現』的連結一律來自實際抓到的候選清單，模型只負責挑選與撰寫介紹，不會憑空生出網址。
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import time
from datetime import date, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
EXTRAS_DIR = ROOT / "data" / "extras"
FINDS_PER_DAY = 2  # 每天介紹幾個新鮮發現
UA = {"User-Agent": "theoria-daily (github.com/blueluna111-Su/theoria)"}

# 『今日一識』輪替的知識類別：刻意挑「知道了，某天真的用得上」的領域。
KNOWLEDGE_CATEGORIES = [
    ("身體與醫學常識", "身體怎麼運作、常見症狀的判讀、什麼時候該就醫、常見迷思"),
    ("法律與自身權益", "台灣常見的消費、租屋、勞動、交通權益與程序（只講原則，提醒以現行法規為準）"),
    ("理財與數字感", "利率、通膨、保險、稅、帳單裡的數學，以及常見的金融話術"),
    ("科技與資安", "手機電腦的實用原理、帳號安全、詐騙手法、隱私設定"),
    ("生活科學", "廚房、居家、清潔、天氣背後的物理化學，以及可以直接照做的小技巧"),
    ("溝通與語言", "說話、寫作、談判、語源與用詞，能立刻用在對話裡的技巧"),
    ("歷史與文化典故", "常聽到的說法、制度、習俗從哪裡來，懂了能看穿現在的事"),
    ("自然與地理", "動植物、地球、天文、環境，以及跟日常生活或安全有關的知識"),
    ("工具與效率", "軟體、鍵盤、檔案管理、家用工具等能省時間的方法"),
    ("飲食與營養", "食物成分、標示怎麼讀、烹調與保存的科學、常見營養迷思"),
]

KNOWLEDGE_SYSTEM = """你是「每日三理」的『今日一識』作者：每天寫一則跨領域、實用、讀完下次真的用得上的知識，用繁體中文（台灣用語）。

鐵則：
1. 實用優先：選題要讓一般成年人「知道了，某天會用到」或「能立刻改變一個小習慣/判斷」，不要純冷知識或背了也沒用的資料。
2. 有趣：開頭要有一個讓人想讀下去的鉤子（反直覺、常見誤解、生活場景）。
3. 準確：停在可靠的概念層級，不杜撰研究數字、法條條號或精確統計；涉及醫療、法律、金錢時，提醒個案以專業意見或現行規定為準。有爭議的說法要誠實標出。
4. 詳細但不冗長：把原理講清楚，附具體例子。
5. 只輸出一個 JSON 物件，不要任何說明文字或 markdown 圍欄。"""

KNOWLEDGE_STRUCTURE = """請輸出以下結構的 JSON：
{
  "title": "這則知識的標題（簡短、具體）",
  "hook": "一句吸引人讀下去的開場（反直覺事實、常見誤解或生活場景）",
  "body": ["把原理完整講清楚的段落1（2～4句）", "段落2", "（可選）段落3"],
  "examples": ["具體生活例子1", "例子2"],
  "takeaway": "下次遇到時可以怎麼做（一兩句、可直接照做）",
  "caveat": "需要注意的限制或例外（沒有就給 null）"
}"""

FINDS_SYSTEM = """你是「每日三理」的『新鮮發現』編輯：從當天實際抓到的 GitHub 新專案與 Hacker News「Show HN」作品裡，挑出最新鮮、有趣、特別、而且一般人或工作者真的用得上的項目，用繁體中文（台灣用語）介紹。

挑選原則：
1. 實用 > 炫技：優先挑「能直接拿來用、或能啟發一個做法」的項目；純學術論文程式碼、半成品、只有開發者圈內才懂的底層函式庫，除非真的很特別，否則不選。
2. 多元：AI 應用很歡迎，但不限於 AI；生活工具、硬體、設計、資料、效率工具等非 AI 項目同樣歡迎。
3. 誠實：只能根據候選提供的資訊描述，不要杜撰它沒提到的功能、價格或數據；資訊不足處就說「依專案介紹」或保守描述。
4. 只輸出一個 JSON 物件，不要任何說明文字或 markdown 圍欄。"""

FINDS_STRUCTURE = """以下是今天的候選清單（JSON 陣列，每個有 cid）：
{candidates}

請挑出今天最值得介紹的 {n} 個。{lean}
輸出：
{{
  "finds": [
    {{
      "cid": "候選的 cid（必須完全一致）",
      "name": "項目名稱（可保留原文）",
      "kind": "分類標籤，2～6字（如 AI 工具、開發者工具、效率工具、硬體、生活應用、資料視覺化）",
      "is_ai": true,
      "one_liner": "一句話說它是什麼",
      "why": "為什麼新鮮/有趣/特別（2～3句）",
      "use": "你可以怎麼用它、或它啟發的做法（具體場景，2～3句）",
      "caveat": "要注意的地方（還很早期、需要技術背景、需付費、隱私等；沒有就給 null）"
    }}
  ]
}}"""


# ---------------------------------------------------------------- candidates

def _seen_urls() -> set[str]:
    seen = set()
    for p in EXTRAS_DIR.glob("*.json"):
        try:
            for f in json.loads(p.read_text(encoding="utf-8")).get("finds", []):
                seen.add(f.get("url", ""))
        except Exception:  # noqa: BLE001
            pass
    return seen


def _clean(text: str | None, limit: int = 400) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def fetch_github(today: date) -> list[dict]:
    since = (today - timedelta(days=10)).isoformat()
    headers = {**UA, "Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    r = requests.get(
        "https://api.github.com/search/repositories",
        params={"q": f"created:>{since} stars:>80 archived:false", "sort": "stars",
                "order": "desc", "per_page": 30},
        headers=headers, timeout=30)
    r.raise_for_status()
    out = []
    for it in r.json().get("items", []):
        out.append({
            "source": "GitHub", "title": it["full_name"], "url": it["html_url"],
            "desc": _clean(it.get("description")), "score": it.get("stargazers_count", 0),
            "meta": {"language": it.get("language"), "topics": (it.get("topics") or [])[:6],
                     "homepage": it.get("homepage") or None},
        })
    return out


def fetch_show_hn(today: date) -> list[dict]:
    since = int(time.mktime((today - timedelta(days=3)).timetuple()))
    r = requests.get(
        "https://hn.algolia.com/api/v1/search",
        params={"tags": "show_hn", "numericFilters": f"created_at_i>{since},points>40",
                "hitsPerPage": 30},
        headers=UA, timeout=30)
    r.raise_for_status()
    out = []
    for h in r.json().get("hits", []):
        hn_url = f"https://news.ycombinator.com/item?id={h['objectID']}"
        title = re.sub(r"^Show HN:\s*", "", h.get("title") or "")
        out.append({
            "source": "Hacker News", "title": title, "url": h.get("url") or hn_url,
            "discuss_url": hn_url, "desc": _clean(h.get("story_text")),
            "score": h.get("points", 0), "meta": {"comments": h.get("num_comments", 0)},
        })
    return out


def fetch_candidates(today: date) -> list[dict]:
    seen = _seen_urls()
    cands: list[dict] = []
    for fn in (fetch_github, fetch_show_hn):
        try:
            got = fn(today)
            print(f"  · {fn.__name__}: {len(got)} 筆")
            cands += got
        except Exception as e:  # noqa: BLE001 — 單一來源失敗不影響另一個
            print(f"  ! {fn.__name__} 失敗（{e}）")
    cands = [c for c in cands if c["url"] not in seen]
    for i, c in enumerate(cands):
        c["cid"] = f"c{i}"
    return cands


# ---------------------------------------------------------------- generation

def _recent_knowledge_titles(n: int = 90) -> list[str]:
    titles = []
    for p in sorted(EXTRAS_DIR.glob("*.json"), reverse=True)[:n]:
        try:
            k = json.loads(p.read_text(encoding="utf-8")).get("knowledge") or {}
            if k.get("title"):
                titles.append(k["title"])
        except Exception:  # noqa: BLE001
            pass
    return titles


def gen_knowledge(today: date) -> dict:
    from gemini import generate_json

    cat, scope = KNOWLEDGE_CATEGORIES[today.toordinal() % len(KNOWLEDGE_CATEGORIES)]
    recent = _recent_knowledge_titles()
    avoid = ("最近寫過（不要重複或太接近）：\n- " + "\n- ".join(recent)) if recent else ""
    prompt = (f"今天的類別：{cat}（範圍：{scope}）\n"
              f"請在這個類別裡挑一個實用又有趣的主題。\n{avoid}\n\n{KNOWLEDGE_STRUCTURE}")
    k = generate_json(KNOWLEDGE_SYSTEM, prompt, temperature=0.8, max_output_tokens=4096)
    k["category"] = cat
    return k


def gen_finds(cands: list[dict], today: date) -> list[dict]:
    from gemini import generate_json

    if not cands:
        return []
    # 給模型的精簡版本（不含網址，避免它自己拼網址）
    brief = [{"cid": c["cid"], "source": c["source"], "title": c["title"], "desc": c["desc"],
              "score": c["score"], **c.get("meta", {})} for c in cands]
    # 單數日偏好非 AI、雙數日偏好 AI，讓長期下來兩種都有
    lean = ("最好一個是 AI 應用、一個是非 AI 項目；兩個不要是同一類，候選不夠好時以品質優先。"
            if FINDS_PER_DAY == 2 else
            "今天若有夠好的非 AI 項目，優先選它。" if today.toordinal() % 2
            else "今天若有夠好的 AI 應用，優先選它。")
    prompt = FINDS_STRUCTURE.format(candidates=json.dumps(brief, ensure_ascii=False), lean=lean, n=FINDS_PER_DAY)
    res = generate_json(FINDS_SYSTEM, prompt, temperature=0.6, max_output_tokens=4096)
    by_cid = {c["cid"]: c for c in cands}
    finds = []
    for f in res.get("finds", []):
        c = by_cid.get(f.get("cid"))
        if not c or any(x["url"] == c["url"] for x in finds):
            continue  # 模型給了不存在/重複的 cid → 丟掉，絕不採用它自編的連結
        f.pop("cid", None)
        finds.append({**f, "source": c["source"], "url": c["url"],
                      "discuss_url": c.get("discuss_url"), "score": c["score"],
                      "repo": c["title"] if c["source"] == "GitHub" else None})
    return finds[:FINDS_PER_DAY]


def mock_extras(today: date) -> dict:
    cat = KNOWLEDGE_CATEGORIES[today.toordinal() % len(KNOWLEDGE_CATEGORIES)][0]
    return {
        "date": today.isoformat(),
        "knowledge": {"category": cat, "title": f"{cat}的一則實用知識（示意）",
                      "hook": "這是離線示意的開場鉤子。",
                      "body": ["這裡會是把原理講清楚的第一段（示意）。", "第二段（示意）。"],
                      "examples": ["生活例子 A（示意）", "生活例子 B（示意）"],
                      "takeaway": "下次可以這樣做（示意）。", "caveat": None},
        "finds": [{"name": f"示意專案 {i}", "kind": "AI 工具" if i == 1 else "效率工具",
                   "is_ai": i == 1, "one_liner": "一句話說它是什麼（示意）。",
                   "why": "為什麼有趣（示意）。", "use": "你可以怎麼用（示意）。", "caveat": None,
                   "source": "GitHub", "url": "https://github.com/", "discuss_url": None,
                   "score": 100 * i, "repo": f"example/demo-{i}"} for i in range(1, FINDS_PER_DAY + 1)],
    }


def ensure_extras(today: date, *, force: bool = False) -> dict | None:
    """產生（或沿用）當日 extras。任何一部分失敗都只略過該部分，不拋例外。"""
    EXTRAS_DIR.mkdir(parents=True, exist_ok=True)
    out = EXTRAS_DIR / f"{today.isoformat()}.json"
    if out.exists() and not force:
        return json.loads(out.read_text(encoding="utf-8"))
    if os.environ.get("THEORIA_MOCK") == "1":
        data = mock_extras(today)
    else:
        data = {"date": today.isoformat(), "knowledge": None, "finds": []}
        try:
            data["knowledge"] = gen_knowledge(today)
        except Exception as e:  # noqa: BLE001
            print(f"  ! 今日一識略過（{e}）")
        try:
            data["finds"] = gen_finds(fetch_candidates(today), today)
        except Exception as e:  # noqa: BLE001
            print(f"  ! 新鮮發現略過（{e}）")
        if not data["knowledge"] and not data["finds"]:
            return None  # 全失敗就不落檔，下次重跑還能再試
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  + wrote {out.relative_to(ROOT)}")
    return data


def load_all() -> list[dict]:
    """所有日期的 extras，新到舊。"""
    items = []
    for p in sorted(EXTRAS_DIR.glob("*.json"), reverse=True):
        try:
            items.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            pass
    return items


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    d = date.fromisoformat(a.date) if a.date else date.today()
    print(json.dumps(ensure_extras(d, force=a.force), ensure_ascii=False, indent=2))
