"""Daily orchestrator: advance schedule -> generate missing content -> render HTML.

  python scripts/run_daily.py                 # real run (needs GOOGLE_API_KEY)
  THEORIA_MOCK=1 python scripts/run_daily.py   # offline, placeholder content
  python scripts/run_daily.py --date 2026-06-26 --force   # pin date / re-advance
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import render  # noqa: E402
import schedule  # noqa: E402
from generate import ensure_content  # noqa: E402

REPO = ROOT.parent


def taipei_today() -> date:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Taipei")).date()
    except Exception:  # noqa: BLE001  (Windows without tzdata, etc.)
        return date.today()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="override today (YYYY-MM-DD)")
    ap.add_argument("--force", action="store_true", help="advance even if already run today")
    ap.add_argument("--no-generate", action="store_true", help="skip Gemini; render existing only")
    ap.add_argument("--replenish-now", action="store_true", help="force a pool top-up regardless of stock")
    args = ap.parse_args()

    today = date.fromisoformat(args.date) if args.date else taipei_today()
    today_iso = today.isoformat()
    generated_at = today_iso

    state = schedule.load_state()
    schedule.run_schedule(state, today_iso, force=args.force)
    if state.pop("_pool_exhausted", False):
        print("  ! pool exhausted — repeating earlier theories; consider expanding data/pool.json")

    active = state["current"]["active"]
    print(f"今天 {today_iso}：第 {state['current']['day']} 天 / 3 — 主題 {active}")

    if not args.no_generate:
        for tid in active:
            ensure_content(tid)

    reviews = schedule.pick_reviews(state, today_iso)
    if reviews:
        print(f"複習卡：{[r['id'] for r in reviews]}")
        for r in reviews:  # make sure review theories have content (should already)
            if not args.no_generate:
                ensure_content(r["id"])

    # 自動補充理論池：存量低於門檻（或被強制）時請 AI 提一批新理論
    if not args.no_generate and os.environ.get("THEORIA_MOCK") != "1":
        try:
            import replenish
            added = replenish.maybe_replenish(state, force=args.replenish_now)
            if added:
                print(f"  + 理論池自動補充 {len(added)} 個：{[a['name_zh'] for a in added]}")
        except Exception as e:  # noqa: BLE001 — 補充失敗不應讓每日生成失敗
            print(f"  ! 理論池補充略過（{e}）")

    (REPO / "index.html").write_text(
        render.render_index(state, reviews, today, generated_at), encoding="utf-8")
    (REPO / "archive.html").write_text(
        render.render_archive(state, today, generated_at), encoding="utf-8")
    print("  + rendered index.html, archive.html")

    # 每則「講過/進行中」的理論各產一頁可回頭重讀的詳情頁（theory/<id>.html）
    theory_dir = REPO / "theory"
    theory_dir.mkdir(exist_ok=True)
    content_dir = REPO / "data" / "content"
    readable = sorted(p.stem for p in content_dir.glob("*.json"))
    for tid in readable:
        (theory_dir / f"{tid}.html").write_text(
            render.render_theory(state, tid, today, generated_at), encoding="utf-8")
    print(f"  + rendered {len(readable)} 個理論詳情頁 → theory/")

    schedule.save_state(state)
    print("  + saved state.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
