"""Render index.html and archive.html from state + generated content."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = ROOT / "data" / "content"
POOL = ROOT / "data" / "pool.json"
TEMPLATES = ROOT / "templates"

WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]
DAY_FOCUS = {1: "今天是完整入門", 2: "今天進到「進階與爭論」", 3: "今天進到「實戰與內化」收成日"}
DOMAIN_SHORT = {"econ": "經濟", "psych": "心理", "social": "社會", "health": "健康", "humanities": "人文"}
DOMAIN_LABEL = {
    "econ": "經濟 · 行為經濟", "psych": "心理", "social": "社會 · 人類學",
    "health": "健康", "humanities": "人文 · 哲學",
}
DOMAIN_ORDER = ["econ", "psych", "social", "health", "humanities"]


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True, lstrip_blocks=True,
    )


def _load_content(theory_id: str) -> dict:
    return json.loads((CONTENT_DIR / f"{theory_id}.json").read_text(encoding="utf-8"))


def _has_content(theory_id: str) -> bool:
    return (CONTENT_DIR / f"{theory_id}.json").exists()


def _date_str(d: date) -> str:
    return f"{d.year} 年 {d.month} 月 {d.day} 日 · 週{WEEKDAYS[d.weekday()]}"


def _md(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.month}/{d.day}"


def _pool_notice(state: dict) -> dict | None:
    """Banner shown when the unused-theory stock is low (mainly a fallback if
    auto-replenish failed, since replenish normally tops up before render)."""
    data = json.loads(POOL.read_text(encoding="utf-8"))
    used = set(state.get("used_ids", []))
    unused = sum(1 for t in data["theories"] if t["id"] not in used)
    low = state.get("pool_low_notice", state.get("pool_min_unused", 12))
    if unused <= 3:
        return {"level": "crit", "unused": unused,
                "text": f"新理論即將用完（尚餘 {unused} 個未登場）。自動補充可能未成功，"
                        "建議到 Actions 手動「強制補充理論池」，或擴充 data/pool.json。"}
    if unused <= low:
        return {"level": "low", "unused": unused,
                "text": f"新理論庫存偏低：尚有 {unused} 個未登場，系統會在每日更新時自動補充。"}
    return None


def render_index(state: dict, reviews: list[dict], today: date, generated_at: str) -> str:
    active_ids = state["current"]["active"]
    active_day = state["current"]["day"]
    theories = [_load_content(i) for i in active_ids]

    review_ctx = []
    for r in reviews:
        c = _load_content(r["id"])
        rv = c.get("review", {})
        review_ctx.append({
            "name_zh": c["name_zh"], "domain_class": c["domain_class"],
            "domain_short": DOMAIN_SHORT.get(c["domain_class"], ""),
            "question": rv.get("question", ""), "answer": rv.get("answer", ""),
            "answer_example": rv.get("answer_example", ""), "mnemonic": rv.get("mnemonic", ""),
            "distance_days": r["distance_days"], "completed_str": _md(r["completed_date"]),
            "nth": r["nth"],
        })

    tmpl = _env().get_template("index.html.j2")
    return tmpl.render(
        date_str=_date_str(today), active_day=active_day,
        hero_focus=DAY_FOCUS.get(active_day, ""), theories=theories,
        reviews=review_ctx, generated_at=generated_at, note=None,
        pool_notice=_pool_notice(state),
    )


def render_archive(state: dict, today: date, generated_at: str) -> str:
    pool = json.loads(POOL.read_text(encoding="utf-8"))["theories"]
    active = set(state["current"]["active"]) if state.get("current") else set()
    used = set(state["used_ids"])
    completed = {c["id"]: c for c in state["completed"]}

    def is_due(tid: str) -> bool:
        c = completed.get(tid)
        if not c:
            return False
        nxt = c["review_due"][c["reviews_done"]:]
        return bool(nxt) and date.fromisoformat(nxt[0]) <= today

    groups = []
    due_count = 0
    for dc in DOMAIN_ORDER:
        chips = []
        for t in pool:
            if t["domain_class"] != dc:
                continue
            tid = t["id"]
            due = is_due(tid)
            due_count += 1 if due else 0
            if tid in active:
                badge = "· 進行中"
            elif tid in completed:
                badge = "● 待複習" if due else "· 已講"
            elif tid in used:
                badge = "· 已講"
            else:
                badge = "· 待排"
            # 有產出內容的（講過或進行中）才可點進去回頭重讀
            href = f"theory/{tid}.html" if _has_content(tid) else None
            chips.append({"name_zh": t["name_zh"], "name_en": t.get("name_en", ""),
                          "badge": badge, "due": due, "href": href})
        if chips:
            groups.append({"domain_class": dc, "label": DOMAIN_LABEL.get(dc, dc), "chips": chips})

    tmpl = _env().get_template("archive.html.j2")
    return tmpl.render(
        groups=groups, total=len(pool), seen=len(used), active_count=len(active),
        due_count=due_count, generated_at=generated_at, note=None,
        pool_notice=_pool_notice(state),
    )


def render_theory(state: dict, theory_id: str, today: date, generated_at: str) -> str:
    """Render a standalone, re-readable detail page for one theory.

    Completed theories are fully unlocked (all three days). The currently-active
    theory mirrors today's unlock level so the archive can't leak gated days.
    """
    t = _load_content(theory_id)
    cur = state.get("current") or {}
    if theory_id in cur.get("active", []):
        unlocked_day = cur.get("day", 1)
        status_label = f"進行中 · 第 {unlocked_day} 天 / 3"
    else:
        unlocked_day = 3
        status_label = "理論回顧 · 完整三天"

    tmpl = _env().get_template("theory.html.j2")
    return tmpl.render(
        t=t, unlocked_day=unlocked_day, status_label=status_label,
        generated_at=generated_at,
    )
