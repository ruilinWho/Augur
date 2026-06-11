# ADR-0012 — 外部社交/论坛信源接入策略

日期：2026-06-05

后续变更：2026-06-06 通过 [ADR-0013](0013-tikhub-social-source-layer.md) 接入 TikHub，
覆盖本文关于“小红书仍未接入”的阶段性判断；雪球退役判断不变。
后续变更（2026-06-11）：推特全局源由 twtapi 改为**唯一走 TikHub**（twtapi 仅每股专属 X 仍用作回退）；
**Reddit 直连公共 JSON 被 IP 封 403、`reddit.py` 已删，全 Reddit 走 TikHub**（关键词搜 + 子版 feed）；微信源已删（服务端 400）。

## 背景

作者希望 Augur 能持续聚合 X、Reddit、雪球、小红书等外部社交/论坛源，并且在设置页直接告诉他去哪里找 key、该源最适合怎么用、当前接入边界是什么。

这些平台的 API 可用性差异很大：X 官方 API 可用但成本/权限路径复杂；Reddit 轻量公开 JSON 可用但官方 Devvit/OAuth 路线另行审批；雪球和小红书没有确认的一手公共内容搜索 API，稳定接入通常依赖登录 Cookie 或商家开放平台。

## 决策

1. `news/source_registry.py` 是外部信源凭证入口与接入策略的单一真相，新增字段：
   - `docs_url`
   - `official_url`
   - `setup`
   - `best_use`
   - `boundary`
2. 设置·数据/信源详情页和设置·全部体检都消费这些字段，不在前端组件里写死平台说明。
3. X 当前继续走 `twtapi`，填 `TWTAPI_KEY`。X 官方 `console.x.com` 只作为未来原生 X API 适配器入口展示，不混淆为当前凭证。
4. Reddit 当前继续用 public subreddit JSON，无需 key；若未来需要更稳额度、写入或私有能力，再走官方 Devvit/OAuth 路线。
5. 雪球/小红书即使作者填了 token/cookie，在真实适配器和合规限流策略完成前仍显示“未接入”，不能伪装可用。

## 权衡

- 这让设置页出现少量解释文字，但这些文字是操作必需信息，不是 UI 教学噪音。
- X 选择 twtapi 比官方 API 更务实，但它是非官方桥，必须持续保留中文诊断和额度/鉴权边界。
- Reddit public JSON 足够支撑个人本地轻量研究，但不能无限放大抓取规模。
- 雪球/小红书最有社区情绪价值，也最容易触碰账号隐私、Cookie 失效和反爬风险；因此先登记关注用户/关键词，不抢做脆弱适配器。

## 后果

- 作者在配置页能直接看到“去哪拿凭证、看哪篇文档、这个源该怎么发挥最大价值”。
- 后续接入新社交源时，必须先补注册表元数据，再补适配器。
- 信源测试的“未接入”是有意状态，不是 bug；尤其适用于雪球/小红书。

## 相关记忆

- [external-source-api-setup.md](../memory/external-source-api-setup.md)
- [per-stock-source-tracking.md](../memory/per-stock-source-tracking.md)
- [twtapi-source-quirks.md](../memory/twtapi-source-quirks.md)
