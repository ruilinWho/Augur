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

## 【2026-06-11】微信源已彻底删除（TikHub 服务端长期故障）

逐端点实测确认 TikHub 整个 `wechat_mp/web/*` 组都服务端 400（详见下方「当前测试结果」），作者遂要求
**把微信相关功能（含前端）全删**。改动：
- **后端**：`tikhub.py` 删 `fetch_wechat`/`wechat_keywords`/`ping_source` 微信分支/`source_names` 微信
  条目/`_best_url` 的 sogou 兜底/`social_search_for_stock` 的微信 job；`ingest._ADAPTERS`/`_HEALTH_SOURCE_IDS`
  删微信；`source_registry` 删 `tikhub_wechat` 源条目 + `_CONFIG_VALUE`；`source_test` 删标签/探活集合；
  `relevance._select_pending` 去掉 `微信·%` 跳过；`service` 的 `_SOCIAL_PREFIXES`/`_SOCIAL_LANES`/
  `_PULSE_LANES`/`_platform_counts`/社媒热度 heading 全删微信。
- **前端**：`consts.ts`（SourceLaneId/INFO_SECTIONS/SOURCE_LANES）、`store.ts`（InfoSection）、
  `KnowView.tsx`（一键生成社媒列表）删 `wechat`/`微信·`。
- **资源/测试**：`social_keywords.yaml` 删 `wechat:` 段；`test_pure.py` 删 `assert "微信" in sources`
  （顺带把残留 `X2·` 测试标签更到 `X·`）。
- **数据**：删 `微信·%` news_items 行（实测 0 行，端点从没返回过数据）+ 删中文前缀塌缩遗留的孤儿
  cluster scope `src:_:all@1d`。
- 想恢复：TikHub 修好其 `wechat_mp/web/*` 后，可参照 git 历史把 `fetch_wechat`+注册表条目加回。

## Provider 口径

- 统一 key：`TIKHUB_KEY`。五个 Augur 源共用这一份 key，不要拆成多个 secret。
- 鉴权：TikHub 文档示例使用 Bearer Token，Augur 适配器统一发 `Authorization: Bearer <key>`。
- 基础域名：默认按 `https://api.tikhub.io` → `https://api.tikhub.dev` 顺序尝试；中国大陆网络不稳时也可在 `.env` 写 `TIKHUB_BASE_URL=https://api.tikhub.dev` 固定使用备用域名。
- 注册表条目：
  - `tikhub_twitter` → 推特（唯一推特源），source prefix `X·`
  - `xiaohongshu` → 小红书，source prefix `小红书·`
  - `tikhub_threads` → Threads，source prefix `Threads·`
  - `tikhub_reddit` → Reddit · TikHub，source prefix `Reddit·TikHub·`
  - ~~`tikhub_wechat` → 微信公众文章~~（**已删除**，TikHub 服务端故障，见顶部章节）

## 已接端点

- Twitter 搜索：`/api/v1/twitter/web/fetch_search_timeline`
- Twitter 用户推文：`/api/v1/twitter/web/fetch_user_post_tweet`
- 小红书笔记搜索：`/api/v1/xiaohongshu/app_v2/search_notes`
- Threads 搜索：`/api/v1/threads/web/search_top`
- Reddit 动态搜索：`/api/v1/reddit/app/fetch_dynamic_search`
- ~~微信公众文章搜索：`/api/v1/wechat_mp/web/fetch_search_article`~~（**已删除**，整组服务端 400）

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
- **【仍坏，TikHub 服务端，2026-06-11 用真实 key 逐端点实测确认】整个 `wechat_mp/web/*` 组都
  400**，不只是文章搜索：
  - `fetch_search_article`（搜文章）、`fetch_search_official_account`（搜公众号）、
    `fetch_mp_article_list`（按真实 `ghid=gh_a3d35d4c9d3f` 取列表）三个都 400“请求失败……不扣费”，
    两域名一致，参数与文档**完全吻合**。错误体自带 `request_id`，让“提交 response JSON 给支持”。
  - 即**非我方参数/接口类型问题**（作者一度怀疑“接口类型不对”——不是），是 TikHub 端故障。
  - 对照：同 key 打小红书 `search_notes` → 200，证明 key/套餐没问题。`fetch_mp_article_list`
    用假 `ghid=test` 曾回 200，那只是 TikHub 的“已受理将计费”包装层，不是真数据；真实 ghid 即 400。
  - 处置：`fetch_wechat` 的 `retries` 由 3 改 **0**（确诊坏了，别每次刷新都白白重试拖慢）；适配器
    优雅跳过（计入 sources_failed、不阻断其余）。TikHub 修了**自动恢复**（参数仍按文档保留）。
  - 想催修：带上某个 `request_id` 找 TikHub 支持（Discord）。`wechat_channels/*` 是视频号、非文章，
    不是替代品。若以后要绕过搜索，唯一活着的思路是“按 ghid 订阅特定公众号 + `fetch_mp_article_list`”，
    但该端点眼下也 400，且 ghid 难发现（搜公众号端点也坏），暂不值得做。
- 「看·社媒热度」是即时体验：按平台并发探测、每平台最多 10 条、某个 endpoint 失败不阻断
  其他源。当前真实抓取 NVDA 可得到小红书/Threads/Reddit 各 10 条；Twitter/微信临时失败会被跳过。
- 本文件不记录 key 明文。key 只应存在于 gitignored `backend/.env` 或 `data/config.local.json`。

## 产品规则

- TikHub 社媒结果先入 Augur 流水线，再参与日报/要事/机会；不要把 TikHub 原始 JSON 直接暴露到前端。
- 「看·社媒热度」只使用 Twitter 第二源 + 小红书搜索，并且只展示 AI 摘要、热度、观点倾向、偏多/反证/观察项，不展示原始帖子列表。
- 如果模型未配置，社媒热度可回退为“抓到 N 条但未生成摘要”，但不能展示原始帖子洪流。
