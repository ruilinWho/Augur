# 综合日报是一体化入口

日期：2026-06-11

作者明确要求：「知 → 资讯」里的日报必须在单张卡片中整合所有信息，包括新闻、博客、推特、小红书、Threads、Reddit 等所有来源。即使日报很长也没关系，核心目标是整体性：从一篇日报中看到当天全局、机会、风险、反证和后续动作。

**后续（2026-06-11 同日修订）**：「决策」tab 已删除、并入「总结」——两页内容此前已退化成同一张日报，重复。但作者要求把原「决策」里**关联标的的可点引导**找回来：综合日报正文只能"叙述"机会，给不了每只票「看 K 线 / 研 深度研究」的可点入口，所以「总结」页 = **综合日报卡 ＋ 下方「今日机会」卡**（`OpportunitiesPanel`，每条机会列关联标的 chip：名字→看、研→深研）。这是对"不再铺分散模块"的**有意例外**：机会卡是 actionable 引导、不是信息补丁；社媒仍只进日报正文、不另起卡。

**再后续（2026-06-12 结构化重设计）**：作者反馈 markdown 长文「太长、根本无法专注读」。日报改为**结构化卡片**——"整体性"目标不变，但靠**分层 + 分点 + 卡片**实现，不再是一坨长文：
- `service.generate_report()`（取代 `generate_report_stream`）一次结构化 LLM 调用 → `{verdict 总判断, sections[], risks[], watch[]}`，再**确定性接地**公司名→MARKET:CODE（复用 `grounding.resolve_company` + 交叉自选，与 `generate_opportunities` 同口径），落库 `news_reports.body` 存结构化 JSON。
- section = `{headline（小标题）, importance（critical/high/med/low＝非常重要/重要/留意/次要）, why, points[CitedPoint], related[RelatedSymbol]}`。
- 前端 `DigestReport.tsx` 渲染：总判断卡 + 主题卡（重要性徽章 · **加粗下划线小标题**[作者明确要求双重强调] · 分点 `CitedList` · 关联标的「看/研」`RelatedChip`）+ 风险卡 + 明天卡。
- `RelatedChip`/`CitedText`/`CitedList` 抽到 `shared.tsx`，日报/机会/个股资讯共用（单一真相）。
- 生成从 SSE 流式改为**阻塞** `POST /news/report/generate`（返回结构化报告，~20–40s；结构化 JSON 无法有意义地流式）。作者明示「宁愿多次调用 LLM」——目前一次结构化调用 + 接地够用；若某段深度不足，可拆成 outline + 每段并行细化（已有并行基建）。

**同日（2026-06-12）：分区级日报**——新增「资讯·板块」的「分区」lane（紧邻「总结」），是综合日报的 **portfolio 轴姊妹**：综合日报按**主题**组织全球新闻，分区日报按作者**一级自选分区**组织、逐股呈现「我的盘子今天发生了什么」。复用同一套结构化机器（`_cited_points`/`_complete_json`/grounding 思路），但 scope 靠 `news_item_symbols` 挂钩、每个一级分区一次并行 LLM 调用、`mover.symbol` 确定性校验（必为本分区票）。落 `news_section_reports`、并入 `generate_all`。详见 [section-level-daily-report](section-level-daily-report.md)。

实现边界：

- `service.generate_report()` 使用 `digest_items_for_day()`，它合并：
  - 普通新闻/RSS/博客：沿用 `relevance != 2` 过滤；
  - 社媒 lane：`X·`、`小红书·`、`Threads·`、`Reddit·`，沿用各自 lane 规则（不套新闻 relevance、按 `fetched_at` 归桶）。
- 普通「新闻」板块仍用原来的 `items_for_day()`，继续排除社媒，避免新闻时间线被社媒噪音污染。只有综合日报显式合并所有来源。
- 日报 prompt（`resources/prompts/news_digest.md`）是**结构化 JSON 口径**：产出 verdict + sections（headline/importance/why/points[refs]/companies）+ risks + watch；社媒只能作为弱信号/情绪/讨论热度，不可当成事实定论。
- 前端「总结」页（`DaySummaryView`）= `DigestBlock`（结构化日报卡，`DigestReport.tsx`）＋ `OpportunitiesPanel` 今日机会卡（`showGenerate=false`，由顶部「刷新并生成」按钮并行驱动两者）。除机会卡外不再铺要事/社媒脉搏等分散模块。单独的新闻/博客/社媒板块保留给追溯原始信息流和手动生成 lane 要点。
- 研报/笔记正文走 `components/Markdown.tsx`（零依赖、单一真相），支持 #–#### 标题 / 有序无序列表 / 表格 / 斜体 / 代码 / `[n]` 引用上标；日报结构化后正文不再走它，仅旧 markdown 报告经 `get_report` 进 `markdown` 字段时前端回退 `<Markdown>` 渲染。
- 「自上次以来」不是独立卡片，放在「总结」标题行同一高度，作为低噪音计数 chip。计数由 `GET /news/read-state` 返回，按 `news_items.fetched_at > prefs.news_read_at` 统计所有 lane；`service.refresh()` 和 `refresh_directed()` 成功完成后自动推进 `news_read_at`，所以手动刷新、一键刷新并生成、APScheduler 自动刷新都会自动“标记已读”，前端不再提供手动按钮。

未来改动注意：

- 不要把社媒继续作为「总结」的独立小卡补丁；应该进入综合日报输入和正文。（「今日机会」卡是例外——它是关联标的的可点 actionable 引导，不是信息补丁。）
- 如果新增信源 lane，判断它是否应该进入 `digest_items_for_day()`。原则上「总结」的日报要吃所有来源。
- 日报现在**就是**卡片化结构（总判断/主题/风险/明天），不要倒退回 markdown 长文；要更深就加 LLM 调用（作者「宁愿多次调用」），别把内容塞进更长的 prose。
- 不要把「自上次以来」重新放成日报上方的独立模块；它只是标题行的新鲜度提示，刷新任务自动推进已读基准。
