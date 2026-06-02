# ADR 0009 — 「研」单股深度研究：本地确定性数据接地 + 长上下文流式带引用报告

- **状态：** 已接受
- **日期：** 2026-06-03
- **决策者：** 主人 + Claude

> 主人指令：前面一批前端反馈做完之后，**开始做「研」支柱的设计与实现**。「研」= 三根支柱之二：用 LLM 对单支股票做详尽分析。

## 背景

- 「研」是 Augur 三支柱（看/研/知）之二，此前只有占位页（`<Placeholder pillar="研"/>`）。
- Augur 已沉淀大量**确定性数据**：行情（`market/`）、基本面快照 + 季度财报趋势（`fundamentals.py`）、个股相关新闻（`news/ticker_news.py` + 聚合流，已 cheap-LLM 清洗）、SEC 申报（`edgar.py`）。这些是「研」的天然原料。
- 护栏（§11）：**非投资建议**、**暴露不确定性**、**不编造**、密钥不入库、尊重限流、本地优先。
- 设计阶段跑了一个 4-agent 设计 workflow（thesis-first / fundamentals-first / catalyst-first 三视角各出方案 → 评审合成），产出最终报告骨架与提示词。

## 决策

### 1. 接地范围：先只用「本地已有确定性数据」，暂不引入实时网络

- `research/service.gather(symbol)` 汇集：`search.display_name` + `_price_summary`（OHLCV 1y：最新/近一年涨跌/52 周区间）+ `fundamentals.get_fundamentals`（市值/PE/营收/净利/净利率/EPS）+ `get_financials(quarter, ~6 期)` + `news_service.news_for_symbol(limit=12)`（已清洗）+ `edgar.filings_for(limit=8)`。
- **不**接实时网络搜索 / Deep Research / 分析师一致预期 / 估值模型——**列为下一步增强**（见「后果」）。
- **为什么先这样**：① 确定性数据零幻觉风险、零额外限流压力、即时可用；② 先把「研」端到端跑通（数据→提示词→流式→落库→前端渲染），网络检索是正交增量；③ 隐私/成本可控。代价：报告缺同行对比与前瞻预期——**靠提示词诚实点名这些盲区**，不假装拥有。

### 2. 报告结构（设计 workflow 三视角合成）

顺序 = **先抓结论与催化 → 再用财务质地坐实 → 最后摊开风险**：

1. **一句话结论**（≤60 字，引用块）
2. **核心看点**（3–5 条，📈多/📉空 兼列 + `[n]`/数值）
3. **近期催化与动态**（★ 报告重心：新闻 `[n]` + SEC 申报 `[n]` → 催化剂，逐条「发生了什么 / 为何重要 / 利好利空待观察」）
4. **基本面与估值**（快照解读，相对自身历史、不与同行/预期比、不给目标价）
5. **财务趋势**（季度 ~6 期：增长 / 盈利质量 / 现金流质地，回扣论点；可用表格）
6. **多空逻辑**（Bull/Bear 各 2–3 条因果链，诚实评强弱不注水）
7. **风险与不确定性**（含**明确点出数据盲区**：无实时报价时效、无分析师预期、无同行对比、新闻可能单源滞后）
8. **来源**（正文引用过的 `[n]` 逐条列出）
9. 结尾**单句**非投资建议免责

提示词 `resources/prompts/research_stock.md`（复用 `_load_prompt(name)` → `resources/prompts/{name}.md` 约定，占位符 `{{NAME}}/{{SYMBOL}}/{{MARKET}}/{{DATA}}`）。设计期一度并存 `stock_research.md` / `research_report.md` 两草稿，已删，单一真相落在 `research_stock.md`（代码按此名加载）。

### 3. 防幻觉八铁律 + 引用机制

- 八铁律取三视角并集去重：只用所给材料、**绝不编造数字**（缺则「暂无」、不二次推导新精确数、不用记忆旧数）、**不假装有网络/分析师预期/估值模型/目标价**、单位币种照标、事实 vs 推断对冲、新闻单源标题党对冲、缺数据不留白也不硬凑、不构成投资建议。
- 引用：**结构化数字（基本面/财报/价格）不标号**（非外部来源）；**新闻与 SEC 申报各自带 `[n]`**，正文内联标注，文末「来源」节列出。`gather` 给每条新闻/申报编号并带 `url`，落库 `sources:[{n,title,source,url}]` 供前端把 `[n]` 渲染为**可点跳来源**的上标。

### 4. 角色、流式、持久化

- 走 **deep_research 角色**（主人路由到长上下文模型；现状 relay·claude-sonnet）。`generate` 前 `gateway.check_ready("deep_research")`，未配回 503。
- **SSE 流式**（同步生成器在 threadpool 迭代，与 `/news`、`/llm` 一致）：`POST /research/stock/generate?symbol=` 增量吐 Markdown，完成落库。
- **持久化**：`research_reports(symbol UNIQUE, name, body, sources, model, created_at)`，**一股一份、重生成覆盖**（`ON CONFLICT(symbol) DO UPDATE`）。`GET /research/stock?symbol=`（404=暂无）。一股一份够用（研究是「当前快照」），版本历史列为后续。

### 5. 前端

- 「研」Tab = `features/research/ResearchView.tsx`：消费 `store.selectedSymbol`，未选标的 → 空舞台引导；`useResearchReport(symbol)` 载持久化报告；「生成深度研究 / 重新生成」按钮 SSE 流式（`streamResearch`，AbortController 可中断）。
- **自写轻量 Markdown 渲染器**（不引依赖，复用 `.digest` 排版）：`##` 标题 / `>` 引用块 / `-` 列表 / `|表格|`（财务趋势）/ `**强调**` / 裸 URL→链接 / `[n]`→上标（有源 url 则 `<a>` 可点）。沿用 Anthropic 纸感设计 token。

## 后果

- **正面**：三支柱齐活；端到端零幻觉接地（确定性数据 + 严格提示词）；引用可溯源；报告美观（暖纸感 + 可点引用 + 财务表）；流式即时反馈。真机验证 US:NVDA：128 deltas / 3.1k 字 / 含财务表 + 12 条带 url 引用 + 诚实点出「缺分析师预期/同行对比」。
- **代价 / 待办（下一步增强）**：① 无实时网络/Deep Research → 缺最新盘面外事件与前瞻预期（已靠提示词点名盲区）；② 无同行对比与一致预期；③ 一股一份无版本历史；④ 非美股无 SEC 申报（KR DART / CN cninfo 一手未接，财务/新闻仍覆盖）；⑤ 财报分析面板的 AI 解读待以本编排的多轮带引用形式回归。
- **不跨越的边界**：报告**不给买卖结论、不给评级、不给目标价**（§11.1/§11.3）；只研究、不建议。
