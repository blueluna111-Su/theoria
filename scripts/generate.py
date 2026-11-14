"""Generate one theory's full 3-day arc as structured JSON, per the locked spec.

Usage:
  python scripts/generate.py <theory_id>          # real, needs GOOGLE_API_KEY
  THEORIA_MOCK=1 python scripts/generate.py <id>  # offline placeholder (for layout tests)

Output: data/content/<id>.json
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "data" / "pool.json"
CONTENT_DIR = ROOT / "data" / "content"

# ---------------------------------------------------------------- spec / prompt

SYSTEM = """你是「每日三理」的學術內容作者。你為一般成年讀者撰寫『可應用』的學術理論深度介紹，用繁體中文（台灣用語）。

寫作鐵則（務必全部遵守）：
1. 文風要詳細、完整、清楚，把每一句話講透——用完整解釋的段落，不要寫成一句一個重點的精簡筆記或電報體。每個概念都要說明「是什麼、為什麼、所以呢」，讓讀者不必自行補完。
2. 每一個分段都要附 1～3 個具體、生活化的例子（examples）。例子是核心學習因子，不是裝飾。
3. 準確性：停在概念層級。不要杜撰、不要捏造具體的研究數字、樣本數或精確統計；對有爭議或被誇大的說法，要誠實標明它有爭議。寧可說「大約/有研究指出」也不要編造精確數據。
4. 重視『可應用』：讀者要能把理論用在生活與工作上。
5. 只輸出一個 JSON 物件，不要加任何說明文字或 markdown 圍欄。"""

# 三天弧 + 第三天六塊 + 複習卡的 JSON 結構（模型要照填）
STRUCTURE = """請輸出以下結構的 JSON（值都用繁體中文；examples 是字串陣列）：

{
  "day1": {   // 第1天「入門全貌」：一篇完整、夠深、自成一體的文章（概念+機制+應用快覽+侷限）
    "segments": [   // 4～6 段；每段一個小主題
      { "lead": "該段開頭的一句重點（會以粗體呈現）", "body": "把這個重點完整講透的說明（2～4 句）", "examples": ["例子1", "例子2"] }
    ],
    "mnemonic": "一句話記憶點"
  },
  "day2": {   // 第2天「進階與爭論」：更深的機制、子概念/效應家族、學界爭議與反例、跨理論連結
    "segments": [   // 4～6 段；其中至少一段談「學界爭議或侷限」
      { "lead": "...", "body": "...", "examples": ["..."],
        "bullets": [ { "text": "條列項說明（可省略此欄）", "example": "該項的例子" } ] }
    ],
    "mnemonic": "進階記憶點"
  },
  "day3": {   // 第3天「實戰與內化」＝收成日，最厚最廣，固定六塊：
    "intro": "一句開場，說明今天要把理解變成可用工具",
    "app_map": [   // ①跨領域應用地圖：4～6 個不同生活/工作領域
      { "domain": "領域(如 理財投資)", "body": "在這個領域怎麼用/怎麼防", "example": "例子" }
    ],
    "method": {    // ②核心方法：被它影響時怎麼解 / 或怎麼主動運用（依理論而定）
      "heading": "這塊的小標題(如 自我防身：三個解法)",
      "items": [ { "title": "方法名", "body": "完整說明", "example": "例子" } ]   // 3～4 個
    },
    "combos": [    // ③組合拳：和其他理論一起用
      { "with": "另一個理論名", "body": "兩者怎麼搭", "example": "例子" }   // 2～3 個
    ],
    "antipatterns": [   // ④反模式：常見錯用
      { "body": "別這樣用的說明", "example": "例子(可為 null)" }   // 3 個
    ],
    "checklist": {  // ⑤收成清單 SOP
      "title": "清單標題(如 面對X時跑這張SOP)",
      "items": ["可勾選的自問句1", "...", "..."]   // 5 個
    },
    "practice": {   // ⑥本週實作：三級進階
      "observe": "觀察級任務", "intervene": "介入級任務", "habit": "建立習慣級任務"
    },
    "mnemonic": "內化記憶點"
  },
  "review": {   // 供未來『回想卡』複習用（主動回想：先問後答）
    "question": "一句能勾起回想的問題",
    "answer": "完整、清楚的答案（2～4 句）",
    "answer_example": "一個例子",
    "mnemonic": "一句話記憶點"
  }
}"""


# 機率統計類：讀者已有基礎、要的是「進階理解＋能自己在日常算」，所以加一份專屬規格。
STATS_ADDENDUM = """
【本篇屬於「機率 · 統計思維」，請在上述結構之上額外遵守】
A. 程度：讀者已學過基礎（均值回歸、基本率、倖存者偏差、辛普森悖論、相關≠因果），
   不要花篇幅重講入門，直接從中階切入；但每個術語第一次出現仍要用白話解釋，不堆公式。
B. 算給你看：day1 與 day2 的每一段，至少一個 examples 要是「帶具體數字、一步步算出結論」的算例
   （例如用 1000 人的自然頻率表、簡單的期望值、機率樹）。數字一律標明是『假設數字』示範用，
   不可冒充真實研究數據。算式只用加減乘除與比例，心算或手機計算機就能跟著算。
C. 直覺工具：day2 至少一段專講「不用公式的心算捷徑或直覺檢查法」，讓讀者在現場就能估。
D. 練習題（主動回想，會以『先想再看解答』呈現）：
   - 在 day2 物件中加入 "drills"：2 題，偏觀念與小算例。
   - 在 day3 物件中加入 "drills"：3 題，取材自真實生活情境（理財、健康新聞、工作數據、購物、人際判斷），
     難度遞增，至少一題需要讀者自己動手算。
   每題格式：{ "question": "題目（情境完整、數字給足）", "hint": "一句提示（可為 null）",
              "answer": "完整解答：列出計算步驟與結論，再用一句話點出這題的日常啟示" }
E. day3 的 method 要寫成「一步步的操作流程」（第一步先問什麼、第二步怎麼估、第三步怎麼決定），
   practice 三級任務要包含『拿自己生活中的真實數字算一次』。
"""

DOMAIN_ADDENDUM = {"stats": STATS_ADDENDUM}


def build_prompt(meta: dict) -> str:
    hint = f"（重點方向：{meta['note']}）" if meta.get("note") else ""
    author = meta.get("author") or "（請勿杜撰，不確定就不寫作者）"
    year = meta.get("year") or "（不確定就略過年份）"
    return (
        f"理論：{meta['name_zh']}（{meta.get('name_en','')}）\n"
        f"領域：{meta['domain']}\n"
        f"提出者：{author}　年份：{year}\n"
        f"{hint}\n\n"
        f"{STRUCTURE}"
        f"{DOMAIN_ADDENDUM.get(meta.get('domain_class'), '')}"
    )


# ---------------------------------------------------------------- generation

def generate(meta: dict, api_key: str | None = None) -> dict:
    from gemini import generate_json  # local import so mock path needs no requests

    content = generate_json(SYSTEM, build_prompt(meta), api_key=api_key, temperature=0.5)
    return _wrap(meta, content)


def mock_content(meta: dict) -> dict:
    """Schema-valid placeholder so render/layout can be tested without an API key."""
    n = meta["name_zh"]
    seg = lambda i: {
        "lead": f"關於「{n}」的第 {i} 個重點（這是離線示意內容）。",
        "body": f"這裡會是把「{n}」的這個重點完整講透的詳細說明，由 AI 依規格生成。目前是 mock 佔位文字，用來驗證版型與流程是否正確。",
        "examples": [f"「{n}」的生活化例子 A。", f"「{n}」的生活化例子 B。"],
    }
    drill = lambda i: {"question": f"「{n}」練習題 {i}（示意）：情境與數字。",
                       "hint": "一句提示（示意）" if i % 2 else None,
                       "answer": f"練習題 {i} 的解答步驟與日常啟示（示意）。"}
    extra2 = {"drills": [drill(1), drill(2)]} if meta.get("domain_class") == "stats" else {}
    extra3 = {"drills": [drill(1), drill(2), drill(3)]} if meta.get("domain_class") == "stats" else {}
    return _wrap(meta, {
        "day1": {"segments": [seg(1), seg(2), seg(3)], "mnemonic": f"{n}：一句話記憶點（示意）。"},
        "day2": {"segments": [seg(1), {**seg(2), "bullets": [
            {"text": f"{n} 的子概念一", "example": "子概念一的例子"},
            {"text": f"{n} 的子概念二", "example": "子概念二的例子"}]}, seg(3)],
            "mnemonic": f"{n}：進階記憶點（示意）。", **extra2},
        "day3": {
            "intro": f"把「{n}」變成拿得出手的工具（示意）。",
            "app_map": [{"domain": d, "body": f"在{d}怎麼用{n}", "example": f"{d}的例子"}
                        for d in ["理財投資", "職涯工作", "人際關係", "健康習慣"]],
            "method": {"heading": "核心方法（示意）", "items": [
                {"title": f"方法{i}", "body": f"{n} 方法{i} 的完整說明（示意）。", "example": f"方法{i}的例子"}
                for i in (1, 2, 3)]},
            "combos": [{"with": "另一理論", "body": "兩者怎麼搭（示意）", "example": "組合的例子"}],
            "antipatterns": [{"body": f"別這樣用 {n}（示意 {i}）", "example": None} for i in (1, 2, 3)],
            "checklist": {"title": f"面對與「{n}」有關的決定時（示意）",
                          "items": [f"自問句 {i}（示意）" for i in range(1, 6)]},
            "practice": {"observe": "觀察級任務（示意）", "intervene": "介入級任務（示意）",
                         "habit": "建立習慣級任務（示意）"},
            "mnemonic": f"{n}：內化記憶點（示意）。", **extra3,
        },
        "review": {"question": f"還記得「{n}」嗎？它的核心是什麼？",
                   "answer": f"「{n}」的完整答案（示意）。", "answer_example": "答案的例子（示意）。",
                   "mnemonic": f"{n}：一句話記憶點（示意）。"},
    })


def _wrap(meta: dict, content: dict) -> dict:
    """Attach metadata to generated content."""
    return {
        "id": meta["id"],
        "name_zh": meta["name_zh"], "name_en": meta.get("name_en", ""),
        "domain": meta["domain"], "domain_class": meta["domain_class"],
        "author": meta.get("author"), "year": meta.get("year"),
        **content,
    }


def load_pool() -> dict[str, dict]:
    data = json.loads(POOL.read_text(encoding="utf-8"))
    return {t["id"]: t for t in data["theories"]}


def ensure_content(theory_id: str, *, force: bool = False) -> Path:
    """Generate content/<id>.json if missing (or forced). Returns the path."""
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    out = CONTENT_DIR / f"{theory_id}.json"
    if out.exists() and not force:
        return out
    meta = load_pool()[theory_id]
    if os.environ.get("THEORIA_MOCK") == "1":
        content = mock_content(meta)
    else:
        content = generate(meta)
    out.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  + wrote {out.relative_to(ROOT)}")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python scripts/generate.py <theory_id> [--force]")
    ensure_content(sys.argv[1], force="--force" in sys.argv)
