# AGENTS.md — Augur

> **Augur** 是一个本地优先、LLM 驱动的个人多市场投资**研究**工作台（macOS）。
> 本文件是**项目宪法**。**每次会话开始请完整读一遍。**
> 它会被自动载入上下文——请保持精炼、最新、高信噪比。
> **更新 `AGENTS.md` + `docs/` 是每次改动的一部分**，不是事后补的（见 §10）。

---

## 1. Augur 是什么 —— 以及不是什么

四根支柱 / four pillars：

1. **看 · View** —— 美股 / 港股 / A股 / 韩股的 K 线，以**极致美观**的方式渲染。
2. **研 · Research** —— 用 LLM + Deep Research 对单支股票做详尽、可用于主动决策的分析。
3. **知 · Know** —— 每天聚合全球顶级信源与社媒/论坛弱信号，由 LLM 蒸馏成**决策级日报 / 要事 / 机会 / 风险反证**，让作者在天级别与世界信息流同步并形成动作判断。
4. **记 · Note** —— **与个股无关的自由长文笔记**（市场随想 / 方法论 / 复盘思考），markdown 长文、置顶、防抖自动保存。区别于绑定个股的「判断日记」「导入研报」。

贯穿四者的基础设施：

- **自选分区（两级板块）** —— 自定义 List / 板块来组织你跟踪的标的（见 §8）。
- **统一 LLM 网关** —— 任意厂商、可自配 `base_url`（见 §6）。

表层：贴合 **Anthropic 设计哲学**、字体/行距可调、**设计师级美观**的 UI（见 §9——**美观是硬指标，不是装饰**）。

**非目标 —— 硬边界（无明确指令不得跨越）：**

- ❌ **不是交易终端。** Augur 永不下单、不动钱、不执行任何交易。（见 §11）
- ❌ **不是喊单器，也不替作者承担交易执行。** Augur 的目标是让作者**仅通过 Augur** 做出上好的、精良的、专业的、时效性的、全面的、主动 / Active / 激进的投资决策；输出必须暴露不确定性、标注来源、给出反证条件与风险边界。
- ❌ **不是多用户 / 云 SaaS。** 单用户，本地运行在作者的 Mac 上。

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
│  notes/     → 「记」自由长文笔记（与个股无关）             │
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
├── AGENTS.md              ← 你在这（项目宪法）
├── README.md              ← 面向人的简介
├── docs/                  ← 架构 · 路线图 · 设计系统 · ADR · 记忆
│   ├── architecture.md
│   ├── roadmap.md
│   ├── design-system.md   ← 设计系统（美学准则在此）
│   ├── decisions/         ← ADR 架构决策记录（只增不改）
│   └── memory/            ← 跨会话项目记忆（见 §10）
├── backend/               ← Python（uv 管理）FastAPI 服务
│   ├── pyproject.toml
│   └── augur/  market/ · watchlist/ · journal/ · llm/ · research/ · news/ · notes/ · storage/ · config.py · main.py
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
| 前端包管理 | **npm（当前）** | 仓库真相是 `package-lock.json`；pnpm 是原目标，待本机环境可用再切 |

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
- **功能开发**在 `main` 的分支上做；初始脚手架/文档可直接提交 `main`（作者已授权 Codex 自行 commit & push）。
- 提交带 co-author trailer（遵循 harness 规则）。

### 本地运行（随脚手架落地更新）
```bash
# 后端（在 backend/ 里 `uv sync` 之后）
cd backend && uv run uvicorn augur.main:app --reload --port 8788

# 前端
cd frontend && npm run dev
```

---

## 6. LLM 网关约定（`backend/augur/llm/`）

- **一切走 litellm。** 不在各 feature 里散落直连 `openai`/`anthropic` SDK。
- 模型 = **可动态增删的连接列表**（不再写死厂商）：每个连接 `{id, name, base_url, api_key, model, web_search}`，**一律 OpenAI 兼容**（`litellm model="openai/<model>"` + `api_base` + `api_key`，覆盖 DeepSeek/各类中转站/OpenRouter/国产模型；原生 Anthropic 走中转站）。详见 [ADR-0008](docs/decisions/0008-settings-v2-dynamic-llm-connections.md)。
- **联网检索（连接级 `web_search` 开关）**：开启后 `gateway._kwargs` 注入 `extra_body={"enable_search":True, "search_options":{"search_strategy":"max","forced_search":True}}`（**通义千问 Qwen/百炼** 的联网参数；Perplexity 需国际卡、作者办不了，故选 Qwen 这条国内可走的路）。供「研·Deep Research」与「知·个股·信源调研」走 `deep_research` 角色联网。**仅该开在支持联网的连接上**（不支持的厂商服务端会忽略/报错）。`web_search` 字段仍存于 `runtime_config`、`gateway` 仍据它注入，但**设置卡的「联网检索」开关已按作者要求移除**（暂不在 UI 暴露；省略该字段＝保留已存值不动，可来日恢复或经 `config.local.json` 直配）。官方 OpenAI Deep Research API 已确认可用（Responses API `o3-deep-research` / `o4-mini-deep-research`），后续「研」按 ADR-0011 做官方优先、自建兜底。
- 区分**角色**：`chat`、`deep_research`、`summarize`、`cheap`。每角色**指到一个连接**——作者可把摘要/翻译/筛选路由到便宜模型、深度分析路由到前沿模型。`gateway` 解析角色→连接→OpenAI 兼容调用；有**测试连接**端点 `/settings/llm/test`（发极小请求验证）。
- **两处配置，同一真相：** 既可改 gitignored `backend/.env`，也可在前端**「设置」页**改（连接增删/角色指派/信源 key），落 gitignored `data/config.local.json`（`runtime_config`，注入 `os.environ` **即时生效、无需重启**，UI 优先于 `.env`；**首次自动把旧 `.env` 配置迁成连接**，不中断）。`/settings/*` 端点**绝不打日志、写入名经 guard**（§11）；密钥**永不入 git**（`data/` gitignore）。**本地单用户 UI 回显明文 key**（作者明确要求"反正只有我自己用"——key 仅在 localhost 后端↔前端间流动）。数据/新闻信源 key 也走这里（`news/source_registry.py` 注册表驱动，**按 财经/新闻/论坛 三类**[`group`]＋支付方式徽标；详见 [ADR-0007](docs/decisions/0007-api-config-and-source-feasibility.md)）。**信源还可声明可配置项**（注册表 `config` 字段，type=accounts/tags）：**Twitter 关注账户**、**东财检索关键词**等在设置页源行内可增删（`runtime_config.get/set_source_config`，gitignored、即时生效、read-with-fallback 到内置默认；`POST /settings/source/config` 校验+清洗）。
- 面向用户时**总是流式**。**总是把 token 用量记到 `data/db`** 以便看成本。
- 提示词模板放 `resources/prompts/`（版本化），按名加载——别在代码里内联大段提示词。

---

## 7. 行情数据约定（`backend/augur/market/`）

- **内部归一化符号：** `MARKET:CODE` → `US:AAPL`、`HK:00700`、`CN:600519`、`KR:005930`。每个适配器负责与各库原生格式互转。
- **适配器模式：** 每个源一个模块（`fdr.py`、`akshare.py`、`yfinance.py`、`pykrx.py`），统一在 `MarketAdapter` 接口后（`get_ohlcv`、`search`、`quote`）。一个 resolver 按市场选最佳适配器并带回退。
- **缓存优先：** OHLCV 缓存为 Parquet 到 `data/cache/`，键为 `MARKET:CODE/interval`。只抓缺失的尾巴。尊重限流。
- 各市场的交易日历、币种、代码格式都不同——存进适配器元数据，**别假设美股惯例**。
- **检索（`search.py` + `listings.py`）= 本地目录 ∪ 东方财富实时联想，统一打分去重。** 本地目录（FDR 列表 + akshare A股中文名 + KOSPI/KOSDAQ 韩文名，缓存 Parquet）管美股英文名 + 韩股 + 离线兜底；东财 suggest 管港股/A股/新股 + 拼音（MiniMax/智谱 也搜得到）；跨语言别名靠 `resources/sources/aliases.yaml`（海力士→KR:000660）。带缓存/超时/失败降级。**坑见 [docs/memory/search-data-sources.md](docs/memory/search-data-sources.md)**（东财无韩股、`push2` 被代理拦截、FDR 港股列表未实现…）。
- **港股回收代码兜底（`hk_backfill.py`）**：HKEX 代码退市后会被**回收再分配**（如 `00100`＝老 Clear Media 退市 → 2026-01-09 给 MiniMax-W），雅虎/FDR 把新旧历史搅在一起、**只吐最新 1 根**。`service._fetch_daily`：HK 的 FDR 结果 `< _HK_THIN_ROWS(10)` 根时回退 `hk_backfill.hk_history`＝**腾讯**（`web.ifzq.gtimg.cn`，直连含当日）首选、失败回退**新浪**（akshare `stock_hk_daily`）——两者都**不走 `push2his`**（被代理拦截，**别用 `stock_hk_hist`**）。source 记 `hk_backfill`，带 TTL 不狂打、放在"最新交易日"判断前（坏缓存也能回填）、不可达则静默回退 FDR。前端 K 线对 `≤3` 根标的显「新股 · 仅 N 个交易日」（区分真新股 vs 数据缺）。K 线区间＝**1月/3月/6月/1年**（`3m` 走通用 range 解析）。
- **基本面（`fundamentals.py`）= yfinance（雅虎）一库覆盖四市场**：① 快照 `get_fundamentals`（市值/P-E/净利率，缺 P/E 用 市值/净利润 兜底）→ 前端置于 **K 线上方** 的指标条；② 历史 `get_financials(symbol, period)`（营收/营收增长/净利/净利率/EPS/EPS增长/自由现金流 + 财报链接）→ **K 线下方「财报分析」趋势表**（默认显示关键行、「更多指标」展开其余；**最新一期在右边缘**，列定宽、过宽则横向滚动并默认滚到最新）。**季度（默认，~5–7 期）/ 年度（~4–5 年）段控可切**；**增长率一律同比**（季度 vs 去年同季＝回退 4 列、年度 vs 上一年），避开季节性误导。本币原值，前端按亿/万亿格式化；缺数据置 null → 「—」。6h 缓存（key 含 period）。**LongBridge OpenAPI 已调研、暂不采用**（偏交易、需账号/凭证、基本面薄——见 ADR-0004）。

---

## 8. 自选分区（两级板块）约定（`backend/augur/watchlist/`）

作者用**自定义"分区/板块/List"**来组织跟踪的标的。这是贯穿看/研/知/记的导航基础设施（看哪些、研哪些、新闻按分区聚合）。

- **硬约束：最多两级（invariant）。**
  - 一级板块：如 `半导体`、`航天`、`新能源`。
  - 二级板块：挂在某一级下，如 `半导体/GPU`、`半导体/光通信模块`。
  - **二级板块不能再有子级。** 后端 service 层强制 `depth ≤ 2`；前端不暴露第三级入口。
- **数据模型（SQLite）：**
  - `sections(id, name, parent_id /* NULL=一级 */, sort_order, created_at)`
  - `watchlist_items(id, section_id, symbol /* MARKET:CODE */, note, sort_order, added_at)`
  - 一只标的**可同时属于多个分区**；可直接挂在一级下，也可挂在二级下。
- **市场（美/港/A/韩/全部）是过滤器，不是第三层。** 标的的市场已编码在 `symbol`（`MARKET:CODE`）里；导航上市场是个跨分区的**筛选器**（面板顶部分段控件），与"两级板块"正交——既好看，又保住两级铁律。
- **分区按"标的所在市场"显示（不是死绑一个市场）。** 一个分区可跨市场（`半导体` 里能同时有 `US:NVDA` + `KR:000660`）。选了具体市场时，只露出在该市场**有标的**的分区、且只显示该市场的标的（`半导体` 在韩股只露海力士、在 A 股只露 300308）；**有标的、但本市场无标的的分区被隐藏**（这样有美股的 `大模型` 不污染韩股）；但**真正的空分区（任何市场都没标的）在所有市场都显示**——它无市场归属，便于在任一市场视图里就地创建并填充（作者反馈：在港股下建新板块不应被甩去「全部」）。逻辑在 `service.list_tree(market)`（`has_any_stock` 判定空分区豁免剪枝）。
- **前端** `features/watchlist/` 是看/研的**上下文面板**（左栏，顶栏 Tab 之下）：市场过滤器 + 可折叠两级树，**dnd-kit 拖拽**：①标的跨板块换区 + 列内重排（`PATCH /watchlist/items/{id}` 移动 + `/reorder`），②**板块本身可拖拽排序**（一级、二级两层皆可，`SecRow` 同为 sortable+droppable——拖标的悬停才显 `drop-into` 虚线、拖板块互相经过只重排）。**板块重排市场安全**：前端只传当前市场可见的子集，后端 `_reorder_sections` 只在「被拖动子集占据的槽位」内重排、隐藏兄弟（有标的但本市场无的板块）原地不动，避免跨市场顺序错乱。整行点击折叠；**列2（二级板块卡）**：有子板块时顶部给一个 **「全部」**（聚合 直属＋所有二级的标的、按 symbol 去重、**只读**——跨板块拖排无意义）+ **「直属」仅当有直属标的才显示**（空则隐藏，避免冗余）；点一级板块默认落到「全部」（无子板块则直接显其标的）。**分区名双击重命名**（`PATCH /watchlist/sections/{id}` 按 id 改、市场无关；前端失效**所有市场**的 sections 查询→切市场即时一致、不"分叉"；同层重名 409 拒绝、空名 422；单击/双击靠 190ms 延迟消歧避免误折叠）；检索式加股（选了市场只敲代码即可，`全部`则全市场搜）；点击标的 → 在主舞台看/研。**左栏宽度可拖拽**（`--panel-w`，持久化）。
- **标的行 + 个股标题显示"看得懂的简洁名"**（`search.display_name`：KR:000660→SK海力士；**美股英文名去公司后缀** `_clean_name`：Redwire Corp→Redwire、Planet Labs PBC→Planet Labs、Apple Inc.→Apple、Micron Technology→Micron、Credo Technology Group Holding→Credo（含 Technology/Technologies，迭代去多重后缀；词内如 Vishay Intertechnology 不误切）；CJK 名不受影响；搜索仍同时认原名与清洗名），代码/市场作次要信息；名字随报价端点 `/market/quote` 的 `name` 字段带出。
- 删除一级板块时如何处理其下二级与标的：**级联删除**（FK `ON DELETE CASCADE`，连带二级与标的）。

---

## 9. 设计系统（**美学是硬指标**）

完整 token 与排版见 [docs/design-system.md](docs/design-system.md)。**这里是不可妥协的纲领：**

- **美观对 Augur 是功能性的，不是装饰。** 作者明确要求：前端美观度对齐 **Anthropic / 资深产品设计师** 水准，而且**这会直接影响投资的理智性**——平静、克制、低噪音的界面支持更清醒、更少情绪化的决策；杂乱刺眼的界面会侵蚀判断。
- **完成标准 = "资深产品设计师会让它上线吗？"** 绝不留默认样式、未对齐、粗糙的 UI。宁可少做一个功能，也要把已做的做到精致。
- **暖纸感**，非惨白。米白/象牙底、柔和描边、慷慨留白、温和圆角、克制动效。
- **标志性强调色** ≈ 陶土/珊瑚 `#D97757`，少量点睛。其余低饱和、安静的配色。
- **排版 = 英文衬线 + 中文苹方**（Anthropic 路子）：英文/标题用 **Source Serif 4** 衬线，**所有中文用苹方**（`PingFang SC`，系统）——不用中文宋体。仅 Source Serif 4/JetBrains Mono 自托管到 `resources/fonts/`。
- **K线红绿要「蜡笔纸感」**：**规整矩形 · 直角不加圆角**（圆角小尺寸下显歪）、哑光低饱和、半透明、轻 + 极淡纸纹，绝不鲜艳实心。涨跌色习惯可配（美股绿涨红跌；A/港/韩红涨绿跌）。
- **导航外壳：** 功能切换在**顶栏**（`Augur` 一行横向 Tab 看/研/知/记 + 右上齿轮进设置）；下方两栏＝上下文面板（自选分区树 / 日报列表 / 笔记列表 / 设置分类）＋主舞台。**所有 Meta 设置集中在「设置」**，不散落顶栏。
- **浏览器标签页图标：** favicon 使用 `🌱`（`frontend/public/favicon.svg`），保持轻量、自然、克制。
- **主舞台默认全宽、文案低噪音。** 看/研/知/记/设置的主舞台应占满剩余宽度，避免遗留窄列 `max-width`；空态只标状态（暂无/加载/生成中/选择标的），不写“从左侧选择/点某按钮”的教学句；设置行优先“标签 + 控件”，说明只留给风险、隐私、不可逆操作。
- **按钮必须先设计对齐。** 新增任何按钮前先确定其所属操作列/操作行；命令按钮（测试/保存/添加/删除）用固定宽度和稳定位置对齐，信息入口（凭证/文档/官方入口）优先用文本链接，不伪装成散落的小按钮。每个页面完成前检查按钮是否落在同一视觉网格上。
- **字体/字号/行距/行宽是用户可调的一等公民**，全部走 CSS 变量；组件只读 token。

---

## 10. 文档与记忆纪律（重要）

本项目**全程由 LLM 协助开发**，所以写下来的持久上下文就是产品的记忆。规则：

- **每次改动同一口气更新文档。** 新能力 → 更新 `AGENTS.md` 相关 § + `docs/`。带权衡的新决策 → 在 `docs/decisions/` 加一篇 ADR（只增不改、编号）。
- **`docs/roadmap.md`** 是实时状态板——已完成、当前焦点、下一步。里程碑移动就更新它。
- **`docs/memory/`** 存放放不进代码或 ADR 的跨会话上下文：坑、数据源怪癖、作者偏好、"为什么放弃了 X"。一文件一主题。（这是**项目级记忆**，区别于 Codex 的个人 `~/.Codex` 记忆。）
- 当你（LLM）学到某个非显然、未来会话会重复踩坑的东西——**在结束这一轮前把它写下来**，放对地方。
- 保持 `AGENTS.md` 精瘦：深度内容链接到 `docs/`；本文件是索引 + 不变量，不是百科。

---

## 11. 护栏 —— 不可妥协

1. **永不交易、永不动钱。** 只做研究。
2. **git 里不放密钥。** API key 放 gitignore 的 `.env` / 系统 Keychain。绝不把 key 打进日志或提交。`data/` 被忽略——保持如此。
3. **主动决策必须可追溯。** 免费数据源可能延迟/出错；LLM 分析会幻觉。任何主动结论都要标注新鲜度、引用来源、触发条件、反证条件与不确定性。
4. **尊重限流。** 激进缓存、失败退避。别把作者的 IP 打到被封。
5. **本地优先且私密。** 无遥测、不把作者数据发往任何地方，除非作者明确配置的 LLM 厂商。

---

## 12. 当前状态与下一步

- **「记」（第 4 支柱，新）：** `notes/`（schemas/service/router）+ `notes` 表（title/body/pinned/时间戳）。`GET/POST /notes`、`GET/PATCH/DELETE /notes/{id}`。前端「记」Tab＝左栏 `NotesNav`（列表：置顶在前 + 预览 + 相对时间 +「＋新建」）＋主舞台 `NotesView`（标题 + 正文 编辑/预览 切换 + 置顶/删除 + **防抖 700ms 自动保存**带「已保存/未保存/保存中」状态）。**与个股无关的自由长文**（市场随想/方法论/复盘思考）；区别于 journal/imported_reports（均绑定个股）。store＝`features/notes/store.ts`（selectedId，非持久）。**共享 Markdown 组件** `components/Markdown.tsx`（`##`/`#`/`>`/`-`/`|表格|`/`[n]` 可点引用）——研/导入研报/记 共用，取代各处手写解析（导入研报因此获得表格/链接支持）。
- **新闻自动标股（不限自选，"发现机会"）：** `news/stock_tag.py` + `news/grounding.py`——对相关新闻批量 LLM 识别涉及的上市公司 → **确定性接地**到真实 `MARKET:CODE`（防编造，与「今日机会」同款 `grounding.resolve_company`）→ 写 `news_item_symbols`（`matched_by='llm'`）。新闻卡股票 chip 不再只显自选：**自选股=陶土+圆点、LLM 发现的非自选股=中性**，都可点→看（作者：「看到新闻去看相应的股票，即使不在自选，才叫发现机会」）。`news_items.tagged` 每条只标一次；`linker.attach_symbols` 带 `in_watchlist` 区分。`refresh` 链：摄取→翻译→relevance→linker→**stock_tag**。relevance/translate **循环到清空**（不再封顶，垃圾都滤、英文都翻）。
- **夜间全面优化（10 领域审计→实现，见 [docs/roadmap.md](docs/roadmap.md)）：** 后端稳健性（SQLite WAL+busy_timeout、**token 用量落库** `/llm/usage`、EDGAR 缓存 TTL、财联社失败正确记健康度、**A股北交所 BSE 解析** `symbols.cn_exchange`、个股资讯词边界去误配、relevance 积压改 ASC、调度补「今日机会」、SSE 防代理缓冲头+错误帧收尾、CORS 任意本地端口、web_search 仅注入研/对话角色）；前端（**SSE 错误吞噬修复** `consumeSSE`、`HttpError.status` 判 404 空态、全局 `ErrorBoundary`、`MotionConfig reducedMotion`、细粒度 `useUI` selector 修拖栏重渲染、**K 线蜡烛半透明蜡笔纸感**、平盘态、报价新鲜度标注、基本面/财报「失败≠无数据」、研报常驻决策边界说明、`--measure` 行宽、齿轮右对齐、`#fff`→`--accent-ink`）。
- **本地运行：** 后端 `cd backend && uv run uvicorn augur.main:app --reload --port 8788`；前端 `cd frontend && npm run dev`（:5173，已代理 `/market /watchlist /journal /llm /news /research /notes /settings /health`）。LLM 需 `backend/.env` 或设置页运行时配置（见 `.env.example`，**密钥永不入库**）。
- **知·个股（融合主线，已落地）：** `news_items.lane`（`feed` RSS策展流 / `ticker` 自选股定向抓取）。**①定向抓取** `directed.py`：每只自选股按 ticker 直取雅虎新闻、落 `lane='ticker'` 并**确定性挂钩**（`matched_by='targeted'`），补齐新上市/冷门票名字盲区；全局流/日报/要点/翻译/相关性**只扫 `lane='feed'`**、prune 豁免定向源（28 股不淹宏观流）；`POST /news/directed/refresh`＋并入 scheduler。**②标的叙事** `stock_narratives`＋`generate_narrative`：近 45 天挂钩资讯喂 summarize → `{summary 主线, timeline[{date,title,importance,refs}]}`、事件提炼合并、refs 接真实条目、防幻觉；`GET/POST /news/narrative`、`GET /news/stock`；前端**「知」新增一级「个股」**（二级=自选股列表、主舞台=综述+左轴时间线+抓取/重生成+资讯流）。提示词 `stock_narrative.md`。**③机会卡直通研** `store.research(symbol)`＋机会卡关联 chip 拆分胶囊「名字→看 · 研→研」。**④晨读 Top3**：总览 hero「晨读 · 今日要事」复用 news@1d 要点前 3、scheduler 每日预生成；前端为可展开卡片，展开显示该要事对应的信源与原始信息。**⑤「自上次以来」** `useUI.lastSeenNewsAt`（持久化）+ `markNewsSeen`：总览列出打卡基准后的新条目（确定性零 LLM）。融合主线队列 ①–⑦ 全落地。
- **知·决策级升级（新，ADR-0010）：** 产品目标改为 **decision-grade active investing workbench**：作者应能仅通过 Augur 做出专业、及时、全面、主动/激进且可追溯的投资决策；Augur 仍永不下单/不动钱。前端「资讯」第三层新增**决策**页：当日主动机会、风险/反证、催化、关联标的集中一屏，chip 直达「看/研」。提示词改为输出动作倾向、触发条件、反证条件与不确定性。**多信源 lane**：资讯第三层＝总结 / 决策 / 新闻 / 推特 / Reddit / 雪球 / 小红书；新闻按 theme，社交/论坛按 `source_prefix`+category，共用时间线/要点/市场/仅自选过滤。**Reddit 已真实接入**：`reddit.py` public JSON，配置 `reddit.subreddits`，source=`Reddit·r/<sub>`，并入 ingest→translate→relevance→linker→stock_tag；设置页可配/可测试。**雪球**已接入轻量内容探活（`xueqiu.py`，完整 Cookie header 才可靠），但尚未并入自动抓取；**小红书**仍只登记配置与 UI lane，不伪装已接入。
- **深夜产品修正（新）：** 「资讯」source lane 的 cluster scope 按真实 lane 分离，避免 Reddit/雪球/小红书读到新闻/推特旧要点；雪球/小红书 lane 支持**关注用户 + 个股/关键词**配置；cluster 标题/理由清洗 `[47]` 这类裸编号；「决策」显示当日独立信源数；「看·相关资讯」改为 AI 摘要卡（`/news/for/brief`），不再铺直接新闻列表；「记」去冗余标题/空态文案；设置·模型连接卡默认折叠且编辑字段按 base_url 短、API key 长分配；数据/信源名称保持唯一官方名，Bloomberg 频道成为可配置项，信源「测试 / 保存 / 添加」按钮统一操作列对齐。
- **看·个股头部信息层级（新）：** K 线头部按第一性原理收敛为一个统一信息带：当前价/涨跌、52 周位置百分比、市值、市盈率、净利率、更新时间；删除日内高低、52 周刻度条和 `fdr/yfinance` 等内部适配器名，不再把基本面指标拆成独立 snapshot 条。规则见 [docs/memory/view-stock-info-hierarchy.md](docs/memory/view-stock-info-hierarchy.md)。
- **信源测试修正（新）：** 设置·数据/信源的操作按钮固定宽度且 `nowrap`，`测试中…` 不再换成两行；twtapi 兼容新版 `api.twtapi.io` 与旧版 `api.twtapi.com/api/v1/twitter`，并区分 key 无效、HTTP 429、旧 API `code=429/sub_code=42903` 月度额度用完、账号不存在，不再误报“解析账号失败”；**所有信源测试错误统一翻成中文问题诊断**（没有配置/没有接入/没有额度/没有权限/网络超时/适配器需更新），不向作者显示 `RuntimeError`/第三方英文报错；信源详情页测试结果必须全宽换行显示，不复用模型卡片 150px 省略徽标（见 [docs/memory/source-test-diagnostics.md](docs/memory/source-test-diagnostics.md) + [docs/memory/twtapi-source-quirks.md](docs/memory/twtapi-source-quirks.md)）。Tushare Pro / 必盈 / iTick 已按作者要求从设置页与探活注册中移除。
- **设置 · 全部 / 信源健康度（新）：** 设置左栏新增**「全部」**（默认入口）：`POST /settings/test-all` 一键体检所有 LLM 连接 + 登记信源 API，按**接通 / 未配置 / 额度 / 权限或余额 / 未接入 / 异常**展示，并给 twtapi、雪球、小红书等凭证入口；体检结果**不返回 key**。`source_health` 表补 `last_error`，`ingest_all` 记录最近失败中文原因，公共 RSS 401/403 归为“源站拒绝访问/反爬/下线/UA 需更新”而非凭证问题；前端健康度默认只列异常源，可“显示全部”展开 90+ 源。见 [docs/memory/source-health-dashboard.md](docs/memory/source-health-dashboard.md)。
- **外部信源接入向导（新）：** `news/source_registry.py` 增加 `docs_url/official_url/setup/best_use/boundary`，设置·数据/信源与设置·全部体检直接展示**取凭证入口 + 文档/官方入口 + 最佳用途 + 接入边界**。核查结论：X 当前用 `twtapi` 的 `TWTAPI_KEY`（X 官方 `console.x.com` 仅作未来原生适配器入口）；Reddit public JSON 已接且无需 key；雪球暂无一手公共内容 API，非官方路线是网页登录 Cookie/token；小红书官方 Ark App Key 偏商家开放平台，不等于公开笔记搜索 API。见 [ADR-0012](docs/decisions/0012-external-social-source-strategy.md) + [docs/memory/external-source-api-setup.md](docs/memory/external-source-api-setup.md)。
- **白天自动 · 全部生成（新）：** `service.generate_all(date, refresh_first)`＝**单一真相**：刷新信源（RSS+推特+自选定向）→ 蒸馏当天 日报/要事/**推特要点**/机会，每步独立成败、LLM 未配则只刷新。供两处共用：① 调度器 `_hourly_job` 每个整点跑（**默认 11:00–23:00 可配**，`runtime_config.get/set_auto_refresh`＋`GET/POST /settings/schedule`＋设置页「自动」，运行时读配置即时生效；`max_instances=1`+APScheduler 不堆叠）；② 前端「资讯·总结」**「一键刷新并生成」**按钮（先刷新→并行 日报/要事/推特要点/机会，带 `抓取·日报·要事·推特·机会` 状态点）。**新闻/推特默认「要点」**（仅今天，历史日默认时间线）。**积压清空根治**（作者诊断「新闻多但要事/机会涉及少」）：relevance/translate/stock_tag 的 loop-until-empty 改为**毒批跳过**（`_select_pending(limit, offset)`，队首一批解析失败时 advance offset 继续清，连续 `_MAX_FAILS=5` 批才停）——旧 `break` 会让队首毒批永久堵死整条 ASC 队列（实测 969 条 `relevance=0` 跨 13 天积压）；`stock_tag.tag_pending` 也改循环到清空。**蒸馏深度可配**：要点/机会喂 LLM 的当日条数上限**可配、默认 1000、0=不限**（`runtime_config.get/set_cluster_input_max`，`_cap_items` 读它，超出记日志不静默丢；设置页「自动 · 生成 · 蒸馏深度」选；日报不受限、始终喂全部）。删死常量 `_DIGEST_INPUT_MAX`/`_OPP_INPUT_MAX`。**今日要事条数可配**（`brief_top_n` 默认 5，原写死 3；`MorningBrief` 读 `useSchedule`；同设置段选）。**LLM 调用并行化**（作者：尽量并行、不担心 token）：① `generate_all` 的 日报/要事/推特要点/机会 **4 个生成并发**（`ThreadPoolExecutor`，各写不同表/scope、WAL 串行化写；前端按钮本就并行，此为补齐每小时调度）；② translate/relevance/stock_tag 的批量 LLM 改 **每轮并发多批**（`news/_batch.map_batches`，`WORKERS=8`，window=`_BATCH×WORKERS`，毒「窗」跳过逻辑同前；`market.search`/`gateway` 用量落库均线程安全）。
- **每股专属信源回流（新）：** `stock_sources` Phase 2 已接上「追踪」闭环：作者/LLM 为某股发现并启用的 **X 账号 / Reddit 子版 / RSS·Atom URL** 会随 `POST /news/directed/refresh?symbol=` 抓取，写入 `news_items(lane='ticker')` 并以 `matched_by='stock_source'` 确定性挂回该股；`news_for_symbol` 现在合并 Yahoo ticker 新闻、持久化挂钩流与聚合流，再交给 `/news/for/brief` 做 AI 摘要。因此「看·相关资讯」会看到专属源的新信息，且卡片头部显示专属源数量与「刷新」按钮。普通网页、雪球、小红书仍需各自稳定适配器/Cookie 策略后才能真实抓取；不把未接入源伪装成已接入。细节见 [docs/memory/per-stock-source-tracking.md](docs/memory/per-stock-source-tracking.md)。
- **下一步：** M3 续——**X(twtapi) 已接入**（`news/twtapi.py`，screen_name→rest_id→GraphQL 时间线，归一进 `ingest_all`，账号清单 `resources/sources/x_accounts.yaml`，英文推文经 translate 自动翻中；见 ADR-0007 §5）、雪球从轻量探活推进到关注用户/关键词抓取、小红书等登录型论坛源适配器待作者定夺、个股 IR 新闻室·官方 X 并入「一条龙」、KR DART / CN cninfo 一手扩展、arXiv 论文 lane、机会接地阈值调优、日报/机会按**自选分区**聚合；M2「研」续——深度增强：接**实时网络搜索 / Deep Research**（多轮检索→综合）、按**自选分区**批量研究、报告版本历史、财报分析面板回归 AI 解读。
- 完整分阶段计划与实时状态见 [docs/roadmap.md](docs/roadmap.md)。
