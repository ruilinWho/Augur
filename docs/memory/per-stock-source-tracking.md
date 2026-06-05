# 每股专属信源追踪

日期：2026-06-05

作者想要的产品形态：对每只股票自动发现该看的账号/论坛/新闻源，作者确认后持续追踪，并把这些信息并入「看·相关资讯」的 AI 摘要，而不是只看泛新闻。

已实现闭环：

- 「知·个股」的 `StockSourcesPanel` 负责调研/手动添加/启用信源；候选仍默认未启用，避免 LLM 编造句柄或 URL 直接污染信息流。
- `POST /news/directed/refresh?symbol=MARKET:CODE` 现在会同时跑 Yahoo ticker 新闻和 `stock_sources.refresh_many`。
- 启用源抓到的条目写入 `news_items`，新条目使用 `lane='ticker'`，并写 `news_item_symbols(matched_by='stock_source')` 确定性挂回该股。
- `news_for_symbol` 会合并 Yahoo ticker 新闻、持久化挂钩流、聚合流匹配，再交给 `/news/for/brief` 做 AI 筛选/摘要；所以「看·相关资讯」能消费专属源。
- 前端「看·相关资讯」头部显示 `专属 N`（仅启用源大于 0 时）和「刷新」按钮；刷新后失效 `stock-news` / `stock-news-brief` / `news-for` 查询。

当前支持的 `ref`：

- X：`@nvidia`、`nvidia`、`https://x.com/nvidia/status/...`、`https://twitter.com/nvidia`，走 `twtapi.fetch_accounts`，需要 `TWTAPI_KEY` 且额度可用。
- Reddit：`r/NVDA_Stock`、`https://www.reddit.com/r/NVDA_Stock/new/`，走 public JSON。
- RSS/Atom：`https://example.com/feed.xml` 或可被 feedparser 解析的 feed URL。

明确不支持但不能伪装：

- 普通官网/IR 页面如果不是 RSS/Atom，不会自动抽取页面内容；后续要做 feed 自动发现或网页正文抓取。
- 雪球/小红书需要登录 Cookie/稳定接口与限流策略，当前只登记配置槽，不抓取。
- X 账号、Reddit 子版、URL 的强验证仍很薄：当前是抓到条目才标 `verified=1`，后续应补独立探活和中文诊断。

实现边界：

- `stock_sources.refresh_symbol` 的窗口默认近 30 天，避免每次抓过多历史。
- 只有作者启用的源会抓取；LLM 调研出的候选不会自动启用。
- 如果 URL 已经存在于全局 feed lane，`INSERT OR IGNORE` 不会改原 `lane`，但会补 `news_item_symbols` 关联，因此仍可出现在该股相关资讯里。
