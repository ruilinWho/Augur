# ADR 0006 — 顶级一手信源战略：~90 源扩容 · 个股 EDGAR 一条龙 · X 官方号选项

- **状态：** 已接受（信源 + EDGAR）；X 官方号**待主人定夺**（见下）
- **日期：** 2026-06-02
- **决策者：** 主人 + Claude

> 主人原话（要点）：①「知」里的美股信源还不够好，**调研怎么找到最好的美股信源**；②每天找更多信息（**10x**）——「更多的信息代表更多的机会」，但**一定要用顶级的、一手的信源，这是整个系统的价值、生死攸关所在**；③考虑接入 X(Twitter) 官方号（Anthropic/NVIDIA/OpenAI…）；④对关注的股票，**一条龙接入所有信源**（官方网页、官方 X…），「基于 LLM 的能力可以做到吧？不要省 Token」。

## 背景

- M3 起步版 41 个泛源里，行情/宏观只有 CNBC + 华尔街见闻两条二手；前沿方向虽好，但**缺一手**（央行原文、官方数据、公司新闻室、监管文件、个股财报）。
- 护栏：只研究不交易、不构成建议、**暴露不确定性**、**本地优先**（数据只发往主人配置的厂商）、尊重限流（§1/§5/§11）。
- 用 4 路 workflow agent 并行调研（美股宏观/监管 · AI/芯片/航天一手 · X 接入可行性 · 个股 EDGAR/IR），再**自己 httpx+feedparser 硬验证**（不信 agent 的「verified」）。

## 决策

### 1. 信源战略 = 一手优先；~90 源（10x）

**取舍铁律：一手 > 二手。** 优先级：**央行/监管机构/官方编号数据/公司新闻室·IR/官方研究博客 ＞ 精英二手（WSJ/FT/The Information/SemiAnalysis…）＞ 泛聚合**。理由：系统价值＝信源质量；二手会延迟、转述失真、夹带噪音。

`feeds.yaml` 从 41 扩到 **~90**，硬验证 **90/93 可抓**（个别 Cloudflare 源数据中心 IP 被挡、主人住宅 IP 可达，已注明并保留——ingest 容忍单源失败、不会因偶发 403 删源）。新增主力：

- **宏观/政策（全一手）**：美联储全家（新闻稿 / FOMC / 演讲 / 证词 / 主席 Powell / FEDS Notes）+ 地区联储（纽约 Liberty Street、亚特兰大 Macroblog、达拉斯…）；**官方经济数据** BEA（GDP/PCE）、Census（零售/耐用品/房屋）、BLS（就业/CPI/PPI）；**监管** SEC / FTC / DOJ 反垄断；财政部国债拍卖。
- **AI 一手**：OpenAI、DeepMind、Google AI/Research、Microsoft Research、Meta（新闻室+工程）、NVIDIA（博客+技术博客）、Apple ML、AWS ML、BAIR、Hugging Face；Anthropic/Mistral 无官方 RSS → 用 GitHub 镜像。
- **芯片一手**：NVIDIA/Intel/AMD/Micron/Broadcom/Arm/SK hynix 新闻室·IR。
- **航天一手**：NASA（新闻稿/科学/突发）、JPL、ESA、Rocket Lab IR。
- **精英二手**：WSJ Markets、MarketWatch、FT、The Information、Stratechery、MIT Tech Review、SemiAnalysis、IEEE Spectrum。

**新增 `macro` 主题（宏观/政策）**：把 Fed/CPI/GDP/监管类从 `markets` 拆出，避免污染前沿主题；含公司名时仍先被 ai/chips 截走（多标签兼得）。10 主题全链路打通。

**arXiv 论文**（cs.AI/LG/CL/CV/RO…，已验证可抓）**暂不并入主清单**：量太大（单 cs.CV 一天数百），会淹没日报与机会抽取。列为「论文 lane」待办——未来单独通道 + 采样，不混入日报。

### 2. 个股「一条龙」一手 = SEC EDGAR（美股先行，确定性而非 LLM 抓取）

主人问「基于 LLM 一条龙接入个股所有信源，做得到吧」。**做得到，但一手文件的「获取」要的是「不编造」**——因此用**结构化官方 API**，不用 LLM 抓网页：

- `edgar.py`：`US:TICKER` → ticker→CIK（官方 `company_tickers.json`，缓存 7 天）→ `data.sec.gov/submissions/CIK##########.json` → **高信号表单白名单**（8-K/10-Q/10-K/20-F/6-K/S-1/424B/SC 13D/SC 13G/DEF 14A；刻意**不收 Form 4** 内部人交易——量大噪音高）→ 归一化条目。
- **表单类型 + 8-K 事项码给确定性中文标签**（重大事件/季报/年报/经营成果与财务状况（财报）/高管变动/股东投票结果…）——标准化类型用固定对照表即可，**零 token、不幻觉**，比 LLM 翻译更准更快。
- SEC 公平获取：可配置 UA（`config.sec_user_agent`，默认非 PII；主人可在 `.env` 配 `AUGUR_SEC_USER_AGENT="名字 邮箱"` 最稳妥）、进程内 **≤10 req/s** 节流、**6h 缓存**、失败降级空表。
- `GET /news/official?symbol=` → 前端 K 线页**「官方文件 · SEC」**段（form 陶土徽标 + 中文标签 + 申报日 + 直链原文），其上「一条龙」骨架预留 IR 新闻室 RSS、官方 X。
- 港/A/韩官方披露口径不同：**DART**（韩，有干净 REST API + 免费 key，`corpCode.xml` 桥接 `KR:005930`）最可行，**cninfo**（A，非官方 JSON POST，脆）次之，**HKEXnews**（港，无机器 feed）暂缓。

**LLM 的正确位置**：不在「找文件」，而在「读文件内容做综合带引用」——留给 M2 的 `research/` 多轮编排。

### 3. X(Twitter) 官方号 —— 选项与权衡（**待主人定夺**）

调研结论（2026-06）：主人关心的账号（OpenAI/NVIDIA/@sama/@elonmusk…）**只活在 X**；Bluesky/Mastodon 上同名号要么不存在要么 0 帖（连 LeCun 都回 X 了）。而 X 没有免费、稳定、隐私友好的官方 RSS：

| 路径 | 现状（2026） | 裁决 |
|---|---|---|
| 官方 X API | 改按量计费、Basic 对新开发者关闭、需开发者账号 + OAuth | 官僚、政策脆，不作主力 |
| Nitter | 2024 已停摆，公共实例靠激进限流苟活，不适合无人值守 | 弃 |
| RSSHub（自托管） | Twitter 路由需塞自己的 X 登录 cookie（封号风险）+ 维护成本高 | 仅当主人要「零第三方」且接受 cookie 风险 |
| **TwitterAPI.io（商业桥）** | `GET /twitter/user/last_tweets?userName=`，X-API-Key、**无需主人 X 账号**，~$0.15/1k 推、号称 99.99% | **推荐主力** |
| SocialData | 同模式，~$0.20/1k | 备选/降级 |
| Bluesky/Mastodon 原生 RSS | 免费、最私密，但前沿账号几乎没人在用 | 顺带订阅，不作主力 |

**隐私权衡（§5 关键）**：商业桥只需公开用户名 + API key，**不碰主人 X 账号/任何 PII**，符合「经桥抓公开数据可接受」；残留暴露＝桥会知道你**轮询了哪些账号**。若不可接受，唯一零第三方路径是自托管 RSSHub + 自己 cookie（封号风险更糟）。

**为何不擅自接**：X 接入要花钱（第三方/官方）、要主人去办 key、且有上述隐私权衡——触及 §5/§11，**必须主人拍板**。故先把可换桥的 `XBridgeAdapter` 接口留好（凭 key 启用），方案与权衡呈给主人选。

## 后果

- 「知」日报/机会的输入从泛二手升级为**一手为主、~90 源**，覆盖宏观→公司→监管全链；macro 主题让政策面单列、不污染前沿。
- 个股页多了**官方一手文件**一栏（美股），是「一条龙」的第一块，也是未来 `research/` 深读的素材来源。
- 新增依赖面小（EDGAR 仅 httpx，无新三方）；X 一旦定案再加桥适配器 + ADR 补记。

## 备选与放弃

- **arXiv 并入主 feed** — 放弃（量太大淹没日报，改「论文 lane」待办）。
- **LLM 抓个股官网/X 找文件** — 放弃（会幻觉 URL/数字；一手获取要确定性，LLM 用于读不用于找）。
- **官方 X API / Nitter 作主力** — 放弃（官僚/已死）。
- **EDGAR 全市场 8-K firehose 进日报** — 放弃（全市场噪音；个股按需取更干净）。
- **把 SEC 等源因偶发 403 自动删源** — 禁止（数据中心 IP 风控≠源失效；库随 `feeds.yaml` 自愈，靠 ingest 容错而非删源）。
