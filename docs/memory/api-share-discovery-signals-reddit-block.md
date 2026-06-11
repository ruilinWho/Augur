# API 配置分享 + 知导航折叠 + 寻信号/市场屏蔽 + Reddit 直连被封（2026-06-11 五轮）

作者一批「分享/导航/寻/看/设置」改进 + 一个硬约束发现（Reddit）。

## 【硬约束】Reddit 公共 JSON 已被按 IP 封（403）
- 实测：`www.reddit.com` 的 `/r/<sub>/new.json`、`/r/<sub>/about.json`、`/subreddits/search.json`
  **全部 403 "Blocked"**（换浏览器 UA、`old.reddit.com` 也一样，返回的是封禁页）。
- 即 `news/reddit.py` 直连适配器目前**整个死掉**（`fetch_reddit`/`fetch_subreddits` 返回 0 条）。
  全局「资讯·Reddit」lane 靠 **TikHub 的 Reddit**（`tikhub.fetch_reddit`，前缀 `Reddit·TikHub·`）兜底，
  仍有数据；直连那路（`Reddit·r/<sub>`）暂无。
- 代码**保留**直连路径（Reddit 若解封自动恢复）；`search_subreddit` 也保留、被封时优雅返回 []。

## 个股专属子板块 / Reddit 最相关信息（task 8 的「精髓」）
作者要：每股最丰富的 Reddit 相关讨论（它的专属子板块）。受 Reddit 封锁，改走 TikHub：
- `tikhub.search_reddit(query)`：TikHub Reddit 关键词搜索（直连被封后唯一可用路）。
- `stock_sources._fetch_one` kind=reddit：**先试直连子版**（解封即用）→ 无果**退 TikHub 按股名搜**。
- `stock_sources.ensure_auto_reddit(symbol)`：若该股没 Reddit 源，**自动加一个已启用源**
  （`added_by='auto'`）——优先解析真实子板块（直连，目前被封→空），否则用 TikHub 按股名搜（需 TIKHUB_KEY）。
  在 `refresh_symbol` 开头调用 → 每股「刷新相关资讯」首次自动接入 Reddit，不必手动 discover+启用。
- 验证：`tikhub.search_reddit('英伟达')` 返回 7 条；`ensure_auto_reddit('US:NVDA')` 自动加「Reddit · 英伟达」源。

## API 配置一键导出/导入（分享给 contributor）
- `runtime_config.export_api_config()`（LLM 连接 + 角色 + 数据信源 secret，**明文**，单用户本地）/
  `import_api_config(payload)`（覆盖连接/角色、合并 secret，立即注入 os.environ）。
- 路由 `GET/POST /settings/api-config/export|import`；前端 `exportApiConfig`/`importApiConfig` +
  设置·模型页「配置分享」section（导出下载 `augur-api-config.json`、导入读文件 POST）。

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
- **去重**：候选证据除 URL 去重外，加 `_norm_title` 近重标题折叠（同一事件多源/多措辞只留一条）。

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
  `_norm_title`/证据去重）、`discovery/router.py`（signals/markets）、`discovery/schemas.py`（MarketCount/MarketMutePatch）、
  `news/reddit.py`（`search_subreddit`，被封返空）、`news/tikhub.py`（`search_reddit`）、`news/stock_sources.py`
  （`ensure_auto_reddit`/`_resolve_subreddit`/TikHub 兜底）。
- 前端：`api.ts`（export/importApiConfig、useDiscoverySignals/Markets、useMuteMarket）、`settings/SettingsView.tsx`
  （ApiConfigShare、栏宽）、`news/NewsNav.tsx` + `news/store.ts`（nav 折叠）、`news/StockNews.tsx`（删平台计数、hideRefs）、
  `news/NarrativeTimeline.tsx`（hideRefs）、`discovery/DiscoveryView.tsx`（信号 badge、市场屏蔽）、`index.css`
  （`.nrail-collapse`/`.cand-hot`/`.disc-prefs-grp`/`.cfg-hint`）。
- 见 [[tikhub-source-quirks]]、[[per-stock-source-tracking]]、上一轮 [[know-config-collapse-discovery-reasons]]。
