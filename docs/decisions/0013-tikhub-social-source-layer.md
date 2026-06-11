# ADR-0013 — TikHub 社交/论坛信源层

日期：2026-06-06

> **后续变更（2026-06-11）**：本 ADR 列的 `tikhub_wechat`（微信公众文章）**已删除**（`wechat_mp/web/*` 整组服务端长期 400）；**Reddit 不再是「public JSON + TikHub 双通道」——直连被 IP 封、`reddit.py` 已删，全走 TikHub**（关键词搜 + 子版 feed `fetch_subreddit_feed`）；TikHub 同时成为**唯一**推特源（twtapi 退役为每股专属）。下文按当时决策保留。

## 背景

作者决定使用 TikHub 作为一组外部社交/论坛信源的共享 API provider：Twitter 第二源、小红书、Threads、Reddit 关键词搜索、微信公众文章。目标不是展示原始帖子流，而是把弱信号纳入 Augur 的决策链：发现某只股票被大众如何讨论、热度是否变化、哪些观点可作为反证。

## 决策

1. 新增 `backend/augur/news/tikhub.py`，所有 TikHub 信源共用 `TIKHUB_KEY`，鉴权用 Bearer Token；默认按 `api.tikhub.io` → `api.tikhub.dev` 尝试，也可用 `TIKHUB_BASE_URL` 固定基础域名。
2. 五个信源在设置页独立出现：
   - `tikhub_twitter`：Twitter 第二源，source prefix `X2·`
   - `xiaohongshu`：小红书，source prefix `小红书·`
   - `tikhub_threads`：Threads，source prefix `Threads·`
   - `tikhub_reddit`：Reddit · TikHub，source prefix `Reddit·TikHub·`
   - `tikhub_wechat`：微信公众文章，source prefix `微信·公众号·`
3. TikHub 结果归一为 `news_items`，并入既有流水线：规则分类、翻译、相关性过滤、ticker linker、LLM 标股、日报/要事/机会。
4. 前端「资讯」第三层新增 `推特2 / Threads / 微信`，小红书从待接入改为真实 lane；Reddit lane 同时容纳 public JSON 与 TikHub 搜索结果。
5. 「看·相关资讯」新增 `GET /news/social-heat`：只用 TikHub 的 Twitter 第二源 + 小红书搜索某股关键词，经 cheap 模型总结为 `heat / sentiment / bull_points / bear_points / watch`。前端只显示 AI 摘要和平台计数，不展示原始帖子。

## 端点口径

基于 TikHub 官方文档：

- Twitter 搜索：`GET /api/v1/twitter/web/fetch_search_timeline`
- Twitter 用户推文：`GET /api/v1/twitter/web/fetch_user_post_tweet`
- 小红书笔记搜索：`GET /api/v1/xiaohongshu/app_v2/search_notes`
- Threads 搜索：`GET /api/v1/threads/web/search_top`
- Reddit 动态搜索：`GET /api/v1/reddit/app/fetch_dynamic_search`
- 微信公众文章搜索：`GET /api/v1/wechat_mp/web/fetch_search_article`

## 权衡

- TikHub 是第三方桥，不是一手官方 API。它解决“能否稳定获取弱信号”的现实问题，但必须保留中文健康诊断、额度/权限暴露和缓存/限流。
- 社媒热度不是事实数据，容易受转发、标题党、营销号和短期情绪污染。因此 Augur 不把帖子列表铺给作者，只输出 AI 蒸馏后的观点分布、热度和反证。
- 一个 `TIKHUB_KEY` 供五个源共享，设置页会有五张卡，但凭证真相只有一份；这让健康度能按源显示，同时避免多份 key。

## 后果

- 小红书不再是“仅登记”，而是 TikHub 搜索型真实适配器。
- Reddit 形成双通道：public subreddit JSON 负责稳定、免费、低频跟踪；TikHub 负责全站关键词搜索。
- 个股投资判断多了“社媒弱信号”维度，但仍必须与新闻、财务、K 线、研究报告和反证条件共同使用。
- 若 TikHub 返回 401/403/402/429，设置页和健康度会显示中文原因：凭证无效、接口权限/余额不足、额度/频率限制等。

## 相关记忆

- [tikhub-source-quirks.md](../memory/tikhub-source-quirks.md)
- [external-source-api-setup.md](../memory/external-source-api-setup.md)
- [source-test-diagnostics.md](../memory/source-test-diagnostics.md)
