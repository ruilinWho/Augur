# LLM 结构化 JSON 输出的健壮性（坑）

**症状**：作者把 `summarize` 角色指到 **MiMo（mimo-v2.5-pro，推理模型）**后，「一键生成」
偶发看不到「今日要事 / 今日机会」——DB 里 `news_clusters` 当天 `news:all@1d` 的 `body=[]`（空），
但 `item_count=488`（说明喂进去了、LLM 也调用了，是**解析**出 0）。推特要点（只 15 条输入）却稳定正常。

**根因**：**非确定性 + 大输入**。推理模型在大输入（488 条聚类）下**偶尔**把
`<think>…</think>` 推理块 / 自然语言前言写进 `content`、或产出轻微畸形 JSON。旧
`_parse_json_lenient` 只会「剥围栏 + 贪婪 `\{.*\}`」，遇到前言里的花括号或畸形就回 `{}`。
同一 prompt 重跑一次往往就正常（实测一次 0、一次 46、修后 85）。**不是截断**
（`finish_reason=stop`、JSON 结尾完整）、**不是条数过多本身**、**不是 max_tokens**。

**修复**（`news/service.py`）：
1. `_parse_json_lenient` 健壮化：去 `<think>` 块 → 去代码围栏（可不在串首）→ 直接 `json.loads`
   → **字符串感知的括号配平** `_extract_object`（从首个 `{` 配平到匹配 `}`，容忍前言/尾随杂字、
   且不被字符串内的 `{}` 干扰）→ 贪婪兜底。
2. `_complete_json(prompt, role, want_key, attempts=2)`：解析为空 / 缺 `want_key` 时**重试**
   （每次新采样）。`generate_clusters`(clusters) / `generate_opportunities`(opportunities) /
   `generate_narrative`(timeline) 都改走它。

**教训**：凡是要 LLM 吐 JSON 的地方，别假设干净——尤其推理模型、尤其大输入。健壮解析 + 重试是底线。
（`relevance/translate/stock_tag` 走的是另一套 `_strip_fence`+`json.loads`，目前用 cheap 模型尚稳；
若日后也指到推理模型、同样应加固。）
