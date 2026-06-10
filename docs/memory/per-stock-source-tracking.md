# 每股专属信源追踪

日期：2026-06-05

作者想要的产品形态：对每只股票自动发现该看的账号/论坛/新闻源，作者确认后持续追踪，并把这些信息并入「看·相关资讯」的 AI 摘要，而不是只看泛新闻。

已实现闭环：

- 「知·个股」的 `StockSourcesPanel` 负责调研/手动添加/启用信源；候选仍默认未启用，避免 LLM 编造句柄或 URL 直接污染信息流。
- `POST /news/directed/refresh?symbol=MARKET:CODE` 现在会同时跑 Yahoo ticker 新闻和 `stock_sources.refresh_many`。
- 启用源抓到的条目写入 `news_items`，新条目使用 `lane='ticker'`，并写 `news_item_symbols(matched_by='stock_source')` 确定性挂回该股。
- `news_for_symbol` 会合并 Yahoo ticker 新闻、持久化挂钩流、聚合流匹配，再交给 `/news/for/brief` 做 AI 筛选/摘要；所以「看·相关资讯」能消费专属源。
- 前端「看·相关资讯」头部显示 `专属 N`（仅启用源大于 0 时）和「刷新」按钮；刷新后失效 `stock-news` / `stock-news-brief` / `news-for` 查询。

当前支持的 `ref`（kind → 抓取通道）：

- `official_x`/`influencer_x`（X）：`@nvidia`、`https://x.com/nvidia` → 先 `twtapi.fetch_accounts`（需 `TWTAPI_KEY` 且额度可用），**twtapi 返回空则自动回退 `tikhub.user_tweets`（TikHub X2 通道）**——「修 X 通道」：twtapi 月额度耗尽时仍出数据（2026-06-10）。
- `xiaohongshu`（**新**）：`ref` 填**关键词**（公司名/产品名，如「比亚迪」），走 `tikhub.search_xiaohongshu`（app_v2/search_notes，近一周、≤12 条）。不收 URL。
- `threads`（**新**）：`ref` 填**关键词**（英文公司名/ticker），走 `tikhub.search_threads`（web/search_top）。不收 URL。
- `reddit`：`r/NVDA_Stock` → public JSON。
- RSS/Atom（official/ir/fin_site/forum 的 URL）：feedparser。

以上 TikHub kind 共用 `TIKHUB_KEY`，无新增 secret；失败/无 key 时 `_fetch_one` 返回 problem（计入 unsupported），不崩溃。实测（2026-06-10）三类各抓 12 条并确定性挂回该股。

明确不支持但不能伪装：

- 普通官网/IR 页面如果不是 RSS/Atom，不会自动抽取页面内容；后续要做 feed 自动发现或网页正文抓取。
- 小红书/Threads 仅**关键词搜索**，**不支持关注特定账号**（TikHub 该平台 user-posts 端点未接入）。雪球已于 2026-06-06 退役。
- X 账号、Reddit 子版、URL 的强验证仍很薄：当前是抓到条目才标 `verified=1`，后续应补独立探活和中文诊断。

实现边界：

- `stock_sources.refresh_symbol` 的窗口默认近 30 天，避免每次抓过多历史。
- 只有作者启用的源会抓取；LLM 调研出的候选不会自动启用。
- 如果 URL 已经存在于全局 feed lane，`INSERT OR IGNORE` 不会改原 `lane`，但会补 `news_item_symbols` 关联，因此仍可出现在该股相关资讯里。
