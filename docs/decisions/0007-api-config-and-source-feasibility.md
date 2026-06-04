# ADR 0007 — 设置·API 配置中枢 + 顶级数据/新闻源可行性核查

- **状态：** 已接受（配置中枢 + Bloomberg 接入 + 移除太贵源）；财联社/东财免费适配器待接；X 待作者配 key
- **日期：** 2026-06-02
- **决策者：** 作者 + Claude

> 作者要点：①「是不是可以有一个专门的设置页面用来配置 API（含 LLM、资讯网站等）」；②核查朋友推荐的「最好的信息源」有无科技频道、能否接入——国内 万得/iFinD/Choice/DM(FICC)/财联社/华尔街见闻，国外 Bloomberg/Reuters；③「X 之后我会买 api 和 key，其他信源一样，先做好准备就行」；④随后：「太贵的数据信源可以去掉」。

## 背景

- 在此之前，LLM 厂商 key / 角色路由只能改 `backend/.env` 并重启；数据源没有「配 key」的地方。作者希望把「接口配置」做成一等公民，并为将来买入的付费源（先是 X）铺好即插即用的槽。
- 护栏：**密钥永不入库**、不打日志、本地优先、暴露不确定性、尊重限流（§5/§6/§11）。

## 决策

### 1. 运行时配置中枢（`runtime_config` + `/settings` + 设置页）

- **存储：** gitignored `data/config.local.json`（文件权限 0600），存 `secrets`（API key / base_url）与 `roles`（LLM 角色→provider:model）。启动时把 secrets **注入 `os.environ`**，使 litellm/gateway 与各信源适配器在**不重启**下即时读到（它们都走 `os.getenv`）。`.env` 仍支持；UI 存的值优先（便于即时改）。
- **安全（§11）：** GET 只回**脱敏**状态（末 4 位 `····9284`），POST **从不回传明文**、**绝不打日志**；写入 env 名经 **guard**（白名单 + `*_API_KEY/_BASE_URL/_KEY/_TOKEN/_SECRET/_URL` 模式），杜绝写任意环境变量（如 PATH）。
- **端点：** `GET /settings/config`（LLM 角色/厂商 + 数据源状态，全脱敏）、`POST /settings/secret`、`POST /settings/role`。
- **前端「设置」页：** LLM 角色（provider:model 可改）+ 厂商（key 密文/base_url）+ **「数据 / 信源 API」区**（注册表驱动，按需配 key、看状态徽标）。改动即时生效、无需重启。

### 2. 信源注册表（`news/source_registry.py`）

登记**需 key 或需专用适配器**的源 + 计算状态，驱动设置页。普通 RSS 仍在 `feeds.yaml`。

### 3. 源可行性核查结论（作者朋友清单 + 国际两大家）

4 路调研 agent + 实测（curl/feedparser，2026-06）：

| 源 | 科技频道 | 可接入路径 | 裁决 |
|---|---|---|---|
| **Bloomberg** | ✅ Technology | **免费官方 RSS** `feeds.bloomberg.com/technology/news.rss`（+ markets/economics），实测 30 条/源、新鲜 | ✅ **已接入** feeds.yaml（精英二手，未公开文档→带回退） |
| **财联社 CLS** | ✅ 科创(1111) + 电报 | 免费非官方 API：`/v3/depth/home/assembled/1111`，需 `sign=MD5(SHA1(sorted_qs))`、`appName=CailianpressWeb`（旧 `nodeapi/telegraphList` 已死） | ✅ **已接入** `cls.py`（最佳中文科技源） |
| **东方财富（免费）** | ✅ 关键词 | 免费 `search-api-web.eastmoney.com/search/jsonp`（人工智能/半导体/算力…），与现有东财检索同源 | ✅ **已接入** `eastmoney_news.py` |
| **华尔街见闻** | ✅ `tmt-channel` | 已接 RSS；可加 `information-flow?channel=tmt-channel` 焦点科技 lane | ✅ 已有，待加焦点 lane |
| **Reuters** | ✅ Technology | **无免费 RSS**；仅 LSEG/Refinitiv 企业合约（`api.refinitiv.com`，五位数/年、销售开通） | ❌ **太贵，移除**（Google News RSS 仅个人用/跳转链，不作主源） |
| **同花顺 iFinD（付费）** | 偏数据 | 付费 quantapi（约 Wind 5–7 折） | ❌ **太贵，移除** |
| **东财 Choice（付费）** | 偏数据 | EmQuantAPI（约 ¥30k/年） | ❌ **太贵，移除** |
| **万得 Wind** | 终端内 | WindPy 需本机 **Windows** 终端会话（~¥39,800/年） | ❌ **不可用 + 太贵，移除** |
| **DM (Dealing Matrix)** | ❌ 仅 FICC | 实名机构终端，无公开 feed、与科技无关 | ❌ **跳过** |

### 4. 按作者意见「移除太贵的数据信源」

注册表只留**免费 / 极廉**：Bloomberg（免费 RSS）、财联社 / 东财（免费 API）、**X**（TwitterAPI.io 桥，约 $几/月，作者将买 key）。**Reuters/Wind/iFinD/Choice 已从注册表与 `.env.example` 删除**（要时按本 ADR 路径再接）。

### 5. 信源三类重组（财经/新闻/论坛）+ 候选源可行性（2026-06，5-agent 调研）

作者反馈：① 删除注册表里冗长 note（噪音）；② 评估候选源 twtapi/必盈/iTick/Tushare/雪球；③ 把**所有信源 + 设置页**按 **财经 / 新闻 / 论坛** 三类重组。

- **重组**：`source_registry.py` 每条加 `group`（finance/news/forum）+ `cred`（key/token），note 一律 ≤~12 字精简；`groups()` 给三类标签/顺序；`status_list()` 动态补 RSS 条数。前端 `SourcesPage` 按三类渲染独立 Section。
  - **财经**：`market_data` 聚合行（FDR·akshare·yfinance·pykrx，已接入主力）+ 候选 Tushare/必盈/iTick（登记留槽）。
  - **新闻**：`feeds_rss` 聚合行（动态计数，详见 feeds.yaml）+ Bloomberg + 财联社 + 东财资讯 + **X(Twitter) 官方号**（按作者「推特进新闻」）。
  - **论坛**：雪球 Xueqiu（登记留槽，诚实标注「需登录·泄持仓」权衡）。
- **候选源可行性（均先「登记留槽」、不写适配器、由作者定夺）**：
  - **行情类（必盈 `BIYING_API_LICENCE` / iTick `ITICK_API_KEY` / Tushare `TUSHARE_TOKEN`）**：A/港/美/全球行情+基本面**已被 FDR/akshare/yfinance/pykrx 免费覆盖**；免费档过严（iTick 5 次/分；Tushare 仅 A 股日线 50 次/月）或需付费，且每次查询把标的外泄给第三方（增隐私面）。→ 登记备选、不默认启用。
  - **雪球 pysnowball（`XUEQIU_TOKEN`，论坛）**：社区情绪/组合独特，但需**手动登录 token（周级失效）**且把持仓查询**绑作者真实账号泄露**给雪球——触 §11 本地优先私密底线。→ 登记留槽并显式标注权衡，作者知情后自配。
  - **Twitter 桥：改选 twtapi（`TWTAPI_KEY`）取代 TwitterAPI.io，并已实现适配器**。原选 TwitterAPI.io（纯按量更省）但**需国际银行卡，作者办不了**；twtapi 有免费试用 + 月付套餐，作者可付。二者隐私权衡等同（仅看公开官方号、不涉持仓）。`news/twtapi.py` 已接：base `https://api.twtapi.com/api/v1/twitter`、头 `X-API-Key`、两步 `UserResultByScreenName`(username→rest_id) + `UserTweets`(user_id→GraphQL 时间线)；递归取 Tweet、按 `legacy.user_id_str` 滤本人推、`rest_id` 去重、长推取 `note_tweet`，归一进 `ingest_all`（source=`X·<handle>`、prune 豁免、复用 classify/噪音过滤/翻译）。账号清单 `resources/sources/x_accounts.yaml`（15 官方号，可编辑）。docs 为 SPA、端点经实测得出；OpenAPI(`/openapi.json`) 是 catch-all `{path}` 代理。真机验证 15 账号 280 推、英文标题自动翻中。**MCP**：twtapi 另提供 MCP server（`https://mcp.twtapi.com/sse?mcp_key=…`，工具 UserTweets/Search/FollowersLight），MCP key 已存 `TWTAPI_MCP_KEY`——MCP 原生支持作单独架构议题评估（见正文/后续 ADR）。

## 后果

- 作者有了统一的「设置 · API」中枢：现在配 LLM key/路由即时生效；将来买 X（及其他廉价源）key 一填即用。
- **信源按 财经/新闻/论坛 三类总览**：财经类显出已接入的免费行情栈（说明候选付费源「可选·已被覆盖」），论坛类诚实暴露雪球的登录/隐私权衡——契合 §9 低噪音 + §11.3 暴露不确定性。
- 信源策略仍「一手优先、免费为主」；昂贵专业终端不绑死本工具。
- **财联社 / 东财免费科技适配器已接入**（`cls.py` / `eastmoney_news.py`，非 RSS、并入 `ingest_all`、prune 豁免、归一进 `news_items`）。待办：华尔街见闻-tmt 焦点 lane；macOS Keychain 存 key 留 M4。

## 备选与放弃

- **key 只存 .env（不做 UI）** — 放弃（要重启、作者要 UI 可改）。
- **Google News RSS 代 Reuters 作主源** — 放弃（跳转链、个人用 ToS、非一手）。
- **接 Wind/Choice/iFinD/Reuters 付费终端** — 放弃（太贵；Wind 还需 Windows，headless 不可用）。
- **把密钥写进 SQLite/日志** — 严禁（§11）；只进 gitignored `config.local.json`、脱敏回显。
