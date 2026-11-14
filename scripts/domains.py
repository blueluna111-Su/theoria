"""Single source of truth for theory domain classes (學科類別).

Each class: key -> (short label, archive label, guidance for the replenisher).
Adding a class here also needs a matching `.tag--<key>` colour in assets/styles.css.
Selection rule for every class: 只收『跟日常生活或工作有關、一般人學了用得上』的理論，
不收只在專業領域內部才用得到的艱深理論。
"""
from __future__ import annotations

DOMAINS: dict[str, tuple[str, str, str]] = {
    "econ":       ("經濟", "經濟 · 行為經濟", "金錢、交易、誘因、市場怎麼影響日常選擇"),
    "psych":      ("心理", "心理", "情緒、動機、認知偏誤、自我管理"),
    "social":     ("社會", "社會 · 人類學", "群體、人際網絡、社會規範"),
    "health":     ("健康", "健康", "身體、睡眠、壓力、生活型態"),
    "humanities": ("人文", "人文 · 哲學", "思考框架、倫理、哲學、文化"),
    "learning":   ("學習", "學習 · 教育", "怎麼記得住、學得快、教別人（學習科學）"),
    "comm":       ("溝通", "溝通 · 語言", "對話、說服、語言與表達、人際溝通"),
    "work":       ("職場", "職場 · 管理", "團隊、組織、專案、生產力"),
    "design":     ("設計", "設計 · 人因", "好不好用、防錯、環境與介面怎麼影響行為"),
    "stats":      ("機率", "機率 · 統計思維", "看懂數據、機率直覺、避免統計誤判（不需算式也能用）"),
    "nature":     ("自然", "自然 · 生活科學", "物理、生態、演化等可借來理解日常的科學原理"),
    "civic":      ("公民", "公民 · 法政", "法律、政治、公共決策中與一般人切身相關的原理"),
}

DOMAIN_ORDER = list(DOMAINS)
DOMAIN_SHORT = {k: v[0] for k, v in DOMAINS.items()}
DOMAIN_LABEL = {k: v[1] for k, v in DOMAINS.items()}
DOMAIN_HINT = {k: v[2] for k, v in DOMAINS.items()}
