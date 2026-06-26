# 每日三理 · Theoria

每天三個**可應用**的學術理論（人文／社會／經濟／心理／健康…），**同一組講三天、由淺入深**，再加一張**回想卡**複習更早學過的。獨立於 Horizon 的新專案，靜態站架在 GitHub Pages。

**Live：** https://blueluna111-su.github.io/theoria/

## 設計（兩條軸）

1. **深度弧（learning）**：同 3 個理論連續 3 天，每天都深、層層加碼——
   - 第 1 天「入門全貌」：一篇**完整、夠深**的文章（概念＋機制＋應用快覽＋侷限），自成一體。
   - 第 2 天「進階與爭論」：更深的機制、子效應家族、**學界爭議與反例**、跨理論連結。
   - 第 3 天「實戰與內化」＝**收成日**，最厚最廣，固定六塊：① 跨領域應用地圖 ② 核心方法 ③ 組合拳 ④ 反模式 ⑤ 收成清單 SOP ⑥ 本週實作（觀察→介入→建立習慣）。
   - **每一分段都配 1～3 個具體例子**；文風要詳細完整、把話講透，不寫電報體。
   - 準確性停在概念層級，不杜撰具體研究數字。繁體中文（台灣）。
2. **間隔複習（memory）**：每天的回想卡用主動回想（先問後答）叫回**更早**做完的理論，間隔遞增（預設 +7／+21／+60 天，每天 2 張）。

## 自動產出引擎（每天自己跑）

```
data/pool.json          母池：精選理論清單（可自由增補）
data/state.json         帳本：目前這輪是哪3個、第幾天、已完成+複習到期
data/content/<id>.json  每個理論的三天弧結構化內容（生成後快取、會 commit）
scripts/gemini.py       Gemini REST 客戶端（只依賴 requests）
scripts/generate.py     一個理論 → Gemini → 結構化 JSON（規格全寫在 SYSTEM/STRUCTURE）
scripts/schedule.py     推進 day1→2→3、完成排入複習、挑當日到期卡
scripts/render.py       state + content →（Jinja 樣板）→ index.html / archive.html
scripts/run_daily.py    每日總指揮：排程 → 補生成 → 渲染 → 存檔
templates/*.j2          今日頁／歷史頁樣板
.github/workflows/daily.yml   每日 cron（05:30 台北）+ 手動觸發
```

**流程**：Action 每天跑 `run_daily.py` → 排程器推進帳本 → 對缺內容的理論呼叫 Gemini → 渲染 HTML → commit 回 `main` → Pages 自動重建。

## 本地操作

```bash
pip install -r requirements.txt

# 不需 API key，用佔位內容驗證排程/版型：
THEORIA_MOCK=1 python scripts/run_daily.py --date 2026-06-26
# （測完還原：git checkout -- index.html archive.html；並把 data/state.json 重置、刪 data/content）

# 真正生成（需 GOOGLE_API_KEY）：
GOOGLE_API_KEY=xxx python scripts/run_daily.py
GOOGLE_API_KEY=xxx python scripts/generate.py loss-aversion --force   # 只重生某一篇
```

旗標：`--date YYYY-MM-DD` 指定日期、`--force` 同日重跑、`--no-generate` 只渲染不呼叫 AI。

## 上線需要的唯一手動步驟：設定 Gemini 金鑰

Action 跑真內容需要 `GOOGLE_API_KEY`（你 Horizon 用的那把免費 AI Studio 金鑰）。在 theoria repo 設一次即可：

```bash
gh secret set GOOGLE_API_KEY -R blueluna111-Su/theoria        # 貼上金鑰
gh workflow run "每日三理 daily build" -R blueluna111-Su/theoria   # 手動觸發第一次
```

之後每天清晨自動跑。GitHub cron 為盡力而為、可能延遲；若要保證準時，可外掛 cron-job.com 打 workflow_dispatch API（同 Horizon 的做法）。

## 調整點

- 母池增補：直接編 `data/pool.json`（三個一組、跨領域排列，讓每輪有變化）。
- 複習節奏：`data/state.json` 的 `review_intervals_days`、`review_cards_per_day`。
- 一輪幾個主題：`theories_per_cycle`（目前 3）。
- 生成文風／結構：`scripts/generate.py` 的 `SYSTEM` 與 `STRUCTURE`。
- 語言：目前純繁中；雙語可再加。
