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
- ✅ **财报分析面板**（K 线下方、可折叠）：指标卡 + **AI 解读**（调 `/llm/chat` 流式简评，暴露不确定性、不构成投资建议）。
- ✅ LongBridge OpenAPI 调研：暂不采用（偏交易/需凭证/基本面薄），见 [ADR-0004](decisions/0004-llm-live-fundamentals-longbridge.md)。
- ⚪ `research/` 编排器：规划 → 收集（行情+基本面+新闻+网络/Deep Research）→ 综合 → 引用；`POST /research/stock` SSE；报告持久化。
- ⚪ 财报分析升级：接更结构化的财报（akshare/yfinance financials）、多轮、带引用。

## M3 · 新闻聚合 + 趋势日报 ⚪

- ⚪ `resources/sources/*.yaml` 信源注册表（精选全球顶级源）
- ⚪ `news/` 摄取（RSS/API）+ 去重 + 主题聚类
- ⚪ APScheduler 每日任务 → LLM 趋势日报
- ⚪ 新闻 UI：每日日报、主题聚类、信源管理；可按自选分区过滤

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
