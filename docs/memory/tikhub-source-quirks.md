# TikHub 信源接入坑

记录：2026-06-06。

## 【2026-06-11】TikHub 升为唯一推特源（twtapi 退役）

作者要求「删除推特1（twtapi）、把推特2（TikHub）作为唯一推特源」。改动：
- **source prefix `X2·` → `X·`**（TikHub 现是唯一推特源，用规范前缀）；`_SOCIAL_LANES`/`_SOCIAL_PREFIXES`/
  `_platform_counts` 同步；前端删 `twitter2` lane（SourceLaneId/SOURCE_LANES/INFO_SECTIONS/store）。
- **`ingest._ADAPTERS` 删 `X(Twitter)→twtapi.fetch_all`**，`Twitter 第二源→tikhub.fetch_twitter` 改名
  `推特`；`source_registry` 删 twtapi 条目、`tikhub_twitter` 改名「推特」；`source_test`/`_HEALTH_SOURCE_IDS`
  同步；prune 豁免去掉 `twtapi.source_names()` → 老 twtapi `X·<handle>` 数据下次 ingest 自动清。
- **数据迁移**（一次性）：删老 twtapi `X·<handle>` 行、`X2·*` → `X·*`。
- `twtapi.py` **保留**：每股专属信源（`official_x`/`influencer_x`）仍按账号拉、twtapi 失败回退 TikHub。

## Provider 口径

- 统一 key：`TIKHUB_KEY`。五个 Augur 源共用这一份 key，不要拆成多个 secret。
- 鉴权：TikHub 文档示例使用 Bearer Token，Augur 适配器统一发 `Authorization: Bearer <key>`。
- 基础域名：默认按 `https://api.tikhub.io` → `https://api.tikhub.dev` 顺序尝试；中国大陆网络不稳时也可在 `.env` 写 `TIKHUB_BASE_URL=https://api.tikhub.dev` 固定使用备用域名。
- 注册表条目：
  - `tikhub_twitter` → Twitter 第二源，source prefix `X2·`
  - `xiaohongshu` → 小红书，source prefix `小红书·`
  - `tikhub_threads` → Threads，source prefix `Threads·`
  - `tikhub_reddit` → Reddit · TikHub，source prefix `Reddit·TikHub·`
  - `tikhub_wechat` → 微信公众文章，source prefix `微信·公众号·`

## 已接端点

- Twitter 搜索：`/api/v1/twitter/web/fetch_search_timeline`
- Twitter 用户推文：`/api/v1/twitter/web/fetch_user_post_tweet`
- 小红书笔记搜索：`/api/v1/xiaohongshu/app_v2/search_notes`
- Threads 搜索：`/api/v1/threads/web/search_top`
- Reddit 动态搜索：`/api/v1/reddit/app/fetch_dynamic_search`
- 微信公众文章搜索：`/api/v1/wechat_mp/web/fetch_search_article`

注意：最初猜过 Reddit `web/search_posts`，实际会 404，不要使用。文档线索应走 app dynamic search。

## 当前测试结果

- 2026-06-06 复测作者充值后的 key：`get_user_info` 可读到账户余额，`get_endpoint_info`
  对 Twitter 搜索、小红书、Threads、Reddit、微信五个 endpoint 均返回可计费价格，因此
  不是 key 无效或余额不足。
- 小红书 `search_notes`、Threads `search_top`、Reddit `fetch_dynamic_search` 已真实通过探活。
- Reddit 动态搜索参数必须按文档使用 `query`、`search_type=post`、`sort=NEW`、
  `time_range=week`。旧的 `keyword` 会 422。返回结构是
  `data.search.dynamic.components.main.edges[].node.children[]`，必须只解析
  `__typename=SearchPost`，不要用通用递归抓字段，否则会抓到“排序方式”等 UI 文案。
- **【已修，2026-06-11】Twitter 搜索 `fetch_search_timeline` 的 400 是参数问题，不是端点死**：
  对照 OpenAPI（`https://api.tikhub.io/openapi.json`）实测确认——`search_type` 必须 `'Top'`
  （我们原来用 `'Latest'` → 400），且**不能传 `cursor='undefined'`**（传了 → 400）。改成
  `{'search_type':'Top'}`（去 cursor）后稳定 200，实测抓到 64 条真投资推文、生成 29 簇要点。
  注意：`Top` 是热门贴（非最新），会混入老贴，但内容相关。**三处都要改**：`fetch_twitter`、
  `social_search_for_stock` 的 jobs、`ping_source` 的测试。`fetch_user_post_tweet`（按账号拉）
  的 `cursor='undefined'` **是 OK 的**（只有 search 端点拒绝它），别一起改。
- **【仍坏，TikHub 服务端】微信公众文章 `wechat_mp/web/fetch_search_article`**：OpenAPI 里参数
  只有 keyword/offset/sort_type，我们全按文档传（含默认 `sort_type='_0'`）在两个域名仍全部
  400“请求失败……不扣费”。这是 **TikHub 端点本身的问题**（错误信息自己让“提交 response JSON
  给支持”），非 key/参数问题，我们改不了。适配器已优雅跳过（计入 sources_failed、不阻断其余）。
  TikHub 修了就会自动恢复；或带 request_id 找 TikHub 支持。无可用替代端点（其余 wechat_mp/*
  是按 biz 取文章列表、wechat_channels/* 是视频号，都不是关键词文章搜索）。
- 「看·社媒热度」是即时体验：按平台并发探测、每平台最多 10 条、某个 endpoint 失败不阻断
  其他源。当前真实抓取 NVDA 可得到小红书/Threads/Reddit 各 10 条；Twitter/微信临时失败会被跳过。
- 本文件不记录 key 明文。key 只应存在于 gitignored `backend/.env` 或 `data/config.local.json`。

## 产品规则

- TikHub 社媒结果先入 Augur 流水线，再参与日报/要事/机会；不要把 TikHub 原始 JSON 直接暴露到前端。
- 「看·社媒热度」只使用 Twitter 第二源 + 小红书搜索，并且只展示 AI 摘要、热度、观点倾向、偏多/反证/观察项，不展示原始帖子列表。
- 如果模型未配置，社媒热度可回退为“抓到 N 条但未生成摘要”，但不能展示原始帖子洪流。
