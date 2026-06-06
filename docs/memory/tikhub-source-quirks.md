# TikHub 信源接入坑

记录：2026-06-06。

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
- Twitter 搜索 `fetch_search_timeline` 与微信公众文章 `fetch_search_article` 在 `api.tikhub.io`
  和 `api.tikhub.dev` 都返回 TikHub 400：“请求失败，请重试……本次请求不会被扣费。”
  文档默认示例也同样失败；这应显示为 **TikHub 端点当前失败**，不要误判为
  key/余额/权限问题。可带响应 JSON 向 TikHub 支持确认。
- 「看·社媒热度」是即时体验：按平台并发探测、每平台最多 10 条、某个 endpoint 失败不阻断
  其他源。当前真实抓取 NVDA 可得到小红书/Threads/Reddit 各 10 条；Twitter/微信临时失败会被跳过。
- 本文件不记录 key 明文。key 只应存在于 gitignored `backend/.env` 或 `data/config.local.json`。

## 产品规则

- TikHub 社媒结果先入 Augur 流水线，再参与日报/要事/机会；不要把 TikHub 原始 JSON 直接暴露到前端。
- 「看·社媒热度」只使用 Twitter 第二源 + 小红书搜索，并且只展示 AI 摘要、热度、观点倾向、偏多/反证/观察项，不展示原始帖子列表。
- 如果模型未配置，社媒热度可回退为“抓到 N 条但未生成摘要”，但不能展示原始帖子洪流。
