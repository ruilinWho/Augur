# 路线图与状态 — Augur

> **实时状态板。** 里程碑一移动就更新这里。它回答"什么已存在、下一步是什么？"
> `AGENTS.md §12` 指向这里。

图例：✅ 完成 · 🟡 进行中 · ⚪ 未开始

---

## 当前焦点

**M1 / M1.5 / M1.6 / M2 已完成 ✅，M3「知」推进中，M3.5 夜间优化 + 第 4 支柱「记」已落地 ✅。** 四根支柱齐活：**看**（四市场 K 线 + 基本面 + 财报趋势 + 判断日记 marker + 52 周位置 + AI 相关资讯摘要）、**研**（单股深度研究编排：确定性数据 → 长上下文模型流式带引用报告 + 导入研报 + 主动决策框架；官方 OpenAI Deep Research API 路线已定，见 ADR-0011）、**知**（~90 源摄取 + X + Reddit + 分类 + 翻译 + 趋势日报 + 要事/机会 + 决策工作台 + 个股叙事 + 每股专属信源回流 + 噪音过滤 + 自动生成）、**记**（极简 markdown 笔记）。目标已升级为 **decision-grade active investing workbench**（见 [ADR-0010](decisions/0010-decision-grade-active-investing-workbench.md)）：让作者仅通过 Augur 做出专业、及时、全面、主动/激进但可追溯的投资决策。下一步：官方 Deep Research job 化接入、知的分区日报、雪球/小红书真实适配器、更多一手源（KR DART / CN cninfo / 论文 lane 等）。

---

## M3.5 · 夜间全面优化 + 第 4 支柱「记」✅（10 领域审计驱动）

作者「头脑风暴并全面优化」+ 新需求「一个可以『记』的板块，记录与个股无关的长文」。13-agent 审计（10 子系统 + 3 产品视角）→ 优先级实现 → 对抗式复查。

- ✅ **第 4 支柱「记」**：`notes/` 域（schemas/service/router + `notes` 表）+ `GET/POST /notes`、`GET/PATCH/DELETE /notes/{id}`。前端「记」Tab（看·研·知·记）＝`NotesNav`（列表：置顶在前 + 预览 + 相对时间 +「＋新建」）+ `NotesView`（标题 + 正文 编辑/预览 + 置顶/删除 + **防抖 700ms 自动保存**带状态）。与个股无关的长文（市场随想/方法论/复盘）。**共享 Markdown 组件** `components/Markdown.tsx`（研/导入研报/记 共用，导入研报因此获得表格/链接）。
- ✅ **后端稳健性**：SQLite **WAL + busy_timeout**（修后台调度+请求线程并发写锁）；**LLM token 用量落库** `/llm/usage`（§6 死表终于写入，实测已记 18 调用/9万 token）；litellm 静音保险；web_search 仅注入研/对话角色；Parquet 原子写 + 坏缓存自清；EDGAR ticker 缓存 TTL 真生效；财联社 errno 抛错（源健康度正确记失败）；**A股北交所 BSE 解析** `symbols.cn_exchange`（沪/深/北交所单一真相，FDR 不支持时优雅降级）；个股资讯 `_feed_matches` 词边界去误配；relevance 改 ASC（修积压尾部泄漏）；调度补「今日机会」；SSE 防代理缓冲头 + 错误帧统一 [DONE] 收尾；CORS 放行任意本地端口；`_items_between` 去重。
- ✅ **前端稳健性 + 美学**：**SSE 错误吞噬修复** `consumeSSE`（error 移出 JSON.parse 的 catch，三处合一）；`HttpError.status` 判 404 空态（不再脆弱中文子串）；全局 `ErrorBoundary`；`MotionConfig reducedMotion`；细粒度 `useUI` selector（修拖栏重渲染）；**K 线蜡烛半透明蜡笔纸感**（实体 0.5/描边 0.9/影线 0.68）；平盘态；报价新鲜度只显示更新时间、不暴露内部适配器名；基本面/财报「失败≠无数据」；研报常驻决策边界说明；`--measure` 行宽 + 行距随设置；齿轮右对齐；`#fff`→`--accent-ink`；删死代码（Placeholder/themeLabel）。
- ✅ **前端全局布局 / 文案审计（2026-06-04）**：主舞台直系内容默认全宽，移除笔记 920px、空态 320px、设置旧 640/1280px 等遗留窄列；「研/知/记/看/自选/导入研报/专属信源」空态与生成态收敛为状态短句；设置页去长说明，外观页新增**栏宽状态 + 恢复默认**（重置左栏、知二级、信源二级、看三列、K线下方模块顺序）；窄窗口下设置行和页头自动换行防溢出。
- ✅ **决策级目标 +「知」决策工作台（2026-06-04）**：项目目标从“研究辅助”升级为**决策级主动投资工作台**（ADR-0010）；「资讯」第三层新增**决策**页，集中显示当日主动机会、风险/反证、催化与关联标的，机会/标的 chip 可直达「看/研」；提示词同步改为输出动作倾向、触发条件、反证条件与不确定性。
- ✅ **资讯 / 记 / 设置模型审美与功能修正（2026-06-04 深夜）**：① source lane 的 cluster scope 改为按真实 lane 分离（`src:Reddit:*` / `src:X:*` / `src:雪球:*`），修 Reddit/雪球/小红书误读新闻/推特要点旧缓存；② cluster 标题/理由清洗 `[47][51]` 这类裸编号；③「决策」页增加当日独立信源数，强化覆盖意识；④「看·相关资讯」改为 **AI 摘要卡**（`/news/for/brief` + `stock_news_brief.md`），不再铺直接新闻列表；⑤「记」去冗余标题/空态文案，保留新建、标题、正文、预览、置顶、删除、自动保存；⑥ 设置·模型连接卡默认折叠成紧凑摘要，编辑时再展开字段，适合很多模型卡；⑦ 数据/信源名称改为唯一官方名（Bloomberg/财联社/东方财富/X/雪球/RSS），Bloomberg 频道变为可配置项并实际过滤 RSS；⑧ 雪球/小红书新增「关注用户」与「个股/关键词」配置槽，UI lane 明确待接入，不伪装抓取；⑨ 设置页用量卡、模型编辑字段、信源「测试 / 保存 / 添加」按钮做统一操作列对齐，避免宽屏下错位。
- ✅ **看·个股头部信息层级（2026-06-05）**：K 线头部从“日内高低 / 数据源 / 52 周区间 / snapshot 指标条”收敛为单一信息带：当前价/涨跌、52 周位置、市值、市盈率、净利率、更新时间；删除 `fdr/yfinance` 等内部适配器名和日内高低，统一标签、数值、位置条的字体与间距。见 [memory/view-stock-info-hierarchy.md](memory/view-stock-info-hierarchy.md)。
- ✅ **投资者工作流**：看·K 线叠**判断日记 marker**（写判断那天落到 K 线）+ **52 周位置**（当前价分位 + 位置条）；知·个股叙事头部 **看/研 直通 chip** + 生成时间 + 「自生成后新增 N 条」新鲜度；自选分区计数去重；资讯·总结页**一屏一主操作**（一键生成统管，藏子按钮）；设置看 token 用量；稳定 list key。
- ✅ **测试**：补 `backend/tests/test_pure.py`（20 项纯函数，零网络，`uv run pytest` 全过）——填补「装了 pytest 但零测试」缺口。
- ✅ **第二轮作者反馈**：① 日报/研报正文**占满全宽**（撤 `--measure`，记入个人记忆）；② 资讯按**市场/仅自选**过滤；③「自上次以来」放宽窗口（自适应天数 + 上限 500）、**默认收起**；④ **23:30 当天归档** scheduler（没手动点也存档每天）；⑤ 后端 §5 加固：共享 `news/_http.py`（统一 UA + 退避重试）、未来日期钳制、refresh 互斥、twtapi 递归深度上限、directed lang 按市场。
- ✅ **新闻自动标股（不限自选，"发现机会"）** `stock_tag.py` + `grounding.py`：对相关新闻批量 LLM 识别涉及的上市公司 → **确定性接地**到真实 `MARKET:CODE`（防编造，与机会识别同款 grounding）→ 写 `news_item_symbols`（`matched_by='llm'`）。新闻卡的股票 chip 不再只显自选——**自选股=陶土+圆点、LLM 发现的非自选股=中性**，都可点→看。`news_items.tagged` 标记每条只标一次；`linker.attach_symbols` 带 `in_watchlist`。真机验证「携手黑石、高盛…」→ US:BX/US:GS、Broadcom→US:AVGO。
- ✅ **垃圾过滤/翻译彻底化**：relevance/translate 改**循环到清空**（×40 批、≤60 轮≈2400 条/次），不再 150/400 封顶——英文标题都翻、无信息熵的都滤（作者「不心疼 token」）。
- 全程 ruff + tsc + build + pytest 全过；真机验证四市场报价 / notes CRUD / token 用量 / 北交所降级 / 新闻标股接地。

---

## M0 · 脚手架 ✅

- ✅ 仓库结构（`backend/ frontend/ resources/ data/ docs/`）
- ✅ `AGENTS.md` 项目宪法（中文为主）+ `CLAUDE.md` 兼容指针、`.gitignore`（resources 入库 / data 忽略）、README
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
**待补（不阻塞，挪入 M1.x / M2 期间）：** LLM 实时对话需作者在 `.env` 配 key；标的搜索 #9；前端拖拽排序；TanStack Router（当前用 Zustand 管视图，无 URL 路由需求暂缓）。

## M1.5 · UI/UX 精修（Anthropic 级）✅

按作者要求"一眼可感的精致、巧思、易用，且保持简洁"，对 M1 界面全面打磨：
- ✅ 动效（motion）：视图柔和转场、顶栏 Tab 滑动指示器(layoutId)、列表错峰入场、折叠动画、标的切换淡入；easeOutExpo 落定、尊重 `prefers-reduced-motion`
- ✅ 微交互：选中标的左缘陶土强调条、hover 操作淡入、行级过渡
- ✅ 加载骨架（纸感 shimmer）替代"加载中"文字；空态更有引导
- ✅ 全局精修：细滚动条（主题色）、优雅 `:focus-visible` 焦点环、选区色
- ✅ 组件精修：K线头"日内高/低"、研 CTA 卡片、设置卡片化、搜索 ⌘K 巧思
- 明暗双主题 + 看/研/知/设置 四视图截图自检通过、控制台零错、生产构建通过

## M1.6 · 体验功能（作者驱动）✅

- ✅ **全市场模糊检索加股**（`market/search.py` + `listings.py`）：本地目录（FDR 列表 + akshare A股中文名 + KOSPI/KOSDAQ 韩文名，缓存 Parquet）∪ 东方财富实时联想，统一打分去重。港股 MiniMax/智谱、拼音、中文、英文、韩文皆可命中；跨语言别名 `resources/sources/aliases.yaml`（海力士→KR:000660）。带缓存/超时/失败降级。
- ✅ **拖拽换区/重排**（dnd-kit）：标的跨板块移动 + 同区重排；后端 `PATCH /watchlist/items/{id}` + `/reorder`。
- ✅ **左栏可拖拽调宽**（`--panel-w`，夹 208–520px，持久化）；K 线 `autoSize` 自适应回流。
- ✅ **「看」自选改三列 Miller（作者反馈：标的多了单列太挤要频繁滚动）**：仿「知」多列，**一级板块 | 二级板块(+「直属」) | 标的** 三列；选一级→中列显其子板块+直属、右列显标的，点二级→右列换该子板块标的。**每列可拖宽（`kanColW` 持久化）+ 可一键收起成竖条（`kanColClosed`）**。保留全部：市场过滤、检索加股、双击重命名、增删板块/标的、报价行、点击选股；**完整 dnd**——标的列内重排 + **跨列把标的拖到左/中列板块即换区**（`closestCorners`，sec 落点 move / item 落点 reorder）+ **板块本身可拖排序（一/二级两层，`SecRow` sortable+droppable，乐观 `secOrd`/`subOrd`）**。**板块重排市场安全**：只传可见子集，后端 `_reorder_sections` 锚定槽位、隐藏兄弟不动（验证 US 视图重排 `[A,B,C]→[C,A,B]` 时隐藏韩股板块 H 在 ALL 仍原位）。`WatchlistPanel` 为 `Column`+`SecRow`+`StockRow`，`.layout.kan` grid `auto 1fr`。
- ✅ **判断日记**（`journal/` 域）：个股 K 线下方，按日期倒序可折叠卡片，加/改/删/改日期；SQLite `journal_entries` + CRUD。是「研」支柱的轻量前身。
- ✅ **分区按"标的所在市场"显示**（`list_tree` 按内容剪枝）：分区可跨市场，选具体市场只露该市场有标的的分区+该市场的票；空分区只在「全部」出现（修作者反馈：`大模型` 不该出现在韩股）。
- ✅ 文案精简：去掉"数据源…仅供研究"、判断日记副标题/冗长 placeholder（作者要"功能摆在这就行"）。
- ✅ 删除按钮悬浮时整行让位，不再与价格重叠。
- ✅ 决策记录见 [ADR-0003](decisions/0003-search-journal-resizable.md)；数据源坑见 [memory/search-data-sources.md](memory/search-data-sources.md)。

## M2 · 单股深度分析 🟡（起步）

- ✅ **LLM 网关接通**：`.env`（DeepSeek + OhMyGPT 中转）+ `config.py` load_dotenv；四角色实测可用（chat/deep_research→claude-sonnet-4 中转、summarize/cheap→deepseek-chat）；`/llm/chat` SSE 流式验证。密钥永不入库（`.env.example` 模板）。
- ✅ **基本面**（`market/fundamentals.py`，yfinance）：市值/营收/利润/P-E，四市场，6h 缓存，缺数据降级。
- ✅ **财报分析面板**（K 线下方、可折叠）：历史趋势表，**季度（默认）/ 年度段控可切**，最新一期在右、横向可滚（默认滚到最新），关键行默认显示、「更多指标」展开，带财报链接；增长率一律**同比**（季度回退 4 列＝去年同季）避开季节性。_（AI 解读已先移除，待 `research/` 编排成熟后再以多轮带引用形式回归。）_
- ✅ **自选分区去重**：`create_section` 同层同名幂等（重复提交返回既有），根治"两个大模型"。
- ✅ LongBridge OpenAPI 调研：暂不采用（偏交易/需凭证/基本面薄），见 [ADR-0004](decisions/0004-llm-live-fundamentals-longbridge.md)。
- ✅ **「研 · 单股深度研究」编排器**（`research/`）：`gather(symbol)` 收集**已有确定性数据**（display_name + 价格摘要 1y + 基本面快照 + 季度财报趋势 + 个股相关新闻[已清洗] + SEC 申报）并给**编号引用源**（新闻+申报各带 `[n]`）→ `_format_data` 拼事实块 → **deep_research 角色（长上下文模型）SSE 流式** Markdown → 落库（`research_reports` 表，一股一份、重生成覆盖、ON CONFLICT(symbol)）。提示词 `resources/prompts/research_stock.md` 由 4-agent 设计 workflow（thesis/fundamentals/catalyst 三视角 → 评审合成）产出：**先一句话结论 + 多空核心看点 → 近期催化与动态（重心）→ 基本面与估值 → 财务趋势 → 多空逻辑 → 风险与不确定性 → 来源**；八条**防幻觉铁律**（只用所给数据、不编造数字、不假装有网络/分析师预期/估值模型/目标价、事实 vs 推断对冲、单源标题党对冲、内联 `[n]` 引用）。`GET /research/stock`（404=暂无）+ `POST /research/stock/generate`（SSE，check_ready deep_research）。前端**「研」Tab** = `ResearchView`：选中标的 → 生成按钮 → 流式渲染（自写轻量 Markdown：## 标题/`>` 引用块/`-` 列表/`|表格|`/**强调**/`[n]` 上标**可点跳来源 url**）+ 持久化报告加载 + 「重新生成」+ 空态引导；决策级边界说明。真机验证 US:NVDA 端到端（128 deltas、含财务表 + 12 条带 url 引用 + 诚实点出数据盲区）。ruff + tsc + build 全过。
- ✅ **研 · 导入研报**（作者需求）：`imported_reports` 表 + CRUD（list/add/update/delete/reorder）+ `/research/imported`；ResearchView 下方「导入研报」——粘贴他人 markdown 研报、**一股可多份**、记录创建时间、**dnd 拖拽排序**、删除、markdown 渲染（复用 `Digest`）、每份下方**「我的评论」**（blur 自动存）、正文可「编辑」。
- ✅ **作者反馈批次（2026-06）**：① **「看」未自选股一键「＋ 自选」**（`AddToWatchlist`：头部按钮 → 下拉选一级/二级分区或现建新分区加入；已自选则不显）；② **修「研」点股弹回看**（`store.pickInView` 在研留研、在看留看，左栏 StockRow/PlainStockRow 改用之）；③ **数据信源「测试」按钮**（`source_test.test_source` + `POST /settings/source/test`：行情栈/财联社/东财/RSS/Bloomberg/Reddit/X 真探活，雪球/小红书才显待接入，twtapi `ping()` 轻量 <1s 且清楚区分 key 无效/额度用完/账号不存在；错误统一经 `diagnose_problem` 翻成中文问题诊断，不显示异常类名或第三方英文报错；信源详情页结果全宽换行，不再被 150px 省略）；④ **API key 长期明文**（ConnectionCard/SourceDetail 去 `setKey('')`+加 `useEffect` 回灌，保存后仍可见，见 [[single-user-local-convenience]]）；⑤ **连接级「联网检索」开关**（Qwen `enable_search`，替代办不了的 Perplexity）；⑥ 展示名去 Technology 后缀、总览按钮等宽去 ✨、改为决策级边界说明、列2「全部」+空直属不显、日报段头不重叠。
- ⚪ **research/ 深度增强（下一步）**：按 [ADR-0011](decisions/0011-research-deep-research-api-strategy.md) 接 OpenAI Responses API 的 `o3-deep-research` / `o4-mini-deep-research`（background job + web/file/MCP tools + annotations 来源），现有 Augur 本地 gather→`deep_research` 角色作为国内中转/不可用时兜底；再做按**自选分区**批量研究、报告版本历史、财报分析面板回归 AI 解读。

## M3 · 新闻聚合 + 趋势日报 + 投资机会 🟡（推进中）

详见 [ADR-0005](decisions/0005-news-classification-translation-opportunities.md)。
- ✅ **信源（一手优先，~90 源）**：`feeds.yaml` 扩到 **~90 个一手为主的顶级源**——**央行/监管/官方经济数据/公司新闻室·IR/官方研究博客 > 精英二手**（美联储全家 FOMC/Powell/演讲/FEDS Notes + 地区联储、BEA/Census/BLS、SEC/FTC/DOJ反垄断、Treasury 拍卖；OpenAI/DeepMind/Google Research/MSR/Meta/NVIDIA/Apple ML 等官方实验室；Intel/AMD/Micron/Broadcom/Arm/SK hynix 芯片新闻室·IR；NASA/JPL/ESA/Rocket Lab；WSJ/FT/The Information/SemiAnalysis 二手）。workflow 4 路并行调研 + httpx/feedparser 硬验证 **90/93 实测可抓**（个别 Cloudflare 源数据中心 IP 被挡、住宅 IP 可达）。`ingest.py` **并发**抓取 + 近 30 天过滤 + url 去重；`news_items`/`news_reports`/`news_opportunities` 表 + 幂等迁移。arXiv 论文流量太大暂列「论文 lane」待办。
- ✅ **主题分类**：`classify.py`+`themes.yaml`（**10 主题**含新增 **macro 宏观/政策**＝美联储/经济数据/监管；规则法、ASCII 词边界匹配、CJK 子串），ingest store-time 打标 + backfill；日报/要闻按主题分组。
- ✅ **标题翻译**：`translate.py`（en/ko→zh，cheap 角色批量编号清单 + JSON mode，缓存 `title_zh`，隐私优先不用 DeepL/Google）。
- ✅ **趋势日报**：`generate_report_stream`（summarize，按主题分组喂 prompt，SSE 流式落库，一天一份覆盖）。
- ✅ **今日投资机会**：两阶段防幻觉——LLM 给「公司名+市场+code_guess」→ `market.search` 接地真实 `MARKET:CODE`（弱模糊判未解析）+ 交叉自选高亮；`GET/POST /news/opportunities`，前端机会卡（chip 跳「看」、已关注陶土高亮、决策边界说明）。
- ✅ APScheduler 每日 07:30：抓取+翻译+日报（`scheduler.py`，失败不阻断）。「知」UI：日报列表＋正文＋今日机会＋按主题分组要闻流。
- ✅ **噪音过滤（两层）**：① `filter.py` 规则滤纯盘面/价格波动（摄取时，留基本面/宏观/风险）；② `relevance.py` **cheap 小模型批量判投资相关性**（作者反馈仍有无关新闻 → 不心疼 token 用小模型筛；`relevance` 列 0未判/1留/2弃，feed/日报/机会取 `relevance≠2`、未判仍显＝优雅降级，refresh 时跑、失败不阻断）。真机实测 240 判/56 弃：准滤 MarketWatch 退休理财鸡汤、消费手机/游戏/车、纯流向数据，留 HBM 涨价/算力/并购/政策。
- ✅ **信源精简**：韩源砍到 1（The Elec），聚焦美股 + 国内源；`_prune_removed_sources` 让库随 feeds.yaml 自愈。
- ✅ **个股「相关资讯」（API + 聚合双源 → AI 摘要）**：`GET /news/for` = **雅虎逐-ticker 新闻 API**（`ticker_news.py`，yfinance `.news`，四市场按 ticker 直取该公司新闻、兼容新旧 .news 结构、3h 缓存）**∪** 聚合流按公司名（中/英）匹配（中文翻译版），url 去重、时间倒序、失败降级；随后 `GET /news/for/brief` 用 summarize 角色把条目筛选/去重/合成 summary + points + risks（缓存 1h）。前端 StockNews **只显示 AI 摘要卡，不直接展示新闻列表**。
- ✅ **个股一手「一条龙」起步（SEC EDGAR）**：`edgar.py` 美股 ticker→CIK（官方 `company_tickers.json` 缓存 7 天）→ `data.sec.gov` submissions JSON → 高信号表单白名单（8-K/10-Q/10-K/20-F/6-K/S-1/424B/13D/13G/DEF 14A，**不收 Form 4 噪音**）；表单 + 8-K 事项码给**确定性中文标签**（零 token 不幻觉）；可配 SEC UA + ≤10 req/s + 6h 缓存 + 失败降级。`GET /news/official` → K 线页**「官方文件 · SEC」**段（陶土等宽 form 徽标 + 中文标签 + 申报日 + 直链）。真机验证 RKLB/NVDA/AAPL/TSLA/AMD 全中。详见 [ADR-0006](decisions/0006-first-hand-sources-edgar-x.md)。
- ✅ **X 官方号——已接入（twtapi 桥）**：**桥选 twtapi**（原 TwitterAPI.io 需国际银行卡、作者办不了；twtapi 有免费试用+月付）。`news/twtapi.py`：兼容新版 `api.twtapi.io`（`/user` + `/user_tweets`）与旧版 `api.twtapi.com/api/v1/twitter`（`UserResultByScreenName` + `UserTweets`），递归取 Tweet、按作者 id 过滤本人推文、`rest_id` 去重、长推取 `note_tweet`；归一为 news_items 并入 `ingest_all`（source=`X·<handle>`、prune 豁免）。账号清单 `resources/sources/x_accounts.yaml`（15 个 AI/芯片/航天/机器人官方号，可编辑）。key 走 `TWTAPI_KEY`（gitignored）；设置页测试会清楚暴露 key 无效、HTTP 429、旧 API `code=429/sub_code=42903` 月度额度用完，而不再误报“解析账号失败”。真机验证：15 账号 280 推、入库后英文标题经既有 translate 自动翻中。见 ADR-0006 §3 + ADR-0007 §5 + [memory/twtapi-source-quirks.md](memory/twtapi-source-quirks.md)。
- ✅ **多信源 lane 扩展（新闻 / 推特 / Reddit / 雪球 / 小红书）**：前端「资讯」第三层从固定新闻/推特改为多 source lane；已接入 lane 共用时间线/要点/市场/仅自选过滤和标股 chip。**Reddit 已真实接入**：`reddit.py` 走 public JSON（配置 subreddit，source=`Reddit·r/<sub>`），并入 ingest→翻译→relevance→linker→stock_tag 流水线；设置页可配 subreddit 且可测试。**雪球/小红书**：已登记 token、关注用户、个股/关键词配置与 UI lane；当前 lane 显示待接入，待登录 Cookie / 稳定 API 后接真实适配器，不伪装抓取。
- ✅ **信源三类重组（财经/新闻/论坛）+ 候选源可行性**（5-agent 调研，详见 [ADR-0007](decisions/0007-api-config-and-source-feasibility.md) 第 5 节）：`source_registry.py` 每条加 `group`+`cred`、加 `market_data`/`feeds_rss` 聚合行；前端 `SourcesPage` 按三类独立 Section 渲染。**财经**=内置行情栈(FDR·akshare·yfinance·pykrx 已接；Tushare Pro/必盈/iTick 已按作者要求移除)；**新闻**=RSS+Bloomberg+财联社+东方财富+X；**论坛**=Reddit+雪球+小红书。名称保持唯一官方名；Bloomberg 频道从名称移入可配置项并实际过滤 RSS。
- ✅ **设置 · API 配置中枢 + 顶级源核查**：`runtime_config`（gitignored `data/config.local.json`、注入 env 即时生效、脱敏回显、写入名 guard）+ `/settings` + 「设置」页（LLM key/base/角色路由 + 数据信源 key 皆可 UI 改、无需重启）+ `news/source_registry.py`。**Bloomberg 科技/市场**免费官方 RSS 已接入；核查作者朋友清单后**按其意见移除太贵源**（Reuters/LSEG、万得 Wind、同花顺 iFinD、东财 Choice），留免费 Bloomberg/财联社/东财 + 极廉 X。详见 [ADR-0007](decisions/0007-api-config-and-source-feasibility.md)。
- ✅ **外部社交/论坛信源接入向导（2026-06-05）**：`source_registry.py` 成为凭证入口与信源策略的单一真相，新增 `docs_url/official_url/setup/best_use/boundary`；设置·数据/信源详情页和设置·全部体检同时展示“获取凭证 / 文档 / 官方入口 + 接入方式 + 最佳用途 + 边界”。核查结论：X 当前用 `twtapi` key，X 官方 API 入口只作为未来原生适配器参考；Reddit public JSON 无需 key；雪球没有确认的一手公共内容 API，非官方路径依赖登录 Cookie/token；小红书 Ark App Key 偏商家开放平台，不等于公开笔记搜索。见 [ADR-0012](decisions/0012-external-social-source-strategy.md) + [memory/external-source-api-setup.md](memory/external-source-api-setup.md)。
- ✅ **设置 v2（作者反馈：多页 + Anthropic 风 + 动态 LLM + 测试按钮）**：左栏变真导航（**全部**/外观/模型/数据信源/自动，`store.settingsPage`）；**全部**页一键体检 LLM 连接 + 信源 API，显示接通/待配置/额度/权限/未接入，并给 twtapi/雪球/小红书等凭证入口；**LLM 改可动态增删连接列表** `{name,base_url,api_key,model}`（一律 OpenAI 兼容，角色→连接 指派，**测试连接**端点实测 DeepSeek/relay 通、伪 key 报错），`runtime_config` 首次自动从 `.env` 迁移（迁出 relay+deepseek、四角色就位、不中断）；Anthropic 风格行 + 信源**支付徽标**（微信/支付宝优先）。详见 [ADR-0008](decisions/0008-settings-v2-dynamic-llm-connections.md)。
- ✅ **付费源支付方式调研**（5-agent workflow）：哪些支持微信/支付宝优先——LLM 优先 DeepSeek/国产/支付宝可充中转，X 桥无支付宝（加密/虚拟卡），中文终端太贵全弃。见 [memory/payment-methods-sources.md](memory/payment-methods-sources.md)。
- ✅ **「知」二层噪音过滤（从严）+ 按天**：`filter.py` 规则之上加 `relevance.py`（cheap 小模型判投资相关性，**从严**：丢娱乐/消费/生活/**标题党/清单体/泛泛展望/纯涨跌**；feed/日报/机会取 `relevance≠2`）；从严实测 400 判/137 弃。**日报与机会改喂当天全部新闻**（`items_for_day` 按作者时区，长上下文吃得下，不再只取最近 N 条）；**今日要闻按天归类**（今天/昨天/日期）。
- ✅ **个股相关新闻接 API + LLM 清洗**：`ticker_news.py`（yfinance `.news` 逐 ticker，四市场）∪ 聚合流按名匹配，再经 cheap LLM **清洗**（`stock_news_clean.md`：去标题党/无关、译非中文、去重，缓存 1h）。真机验证 NVDA 5 条全中文、去重、无标题党。
- ✅ **前端打磨（作者反馈）**：① 看·K 线下方模块（财报/相关资讯/判断日记）**可拖拽重排**（dnd-kit + 持久化 `kanOrder`；展开/收起状态持久化到 `kanModuleOpen`，关闭财报/判断日记后换股不自动展开；手柄顶部居中 hover 浮现，仅手柄可拖、模块内交互不受影响）；② 移除「官方文件·SEC」UI 段（一般不看；`edgar.py` 后端保留）；③ **设置页重做为卡片网格**（填满舞台宽度、按钮内联，修「没拉伸/按钮换行/不美观」）。真机验证、零控制台错。
- ✅ **免费中文科技源接入**：`cls.py`（财联社科创电报 `depth/assembled/1111`，sign=MD5(SHA1(sorted_qs))、appName=CailianpressWeb；旧 nodeapi 路径已死）+ `eastmoney_news.py`（东财 `search-api-web` JSONP，按 人工智能/半导体/算力/机器人/大模型/芯片 关键词检索）。非 RSS 适配器并发并入 `ingest_all`，`source` 名（财联社/东方财富）经 `_prune_removed_sources` **豁免**（否则不在 feeds.yaml 会被误删）；复用 classify + 噪音过滤、中文免翻。真机验证：财联社 25 + 东财 42 条、二次 ingest 不被 prune 删。
- ✅ **「知」两列纵向导航重构（作者驱动）**：左栏改为 **Miller 两列**——列1 一级 rail（总览/日报/新闻/推特/机会，motion 选中 pill），选中后列2 弹出二级卡（**日报→按天 · 新闻→主题 · 推特→账号分类**；**总览/机会无二级**，layout 2 列）。主舞台按 (一级,二级) 路由到子视图：总览=日报+机会+要闻、日报=某天 digest、新闻=主题要闻流、推特=X 源按账号分类流、机会=机会卡。`features/news/{NewsNav,consts,shared,KnowView}.tsx` + store 改 `primary/secondary`；`.layout.know-2/know-3` grid。后端 `/news/feed` 加 `theme` + `source_prefix`（'X·' 取推特源）。tsc+build+ruff 全过。
- ✅ **信源可配置（通用机制）+「知」二级卡可拖拽调宽**（作者驱动）：`runtime_config.get/set_source_config(source_id, field)`（gitignored、即时生效、read-with-fallback 到内置默认）+ 注册表每源可声明 `config` 字段（type=accounts/tags）+ `POST /settings/source/config`（校验+清洗：账户去@/去重/分类白名单、关键词去空去重）。**Twitter 账户**（增删 screen_name+分类，原 `x_accounts.yaml` 作默认）与**东财关键词**（增删，原硬编码作默认）已 UI 可配（设置页源行内可展开编辑器）。`twtapi.accounts()`/`eastmoney_news.keywords()` 改为配置优先。「知」二级卡宽 `newsSubW`（持久化、拖拽，`.layout.know-3` 用 `--news-sub-w`）。**信源设置页改二级菜单**（左侧按 财经/新闻/论坛 列源名 + 状态点，右侧选中源的干净子页面）+ **彻底清掉源行的说明性文案**（作者「全部都是 UI 无关的垃圾信息」：note/payment/key-hint 前端一律不渲染，子页只留 名称+状态+key/账户/关键词 控件；见 [memory/concise-ui-copy.md](memory/concise-ui-copy.md)）。
- ✅ **新闻/推特「要点」（去重聚类 + 按投资重要性排序 + 时间范围）**（作者反馈「新闻重复、信息熵低」+ 后续三连）：`service.generate_clusters(theme, source_prefix, category, days)`——把近 `days` 天某范围（新闻按 theme / **推特按 source_prefix='X·'+账号分类**）经筛选新闻喂 summarize 模型，**按事件去重合并成簇** + 每簇给合并中文标题 / **4 级重要性（非常重要 critical / 重要 / 一般 / 次要）** / 一句为何 / 成员[n]，按重要性排序、噪音丢弃；落库 `news_clusters`（`report_date`+`scope` 串如 `news:ai@7d`/`tw:all@1d` 唯一，重生成覆盖）。`GET/POST /news/clusters?theme&source_prefix&category&days`。前端**「新闻」与「推特」视图都有「时间线/要点」切换 + 时间范围段控（今天/近7天/近30天）**；要点=重要性徽标（非常重要实心陶土）+ 合并标题 + 价值 + 展开多源链接，次要默认折叠。**新闻一直持久化**（news_items 不按龄删除），`days` 让作者翻历史而非只看当前（`recent_items`/`items_for_window` 加 days/source_prefix/category）。提示词 `news_clusters.md`（critical 从严）。真机：新闻 200→102 簇含 Marvell 合并 7 源；推特 13→10 簇。
- 🟡 **「知」融合主线 + 速赢（作者拍板，6 视角头脑风暴 57 点子合成的菜单 → 选定「融合主线+速赢组合」分批落地）**：
  - ✅ **① Ticker 挂钩层（底座）**：`news_item_symbols(news_id,symbol,name,confidence,matched_by)` + `linker.py`——**零幻觉**只用自选股的 中文名/英文名首词/代码 对标题(含中文译题)做词边界/子串命中，不调 LLM；`linked` 列增量幂等、`relink_all` 重挂、`attach_symbols` 给 feed 批量挂股。并入 `refresh`+scheduler。`POST /news/relink`。前端 feed 每条带**可点 ticker chip → 跳「看」**(看×知融合)。实测：2583 条→244 挂钩/8s、零 LLM，NVDA 105/MSFT 50/RKLB 32，feed 11/120 带股。这是分区日报/个股时间线/K线锚点/影响链/预期差等的共同前置。
  - ✅ **② 信源健康度**：`source_health` 表 + `ingest_all` 记录每源成败/条数/最近成功时间/最近失败原因；`GET /news/source-health`（纯统计无 LLM）。前端已并入「设置 · 全部」：指标卡 + 默认只看异常源 + 可展开全部，公共 RSS 的 401/403 归为“源站拒绝访问/反爬/下线”，不误写成凭证问题。见 [memory/source-health-dashboard.md](memory/source-health-dashboard.md)。
  - ✅ **③ 自选股驱动定向抓取 lane（`directed.py`）**：对每只自选股按 ticker 直取雅虎逐-ticker 新闻、落库 `lane='ticker'` 并**确定性挂钩**（`matched_by='targeted'`，零幻觉）——补齐新上市/冷门票（CRWV/NBIS/ALAB）名字不在本地目录的盲区。新增 `news_items.lane` 列：`feed`（RSS 策展流）/`ticker`（定向）；全局流/日报/要点/翻译/相关性判定**只扫 `lane='feed'`**，prune 豁免定向源——28 只股不淹没宏观流。`POST /news/directed/refresh`、并入 scheduler 每日。
  - ✅ **④ 标的叙事时间线（`stock_narratives` + `service.generate_narrative`）**：把某股近 45 天挂钩资讯（定向 ∪ 名字挂钩聚合）喂 summarize → JSON `{summary 当前主线, timeline:[{date,title,importance,refs[]}]}`，事件提炼合并、refs 接真实条目、防幻觉。`GET /news/narrative`、`POST /news/narrative/generate`、`GET /news/stock`。前端**「知」新增一级「个股」**（二级=自选股列表，主舞台=综述 + 左轴时间线 + 抓取/重生成 + 资讯流）。真机 US:CRWV：主线 + 3 事件，refs 混合 Simply Wall St.(定向)＋Bloomberg·科技(挂钩)。
  - ✅ **⑤ 机会卡直通「研」**：`store.research(symbol)`（选标的 + 进「研」）；机会卡已解析关联 chip 改**拆分胶囊**「名字→看 · 研→深度研究」，一键从机会进单股研究。
  - ✅ **⑥ 晨读 Top3**：总览顶部 hero「晨读 · 今日要事」＝复用 news@1d 要点的前 3（重要性徽标 + 标题 + 为何要紧 + 序号），scheduler 每日预生成（早晨即就绪），可手动「✨ 生成晨读」；前端为可展开卡片，展开后显示该要事来自哪些信源与原始标题。
  - ✅ **⑦「自上次以来」增量**：`useUI.lastSeenNewsAt`（持久化）+ `markNewsSeen`；总览「自上次以来 · N」列出打卡基准后发布的新条目（确定性、零成本、零 LLM），「标记已读」推进基准；首访给「标记此刻为已读」起点。
  - ✅ **⑧ 统一时间轴 · 「某天快照」**（作者：「每天信息不一样，怎么存/看某一天/更新」）：审计确认**存**(news_items 永不按龄删、按 published_at 沉淀；reports/opps 一天一份)与**更新**(refresh 累积去重 + scheduler 每日 + 自上次以来 diff)已扎实；**看某一天**原先只有日报兑现 → 现把「日历日」做成贯穿轴。修 `get/generate_clusters` **写死 `_today()` 的 bug**（历史要点不可达）→ 加 `day` 参（report_date=该日、`items_for_day(day)` 重建）；`recent_items(day=)` 取当日要闻；`/news/feed?day=`、`/news/clusters?date=` 加参。前端**「日报」Tab 改名「每日」**＝**某天快照**：二级列每天（今天置顶），主舞台＝那天的 趋势日报 + 要事 Top3 + 当日机会 + 当日要闻（`DaySnapshotView`，复用 `MorningBrief(date)`/`OpportunitiesPanel(date)`/`DigestBlock(date)`）。
  - 🟡 **⑨ 组件化信源 · 每股专属信源画像**（作者想法）：`stock_sources(symbol,kind,name,ref,enabled,verified,added_by)` 表 + `stock_sources.py`——LLM（`deep_research` 角色，指到联网 Qwen/OpenAI Deep Research 等模型更准）调研某股该看哪些源（官网/IR/官方X/大V/Reddit/雪球/财经站）→ 落库**待确认候选**，作者在「知·个股」面板逐个 mark（启用/手动增删）。防幻觉：候选默认 `enabled=0 verified=0`、`ref` 须真实、作者拍板。`GET/POST /news/sources`、`/discover`、`PATCH/DELETE /sources/{id}`；前端 `StockSourcesPanel`（开关组件 + 类别徽标 + 可点 ref + 手动加）。**已落地**：表/调研/CRUD/UI + **启用源回流定向 lane**（X 账号→twtapi、Reddit 子版→public JSON、RSS/Atom URL→feedparser，写 ticker lane 并挂 `matched_by='stock_source'`，进入「看·相关资讯」AI 摘要；卡片头部有「专属 N」与刷新按钮）。**待续**：更严格的句柄/子版/URL 验证、普通网页 feed 自动发现、雪球/小红书真实适配器、官网/IR 无 RSS 页面解析。
  - 🟡 **联网检索（Deep Research 第一步）**：Perplexity 需国际卡（作者办不了，同 twtapi 之困）→ 改走**通义千问 Qwen/百炼**（支付宝、OpenAI 兼容、`enable_search` 的 `max/agent` 策略≈多轮深度检索）。已落地**连接级 `web_search` 开关**（`gateway._kwargs` 注入 `extra_body.enable_search`；`runtime_config`/`settings_router`/前端 ConnectionCard 联网开关）。作者加 Qwen 连接（`dashscope.aliyuncs.com/compatible-mode/v1` + `qwen-plus` + 勾联网）、指 `deep_research` 角色 → 信源调研与「研」即联网。备选：智谱 GLM web_search、博查 Bocha 搜索 API + DeepSeek 自建 pipeline。
  - ⚪ **后续**：句柄/子版/URL 验证、Reddit 抓取器、启用源喂回定向 lane、分区日报、影响链、预期差、「研」联网多轮增强。
  - 测试自选库（28 个 US ticker：NVDA/MU/RMBS/CRDO/ALAB/SNDK + 光通信 LITE/CIEN/COHR/CLS + 航天 ASTS/RKLB/RDW/PL + AI云 ORCL/CRWV/NBIS/PLTR/GOOG/META/MSFT/AMZN + SOFI/HOOD + TSLA/AAPL + HIMS + QQQ，两级分区）已入本地库模拟真实环境。
- ⚪ 华尔街见闻-tmt 焦点科技 lane、个股 IR 新闻室·官方 X 并入「一条龙」、KR DART / CN cninfo 一手扩展、arXiv 论文 lane、机会接地阈值调优。

## M4 · 原生打包 + 打磨 ⚪

- ⚪ Tauri 2 外壳；PyInstaller sidecar；原生窗口/菜单
- ⚪ macOS Keychain 存密钥；数据移到 `~/Library/Application Support/Augur/`
- ⚪ DMG 构建；应用图标；动效/性能打磨
- ⚪ 明暗主题定稿（都保持暖色）

---

## 待办 / 想法（未排期）

- **长期有用功能池（10 年视角）**
  - ✅ 信息覆盖意识：决策页显示当日独立信源数，避免单一来源误导。
  - ✅ 个股资讯只读 AI 摘要：看 K 线时不被新闻列表淹没，只看驱动/风险/反证。
  - ✅ 关注型社区源骨架：Reddit subreddit、雪球/小红书关注用户、个股/关键词配置。
  - ✅ 研究引擎路线：官方 OpenAI Deep Research API 优先，自建 Augur gather 兜底（ADR-0011）。
  - ⚪ 组合级风险暴露：按行业/国家/因子/市值/相关性看自选池，不接交易账户也能做研究组合。
  - ⚪ 预期差日志：记录“市场当前共识/我不同意什么/验证日期”，到期自动回看。
  - ⚪ 催化日历：财报、发布会、监管节点、宏观数据、锁定期、产品发布日期。
  - ⚪ 反证雷达：每个高 conviction 标的维护 3-5 条反证条件，新闻触发时置顶。
  - ⚪ 来源可靠度评分：按信源历史命中率、原创性、重复率、标题党率给权重。
  - ⚪ 决策复盘闭环：研究报告 → 判断日记 → 结果回看 → 方法论笔记自动串联。
- 组合视图（只读，不含持仓/交易）
- 跨市场对比与板块热力图
- 由 LLM 用量日志驱动的成本面板
- 提醒规则（"日报里提到 X 就通知我"）
- 研究报告导出 PDF/Markdown
