# 分区级日报（自选分区情报）

日期：2026-06-12

「资讯·板块」新增**「分区」lane**（`InfoSection='sectors'`，与「总结」同属 `digest` 导航组、紧邻其后）。这是[综合日报](integrated-daily-report.md)的 **portfolio 轴姊妹**：

- **综合日报（总结）** 按**主题**组织全球新闻（AI/芯片/宏观…）——世界今天发生了什么。
- **分区日报（分区）** 按作者**一级自选分区**组织、**逐股**呈现——「我的半导体板块今天发生了什么」。

两者互补、共存，都按日历日切片、都由「刷新并生成」一键驱动。分区日报的价值是 **portfolio-aware + 逐股 actionable**：每只异动票直接给「看 K 线 / 研 深度研究」入口，正是作者想要的「个股挂钩按钮」。

## 数据流（后端 `news/service.py`）

- **scope 靠挂钩，不靠重标**：复用 `news_item_symbols`（确定性 linker `term` ∪ 定向 `targeted` ∪ LLM 标股 `llm`）。`_day_items_by_symbol(symbols, day)` 一次 `IN` 查询批量取当天挂到各持有票的新闻，按 symbol 分桶、每桶封顶 `_SECTION_PER_STOCK_CAP=22`。日界用 `COALESCE(published_at, fetched_at)`（与 `items_for_day` 同口径）。**零新增标股成本**——吃 refresh 阶段已落库的挂钩。
- **每个一级分区一次结构化 LLM 调用、分区间并行**（`ThreadPoolExecutor`，`_SECTION_WORKERS=6`；嵌套在 `generate_all` 的并行池内，纯 I/O 线程安全）。作者「宁愿多次调用 LLM」。
- `_section_stocks(node)`：一级分区 → `[(symbol, 展示名, 二级板块名)]`，**直属 + 所有子板块、按 symbol 去重**（与自选面板「全部」聚合同口径；depth≤2，二级板块名作每股 `sub` 标签）。
- `_section_digest_block`：逐股分组、带全局 `[n]` 编号；**同一条新闻挂到分区内多只票时共用同一 `[n]`**（按 news id 去重编号），分别列在各自票下。
- prompt `resources/prompts/section_digest.md` → `{pulse, movers:[{symbol, importance, headline, points:[refs]}]}`。
- `_assemble_section_report`：**`mover.symbol` 必为喂进去的本分区票**（不在集合里直接丢弃——零编造，比全局日报的公司名 grounding 更强，因为候选集是确定的）；`importance` 校验进 `_IMP_ORDER`、按之排序；`points` 经 `_cited_points` 映射回原始链接；**`quiet` 确定性算出**（= 本分区里没成为 mover 的票，含「有新闻但 LLM 判不重要」与「当天无新闻」两种），**不信 LLM 的 quiet 输出**；聚合 `importance` = 最热 mover。movers 封顶 `_SECTION_MOVERS_CAP=12`，超出进 quiet。
- 落 **`news_section_reports(report_date, section_id, section_name, sort_order, body, model, item_count, PK(report_date,section_id))`**，`body` 存 `{pulse,importance,movers,quiet}` JSON。**整日 DELETE+insert**（像 `_save_opportunities`）——已删/改名的分区不留陈旧行。无自选 → 清空当天。
- `get_section_reports(day)` 读全部行、按 **有动静→重要性→分区 sort_order** 排序。`generate_*` 都返回 `get_section_reports(rd)`（与 `generate_report` 同模式）。
- **接进 `generate_all` 的并行 `tasks`**（`section_reports`）→ 晨间 07:30 / 归档 23:30 / 白天每小时自动保温，晨读即就绪。

## 前端

- `SectionDigest.tsx`：`SectionReportsView`（头：标题「今天/日期 · 分区」+「刷新并生成分区日报」；今天先 `refresh ∥ refreshDirected` 再 `genSections`，历史日只生成）+ `BoardCard`（分区名**加粗下划线**、`N 异动`、板块脉搏、movers、`其余安静` 页脚）+ `Mover`（重要性徽章 · 名字→`select` 看 · `市场badge` · `sub` 二级板块 · **当日涨跌 chip（仅今天，`useQuote(isToday?sym:null)`，`var(--up/--down)`）** · 研→`research` · headline · `CitedList`）。
- 全部安静的分区收进底部 `今日安静` 页脚；全分区皆安静 → 空态「今天自选分区暂无明显动静」。空态只标状态、无教学句。
- API：`useSectionReports(date)`（GET 恒 200，`boards` 空＝未生成，无 404 兜底）+ `useGenerateSectionReports()`（POST，阻塞）。zod schema 与 `schemas.py` 三处同步（service dict → Pydantic → zod，否则 FastAPI `response_model` 静默剥字段）。
- `consts.ts` `INFO_SECTIONS` 加 `{id:'sectors',label:'分区',group:'digest'}`；`store.ts` `InfoSection` 加 `'sectors'`；`KnowView.InfoView` 路由 `infoSection==='sectors'`。

## 未来改动注意

- **scope 永远走 `news_item_symbols`**——新增信源 lane 时，只要它会被 linker/stock_tag 挂钩，就自动进分区日报，无需改这里。
- 想加深某分区 → 多调 LLM（作者「宁愿多次调用」），别把更多内容塞进单次 prompt。可考虑：分区内再按二级板块分组渲染、机会/反证按分区切片、分区级「自上次以来」。
- **当日涨跌 chip 只在今天显示**（报价只反映「现在」，挂到历史日会误导）；历史日 `useQuote` 传 `null` 禁用。
- 分区日报与综合日报**刻意分开两个 lane**，不要合并回一坨——主题轴与 portfolio 轴是两种心智模型。
- 单元测试守 `_section_digest_block`（共享新闻去重编号）与 `_assemble_section_report`（编造 symbol 丢弃 + 重要性排序 + quiet 计算）两个纯函数不变量（`tests/test_pure.py`）。
