"""Ledger / scheduler for 每日三理.

State machine over data/state.json:
- advance the current 3-day cycle (day 1 -> 2 -> 3);
- when a cycle finishes, file its theories into the review queue with
  expanding-interval due dates, then start a new cycle from the pool;
- pick the review cards that are due today.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "state.json"
POOL = ROOT / "data" / "pool.json"


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def pool_theories() -> list[dict]:
    return json.loads(POOL.read_text(encoding="utf-8"))["theories"]


def pool_ids() -> list[str]:
    return [t["id"] for t in pool_theories()]


def _d(iso: str) -> date:
    return date.fromisoformat(iso)


def _start_cycle(state: dict, today_iso: str) -> None:
    """Pick the next cycle, guaranteeing at least one `fresh` theory when any remain.
    Composition: 1 fresh + (n-1) core; fall back across tiers if one runs short."""
    theories = pool_theories()
    used = set(state["used_ids"])
    n = state["theories_per_cycle"]
    fresh_avail = [t["id"] for t in theories if t.get("tier") == "fresh" and t["id"] not in used]
    core_avail = [t["id"] for t in theories if t.get("tier") != "fresh" and t["id"] not in used]

    chosen: list[str] = []
    if fresh_avail:                              # guarantee >=1 fresh per cycle
        chosen.append(fresh_avail.pop(0))
    for src in (core_avail, fresh_avail):        # fill the rest: core first, then leftover fresh
        while len(chosen) < n and src:
            chosen.append(src.pop(0))

    if len(chosen) < n:                          # pool exhausted -> allow repeats from start
        state["_pool_exhausted"] = True
        for i in (t["id"] for t in theories):
            if i not in chosen:
                chosen.append(i)
            if len(chosen) == n:
                break

    state["current"] = {"active": chosen, "day": 1, "cycle_started": today_iso}
    state["used_ids"] = list(dict.fromkeys(state["used_ids"] + chosen))


def _finalize(state: dict, cur: dict, today_iso: str) -> None:
    today = _d(today_iso)
    due = [(today + timedelta(days=n)).isoformat() for n in state["review_intervals_days"]]
    for tid in cur["active"]:
        state["completed"].append({
            "id": tid,
            "completed_date": today_iso,
            "last_seen": today_iso,
            "review_due": due,
            "reviews_done": 0,
        })


def run_schedule(state: dict, today_iso: str, *, force: bool = False) -> dict:
    """Advance the ledger to reflect `today`. Idempotent per date unless force."""
    if state.get("last_run_date") == today_iso and not force:
        return state  # already advanced today

    cur = state.get("current")
    if not cur or not cur.get("active"):
        _start_cycle(state, today_iso)
    elif cur["day"] < state["cycle_length"]:
        cur["day"] += 1
    else:
        _finalize(state, cur, today_iso)
        _start_cycle(state, today_iso)

    state["last_run_date"] = today_iso
    return state


def pick_reviews(state: dict, today_iso: str) -> list[dict]:
    """Return up to N due review cards, marking each as reviewed (mutates state)."""
    today = _d(today_iso)
    candidates = []
    for c in state["completed"]:
        pending = [dd for dd in c["review_due"][c["reviews_done"]:] if _d(dd) <= today]
        if pending:
            candidates.append((_d(c["review_due"][c["reviews_done"]]), c))
    candidates.sort(key=lambda x: x[0])

    picked = []
    for _due, c in candidates[: state["review_cards_per_day"]]:
        distance = (today - _d(c["last_seen"])).days
        c["reviews_done"] += 1
        c["last_seen"] = today_iso
        picked.append({
            "id": c["id"],
            "completed_date": c["completed_date"],
            "nth": c["reviews_done"],
            "distance_days": max(distance, 0),
        })
    return picked
