# ADR 0007 — 设置·API 配置中枢 + 顶级数据/新闻源可行性核查

- **状态：** 已接受（配置中枢 + Bloomberg 接入 + 移除太贵源）；财联社/东财免费适配器待接；X 待主人配 key
- **日期：** 2026-06-02
- **决策者：** 主人 + Claude

> 主人要点：①「是不是可以有一个专门的设置页面用来配置 API（含 LLM、资讯网站等）」；②核查朋友推荐的「最好的信息源」有无科技频道、能否接入——国内 万得/iFinD/Choice/DM(FICC)/财联社/华尔街见闻，国外 Bloomberg/Reuters；③「X 之后我会买 api 和 key，其他信源一样，先做好准备就行」；④随后：「太贵的数据信源可以去掉」。

## 背景

- 在此之前，LLM 厂商 key / 角色路由只能改 `backend/.env` 并重启；数据源没有「配 key」的地方。主人希望把「接口配置」做成一等公民，并为将来买入的付费源（先是 X）铺好即插即用的槽。
- 护栏：**密钥永不入库**、不打日志、本地优先、暴露不确定性、尊重限流（§5/§6/§11）。

## 决策

### 1. 运行时配置中枢（`runtime_config` + `/settings` + 设置页）

- **存储：** gitignored `data/config.local.json`（文件权限 0600），存 `secrets`（API key / base_url）与 `roles`（LLM 角色→provider:model）。启动时把 secrets **注入 `os.environ`**，使 litellm/gateway 与各信源适配器在**不重启**下即时读到（它们都走 `os.getenv`）。`.env` 仍支持；UI 存的值优先（便于即时改）。
- **安全（§11）：** GET 只回**脱敏**状态（末 4 位 `····9284`），POST **从不回传明文**、**绝不打日志**；写入 env 名经 **guard**（白名单 + `*_API_KEY/_BASE_URL/_KEY/_TOKEN/_SECRET/_URL` 模式），杜绝写任意环境变量（如 PATH）。
- **端点：** `GET /settings/config`（LLM 角色/厂商 + 数据源状态，全脱敏）、`POST /settings/secret`、`POST /settings/role`。
- **前端「设置」页：** LLM 角色（provider:model 可改）+ 厂商（key 密文/base_url）+ **「数据 / 信源 API」区**（注册表驱动，按需配 key、看状态徽标）。改动即时生效、无需重启。

### 2. 信源注册表（`news/source_registry.py`）

登记**需 key 或需专用适配器**的源 + 计算状态，驱动设置页。普通 RSS 仍在 `feeds.yaml`。

### 3. 源可行性核查结论（主人朋友清单 + 国际两大家）

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

### 4. 按主人意见「移除太贵的数据信源」

注册表只留**免费 / 极廉**：Bloomberg（免费 RSS）、财联社 / 东财（免费 API）、**X**（TwitterAPI.io 桥，约 $几/月，主人将买 key）。**Reuters/Wind/iFinD/Choice 已从注册表与 `.env.example` 删除**（要时按本 ADR 路径再接）。

## 后果

- 主人有了统一的「设置 · API」中枢：现在配 LLM key/路由即时生效；将来买 X（及其他廉价源）key 一填即用。
- 信源策略仍「一手优先、免费为主」；昂贵专业终端不绑死本工具。
- **财联社 / 东财免费科技适配器已接入**（`cls.py` / `eastmoney_news.py`，非 RSS、并入 `ingest_all`、prune 豁免、归一进 `news_items`）。待办：华尔街见闻-tmt 焦点 lane；macOS Keychain 存 key 留 M4。

## 备选与放弃

- **key 只存 .env（不做 UI）** — 放弃（要重启、主人要 UI 可改）。
- **Google News RSS 代 Reuters 作主源** — 放弃（跳转链、个人用 ToS、非一手）。
- **接 Wind/Choice/iFinD/Reuters 付费终端** — 放弃（太贵；Wind 还需 Windows，headless 不可用）。
- **把密钥写进 SQLite/日志** — 严禁（§11）；只进 gitignored `config.local.json`、脱敏回显。
