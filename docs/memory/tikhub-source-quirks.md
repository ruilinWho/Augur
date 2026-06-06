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

- 用作者提供的 TikHub key 做轻量探活时，五个源均被诊断为“当前凭证没有这个接口权限，可能需要充值、开通套餐或提高积分”。Reddit 早期猜测端点返回过 404，已改为文档线索里的 dynamic search。
- 不要把这类结果解释成 Augur 解析失败。UI 应显示“凭证无效/无权限”或“余额、套餐、接口权限未开通”，取决于 TikHub 返回。
- 本文件不记录 key 明文。key 只应存在于 gitignored `backend/.env` 或 `data/config.local.json`。

## 产品规则

- TikHub 社媒结果先入 Augur 流水线，再参与日报/要事/机会；不要把 TikHub 原始 JSON 直接暴露到前端。
- 「看·社媒热度」只使用 Twitter 第二源 + 小红书搜索，并且只展示 AI 摘要、热度、观点倾向、偏多/反证/观察项，不展示原始帖子列表。
- 如果模型未配置，社媒热度可回退为“抓到 N 条但未生成摘要”，但不能展示原始帖子洪流。
