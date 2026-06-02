# 路线图与状态 — Augur

> **实时状态板。** 里程碑一移动就更新这里。它回答"什么已存在、下一步是什么？"
> `CLAUDE.md §12` 指向这里。

图例：✅ 完成 · 🟡 进行中 · ⚪ 未开始

---

## 当前焦点

**M1 + M1.5 + M1.6 已完成 ✅** —— 基础功能跑通 + UI/UX 精修到 Anthropic 级 + 一批体验功能（全市场模糊检索加股、拖拽换区、左栏可调宽、判断日记）。下一步 **M2（单股深度分析）**。

---

## M0 · 脚手架 ✅

- ✅ 仓库结构（`backend/ frontend/ resources/ data/ docs/`）
- ✅ `CLAUDE.md` 宪法（中文为主）、`.gitignore`（resources 入库 / data 忽略）、README
- ✅ 规划文档：架构、路线图、设计系统、ADR-0001/0002
- ✅ 项目记忆约定（`docs/memory/`）+ 前沿技术栈定稿

## M1 · 基础设施 + 自选分区 + K线 ✅（基础功能跑通）

**后端**（真实数据验证）
- ✅ `uv` 项目 + 依赖；FastAPI 在 `:8788` 启动；`config.py`（设置 + 角色路由）
- ✅ `llm/` —— litellm 网关：角色路由、自配 `base_url`、SSE 流式（`/llm/roles`、`/llm/chat`）
- ✅ `market/` —— `MarketAdapter` + FdrAdapter（美/中/港）+ PykrxAdapter（韩），Parquet 缓存优先 + 10min TTL
- ✅ `watchlist/` —— 两级分区 CRUD + `/reorder`，强制 `depth ≤ 2`；市场作正交过滤
- ✅ 端点：`/market/ohlcv`(日/周/月)、`/market/quote`、`/watchlist/*`、`/llm/*`
- ✅ `/market/search` —— M1.6 落地（本地目录 ∪ 东财实时联想，见下）

**前端**（Vite 8 + React 19 + Tailwind v4 + TanStack Query + Zustand + Zod）
- ✅ 脚手架 + 设计 token（纸感/蜡笔/Source Serif + 苹方）落进 `theme`
- ✅ 顶栏外壳（看/研/知 + 设置齿轮）+ 上下文面板 + 主舞台
- ✅ 设置：字号/行距/标题字体/主题/涨跌色习惯（实时 CSS 变量 + 持久化）+ LLM 角色状态
- ✅ 自选分区面板：市场过滤 + 两级树 + 内联新建/加标的 + 每行实时报价 + 点击选股
- ✅ K线（Lightweight Charts v5）：四市场真实数据、蜡笔纸感主题、明暗、周期切换、空态
- ✅ dnd-kit 拖拽换区/重排（M1.6 落地）

**已达成退出标准：** 点分区里的票 → 看到真实四市场 K 线；明暗/排版/涨跌色实时可调；各屏达设计师级完成度（已截图验证）。
**待补（不阻塞，挪入 M1.x / M2 期间）：** LLM 实时对话需主人在 `.env` 配 key；标的搜索 #9；前端拖拽排序；TanStack Router（当前用 Zustand 管视图，无 URL 路由需求暂缓）。

## M1.5 · UI/UX 精修（Anthropic 级）✅

按主人要求"一眼可感的精致、巧思、易用，且保持简洁"，对 M1 界面全面打磨：
- ✅ 动效（motion）：视图柔和转场、顶栏 Tab 滑动指示器(layoutId)、列表错峰入场、折叠动画、标的切换淡入；easeOutExpo 落定、尊重 `prefers-reduced-motion`
- ✅ 微交互：选中标的左缘陶土强调条、hover 操作淡入、行级过渡
- ✅ 加载骨架（纸感 shimmer）替代"加载中"文字；空态更有引导
- ✅ 全局精修：细滚动条（主题色）、优雅 `:focus-visible` 焦点环、选区色
- ✅ 组件精修：K线头"日内高/低"、研 CTA 卡片、设置卡片化、搜索 ⌘K 巧思
- 明暗双主题 + 看/研/知/设置 四视图截图自检通过、控制台零错、生产构建通过

## M1.6 · 体验功能（主人驱动）✅

- ✅ **全市场模糊检索加股**（`market/search.py` + `listings.py`）：本地目录（FDR 列表 + akshare A股中文名 + KOSPI/KOSDAQ 韩文名，缓存 Parquet）∪ 东方财富实时联想，统一打分去重。港股 MiniMax/智谱、拼音、中文、英文、韩文皆可命中；跨语言别名 `resources/sources/aliases.yaml`（海力士→KR:000660）。带缓存/超时/失败降级。
- ✅ **拖拽换区/重排**（dnd-kit）：标的跨板块移动 + 同区重排；后端 `PATCH /watchlist/items/{id}` + `/reorder`。
- ✅ **左栏可拖拽调宽**（`--panel-w`，夹 208–520px，持久化）；K 线 `autoSize` 自适应回流。
- ✅ **判断日记**（`journal/` 域）：个股 K 线下方，按日期倒序可折叠卡片，加/改/删/改日期；SQLite `journal_entries` + CRUD。是「研」支柱的轻量前身。
- ✅ **分区按"标的所在市场"显示**（`list_tree` 按内容剪枝）：分区可跨市场，选具体市场只露该市场有标的的分区+该市场的票；空分区只在「全部」出现（修主人反馈：`大模型` 不该出现在韩股）。
- ✅ 文案精简：去掉"数据源…仅供研究"、判断日记副标题/冗长 placeholder（主人要"功能摆在这就行"）。
- ✅ 删除按钮悬浮时整行让位，不再与价格重叠。
- ✅ 决策记录见 [ADR-0003](decisions/0003-search-journal-resizable.md)；数据源坑见 [memory/search-data-sources.md](memory/search-data-sources.md)。

## M2 · 单股深度分析 🟡（起步）

- ✅ **LLM 网关接通**：`.env`（DeepSeek + OhMyGPT 中转）+ `config.py` load_dotenv；四角色实测可用（chat/deep_research→claude-sonnet-4 中转、summarize/cheap→deepseek-chat）；`/llm/chat` SSE 流式验证。密钥永不入库（`.env.example` 模板）。
- ✅ **基本面**（`market/fundamentals.py`，yfinance）：市值/营收/利润/P-E，四市场，6h 缓存，缺数据降级。
- ✅ **财报分析面板**（K 线下方、可折叠）：历史趋势表，**季度（默认）/ 年度段控可切**，最新一期在右、横向可滚（默认滚到最新），关键行默认显示、「更多指标」展开，带财报链接；增长率一律**同比**（季度回退 4 列＝去年同季）避开季节性。_（AI 解读已先移除，待 `research/` 编排成熟后再以多轮带引用形式回归。）_
- ✅ **自选分区去重**：`create_section` 同层同名幂等（重复提交返回既有），根治"两个大模型"。
- ✅ LongBridge OpenAPI 调研：暂不采用（偏交易/需凭证/基本面薄），见 [ADR-0004](decisions/0004-llm-live-fundamentals-longbridge.md)。
- ⚪ `research/` 编排器：规划 → 收集（行情+基本面+新闻+网络/Deep Research）→ 综合 → 引用；`POST /research/stock` SSE；报告持久化。
- ⚪ 财报分析升级：接更结构化的财报（akshare/yfinance financials）、多轮、带引用。

## M3 · 新闻聚合 + 趋势日报 + 投资机会 🟡（推进中）

详见 [ADR-0005](decisions/0005-news-classification-translation-opportunities.md)。
- ✅ **信源（一手优先，~90 源）**：`feeds.yaml` 扩到 **~90 个一手为主的顶级源**——**央行/监管/官方经济数据/公司新闻室·IR/官方研究博客 > 精英二手**（美联储全家 FOMC/Powell/演讲/FEDS Notes + 地区联储、BEA/Census/BLS、SEC/FTC/DOJ反垄断、Treasury 拍卖；OpenAI/DeepMind/Google Research/MSR/Meta/NVIDIA/Apple ML 等官方实验室；Intel/AMD/Micron/Broadcom/Arm/SK hynix 芯片新闻室·IR；NASA/JPL/ESA/Rocket Lab；WSJ/FT/The Information/SemiAnalysis 二手）。workflow 4 路并行调研 + httpx/feedparser 硬验证 **90/93 实测可抓**（个别 Cloudflare 源数据中心 IP 被挡、住宅 IP 可达）。`ingest.py` **并发**抓取 + 近 30 天过滤 + url 去重；`news_items`/`news_reports`/`news_opportunities` 表 + 幂等迁移。arXiv 论文流量太大暂列「论文 lane」待办。
- ✅ **主题分类**：`classify.py`+`themes.yaml`（**10 主题**含新增 **macro 宏观/政策**＝美联储/经济数据/监管；规则法、ASCII 词边界匹配、CJK 子串），ingest store-time 打标 + backfill；日报/要闻按主题分组。
- ✅ **标题翻译**：`translate.py`（en/ko→zh，cheap 角色批量编号清单 + JSON mode，缓存 `title_zh`，隐私优先不用 DeepL/Google）。
- ✅ **趋势日报**：`generate_report_stream`（summarize，按主题分组喂 prompt，SSE 流式落库，一天一份覆盖）。
- ✅ **今日投资机会**：两阶段防幻觉——LLM 给「公司名+市场+code_guess」→ `market.search` 接地真实 `MARKET:CODE`（弱模糊判未解析）+ 交叉自选高亮；`GET/POST /news/opportunities`，前端机会卡（chip 跳「看」、已关注陶土高亮、非投资建议脚注）。
- ✅ APScheduler 每日 07:30：抓取+翻译+日报（`scheduler.py`，失败不阻断）。「知」UI：日报列表＋正文＋今日机会＋按主题分组要闻流。
- ✅ **噪音过滤（两层）**：① `filter.py` 规则滤纯盘面/价格波动（摄取时，留基本面/宏观/风险）；② `relevance.py` **cheap 小模型批量判投资相关性**（主人反馈仍有无关新闻 → 不心疼 token 用小模型筛；`relevance` 列 0未判/1留/2弃，feed/日报/机会取 `relevance≠2`、未判仍显＝优雅降级，refresh 时跑、失败不阻断）。真机实测 240 判/56 弃：准滤 MarketWatch 退休理财鸡汤、消费手机/游戏/车、纯流向数据，留 HBM 涨价/算力/并购/政策。
- ✅ **信源精简**：韩源砍到 1（The Elec），聚焦美股 + 国内源；`_prune_removed_sources` 让库随 feeds.yaml 自愈。
- ✅ **个股「相关资讯」（API + 聚合双源）**：`GET /news/for` = **雅虎逐-ticker 新闻 API**（`ticker_news.py`，yfinance `.news`，四市场按 ticker 直取该公司新闻、兼容新旧 .news 结构、3h 缓存）**∪** 聚合流按公司名（中/英）匹配（中文翻译版），url 去重、时间倒序、失败降级。真机验证 NVDA/三星/腾讯 API 均有结果（Marvell/HBM/AI agent…）。前端 StockNews 自动渲染（响应同 NewsItem 形）。
- ✅ **个股一手「一条龙」起步（SEC EDGAR）**：`edgar.py` 美股 ticker→CIK（官方 `company_tickers.json` 缓存 7 天）→ `data.sec.gov` submissions JSON → 高信号表单白名单（8-K/10-Q/10-K/20-F/6-K/S-1/424B/13D/13G/DEF 14A，**不收 Form 4 噪音**）；表单 + 8-K 事项码给**确定性中文标签**（零 token 不幻觉）；可配 SEC UA + ≤10 req/s + 6h 缓存 + 失败降级。`GET /news/official` → K 线页**「官方文件 · SEC」**段（陶土等宽 form 徽标 + 中文标签 + 申报日 + 直链）。真机验证 RKLB/NVDA/AAPL/TSLA/AMD 全中。详见 [ADR-0006](decisions/0006-first-hand-sources-edgar-x.md)。
- 🟡 **X 官方号——准备就绪（待主人配 key）**：调研定论 关键账号只活在 X、官方 API 官僚、Nitter 已死；选定**商业桥 TwitterAPI.io**（无需主人 X 账号、约 $几/月、隐私权衡＝桥知道轮询了哪些公开账号）。已在「设置 · 信源 API」留可换桥槽（配 `TWITTERAPI_KEY` 即启用），`XBridgeAdapter` 待接。见 ADR-0006 第 3 节。
- ✅ **设置 · API 配置中枢 + 顶级源核查**：`runtime_config`（gitignored `data/config.local.json`、注入 env 即时生效、脱敏回显、写入名 guard）+ `/settings` + 「设置」页（LLM key/base/角色路由 + 数据信源 key 皆可 UI 改、无需重启）+ `news/source_registry.py`。**Bloomberg 科技/市场**免费官方 RSS 已接入；核查主人朋友清单后**按其意见移除太贵源**（Reuters/LSEG、万得 Wind、同花顺 iFinD、东财 Choice），留免费 Bloomberg/财联社/东财 + 极廉 X。详见 [ADR-0007](decisions/0007-api-config-and-source-feasibility.md)。
- ✅ **设置 v2（主人反馈：多页 + Anthropic 风 + 动态 LLM + 测试按钮）**：左栏变真导航（外观/模型/数据信源，`store.settingsPage`）；**LLM 改可动态增删连接列表** `{name,base_url,api_key,model}`（一律 OpenAI 兼容，角色→连接 指派，**测试连接**端点实测 DeepSeek/relay 通、伪 key 报错），`runtime_config` 首次自动从 `.env` 迁移（迁出 relay+deepseek、四角色就位、不中断）；Anthropic 风格行 + 信源**支付徽标**（微信/支付宝优先）。对抗式 code-review workflow（3 审 + 核验）0 确认问题。详见 [ADR-0008](decisions/0008-settings-v2-dynamic-llm-connections.md)。
- ✅ **付费源支付方式调研**（5-agent workflow）：哪些支持微信/支付宝优先——LLM 优先 DeepSeek/国产/支付宝可充中转，X 桥无支付宝（加密/虚拟卡），中文终端太贵全弃。见 [memory/payment-methods-sources.md](memory/payment-methods-sources.md)。
- ✅ **「知」二层噪音过滤（从严）+ 按天**：`filter.py` 规则之上加 `relevance.py`（cheap 小模型判投资相关性，**从严**：丢娱乐/消费/生活/**标题党/清单体/泛泛展望/纯涨跌**；feed/日报/机会取 `relevance≠2`）；从严实测 400 判/137 弃。**日报与机会改喂当天全部新闻**（`items_for_day` 按主人时区，长上下文吃得下，不再只取最近 N 条）；**今日要闻按天归类**（今天/昨天/日期）。
- ✅ **个股相关新闻接 API + LLM 清洗**：`ticker_news.py`（yfinance `.news` 逐 ticker，四市场）∪ 聚合流按名匹配，再经 cheap LLM **清洗**（`stock_news_clean.md`：去标题党/无关、译非中文、去重，缓存 1h）。真机验证 NVDA 5 条全中文、去重、无标题党。
- ✅ **前端打磨（主人反馈）**：① 看·K 线下方模块（财报/相关资讯/判断日记）**可拖拽重排**（dnd-kit + 持久化 `kanOrder`，手柄顶部居中 hover 浮现，仅手柄可拖、模块内交互不受影响）；② 移除「官方文件·SEC」UI 段（一般不看；`edgar.py` 后端保留）；③ **设置页重做为卡片网格**（填满舞台宽度、按钮内联，修「没拉伸/按钮换行/不美观」）。真机验证、零控制台错。
- ✅ **免费中文科技源接入**：`cls.py`（财联社科创电报 `depth/assembled/1111`，sign=MD5(SHA1(sorted_qs))、appName=CailianpressWeb；旧 nodeapi 路径已死）+ `eastmoney_news.py`（东财 `search-api-web` JSONP，按 人工智能/半导体/算力/机器人/大模型/芯片 关键词检索）。非 RSS 适配器并发并入 `ingest_all`，`source` 名（财联社/东方财富）经 `_prune_removed_sources` **豁免**（否则不在 feeds.yaml 会被误删）；复用 classify + 噪音过滤、中文免翻。真机验证：财联社 25 + 东财 42 条、二次 ingest 不被 prune 删。
- ⚪ 华尔街见闻-tmt 焦点科技 lane、个股 IR 新闻室·官方 X 并入「一条龙」、KR DART / CN cninfo 一手扩展、arXiv 论文 lane、机会接地阈值调优、按**自选分区**聚合、信源健康度。

## M4 · 原生打包 + 打磨 ⚪

- ⚪ Tauri 2 外壳；PyInstaller sidecar；原生窗口/菜单
- ⚪ macOS Keychain 存密钥；数据移到 `~/Library/Application Support/Augur/`
- ⚪ DMG 构建；应用图标；动效/性能打磨
- ⚪ 明暗主题定稿（都保持暖色）

---

## 待办 / 想法（未排期）

- 组合视图（只读，不含持仓/交易）
- 跨市场对比与板块热力图
- 由 LLM 用量日志驱动的成本面板
- 提醒规则（"日报里提到 X 就通知我"）
- 研究报告导出 PDF/Markdown
