"""每日推播：把今天的三個理論透過 ntfy 推到手機，點通知即開當天頁面。

需要環境變數 NTFY_TOPIC（存成 GitHub secret；沒設就安靜略過）。
"""
import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SITE_URL = "https://blueluna111-su.github.io/theoria/"
DAY_LABELS = {1: "入門全貌", 2: "進階與爭論", 3: "實戰與內化"}


def main() -> int:
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        print("未設定 NTFY_TOPIC，略過推播。")
        return 0

    state = json.loads((ROOT / "data/state.json").read_text(encoding="utf-8"))
    cur = state["current"]
    names = []
    for tid in cur["active"]:
        path = ROOT / "data/content" / f"{tid}.json"
        if path.exists():
            names.append(json.loads(path.read_text(encoding="utf-8"))["name_zh"])
        else:
            names.append(tid)

    day = cur["day"]
    payload = {
        "topic": topic,
        "title": f"每日三理 · 第 {day} 天｜{DAY_LABELS.get(day, '')}",
        "message": "、".join(names),
        "click": SITE_URL,
        "tags": ["books"],
    }
    resp = requests.post("https://ntfy.sh/", json=payload, timeout=20)
    resp.raise_for_status()
    print("已推播：", payload["title"], payload["message"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
