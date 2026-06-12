# 看·综合认知（个人判断 × 公司披露 × 重大事件 × 事实反馈）

日期：2026-06-12。

作者作为产品经理提出：`看` 页里「自己在特定时间的判断」和「个股重要事件时间线」不应分散，因为后续重大新闻、财报、电话会和涨跌其实是在对当时的个人判断做反馈。产品目标是形成一个认知回路：**我的判断被世界事实印证/证伪，从而帮助个人投资认知进化**。

2026-06-12 追加命名：作者认为「认知时间线」不好，正式 UI 名称改为 **「综合认知」**。后端内部 `reflection` 命名可保留为 API/缓存读模型名，但用户可见文案和文档应使用「综合认知」。

## 当前设计

- K 线下方不再同时出现「相关资讯」和「判断日记」两个模块；`KAN_MODULES = ['financials', 'cognition']`。
- `features/news/StockNews.tsx` 现在渲染 **「综合认知」**：
  - 顶部保留个股近况 brief 与社媒热度，作为当前背景。
  - 主线混排 `journal`（个人判断）、`disclosure`（公司披露）和 `news`（重大事件）。
  - 每条个人判断可嵌入 LLM assessment：`印证 / 证伪 / 混合 / 尚未检验`，并带 `confidence`、确定性价格反馈和可点来源。
  - 写判断、编辑、删除仍在同一模块内完成；判断变更会失效综合认知缓存并重生成。
- 后端新增读模型缓存 `stock_reflection_timelines`，通过：
  - `GET /journal/reflection?symbol=MARKET:CODE`
  - `POST /journal/reflection/generate?symbol=MARKET:CODE`
- 生成逻辑在 `journal/service.py`：
  - journal_entries 是作者判断源。
  - 重大事件复用既有 `/news/narrative`（无则尝试生成），避免另造资讯摄取。
  - 公司披露来自 `news.service.stock_disclosures()`：SEC EDGAR filing、financials period 兜底、可选 FMP 电话会 transcript。
  - 价格反馈由后端确定性计算：判断日附近收盘 → 最新收盘，不交给 LLM 编。
  - LLM prompt 在 `resources/prompts/stock_reflection_timeline.md`，硬约束只用给定判断、事件、披露、价格反馈，不能引入外部事实；判断前材料不能当作后续反馈。新闻与披露冲突时以披露优先。

## 呈现细化（2026-06-12）

作者反馈两点，改在 `features/news/StockNews.tsx` + `index.css`：

- **重大事件的来源默认折叠。** 事件标题已由 LLM 归纳好，再平铺一串细粒度来源（The Verge / TheStreet…）是噪音。非判断事件的 `refs` 收进内联 `EventRefs`：默认只显示「N 条来源」可点行（`.cog-src-toggle`），点开才用 `Collapse` 展开列表，沿用项目「无折叠三角」惯例。判断（journal）事件不受影响。
- **总览 / 近况 / 社媒热度三块上下全宽堆叠，各带标题。** `cog-context` 用 `flex-direction:column`，依次 `cog-overview`（总览，`reflection.summary`，accent 左边框强调）→ `cog-now`（近况）→ `cog-social`（社媒），每块 `cog-card-head` 一个小标题——作者反馈「看不出每块是什么」，尤其总览那块被它的 accent 左边框 + 衬线误当成「引用块」，加「总览」标题才清楚。
  - **为什么不并排两栏**：近况内容多、社媒内容少，并排无论等高（撑空）还是顶对齐（一高一矮留白）都不协调；上下全宽既消除高度差、又让长文铺满（契合作者全宽偏好）。中途试过 `1fr 1fr` 等宽（修掉了更早的 `3fr/2fr`+`stretch`+`min-height` 左空右挤），但高度差仍在，最终改上下堆叠。
  - **坑**：固定块数的区域别用 `repeat(auto-fit, minmax(300px,1fr))`——auto-fit 按容器宽算列数（实测 1052px→塞 3 列），多出的空列留白、且全宽块与之不对齐。

## 公司披露层（2026-06-12）

- 新后端接口：`GET /news/disclosures?symbol=MARKET:CODE`。
- `news.service.stock_disclosures()` 统一输出 disclosure events：
  - `filing`：SEC EDGAR 高信号申报（10-Q/10-K/8-K 等）。
  - `financial_period`：yfinance financials 期末日兜底（非正式披露日）。
  - `transcript`：FMP 电话会 transcript（需要 `FMP_API_KEY`，没有 key 时为空）。
- 披露事件同时喂：
  - `stock_news_brief()` 个股近况摘要；
  - `generate_narrative()` 个股重大事件；
  - `generate_reflection_timeline()` 综合认知判断反馈；
  - `KLineView.tsx` marker。
- 设置页新增「FMP 电话会」源，`FMP_API_KEY` 进入 `source_registry.live_secret_names()`，因此会随「配置分享」导入/导出同步。

## K 线 Marker

- 三类事件 marker（个人判断 `判`、财报/申报 `财`、电话会 `会`）**统一钉在价格轴底部一条事件带上**：用 lightweight-charts v5 的 price-based marker（`position:'atPriceBottom'` + `price=区间最低价`），横向对齐成一条带、不再遮挡蜡烛实体；`createSeriesMarkers` 的 `autoScale`（默认 true）会自动下扩价格轴给这条带留空间。形状统一 `circle` 小圆点 + 单字，语义靠色分：`判`=陶土 accent（主观判断），`财`/`会`=墨灰 disclosure（客观披露）。
- 数据来源不变：`判` 来自 `journal_entries.entry_date`；`财` 优先 `/news/disclosures` 的真实 SEC filing date，无披露事件时退回 financials period 期末日；`会` 来自 FMP transcript date。
- **相近事件合并**（`dedupeNear`，`KLineView.tsx`）：同一财报周期常有多份相邻申报（10-Q + earnings 8-K 等），吸附到相邻交易日会挤成一团、前后两天分不清；按交易日索引，间隔不足 `MIN_GAP`(8) 的只留最早一个。判断（`判`）不合并。
- **旧形态**（已废弃）：财/会用 `aboveBar` square 标在蜡烛上方、判用 `belowBar`——作者反馈遮挡蜡烛、不美观、且相近财报重叠。
- **重要限制**：`financial_period` 仍只是期末日兜底，不是正式披露日；任何真实 filing/transcript date 都应优先于它。

## 不变量

- 不要把「判断日记」「公司披露」「重大事件」重新拆成多个并列模块；它们的产品价值在同一个「综合认知」里的因果反馈。
- LLM 评价必须可追溯：输出要带 evidence refs，前端展示可点来源。
- LLM 不负责计算涨跌；涨跌由行情数据确定性计算后喂给模型。
- 公司披露是事实优先级高于普通新闻的材料；不要把它降级成社媒/新闻弱信号。
