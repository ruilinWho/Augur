# CLAUDE.md — Augur

> **Augur** 是一个本地优先、LLM 驱动的个人多市场投资**研究**工作台（macOS）。
> 本文件是**项目宪法**。**每次会话开始请完整读一遍。**
> 它会被自动载入上下文——请保持精炼、最新、高信噪比。
> **更新 `CLAUDE.md` + `docs/` 是每次改动的一部分**，不是事后补的（见 §10）。

---

## 1. Augur 是什么 —— 以及不是什么

三根支柱 / three pillars：

1. **看 · View** —— 美股 / 港股 / A股 / 韩股的 K 线，以**极致美观**的方式渲染。
2. **研 · Research** —— 用 LLM + Deep Research 对单支股票做详尽分析。
3. **知 · Know** —— 每天聚合全球顶级信源，由 LLM 蒸馏成**趋势日报**，让主人在天级别与世界信息流同步。

贯穿三者的基础设施：

- **自选分区（两级板块）** —— 自定义 List / 板块来组织你跟踪的标的（见 §8）。
- **统一 LLM 网关** —— 任意厂商、可自配 `base_url`（见 §6）。

表层：贴合 **Anthropic 设计哲学**、字体/行距可调、**设计师级美观**的 UI（见 §9——**美观是硬指标，不是装饰**）。

**非目标 —— 硬边界（无明确指令不得跨越）：**

- ❌ **不是交易终端。** Augur 永不下单、不动钱、不执行任何交易。（见 §11）
- ❌ **不是投资建议。** 输出是研究辅助——永远暴露不确定性、标注来源。
- ❌ **不是多用户 / 云 SaaS。** 单用户，本地运行在主人的 Mac 上。

---

## 2. 架构总览

```
┌──────────────────────────────────────────────────────┐
│  前端  React 19 + TypeScript + Vite 8                   │
│  · 图表  Lightweight Charts v5 (+ KLineChart A股指标)    │
│  · 路由/状态  TanStack Router/Query + Zustand + Zod      │
│  · 样式  Tailwind v4 + Anthropic 设计 token              │
│  · 动效  Motion   · 字体/行距 = CSS 变量（用户可调）       │
└───────────────────────┬──────────────────────────────┘
                        │  HTTP + SSE（流式）
┌───────────────────────┴──────────────────────────────┐
│  后端  Python 3.13 + FastAPI                            │
│  market/    → 四市场数据适配器 + 检索(本地目录∪东财联想)  │
│  watchlist/ → 自选分区（两级板块）+ 拖拽换区               │
│  journal/   → 判断日记（个股决策复盘）                    │
│  llm/       → litellm 网关（任意厂商、自配 base_url）      │
│  research/  → deep-research 编排                         │
│  news/      → RSS/API 摄取 + APScheduler + 趋势日报       │
│  storage/   → SQLite（元数据）+ Parquet（行情缓存）        │
└───────────────────────┬──────────────────────────────┘
                        │  （Phase 2）
                  Tauri 2 外壳 → 原生 .app（<10MB）
```

完整细节：[docs/architecture.md](docs/architecture.md)。选型理由：[docs/decisions/](docs/decisions/)。

---

## 3. 仓库结构

```
Augur/
├── CLAUDE.md              ← 你在这（项目宪法）
├── README.md              ← 面向人的简介
├── docs/                  ← 架构 · 路线图 · 设计系统 · ADR · 记忆
│   ├── architecture.md
│   ├── roadmap.md
│   ├── design-system.md   ← 设计系统（美学准则在此）
│   ├── decisions/         ← ADR 架构决策记录（只增不改）
│   └── memory/            ← 跨会话项目记忆（见 §10）
├── backend/               ← Python（uv 管理）FastAPI 服务
│   ├── pyproject.toml
│   └── augur/  market/ · watchlist/ · journal/ · llm/ · research/ · news/ · storage/ · config.py · main.py
├── frontend/              ← React + Vite + TS（M1 搭建）
├── resources/             ← 入库的静态资产（版本控制）
│   ├── fonts/             ← 自带字体
│   ├── prompts/           ← LLM 提示词模板（要版本化！）
│   └── sources/           ← 新闻信源清单 + aliases.yaml（跨语言别名种子）（YAML）
├── data/                  ← 仅运行时 · 被 git 忽略 · 在 git 里永不作为真相来源
│   ├── cache/（parquet）   ├── db/（sqlite）  └── logs/
└── src-tauri/             ← Phase 2 桌面外壳
```

**最重要的一条结构规则：** `resources/`（入库）vs `data/`（忽略）。
你**亲手编写的输入** → `resources/`；**运行时生成/抓取的** → `data/`。

---

## 4. 技术栈与关键依赖（**用前沿版本**）

| 层 | 选择 | 一句话理由 |
|---|---|---|
| 后端 | **Python 3.13 / FastAPI** | 唯一有免费四市场数据库的生态 |
| 包管理 | **uv** | 快、可复现；`uv sync` / `uv run` |
| LLM 网关 | **litellm** | 一个接口、100+ 厂商、原生自配 `base_url` |
| 行情数据 | **FinanceDataReader**（基座）+ **akshare**（A股）+ **yfinance**（美/全球）+ **pykrx**（韩） | FDR 一库覆盖四市场，其余加深度 |
| 调度 | **APScheduler** | 每日新闻 / 日报任务 |
| 存储 | **SQLite** + **Parquet**（pyarrow） | 元数据 + 列式行情缓存 |
| 前端 | **React 19 + TypeScript + Vite 8** | 最强图表生态；CSS 易做到美 + 字体可调 |
| 路由/状态 | **TanStack Router** + **TanStack Query** + **Zustand** + **Zod** | 类型安全路由 / 服务端状态 / 客户端状态 / 运行时校验 |
| 图表 | **Lightweight Charts v5**（主）+ **KLineChart**（A股指标） | 35KB、丝滑、多窗格；KLineChart 画 MA/BOLL/MACD |
| 样式 | **Tailwind CSS v4** + 自定义设计 token | Anthropic 主题；CSS-first 配置（见 design-system.md） |
| 拖拽 | **dnd-kit** | 自选分区拖拽组织（无障碍友好） |
| 动效 | **Motion**（motion.dev，原 Framer Motion） | 克制、顺滑的过渡 |
| 桌面（P2） | **Tauri 2** + PyInstaller sidecar | 原生 .app，<10MB（Electron 动辄 100MB+） |
| 前端包管理 | **pnpm** | 快、现代、磁盘友好 |

> 本文件**不钉死精确版本**——`pyproject.toml` / `package.json` 才是版本真相。新增依赖要在提交里说明理由，并优先用上表里的库再考虑替代品。**"前沿"指主流稳定的最新大版本，不是不稳定的实验版。**

---

## 5. 约定

### 后端（Python）
- 一切走 **uv**：`uv add <pkg>`、`uv run <cmd>`、`uv sync`。
- **ruff** 做 lint+format；**mypy/pyright** 做类型。所有公共函数加类型标注。
- FastAPI：路由放 `augur/<domain>/router.py`；纯逻辑放 `service.py`；Pydantic 模型放 `schemas.py`。把 I/O（网络、磁盘）挡在纯逻辑之外，便于测试。
- 所有出站网络请求都走一个小的 **重试/缓存** 包装层——别狂打免费数据源（限流是真的）。
- I/O 密集端点默认 async；数据库（同步）调用丢进 threadpool。

### 前端（TypeScript / React）
- 函数组件 + hooks。Feature-first 目录：`src/features/{kline,watchlist,analysis,news}/`。
- 共享原子组件放 `src/components/`；设计 token 放 `src/theme/`。
- **组件里禁止硬编码颜色 / 字号 / 间距**——一律消费 CSS 变量 / Tailwind token，让字体排版保持用户可调（字体、行距是一等公民）。
- LLM 输出用 SSE 流式，增量渲染。
- **美观是硬指标**：每一屏都按资深产品设计师水准打磨（见 §9）。

### 提交与分支
- Conventional Commits：`feat:`、`fix:`、`docs:`、`refactor:`、`chore:`。
- **功能开发**在 `main` 的分支上做；初始脚手架/文档可直接提交 `main`（主人已授权 Claude 自行 commit & push）。
- 提交带 co-author trailer（遵循 harness 规则）。

### 本地运行（随脚手架落地更新）
```bash
# 后端（在 backend/ 里 `uv sync` 之后）
cd backend && uv run uvicorn augur.main:app --reload --port 8788

# 前端（M1 搭建后）
cd frontend && pnpm dev
```
> ⚠️ M1 落地前，以上是*预期*命令；实际进度看 docs/roadmap.md。

---

## 6. LLM 网关约定（`backend/augur/llm/`）

- **一切走 litellm。** 不在各 feature 里散落直连 `openai`/`anthropic` SDK。
- 模型 = **可动态增删的连接列表**（不再写死厂商）：每个连接 `{id, name, base_url, api_key, model}`，**一律 OpenAI 兼容**（`litellm model="openai/<model>"` + `api_base` + `api_key`，覆盖 DeepSeek/各类中转站/OpenRouter/国产模型；原生 Anthropic 走中转站）。详见 [ADR-0008](docs/decisions/0008-settings-v2-dynamic-llm-connections.md)。
- 区分**角色**：`chat`、`deep_research`、`summarize`、`cheap`。每角色**指到一个连接**——主人可把摘要/翻译/筛选路由到便宜模型、深度分析路由到前沿模型。`gateway` 解析角色→连接→OpenAI 兼容调用；有**测试连接**端点 `/settings/llm/test`（发极小请求验证）。
- **两处配置，同一真相：** 既可改 gitignored `backend/.env`，也可在前端**「设置」页**改（连接增删/角色指派/信源 key），落 gitignored `data/config.local.json`（`runtime_config`，注入 `os.environ` **即时生效、无需重启**，UI 优先于 `.env`；**首次自动把旧 `.env` 配置迁成连接**，不中断）。`/settings/*` 端点**只回脱敏状态、从不回传明文、绝不打日志、写入名经 guard**（§11）。数据/新闻信源 key 也走这里（`news/source_registry.py` 注册表驱动，**按 财经/新闻/论坛 三类**[`group`]＋支付方式徽标；详见 [ADR-0007](docs/decisions/0007-api-config-and-source-feasibility.md)）。
- 面向用户时**总是流式**。**总是把 token 用量记到 `data/db`** 以便看成本。
- 提示词模板放 `resources/prompts/`（版本化），按名加载——别在代码里内联大段提示词。

---

## 7. 行情数据约定（`backend/augur/market/`）

- **内部归一化符号：** `MARKET:CODE` → `US:AAPL`、`HK:00700`、`CN:600519`、`KR:005930`。每个适配器负责与各库原生格式互转。
- **适配器模式：** 每个源一个模块（`fdr.py`、`akshare.py`、`yfinance.py`、`pykrx.py`），统一在 `MarketAdapter` 接口后（`get_ohlcv`、`search`、`quote`）。一个 resolver 按市场选最佳适配器并带回退。
- **缓存优先：** OHLCV 缓存为 Parquet 到 `data/cache/`，键为 `MARKET:CODE/interval`。只抓缺失的尾巴。尊重限流。
- 各市场的交易日历、币种、代码格式都不同——存进适配器元数据，**别假设美股惯例**。
- **检索（`search.py` + `listings.py`）= 本地目录 ∪ 东方财富实时联想，统一打分去重。** 本地目录（FDR 列表 + akshare A股中文名 + KOSPI/KOSDAQ 韩文名，缓存 Parquet）管美股英文名 + 韩股 + 离线兜底；东财 suggest 管港股/A股/新股 + 拼音（MiniMax/智谱 也搜得到）；跨语言别名靠 `resources/sources/aliases.yaml`（海力士→KR:000660）。带缓存/超时/失败降级。**坑见 [docs/memory/search-data-sources.md](docs/memory/search-data-sources.md)**（东财无韩股、`push2` 被代理拦截、FDR 港股列表未实现…）。
- **基本面（`fundamentals.py`）= yfinance（雅虎）一库覆盖四市场**：① 快照 `get_fundamentals`（市值/P-E/净利率，缺 P/E 用 市值/净利润 兜底）→ 前端置于 **K 线上方** 的指标条；② 历史 `get_financials(symbol, period)`（营收/营收增长/净利/净利率/EPS/EPS增长/自由现金流 + 财报链接）→ **K 线下方「财报分析」趋势表**（默认显示关键行、「更多指标」展开其余；**最新一期在右边缘**，列定宽、过宽则横向滚动并默认滚到最新）。**季度（默认，~5–7 期）/ 年度（~4–5 年）段控可切**；**增长率一律同比**（季度 vs 去年同季＝回退 4 列、年度 vs 上一年），避开季节性误导。本币原值，前端按亿/万亿格式化；缺数据置 null → 「—」。6h 缓存（key 含 period）。**LongBridge OpenAPI 已调研、暂不采用**（偏交易、需账号/凭证、基本面薄——见 ADR-0004）。

---

## 8. 自选分区（两级板块）约定（`backend/augur/watchlist/`）

主人用**自定义"分区/板块/List"**来组织跟踪的标的。这是贯穿三大支柱的导航基础设施（看哪些、研哪些、新闻按分区聚合）。

- **硬约束：最多两级（invariant）。**
  - 一级板块：如 `半导体`、`航天`、`新能源`。
  - 二级板块：挂在某一级下，如 `半导体/GPU`、`半导体/光通信模块`。
  - **二级板块不能再有子级。** 后端 service 层强制 `depth ≤ 2`；前端不暴露第三级入口。
- **数据模型（SQLite）：**
  - `sections(id, name, parent_id /* NULL=一级 */, sort_order, created_at)`
  - `watchlist_items(id, section_id, symbol /* MARKET:CODE */, note, sort_order, added_at)`
  - 一只标的**可同时属于多个分区**；可直接挂在一级下，也可挂在二级下。
- **市场（美/港/A/韩/全部）是过滤器，不是第三层。** 标的的市场已编码在 `symbol`（`MARKET:CODE`）里；导航上市场是个跨分区的**筛选器**（面板顶部分段控件），与"两级板块"正交——既好看，又保住两级铁律。
- **分区按"标的所在市场"显示（不是死绑一个市场）。** 一个分区可跨市场（`半导体` 里能同时有 `US:NVDA` + `KR:000660`）。选了具体市场时，只露出在该市场**有标的**的分区、且只显示该市场的标的（`半导体` 在韩股只露海力士、在 A 股只露 300308）；**空分区 / 在该市场无标的的分区被隐藏，只在「全部」出现**（这样 `大模型` 不会污染韩股）。逻辑在 `service.list_tree(market)`（按内容剪枝）。
- **前端** `features/watchlist/` 是看/研的**上下文面板**（左栏，顶栏 Tab 之下）：市场过滤器 + 可折叠两级树，**dnd-kit 拖拽换区/重排**（后端 `PATCH /watchlist/items/{id}` 移动 + `/reorder` 排序）；整行点击折叠；**分区名双击重命名**（`PATCH /watchlist/sections/{id}` 按 id 改、市场无关；前端失效**所有市场**的 sections 查询→切市场即时一致、不"分叉"；同层重名 409 拒绝、空名 422；单击/双击靠 190ms 延迟消歧避免误折叠）；检索式加股（选了市场只敲代码即可，`全部`则全市场搜）；点击标的 → 在主舞台看/研。**左栏宽度可拖拽**（`--panel-w`，持久化）。
- **标的行 + 个股标题显示"看得懂的简洁名"**（`search.display_name`：KR:000660→SK海力士；**美股英文名去公司后缀** `_clean_name`：Redwire Corp→Redwire、Planet Labs PBC→Planet Labs、Apple Inc.→Apple；CJK 名不受影响；搜索仍同时认原名与清洗名），代码/市场作次要信息；名字随报价端点 `/market/quote` 的 `name` 字段带出。
- 删除一级板块时如何处理其下二级与标的：**级联删除**（FK `ON DELETE CASCADE`，连带二级与标的）。

---

## 9. 设计系统（**美学是硬指标**）

完整 token 与排版见 [docs/design-system.md](docs/design-system.md)。**这里是不可妥协的纲领：**

- **美观对 Augur 是功能性的，不是装饰。** 主人明确要求：前端美观度对齐 **Anthropic / 资深产品设计师** 水准，而且**这会直接影响投资的理智性**——平静、克制、低噪音的界面支持更清醒、更少情绪化的决策；杂乱刺眼的界面会侵蚀判断。
- **完成标准 = "资深产品设计师会让它上线吗？"** 绝不留默认样式、未对齐、粗糙的 UI。宁可少做一个功能，也要把已做的做到精致。
- **暖纸感**，非惨白。米白/象牙底、柔和描边、慷慨留白、温和圆角、克制动效。
- **标志性强调色** ≈ 陶土/珊瑚 `#D97757`，少量点睛。其余低饱和、安静的配色。
- **排版 = 英文衬线 + 中文苹方**（Anthropic 路子）：英文/标题用 **Source Serif 4** 衬线，**所有中文用苹方**（`PingFang SC`，系统）——不用中文宋体。仅 Source Serif 4/JetBrains Mono 自托管到 `resources/fonts/`。
- **K线红绿要「蜡笔纸感」**：**规整矩形 · 直角不加圆角**（圆角小尺寸下显歪）、哑光低饱和、半透明、轻 + 极淡纸纹，绝不鲜艳实心。涨跌色习惯可配（美股绿涨红跌；A/港/韩红涨绿跌）。
- **导航外壳：** 功能切换在**顶栏**（`Augur` 一行横向 Tab 看/研/知 + 右上齿轮进设置）；下方两栏＝上下文面板（自选分区树 / 日报列表 / 设置分类）＋主舞台。**所有 Meta 设置集中在「设置」**，不散落顶栏。
- **字体/字号/行距/行宽是用户可调的一等公民**，全部走 CSS 变量；组件只读 token。

---

## 10. 文档与记忆纪律（重要）

本项目**全程由 LLM 协助开发**，所以写下来的持久上下文就是产品的记忆。规则：

- **每次改动同一口气更新文档。** 新能力 → 更新 `CLAUDE.md` 相关 § + `docs/`。带权衡的新决策 → 在 `docs/decisions/` 加一篇 ADR（只增不改、编号）。
- **`docs/roadmap.md`** 是实时状态板——已完成、当前焦点、下一步。里程碑移动就更新它。
- **`docs/memory/`** 存放放不进代码或 ADR 的跨会话上下文：坑、数据源怪癖、主人偏好、"为什么放弃了 X"。一文件一主题。（这是**项目级记忆**，区别于 Claude 的个人 `~/.claude` 记忆。）
- 当你（LLM）学到某个非显然、未来会话会重复踩坑的东西——**在结束这一轮前把它写下来**，放对地方。
- 保持 `CLAUDE.md` 精瘦：深度内容链接到 `docs/`；本文件是索引 + 不变量，不是百科。

---

## 11. 护栏 —— 不可妥协

1. **永不交易、永不动钱。** 只做研究。
2. **git 里不放密钥。** API key 放 gitignore 的 `.env` / 系统 Keychain。绝不把 key 打进日志或提交。`data/` 被忽略——保持如此。
3. **暴露不确定性。** 免费数据源可能延迟/出错；LLM 分析会幻觉。标注新鲜度、引用来源、适当对冲措辞。
4. **尊重限流。** 激进缓存、失败退避。别把主人的 IP 打到被封。
5. **本地优先且私密。** 无遥测、不把主人数据发往任何地方，除非主人明确配置的 LLM 厂商。

---

## 12. 当前状态与下一步

- **现在：** M1 + M1.5 + M1.6 + M2 ✅，**M3「知」推进中**。M1.6 = 全市场检索加股、拖拽换区、可调栏宽、判断日记、个股显示中文名（详见 §7/§8）。**M2**：**LLM 网关接通**（`.env` 配 DeepSeek + OhMyGPT 中转，`config.py` load_dotenv，四角色实测可用，/llm/chat 流式验证）、**基本面**（yfinance）：快照指标条（市值/P-E/净利率）置于 **K 线上方**；K 线下方 **财报分析** 历史趋势表（营收/增长/净利/净利率/EPS/FCF，**季度（默认）/ 年度可切**、最新在右、横向可滚，关键行默认显示、「更多指标」展开，带财报链接；同比口径）。**自选分区去重**：同层同名幂等。**折叠组件**：统一 `components/Collapse.tsx`（grid `0fr↔1fr`，避开 Tailwind `.collapse` 撞名 + motion 失效坑——见 [docs/memory/frontend-gotchas.md](docs/memory/frontend-gotchas.md)），无折叠小三角。**M2「研 · 单股深度研究」**（`research/`，详见 [ADR-0009](docs/decisions/0009-research-pillar-single-stock.md)）：`gather(symbol)` 收集 Augur **已有确定性数据**（价格摘要 1y + 基本面快照 + 季度财报趋势 + 已清洗个股新闻 + SEC 申报）并给**编号引用源**（新闻+申报各带 `[n]`）→ `_format_data` 拼事实块 → **deep_research 角色（长上下文模型）SSE 流式** Markdown 报告 → 落库 `research_reports`（一股一份、重生成覆盖、`ON CONFLICT(symbol)`）。报告结构（提示词 `resources/prompts/research_stock.md`，由 4-agent 设计 workflow 三视角合成）：**一句话结论 → 多空核心看点 → 近期催化与动态（重心）→ 基本面与估值 → 财务趋势 → 多空逻辑 → 风险与不确定性 → 来源**；八条**防幻觉铁律**（只用所给数据、不编造数字、不假装有网络/分析师预期/估值模型/目标价、事实 vs 推断对冲、内联 `[n]` 引用）。`GET /research/stock`（404=暂无）+ `POST /research/stock/generate`（SSE，check_ready deep_research）。前端「研」Tab = `ResearchView`（选标的→生成→流式渲染**自写轻量 Markdown**：`##` 标题/`>` 引用块/`-` 列表/`|表格|`/`[n]` 上标**可点跳来源 url**/重新生成/空态引导，非投资建议）。**口径同 §11**：只综合本地已有数据、暂不引入实时网络（列为下一步增强）、暴露不确定性。真机验证 US:NVDA 端到端（含财务表 + 12 条带 url 引用 + 诚实点出数据盲区）。**M3「知」**（详见 [ADR-0005](docs/decisions/0005-news-classification-translation-opportunities.md)）：`news/` **并发** RSS 摄取（feedparser，**~90 个一手为主的顶级源**＝央行/监管/官方经济数据/公司新闻室·IR/官方研究博客 > 精英二手；`resources/sources/feeds.yaml`：AI/芯片/航天/机器人/科技/宏观/中/韩，近 30 天过滤、url 去重落 SQLite；个股级一手走 `edgar.py` 不在此清单）→ **主题分类**（规则 `classify.py`+`themes.yaml`，10 主题含 macro 宏观/政策，ASCII 词边界匹配）→ **标题翻译**（en/ko→zh，cheap 角色批量缓存 `title_zh`，隐私优先不用 DeepL）→ **趋势日报**（summarize，按主题分组喂 prompt，SSE 流式落库）+ **今日投资机会**（两阶段防幻觉：LLM 给「名+市场」→ `market.search` 接地真实 `MARKET:CODE` + 交叉自选高亮，落 `news_opportunities`）。**APScheduler 每日 07:30** 抓取+翻译+生成。前端**「知」Tab** = 日报列表＋日报正文＋**今日机会卡**（关联个股 chip 可点跳「看」、已关注陶土高亮、非投资建议脚注）＋今日要闻按主题分组流。**噪音过滤两层**：① `filter.py` 规则滤纯盘面/价格波动（摄取时，留基本面/宏观/风险信号）；② `relevance.py` **cheap 小模型批量判投资相关性（从严）**（丢娱乐/消费/生活/**标题党/清单体/泛泛展望/无驱动纯涨跌**，存 `relevance` 列 0未判/1留/2弃；feed/日报/机会只取 `relevance≠2`，refresh 时跑、失败不阻断）——从严实测 400 判/137 弃。**日报与机会改喂当天全部新闻**（`items_for_day` 按主人时区，不再只取最近 N 条；模型长上下文吃得下）；**今日要闻按天归类**（今天/昨天/日期）。个股「相关资讯」另有 LLM 清洗（见下）。**信源精简**、**信源精简**（韩源砍到 1=The Elec，聚焦美股+国内；库随 feeds.yaml 自愈）、**个股「相关资讯」**（看 K 线页一段，`/news/for` = **雅虎逐-ticker 新闻 API**（`ticker_news.py`，yfinance `.news` 覆盖四市场、按 ticker 直取该公司新闻）**∪** 聚合流按公司名匹配，url 去重、时间倒序，再经 **cheap LLM 清洗**（`stock_news_clean.md`：去标题党/无关、译非中文为中文、去重，缓存 1h）、失败降级）。**个股一手「一条龙」起步**（`edgar.py`：美股 SEC EDGAR ticker→CIK→submissions、高信号表单白名单 + 8-K 事项码**确定性中文标签**、6h 缓存/可配 UA/≤10 req/s；`GET /news/official`，`edgar.py`+端点后端保留备 `research/` 深读——**K 线页 UI 段按主人反馈移除**（一般不看）；详见 [ADR-0006](docs/decisions/0006-first-hand-sources-edgar-x.md)）。**设置 v2**（[ADR-0008](docs/decisions/0008-settings-v2-dynamic-llm-connections.md)）：**多页**（左栏导航 外观/模型/数据信源，`store.settingsPage`）+ **Anthropic 风格行**；**LLM 改为可动态增删的连接列表**（`{name,base_url,api_key,model}`，一律 OpenAI 兼容；角色→连接 指派；**测试连接**按钮；首次自动从 `.env` 迁移），`runtime_config`＋`/settings/llm/*`＋`/settings/secret`，落 gitignored `data/config.local.json`、即时生效、脱敏、guard；信源注册表 `news/source_registry.py` 带**支付方式徽标**（微信/支付宝优先，见 [docs/memory/payment-methods-sources.md](docs/memory/payment-methods-sources.md)）。**信源三类重组（财经/新闻/论坛）+ 候选源可行性**（5-agent 调研，ADR-0007 第 5 节）：注册表每条加 `group`+`cred`、删冗长 note、加 `market_data`/`feeds_rss` 聚合行（RSS 动态计数），前端按三类独立 Section 渲染。**财经**=行情栈(FDR·akshare·yfinance·pykrx 已接)+候选 Tushare/必盈/iTick(登记留槽，已被免费栈覆盖)；**新闻**=RSS聚合+Bloomberg+财联社+东财+**X(twtapi)**；**论坛**=雪球(留槽，标注「需登录·泄持仓」)。**Twitter 桥改选 twtapi**（`TWTAPI_KEY`；原 TwitterAPI.io 需国际卡主人办不了，twtapi 有免费试用+月付）。候选 5 源均「先登记留槽、不写适配器」由主人定夺（行情类被现有免费栈覆盖且增隐私面、雪球泄持仓违 §11）。**Bloomberg 科技/市场免费 RSS** + **财联社科创电报**（`cls.py`，sign=MD5(SHA1(qs))）+ **东财关键词资讯**（`eastmoney_news.py`，JSONP）三个免费源已接入（后两者为非 RSS 适配器，并发并入 `ingest_all`、`source` 名经 prune **豁免**）；核查主人朋友清单后**按其意见移除太贵源**（Reuters/LSEG、万得 Wind、同花顺 iFinD、东财 Choice），极廉的 X 待配 key（详见 [ADR-0007](docs/decisions/0007-api-config-and-source-feasibility.md)）。**看·K 线下方模块（财报/相关资讯/判断日记）可拖拽重排**（dnd-kit + 持久化 `kanOrder`，手柄在模块**标题左侧 gutter**、hover 浮现）；**分区名双击重命名**（见 §8，防分叉）；**设置页卡片网格**（填满舞台宽度、按钮内联；二选段控等宽对称）。真机验证、零控制台错、ruff+tsc+build 全过。
- **本地运行：** 后端 `cd backend && uv run uvicorn augur.main:app --reload --port 8788`；前端 `cd frontend && npm run dev`（:5173，已代理 `/market /watchlist /journal /llm /news /research /settings /health`）。LLM 需 `backend/.env`（见 `.env.example`，**密钥永不入库**）。
- **下一步：** M3 续——**X(twtapi) 已接入**（`news/twtapi.py`，screen_name→rest_id→GraphQL 时间线，归一进 `ingest_all`，账号清单 `resources/sources/x_accounts.yaml`，英文推文经 translate 自动翻中；见 ADR-0007 §5）、雪球/Tushare 等候选源适配器待主人定夺、个股 IR 新闻室·官方 X 并入「一条龙」、KR DART / CN cninfo 一手扩展、arXiv 论文 lane、机会接地阈值调优、日报/机会按**自选分区**聚合、信源健康度；M2「研」续——深度增强：接**实时网络搜索 / Deep Research**（多轮检索→综合）、按**自选分区**批量研究、报告版本历史、财报分析面板回归 AI 解读。
- 完整分阶段计划与实时状态见 [docs/roadmap.md](docs/roadmap.md)。
