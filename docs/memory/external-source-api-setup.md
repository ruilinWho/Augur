# 外部社交/论坛信源接入入口与边界

最后核查：2026-06-06。

## 结论

- **X / Twitter**：**全局推特源现在唯一走 TikHub**（填 `TIKHUB_KEY`，见下条）。`twtapi` 桥（`TWTAPI_KEY`，取 key <https://twtapi.io/>、文档 <https://twtapi.io/docs>）**已退役为全局源，仅每股专属 X 信源仍用**（按账号拉、失败回退 TikHub）。X 官方入口 <https://console.x.com/>、getting access <https://docs.x.com/x-api/getting-started/getting-access> 只留作未来原生 X API 适配器入口，非当前凭证。
- **TikHub**：设置里填 `TIKHUB_KEY`，共享给**全部社媒/论坛源——推特（唯一源）/ 小红书 / Threads / Reddit**。文档入口 <https://docs.tikhub.io/>。当前接：Twitter search/user posts、小红书 search_notes、Threads search_top、Reddit 关键词动态搜索 + 子版 feed（`fetch_subreddit_feed`）+ 子版名补全（`fetch_search_typeahead`）。**微信公众文章源已删除**（`wechat_mp/web/*` 整组服务端长期 400，非我方问题）。详见 [tikhub-source-quirks.md](tikhub-source-quirks.md) 与 [ADR-0013](../decisions/0013-tikhub-social-source-layer.md)。
- **Reddit**：**直连 reddit.com 公共 JSON 已被按 IP 封 403、`reddit.py` 已删——全 Reddit 走 TikHub**（共用 `TIKHUB_KEY`，TikHub 完整代理 Reddit API）：全局关键词搜 + 每股专属子板块 feed（`fetch_subreddit_feed`，子版名经 `fetch_search_typeahead` 解析）。官方 Devvit/OAuth（<https://developers.reddit.com/docs/>）是另一套写入/审批流程，未来要更稳额度再走。
- **雪球（2026-06-06 退役）**：没有可确认的一手公共内容 API；唯一的非官方路线是网页登录 Cookie/token（`xq_a_token=...;u=...`，参考第三方 `pysnowball`），但已被雪球 WAF 风控墙（`acw_sc__v2`/`_waf_` 网页壳）封死、打不通内容 JSON，且绑定真实账号足迹、token 周级失效。已整体移除（适配器/注册/探活/前端 lane）；除非雪球放出官方或合规内容接口，否则不要再赌 Cookie 抓取。详见 [xueqiu-source-quirks.md](xueqiu-source-quirks.md)。
- **小红书**：官方开放平台/Ark App Key 获取文档在 <https://school.xiaohongshu.com/en/open/quick-start/how-to-get-app-key.html>，首页/集成说明在 <https://school.xiaohongshu.com/en/open/index.html>。该平台偏商家/订单/商品等开放能力，不等于公开笔记搜索 API。Augur 当前不走浏览器 Cookie，改走 TikHub 小红书搜索端点。

## 最佳用法

- **X**：高信号官方号/公司号/投资人大 V 时间线优先；每股专属信源回流到 ticker lane。**全局推特＝`TIKHUB_KEY`（唯一源）**；`TWTAPI_KEY` 现仅用于每股专属 X 账号（失败回退 TikHub），不再是全局主源。
- **Reddit**：用 subreddit 做弱信号，不看原文洪流，继续走 Augur 的翻译、相关性过滤、股票接地、要点聚类。全部经 TikHub：全局关键词搜 + 每股专属子板块（首次刷新自动解析接入，如 NVDA→r/NVDA_Stock）。
- **雪球**：已退役（见上）。A/H/中概社区情绪与反证线索短期靠 Reddit、X 覆盖。
- **小红书**：只作为消费、品牌、渠道、散户情绪弱信号。现在通过 TikHub search_notes 接入；「看·社媒热度」会把小红书和 Twitter 第二源合成为观点/热度/反证，不展示原始帖子流。

## 产品规则

- 设置页必须在填 key 的同一屏展示：取凭证入口、文档/官方入口、接入方式、最佳用途、边界。
- `source_registry.py` 是这些元数据的单一真相；前端和“全部体检”只消费字段，不在组件里写死解释。
- TikHub 源测试失败时必须区分：未配置 `TIKHUB_KEY`、key 无效/无权限、余额/套餐不足、额度/频率限制、端点变更。不要回英文报错。
