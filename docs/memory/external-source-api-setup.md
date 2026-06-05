# 外部社交/论坛信源接入入口与边界

最后核查：2026-06-05。

## 结论

- **X / Twitter**：Augur 当前不直连 X 官方 API，而是走 `twtapi` 桥，设置里填 `TWTAPI_KEY`。取 key 入口是 <https://twtapi.io/>，文档入口是 <https://twtapi.io/docs>。X 官方入口是 <https://console.x.com/>，官方 getting access 文档是 <https://docs.x.com/x-api/getting-started/getting-access>；官方 key 可用于未来原生 X API 适配器，但不是当前 `news/twtapi.py` 的凭证。
- **Reddit**：当前 `reddit.py` 使用 public subreddit JSON，不需要 key。官方 Devvit 路线不需要传统 `reddit.com/prefs/apps` API key，入口是 <https://developers.reddit.com/docs/> / <https://developers.reddit.com/new>；外部脚本/OAuth 是另一套流程。当前适合轻量拉 `r/<sub>/new.json?raw_json=1`，重度或写入型能力再走官方审批/Devvit。
- **雪球**：未找到可确认的一手公共内容 API。可行但非官方的路线是网页登录后复制 Cookie/token（常见形态 `xq_a_token=...;u=...`），参考第三方 `pysnowball`：<https://pypi.org/project/pysnowball/>。这会绑定作者真实账号足迹，token 也会失效；未实现适配器前必须显示“未接入”。
- **小红书**：官方开放平台/Ark App Key 获取文档在 <https://school.xiaohongshu.com/en/open/quick-start/how-to-get-app-key.html>，首页/集成说明在 <https://school.xiaohongshu.com/en/open/index.html>。该平台偏商家/订单/商品等开放能力，不等于公开笔记搜索 API。没有稳定合规接口前，不做匿名爬虫或浏览器 Cookie 冒充已接入。

## 最佳用法

- **X**：高信号官方号/公司号/投资人大 V 时间线优先；每股专属信源可回流到 ticker lane。后续最值得扩展的是 search/mentions，用于“某股突然被谁讨论”。
- **Reddit**：用 subreddit 做弱信号，不看原文洪流，继续走 Augur 的翻译、相关性过滤、股票接地、要点聚类。默认关注 `stocks`、`investing`、`SecurityAnalysis`、`ValueInvesting`、`wallstreetbets` 和个股子版。
- **雪球**：适合大 V、个股讨论、A/H/中概社区情绪和反证线索；必须做账号隐私提示和限流。
- **小红书**：只作为消费、品牌、渠道、散户情绪弱信号；接入前应先确认合规接口和稳定性，不把“登录 Cookie 可以抓”当作产品能力。

## 产品规则

- 设置页必须在填 key 的同一屏展示：取凭证入口、文档/官方入口、接入方式、最佳用途、边界。
- `source_registry.py` 是这些元数据的单一真相；前端和“全部体检”只消费字段，不在组件里写死解释。
- 雪球/小红书没有真实适配器前，测试结果仍应是“未接入”，即使作者已经填了 token/cookie。
