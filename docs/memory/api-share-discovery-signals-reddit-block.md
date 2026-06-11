# API 配置分享 + 知导航折叠 + 寻信号/市场屏蔽 + Reddit 直连被封（2026-06-11 五轮）

作者一批「分享/导航/寻/看/设置」改进 + 一个硬约束发现（Reddit）。

## 【硬约束】Reddit 直连被按 IP 封 403 → 全 Reddit 走 TikHub，直连源已删（六轮更新）
- 实测：`www.reddit.com` 的 `/r/<sub>/new.json`、`about.json`、`subreddits/search.json` **全部 403
  "Blocked"**（换浏览器 UA、`old.reddit.com` 也一样）。直连 `news/reddit.py` 整个死掉。
- **调研发现 TikHub 完整代理 Reddit API**（不止关键词搜，还有按子版抓 feed、子版搜索补全等）：
  - `fetch_subreddit_feed(subreddit_name, sort=HOT/NEW/TOP…)`：**抓某子版的帖子流**（真子板块数据）。
    结构是 GraphQL（按子版/排序略变），解析只认**直接带 `title` + permalink/id/createdAt 的帖子节点**、
    按归一标题去重（别用递归 `_best_*`，会抽出 gif/头像等资源 url）。
  - `fetch_search_typeahead(query)`：**按词找子版**（如 NVDA → NVDA_Stock/NVDA_trading…），替代被封的直连搜索。
- **作者拍板：既然 TikHub Cover 了 Reddit，删掉直连那套。** 改动：
  - 删 `news/reddit.py`；`ingest._ADAPTERS`/`_HEALTH`/prune 豁免去掉直连 `reddit`；`source_registry` 删
    `reddit` 源条目 + `_CONFIG_VALUE`；`source_test` 删 reddit 探活。全局 Reddit 仅剩 `tikhub_reddit`
    （TikHub 关键词搜）——**直连本就 0 条（被封），删它零数据损失**。
  - 全局 lane prune 只清 `lane='feed'`，每股子版帖在 `lane='ticker'`，不受影响。

## 个股专属子板块 / Reddit 最相关信息（task 8 的「精髓」，已做成真子板块）
每股最丰富的 Reddit 讨论＝它的专属子板块。现在经 TikHub 真正实现：
- `stock_sources._resolve_subreddit(symbol)`：用 `tikhub.search_subreddit_typeahead(ticker/股名)` 解析
  专属子版（取第一个名字含 ticker/公司名、非通用的，typeahead 已按相关性排序）。
- `_fetch_one` kind=reddit：ref 是子版名 → `tikhub.fetch_subreddit_feed(sub)` 抓该子版 feed；ref 非子版名
  （旧关键词源/解析不到）→ 退 `tikhub.search_reddit(股名)` 关键词搜。
- `ensure_auto_reddit(symbol)`：该股没 Reddit 源时**自动加已启用源**（`added_by='auto'`，ref=子版名），
  `refresh_symbol` 开头调用 → 首次刷新自动接入该股专属子板块，不必手动 discover+启用。需 TIKHUB_KEY。
- 验证：US:NVDA → r/NVDA_Stock（12 帖「Just bought 336 shares…」「OpenAI/Anthropic IPOs catalysts for NVDA」）；
  US:TSLA → r/TSLALounge（「$TSLA Daily Thread」）。

## API 配置一键导出/导入（分享给 contributor）
- `runtime_config.export_api_config(allowed_secrets=None)`（LLM 连接 + 角色 + 数据信源 secret，**明文**，单用户本地）/
  `import_api_config(payload, allowed_secrets=None)`（覆盖连接/角色、合并 secret，立即注入 os.environ）。
- 路由 `GET/POST /settings/api-config/export|import`；前端 `exportApiConfig`/`importApiConfig` +
  设置·模型页「配置分享」section（导出下载 `augur-api-config.json`、导入读文件 POST）。

### 【2026-06-11】只导出/导入**在用**的 secret（退役源 key 不外泄、自动清）
作者反馈导出里混着已退役功能的 key（雪球 等）。根因：`export_api_config` 原样 dump `config.local.json` 的
`secrets`，把历史遗留 key 也带出去。三层修复，单一白名单 = `news/source_registry.live_secret_names()`
（＝SOURCES 的 `key_env` ∪ 每股 twtapi 的 `TWTAPI_KEY`；当前 = `{TIKHUB_KEY, TWTAPI_KEY}`）：
- **导出过滤**：`export_api_config(allowed)` 只导出白名单内的 secret（路由传 `live_secret_names()`）。
- **导入过滤**：`import_api_config(payload, allowed)` 只合并白名单内的——老版本导出文件里的退役 key 不会被重新引入。
- **启动自愈**：`runtime_config.prune_secrets(allowed)` 在 `main.lifespan` `load()` 后跑，把
  `config.local.json` 里不在白名单的遗留 key 删掉（只动存储、不碰 os.environ/`.env`；删了会 `log.info`）。
  **退役一个源（从 SOURCES 删）→ 它的 key 下次启动自动清**，无需手动。
- 实测：原 7 个 secret（含 `XUEQIU_TOKEN`/`TWTAPI_MCP_KEY`/`TUSHARE_TOKEN`/`BIYING_API_LICENCE`/`ITICK_API_KEY`）
  启动后自动剩 `TIKHUB_KEY`+`TWTAPI_KEY`；导出无泄漏；导入老配置里的 `XUEQIU_TOKEN` 被挡。
- **加新数据源记得把 key 纳入 `live_secret_names()`**（在 SOURCES 里给 `key_env`，或并入 `_EXTRA_LIVE_SECRETS`），
  否则它的 key 会被当退役 key 清掉/不导出。

## 知·资讯 日期/板块 选择栏可折叠
- news store 加 `navCollapsed` + `toggleNav`；`NewsNav` 加 `.nrail-collapse`（‹/›，与自选「分区」面板同款，
  遵 [[no-collapse-chevrons]] 的「面板折叠用 ‹/›、不用内容三角」），收起后不渲染 `news-sub` 面板、主内容延展。

## 寻：异动信号 + 按市场屏蔽 + 去重
- **异动信号**：`market.service.momentum(symbol)`（近月涨幅% + 放量比，缓存优先日线）；
  `discovery.service.signals()`（对当前 new 候选并发取、30 分钟内存缓存，只回「涨≥12% 且放量≥1.4×」的）；
  路由 `GET /discovery/signals`（**懒加载、与列表/重算解耦**，不拖慢）；前端 `useDiscoverySignals` +
  `.cand-hot` pill（「近月 ↑X% · 放量 Y×」，用涨色）。
- **按市场屏蔽**：`muted_markets`/`set_market_muted`/`market_counts`（复用主题屏蔽机制）；
  路由 `GET /discovery/markets` + `POST /discovery/markets/mute`；`list_candidates` SQL 里 `symbol NOT LIKE 'KR:%'`
  过滤；前端偏好面板加「市场」组（美/港/A/韩 chip，点击屏蔽）。实测屏蔽韩股 → 候选 25→24。
- **去重 + 多源聚合 + 翻译刷新**（2026-06-11 加强，作者反馈「寻」里同一事件多源重复，如美团「发布AI浏览器Tabbit 1.0」
  36氪/东方财富各一条）：抽出 `_dedup_aggregate(ev, fresh)` 做三件事——① 按 `_norm_title` 归一标题把同一事件折叠成
  一条；② 把折叠掉的来源**聚合**进 `sources: list[str]`（卡上主来源后显 `+N`、hover 列全部来源，多源覆盖反成「重要度」信号）；
  ③ `fresh`（读时拉 news_items 最新 `title_zh/source`）覆盖存量快照标题，**接住物化之后才补的中文翻译**。幂等。
  - 两层都用：`refresh()` 物化时 `_dedup_aggregate(...)[:ev_cap]`（收集只按 URL 去重、保留同事件不同源变体，
    上限 `_MAX_EVIDENCE`，给聚合留余量）；`list_candidates()`/`set_status()` 读时 `_enrich_evidence(conn, cands)`
    再跑一遍 → **自愈**：物化在去重逻辑之前的存量重复当场清掉、无需重算。
  - **坑**：evidence 加 `sources` 字段后前端拿不到——FastAPI `response_model=list[Candidate]` 按 `DiscoveryEvidence`
    Pydantic 模型过滤，**漏改 `discovery/schemas.py` 的 `DiscoveryEvidence` 会被静默剥字段**。service 输出 + Pydantic
    schema + 前端 `discoveryEvidenceSchema`（zod）三处都要加。前端 `.ev-src-name`（截断）+ `.ev-src-more`（`+N`，不动标题对齐）。

## 看：去掉两处噪音
- 社媒热度删底部「推特14 小红书14 …」平台计数行（`StockNews` 去 `.srn-social-plat`/`platformEntries`）。
- 时间线删每条下的英文新闻标题：`NarrativeBody` 加 `hideRefs`，`StockNews` 时间线子卡传 `hideRefs`。

## 设置·栏宽：删困惑数字
- 删「268 · 196 · 184 · 156/150/248」原始 px 串（拖拽分隔条本就可配）；改成「拖栏间分隔条调整」提示 + 「恢复默认」。

## 分支清理
- `feat/prompt-templates`/`fix/tikhub-twitter-search`/`refactor/tikhub-only-twitter`/`feat/social-pulse-drop-wechat`
  都已并入 main → 删本地+远端。现仅剩 `main`。

## 相关文件
- 后端：`runtime_config.py`（export/import_api_config + 市场/信号无关）、`settings_router.py`（api-config 路由）、
  `market/service.py`（`momentum`/`parse_symbol`）、`discovery/service.py`（`signals`/`_signal_for`/market mute/
  `_norm_title`/`_dedup_aggregate`/`_enrich_evidence` 证据去重+聚合+翻译刷新）、`discovery/router.py`（signals/markets）、
  `discovery/schemas.py`（`DiscoveryEvidence.sources`/MarketCount/MarketMutePatch）、
  `news/reddit.py`（`search_subreddit`，被封返空）、`news/tikhub.py`（`search_reddit`）、`news/stock_sources.py`
  （`ensure_auto_reddit`/`_resolve_subreddit`/TikHub 兜底）。
- 前端：`api.ts`（export/importApiConfig、useDiscoverySignals/Markets、useMuteMarket）、`settings/SettingsView.tsx`
  （ApiConfigShare、栏宽）、`news/NewsNav.tsx` + `news/store.ts`（nav 折叠）、`news/StockNews.tsx`（删平台计数、hideRefs）、
  `news/NarrativeTimeline.tsx`（hideRefs）、`discovery/DiscoveryView.tsx`（信号 badge、市场屏蔽）、`index.css`
  （`.nrail-collapse`/`.cand-hot`/`.disc-prefs-grp`/`.cfg-hint`）。
- 见 [[tikhub-source-quirks]]、[[per-stock-source-tracking]]、上一轮 [[know-config-collapse-discovery-reasons]]。
