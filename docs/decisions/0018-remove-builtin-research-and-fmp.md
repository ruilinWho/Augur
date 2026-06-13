# ADR-0018 — 移除自建深度研究生成 + 移除 FMP 电话会源

日期：2026-06-13 · 状态：已采纳

## 背景

两件事，同一天由作者决定：

1. **「研」不再自建深度研究生成。** ADR-0009 给「研」做了 `research.gather(symbol)`（收集行情/基本面/财务/已清洗新闻/SEC 申报）→ `deep_research` 角色流式生成带引用 Markdown 的自建研究。但产品方向已转向**外部网页 Deep Research**（ChatGPT/Claude/Gemini 订阅版，能力更强、无 API 成本）：ADR-0014（Prompt 模板）、ADR-0016（网页回流）、ADR-0017（Skills）都在服务「复制 Prompt → 外部跑 → 导入回流」这条链。自建生成沦为低质冗余入口，作者要求整条移除（含存量已生成报告的展示）。

2. **FMP 电话会源不可用。** 公司披露层（见 [company-disclosure-layer](../memory/company-disclosure-layer.md)）接了 FMP earnings-call transcript 作可选源。实测作者的 FMP key：`quote` 等免费 endpoint 正常，但 `earning-call-transcript` / `-dates` 返回 `Restricted Endpoint: not available under your current subscription`——transcript 是**付费档**接口，免费 key 拿不到；且 FMP 适配只支持美股。`fmp.py` 失败静默返回空，表现为「填了 key 但综合认知里什么都没有」。作者要求移除该源。

## 决策

1. **删除自建研究生成全链：**
   - 后端：`research/service.py` 只保留导入研报 CRUD（删 `gather`/`generate_stream`/`_format_data`/`_price_summary`/`get_report`/`_save` 等）；`research/router.py` 删 `GET /research/stock` + `POST /research/stock/generate`，只留 `/research/imported*`；删 `research/schemas.py`、`resources/prompts/research_stock.md`、`db.py` 的 `research_reports` 表定义。
   - 前端：`ResearchView.tsx` 重写为「复制 Prompt + 导入研报」；`api.ts` 删 `useResearchReport`/`streamResearch`/report schema；「知」「寻」里 `research(symbol)` 按钮**仍是跳转研页**（`store.research` = 切 yan 视图），仅改 title 文案。
   - **`deep_research` LLM 角色保留**——`news/stock_sources.discover`（信源调研）、grounding 等仍用，不是研页专属，删它会误伤。
   - 存量已生成报告：连展示一并移除（作者选「一并移除」）；`research_reports` 表残留数据无害（不再读、不再写）。

2. **移除 FMP 电话会源：** 删 `news/fmp.py`；`source_registry` 去 `fmp_transcripts` 注册；`news/service.stock_disclosures` 去 transcript 抓取段、`configured` 去 `fmp`；`source_test` 去分支；`settings_router` 去 `fmp.clear_cache`。`FMP_API_KEY` 退出 `live_secret_names()` → 启动 `prune_secrets` 自动从 `config.local.json` 清掉作者残留 key。**`DisclosureEvent.kind="transcript"` 抽象与 K 线「会」marker 逻辑保留**，待接非付费/非美股 transcript 源（港股 HKEXnews、A 股巨潮等）。

## 后果

- 「研」彻底成为外部研究的**汇集面**：复制 Prompt（模板 + Skills）出去、导入回流进来。与 ADR-0011（官方 Deep Research job 化）不冲突——job 化落地后是**新**的生成路径，不恢复旧的 local-gather。roadmap「Official Deep Research jobs」条目已去掉「local-gather fallback」。
- 「会」marker 当前永远不出现（无 transcript 源），属预期；接新源即恢复。
- 无数据库迁移负担：`research_reports` 表留着不动（gitignored `data/`），新库不再建。
- 验证（TestClient）：`POST /research/stock/generate`→404、`GET /research/imported`→200、披露层 events 无 transcript、`fmp_transcripts` 不在注册表、`FMP_API_KEY` 不在 `live_secret_names()`。
