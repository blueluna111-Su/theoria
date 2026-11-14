"""Auto-replenish the theory pool.

When the number of *unused* theories drops below a threshold, ask Gemini for a
fresh batch of real, applicable theories, de-duplicate against the existing
pool, and append them to data/pool.json. Keeps the library from ever running
dry and keeps adding novel ("fresh") theories automatically.

  python scripts/replenish.py [N]     # force-add N (needs GOOGLE_API_KEY)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "data" / "pool.json"
from domains import DOMAIN_HINT  # noqa: E402

ALLOWED_DC = set(DOMAIN_HINT)

SYSTEM = (
    "你是嚴謹的學術理論策展人，為『每日三理』擴充理論池。"
    "你只提出『真實存在、學界公認、且可應用於日常生活或工作』的理論／框架／效應／定律／偏誤，"
    "涵蓋多種學科（經濟、心理、社會、健康、人文，以及學習、溝通、職場、設計、機率統計、自然科學、法政等）。"
    "篩選的核心標準是『跟一般人的日常有關』：讀完能拿來理解生活、做決定、改善工作或人際；"
    "太專業、只在該學科內部才用得上的理論一律不選。繁體中文（台灣用語）。"
)


def _domain_menu() -> str:
    return "\n".join(f"  - {k}：{h}" for k, h in DOMAIN_HINT.items())


def _underrepresented(pool: list[dict], k: int = 6) -> list[str]:
    """Domain classes with the fewest theories in the pool (ask Gemini to favour them)."""
    from collections import Counter
    cnt = Counter(t.get("domain_class") for t in pool)
    return sorted(DOMAIN_HINT, key=lambda d: cnt.get(d, 0))[:k]


def _prompt(n: int, existing: list[str], favour: list[str] | None = None) -> str:
    listing = "、".join(existing)
    favour_txt = "、".join(favour or [])
    return (
        "理論池已收錄以下理論，請務必避開——不只是名稱，連『概念雷同、互為同義、"
        f"或屬於其中一個子效應』也都不要重複：\n{listing}\n\n"
        f"請提出 {n} 個『不在上面、概念也不重疊』的理論，輸出一個 JSON 物件：\n"
        '{ "theories": [ { "name_zh": "中文名", "name_en": "English name", '
        '"domain": "簡短中文領域", "domain_class": "下列類別代碼其一", '
        '"author": "提出者字串，不確定就 null", "year": 年份整數或 null, '
        '"note": "一句話、突顯它在日常怎麼用", "tier": "fresh 或 core" } ] }\n\n'
        f"類別代碼與範圍：\n{_domain_menu()}\n\n"
        "鐵則：\n"
        "(1) 必須真實、可查證，絕不杜撰名稱或作者；不確定作者或年份就填 null。\n"
        f"(2) 跨領域分散：這 {n} 個要分散在不同類別，不要擠在心理學；"
        f"這次請優先補足目前收錄較少的類別：{favour_txt}。\n"
        "(2b) 日常相關性過濾（最重要）：每個理論都要通過『一般上班族／學生讀完，"
        "這週就能在生活、工作、人際或做決定上用到』的檢驗。"
        "像量子力學詮釋、數論定理、專業法條、臨床診斷準則、學派內部方法論這種"
        "離日常太遠、太專業深入的，一律不要；自然科學與數學類只選能借來理解日常現象或改善判斷的原理。\n"
        "(3) 在通過日常相關性的前提下，偏好『較少見、令人意外、跨學科』的理論（tier 多用 fresh）；"
        "避開人人都知道的教科書款——例如確認偏誤、可得性捷思、月暈效應、基本歸因錯誤、"
        "錨定、沉沒成本、從眾、馬斯洛、稟賦效應這類太常見的，不要選。\n"
        "(4) 重視可應用性：note 要點出它怎麼用在生活或工作。\n"
        "(5) 只輸出 JSON 物件，不要任何其他文字。"
    )


def slugify(name_en: str) -> str | None:
    s = re.sub(r"[^a-z0-9]+", "-", (name_en or "").lower()).strip("-")
    return s or None


def generate_candidates(n: int, existing: list[str], api_key: str | None = None,
                        favour: list[str] | None = None) -> list[dict]:
    from gemini import generate_json  # local import: only needed in the real path

    res = generate_json(SYSTEM, _prompt(n, existing, favour), api_key=api_key, temperature=0.6)
    if isinstance(res, list):
        return res
    return res.get("theories", [])


def add_to_pool(candidates: list[dict], *, default_tier: str = "fresh", pool_path: Path = POOL) -> list[dict]:
    """De-duplicate against the pool and append valid candidates. Returns the added entries."""
    data = json.loads(pool_path.read_text(encoding="utf-8"))
    ids = {t["id"] for t in data["theories"]}
    names: set[str] = set()
    for t in data["theories"]:
        names.add(t["name_zh"])
        names.add((t.get("name_en") or "").lower())

    added: list[dict] = []
    for c in candidates or []:
        zh = (c.get("name_zh") or "").strip()
        en = (c.get("name_en") or "").strip()
        dc = c.get("domain_class")
        if not zh or not en or dc not in ALLOWED_DC:
            continue
        sid = slugify(en)
        if not sid or sid in ids:
            continue
        if zh in names or en.lower() in names:
            continue
        yr = c.get("year")
        entry = {
            "id": sid, "name_zh": zh, "name_en": en,
            "domain": (c.get("domain") or "").strip() or zh,
            "domain_class": dc,
            "author": (c.get("author") or None),
            "year": yr if isinstance(yr, int) else None,
            "note": (c.get("note") or "").strip(),
            "tier": c.get("tier") if c.get("tier") in ("core", "fresh") else default_tier,
        }
        data["theories"].append(entry)
        ids.add(sid); names.add(zh); names.add(en.lower())
        added.append(entry)

    if added:
        pool_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return added


def maybe_replenish(state: dict, *, force: bool = False) -> list[dict]:
    """Top up the pool if unused theories are below the low-water mark (or if forced)."""
    min_unused = state.setdefault("pool_min_unused", 12)
    batch = state.setdefault("pool_replenish_batch", 9)
    data = json.loads(POOL.read_text(encoding="utf-8"))
    used = set(state.get("used_ids", []))
    unused = [t for t in data["theories"] if t["id"] not in used]
    if not force and len(unused) >= min_unused:
        return []
    existing = [f'{t["name_zh"]}({t.get("name_en", "")})' for t in data["theories"]]
    return add_to_pool(generate_candidates(batch, existing, favour=_underrepresented(data["theories"])))


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 9
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    ex = [f'{t["name_zh"]}({t.get("name_en", "")})' for t in pool["theories"]]
    got = add_to_pool(generate_candidates(n, ex, favour=_underrepresented(pool["theories"])))
    print(f"加入 {len(got)} 個：", [a["name_zh"] for a in got])
