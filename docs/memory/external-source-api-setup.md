# 外部社交/论坛信源接入入口与边界

最后核查：2026-06-06。

## 结论

- **X / Twitter**：Augur 当前不直连 X 官方 API，而是走 `twtapi` 桥，设置里填 `TWTAPI_KEY`。取 key 入口是 <https://twtapi.io/>，文档入口是 <https://twtapi.io/docs>。X 官方入口是 <https://console.x.com/>，官方 getting access 文档是 <https://docs.x.com/x-api/getting-started/getting-access>；官方 key 可用于未来原生 X API 适配器，但不是当前 `news/twtapi.py` 的凭证。
- **TikHub**：设置里填 `TIKHUB_KEY`，共享给 **Twitter 第二源 / 小红书 / Threads / Reddit · TikHub / 微信公众文章**。文档入口是 <https://docs.tikhub.io/>。当前按 TikHub 文档接搜索型端点：Twitter search/user posts、小红书 search_notes、Threads search_top、Reddit dynamic search、微信公众文章 search_article。详见 [tikhub-source-quirks.md](tikhub-source-quirks.md) 与 [ADR-0013](../decisions/0013-tikhub-social-source-layer.md)。
- **Reddit**：当前 `reddit.py` 使用 public subreddit JSON，不需要 key。官方 Devvit 路线不需要传统 `reddit.com/prefs/apps` API key，入口是 <https://developers.reddit.com/docs/> / <https://developers.reddit.com/new>；外部脚本/OAuth 是另一套流程。当前适合轻量拉 `r/<sub>/new.json?raw_json=1`，重度或写入型能力再走官方审批/Devvit。
- **雪球（2026-06-06 退役）**：没有可确认的一手公共内容 API；唯一的非官方路线是网页登录 Cookie/token（`xq_a_token=...;u=...`，参考第三方 `pysnowball`），但已被雪球 WAF 风控墙（`acw_sc__v2`/`_waf_` 网页壳）封死、打不通内容 JSON，且绑定真实账号足迹、token 周级失效。已整体移除（适配器/注册/探活/前端 lane）；除非雪球放出官方或合规内容接口，否则不要再赌 Cookie 抓取。详见 [xueqiu-source-quirks.md](xueqiu-source-quirks.md)。
- **小红书**：官方开放平台/Ark App Key 获取文档在 <https://school.xiaohongshu.com/en/open/quick-start/how-to-get-app-key.html>，首页/集成说明在 <https://school.xiaohongshu.com/en/open/index.html>。该平台偏商家/订单/商品等开放能力，不等于公开笔记搜索 API。Augur 当前不走浏览器 Cookie，改走 TikHub 小红书搜索端点。

## 最佳用法

- **X**：高信号官方号/公司号/投资人大 V 时间线优先；每股专属信源可回流到 ticker lane。`TWTAPI_KEY` 是主 X 时间线；`TIKHUB_KEY` 是独立第二源和 search/mentions 补充，不要混淆。
- **Reddit**：用 subreddit 做弱信号，不看原文洪流，继续走 Augur 的翻译、相关性过滤、股票接地、要点聚类。默认关注 `stocks`、`investing`、`SecurityAnalysis`、`ValueInvesting`、`wallstreetbets` 和个股子版；TikHub Reddit 负责关键词搜索补充。
- **雪球**：已退役（见上）。A/H/中概社区情绪与反证线索短期靠 Reddit、X 覆盖。
- **小红书**：只作为消费、品牌、渠道、散户情绪弱信号。现在通过 TikHub search_notes 接入；「看·社媒热度」会把小红书和 Twitter 第二源合成为观点/热度/反证，不展示原始帖子流。

## 产品规则

- 设置页必须在填 key 的同一屏展示：取凭证入口、文档/官方入口、接入方式、最佳用途、边界。
- `source_registry.py` 是这些元数据的单一真相；前端和“全部体检”只消费字段，不在组件里写死解释。
- TikHub 源测试失败时必须区分：未配置 `TIKHUB_KEY`、key 无效/无权限、余额/套餐不足、额度/频率限制、端点变更。不要回英文报错。
