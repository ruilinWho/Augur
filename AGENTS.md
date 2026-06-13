# AGENTS.md — Augur

> **Augur** 是一个本地优先、LLM 驱动的个人多市场投资**研究**工作台（macOS）。
> 本文件是**项目宪法**。**每次会话开始请完整读一遍。**
> 它会被自动载入上下文——请保持精炼、最新、高信噪比。
> **更新 `AGENTS.md` + `docs/` 是每次改动的一部分**，不是事后补的（见 §10）。

---

## 1. Augur 是什么 —— 以及不是什么

五根支柱 / five pillars：

1. **看 · View** —— 美股 / 港股 / A股 / 韩股的 K 线，以**极致美观**的方式渲染。
2. **研 · Research** —— 用外部 Deep Research（网页版 ChatGPT/Claude/Gemini）对单支股票做详尽、可用于主动决策的分析，经 Prompt 模板 + 导入研报回流 Augur（不自建生成）。
3. **知 · Know** —— 每天聚合全球顶级信源与社媒/论坛弱信号，由 LLM 蒸馏成**决策级日报 / 要事 / 机会 / 风险反证**，让作者在天级别与世界信息流同步并形成动作判断。
4. **寻 · Discover** —— 从「知」的信息流里发现**自选之外**反复出现的标的：聚合 LLM 标股（不限自选）、跨天累积提及次数与证据、作者拍板（加入自选 / 忽略）。区别于「机会」（当日事件论点卡）——这是标的轴、跨天累积的候选池（见 [ADR-0015](docs/decisions/0015-discovery-pillar.md)）。
5. **记 · Note** —— **与个股无关的自由长文笔记**（市场随想 / 方法论 / 复盘思考），markdown 长文、一级文件夹归类（拖拽换夹、未归类区、双击重命名）、置顶、防抖自动保存。区别于绑定个股的「判断日记」「导入研报」。

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
│  theses/    → 反证雷达（立论 + 证伪条件 + 新闻监控）        │
│  llm/       → litellm 网关（任意厂商、自配 base_url）      │
│  research/  → deep-research 编排                         │
│  news/      → RSS/API 摄取 + APScheduler + 趋势日报       │
│  notes/     → 「记」自由长文笔记（与个股无关）             │
│  storage/   → SQLite（元数据）+ Parquet（行情缓存）        │
└───────────────────────┬──────────────────────────────┘
                        │  （桌面打包方向）
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
│   └── augur/  market/ · watchlist/ · journal/ · theses/ · llm/ · research/ · news/ · notes/ · storage/ · config.py · main.py
├── frontend/              ← React + Vite + TS 前端
├── resources/             ← 入库的静态资产（版本控制）
│   ├── fonts/             ← 自带字体
│   ├── prompts/           ← LLM 提示词模板（要版本化！）
│   ├── skills/            ← 可插拔投研技能（<slug>/SKILL.md，丢文件夹即生效；见 ADR-0017）
│   ├── userscripts/       ← 网页 Research 回流脚本（ADR-0016）
│   └── sources/           ← 新闻信源清单 + aliases.yaml（跨语言别名种子）（YAML）
└── data/                  ← 仅运行时 · 被 git 忽略 · 在 git 里永不作为真相来源
    ├── cache/（parquet）   ├── db/（sqlite）  └── logs/
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
| 桌面 | **Tauri 2** + PyInstaller sidecar | 原生 .app，<10MB（Electron 动辄 100MB+） |
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

### 打包成可分发 macOS app（Tauri + PyInstaller，见 [ADR-0019](docs/decisions/0019-package-as-macos-app.md)）
```bash
# ① 后端 → 独立二进制 onedir（改了后端代码/依赖后才需重跑）
cd backend && uv run pyinstaller augur.spec --noconfirm
# ② → Augur.app（自动 npm run build + 编 Rust 外壳 + 把后端 onedir 打进 bundle）
cd frontend && npx tauri build   # → src-tauri/target/release/bundle/macos/Augur.app
```
图标源 `frontend/src-tauri/icon-source.svg`；分发件（`首次打开.command` / `安装说明.txt`）在 `packaging/`。后端 spawn/退出清理见 [run_server.py](backend/run_server.py) 的父进程看门狗 + Rust `RunEvent` 双兜底。

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
- **适配器模式：** 每个适配器一个模块（`fdr_adapter.py`、`pykrx_adapter.py`；akshare/yfinance 不是独立适配器，而是内联在 `listings.py`/`fundamentals.py`/`hk_backfill.py`）。**OHLCV** 走统一的 `MarketAdapter` 抽象（`base.py`，只约束 `get_ohlcv`）+ resolver 按市场选适配器并带回退。**search / quote / fundamentals 不塞进适配器接口**，各自独立模块（`search.py`、`market.service` 的 quote、`fundamentals.py`）——它们的数据源与 OHLCV 适配器并非一一对应（如基本面统一走 yfinance、检索走本地目录∪东财）。
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
- **`docs/roadmap.md`** 是产品路线图——当前能力、正在推进、未来方向。路线变化就更新它。
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

Augur 当前已形成完整的本地研究工作台：**看 / 研 / 知 / 寻 / 记** 五个表面都可用，底层包含两级自选分区、四市场行情、动态 LLM 网关、新闻/社媒摄取、SQLite/Parquet 本地存储、运行时设置、信源健康度和调度任务。完整产品状态见 [docs/roadmap.md](docs/roadmap.md)。

- **看：** 四市场 K 线、报价头部、52 周位置、基本面、财报趋势；新增**公司披露层**（SEC 财报/8-K + 财报期兜底），K 线 marker 标 **个人判断「判」**、**财报/申报「财」**、**电话会「会」**（优先真实披露日，无披露源时才退回 financials period 近似；电话会「会」的 transcript 源 FMP 已于 2026-06-13 移除——付费 endpoint、免费档不可用——marker 抽象保留待接新源）。K 线下方的旧「相关资讯」+「判断日记」已合并为单一 **「综合认知」**：顶部保留近况/社媒背景，主线同时呈现个人判断、公司披露、重大事件，并在每条判断下嵌入 LLM 对该判断的事实反馈（印证/证伪/混合/尚未检验 + 确定性价格反馈 + 可点来源）；判断变更会失效缓存，刷新并评价会重抓定向新闻/披露并重算。每条公司披露经 LLM 读 SEC 正文（财报抓 Exhibit 99.1 新闻稿、非财报 8-K 抓主文档正文）产出**投资洞察**（具体 headline + 一句 insight + 利好/利空/中性/存疑徽章 + 确定性），取代旧的机械申报标签，程序性无价值披露隐藏，insight 按 filing 永久缓存。披露材料同时喂个股摘要与重大事件生成；新闻与披露冲突时以披露为事实优先级。头部有**一键复制 Prompt**（共享 `CopyPromptButton`，看/研共用）。详见 [company-disclosure-layer](docs/memory/company-disclosure-layer.md)、[kan-cognition-timeline](docs/memory/kan-cognition-timeline.md)、[stock-info-and-social-lanes](docs/memory/stock-info-and-social-lanes.md)、[view-stock-info-hierarchy](docs/memory/view-stock-info-hierarchy.md)。
- **研：** **不再自建深度研究生成**（2026-06-13 移除 `research.gather` + `deep_research` 流式生成与存量报告展示，见 [ADR-0018](docs/decisions/0018-remove-builtin-research-and-fmp.md)）。研页 = **复制 Prompt**（喂外部网页 Deep Research）+ **导入研报**（回流 ChatGPT/Claude/Gemini 结果，可排序、编辑、写个人评论）；`deep_research` LLM 角色保留（信源调研 `stock_sources.discover` 等仍用）。官方 Deep Research job 化接入是当前优先方向，详见 [ADR-0011](docs/decisions/0011-research-deep-research-api-strategy.md)。**Prompt 模板**（`templates/` 域，SQLite）：设置·模板页管理，`{STOCK}/{NAME}/{MARKET}/{SYMBOL}` 占位符，研页头部「复制 Prompt」按当前标的填充进剪贴板——服务外部网页 Deep Research（ChatGPT/Claude 订阅版无 API），见 [ADR-0014](docs/decisions/0014-prompt-templates.md)。**网页 Research 回流**：导入研报带 `engine`/`source_url`（哪个引擎+原始会话链接），配 `resources/userscripts/augur-capture.user.js`（同源读取→剪贴板→人工粘贴，不驱动会话、不发数据）；Gemini 直接接官方 API。见 [ADR-0016](docs/decisions/0016-web-research-capture.md)。**可插拔 Skills**（`skills/` 域）：`resources/skills/<slug>/SKILL.md`（frontmatter+正文+占位符），丢文件夹即生效；研页「复制 Prompt」合并启用技能+模板，设置·模板页管理启用；含移植的卡点评分卡（`POST /skills/scorecard`）。首个技能「供应链卡点研究」蒸馏自 Serenity 方法。见 [ADR-0017](docs/decisions/0017-pluggable-skills.md)。
- **知：** `feed` lane 聚合 RSS/API/推特/Reddit/TikHub 等全局信源；`ticker` lane 服务自选股定向新闻和每股专属信源。刷新链路为摄取 → 翻译 → relevance → 确定性挂钩 → LLM 标股 → grounding。**「总结」是资讯的单一决策入口（原「决策」tab 已并入、删除）**：上半部分是**结构化综合日报**——不再是 markdown 长文（作者：太长无法专注），而是 `generate_report()` 一次结构化 LLM 调用产出 `{verdict 总判断, sections[], risks[], watch[]}` 再**确定性接地**公司名→MARKET:CODE（复用 `grounding.resolve_company`）：渲染成 **总判断卡 + 主题卡（重要性徽章 critical/high/med/low＝非常重要/重要/留意/次要 · **加粗下划线小标题** · 分点 CitedPoint · 关联标的「看 K 线 / 研 深度研究」chip）+ 风险卡 + 明天继续看卡**（前端 `DigestReport.tsx`）。`digest_items_for_day()` 仍合并普通新闻/RSS/博客 + 推特/小红书/Threads/Reddit 全部社媒 lane 作输入（社媒只作弱信号，不另起卡）。落库 `news_reports.body` 存结构化 JSON；旧 markdown 报告经 `get_report` 进 `markdown` 字段、前端回退 `<Markdown>` 渲染。**＋下半张「今日机会」卡**（`OpportunitiesPanel`，每条机会的关联标的同样给「看/研」chip）。「刷新并生成综合日报」按钮刷新后**并行**生成 日报 + 机会。`RelatedChip`/`CitedList`（`shared.tsx`）被日报/机会/个股资讯共用。研报/笔记正文仍走 `components/Markdown.tsx`（#–#### 标题/列表/表格/斜体/代码/`[n]` 引用）。见 [integrated-daily-report](docs/memory/integrated-daily-report.md)。**分区级日报**（「资讯·板块」的「分区」lane，紧邻「总结」）＝ portfolio 轴日报：把当天新闻按作者**一级自选分区**切片，每个分区一张板块卡（板块脉搏 + 逐股异动：重要性徽章 · 名字→看 · 研 · 二级板块标签 · 当日涨跌〔仅今天〕 · 分点可点引用），无动静的票收进「安静」页脚。scope 靠 `news_item_symbols` 挂钩（只蒸馏挂到持有票的新闻；每条 mover 的 symbol 必为喂进去的本分区票，零编造），每个一级分区一次结构化 LLM 调用、分区间并行，落 `news_section_reports`，并入 `generate_all` 由调度器保温。见 [section-level-daily-report](docs/memory/section-level-daily-report.md)。**反证雷达**（「资讯·板块」的「雷达」lane，与「总结」「分区」同组——三种决策视图：世界/我的盘子/我的判断）＝新域 `theses/`：对持有观点的票记下**立论（看多/看空/观望）+ 证伪条件**（可 `POST /theses/draft` AI 起草），`scan_all` 按每天挂钩新闻（复用 `news_item_symbols` scope）判每条证伪条件**正在发生＝⚡反证 / 明确没发生＝印证**（cheap 角色、立论间并行、`condition_id` 确定性校验零编造、近 7 天滚动重算），并入 `generate_all` 保温；告警配色随作者涨跌色习惯（反证=跌色/印证=涨色）；**分区日报 mover 用 `useThesisFlags` 显 ⚡反证 inline 徽章**跨功能缝合。见 [counter-evidence-radar](docs/memory/counter-evidence-radar.md)。**私有微信公众号 RSS**（设置页「微信公众号 RSS」，`WECHAT_BLOG_RSS_URL`）作为 `博客·微信公众号` 动态追加到 RSS feed，前端「资讯·板块」的「博客」是**专属阅读卡视图**（长文低频，不按单日切片——单日几乎永远空——而是滚动近 30 天聚成阅读清单，署名+标题+摘要节选，不做要点聚类/主题过滤）；带 token URL 只写 `data/config.local.json`，**绝不写 `resources/feeds.yaml` 或文档**，并随「配置分享」导入/导出同步，见 [private-rss-blog-lane](docs/memory/private-rss-blog-lane.md)。**推特唯一源＝TikHub**（前缀 `X·`，twtapi 桥已退役、仅每股专属信源仍用）。**社媒 lane（推特/小红书/Threads/Reddit）不套用新闻的严格 relevance、按抓取日归桶**（否则常年空，见 [stock-info-and-social-lanes](docs/memory/stock-info-and-social-lanes.md)）。**微信 TikHub 源已删除**（TikHub `wechat_mp/web/*` 整组服务端长期 400，非我方问题，见 [tikhub-source-quirks](docs/memory/tikhub-source-quirks.md)）；cluster scope 对中文前缀用哈希，避免 `小红书·` / `博客·` 等全中文前缀塌缩成同一 scope 互相覆盖。**每股专属信源** kind 支持 X（twtapi，失败回退 TikHub）、**小红书/Threads 关键词（TikHub）**、Reddit、RSS/Atom（见 [per-stock-source-tracking](docs/memory/per-stock-source-tracking.md)）。**Reddit 直连 reddit.com 公共 JSON 已被按 IP 封 403** → 直连 `reddit.py` 已删，**全 Reddit 走 TikHub**（TikHub 完整代理 Reddit API）：全局 lane＝`tikhub_reddit` 关键词搜；**每股专属子板块经 TikHub `fetch_subreddit_feed`**（`search_subreddit_typeahead` 解析子版名 → 抓该子版 feed），`stock_sources.ensure_auto_reddit` 首次刷新时**自动接入**该股专属子版（解析不到才退关键词搜）。见 [api-share-discovery-signals-reddit-block](docs/memory/api-share-discovery-signals-reddit-block.md)。**设置·模型页「配置分享」**：一键导出/导入全部 API key（LLM 连接+信源 secret）JSON，明文、分享给 contributor 快速配置。**只导出/导入在用的信源 key**（白名单＝`source_registry.live_secret_names()`）；退役源（雪球/Tushare/必盈/iTick 等）的遗留 key 不外泄，且启动时 `runtime_config.prune_secrets` 从 `config.local.json` 自动清掉——**加新数据源须把 key 纳入 `live_secret_names()`**，否则会被当退役 key 清除。
- **知·新鲜度：** 「自上次以来」只作为「总结」标题行的低噪音计数 chip，不再是日报上方独立卡片；`news_read_at` 由手动刷新、一键刷新并生成、APScheduler 自动刷新自动推进，前端不提供「标记已读」按钮。见 [integrated-daily-report](docs/memory/integrated-daily-report.md)。
- **寻：** `discovery/` 域聚合 `news_item_symbols` 里 `matched_by='llm'` 的**自选外**挂钩，跨天累计提及次数/出现天数/证据，经 `search` top-2 做自选别名归并（跨语言/股份类/双重上市），落 `discovery_candidates`（状态机 new/dismissed/promoted）。候选带主导**主题**；前端「关注中/已忽略」切换 + **主题级 & 市场级屏蔽偏好**（不想看的整类/整个市场如韩股不再出现，可恢复）。**重算时对信号最强的前 N 个（`_JUDGE_MAX`）批量过 cheap-LLM：判「是否值得纳入投资关注」（筛掉蹭热点/八卦）+ 给一句话理由（`reason` 列展示在候选卡上）**；理由按 symbol+提及数缓存、小幅波动复用（LLM 慢，避免每次重算全量重判）。证据**读时去重+多源聚合+翻译刷新**（`_dedup_aggregate` 按归一标题把同一事件多源折叠成一条、合并报道来源在卡上显 `+N`、用最新 `title_zh` 跟进翻译；`list_candidates` 读时 `_enrich_evidence` 自愈存量重复、无需重算。**新增字段须同步 `discovery/schemas.py` 的 `DiscoveryEvidence`，否则 FastAPI `response_model` 会静默剥掉**），条数可配。**近月大涨且放量的候选标「异动」pill**（`/discovery/signals` 懒加载、与列表解耦，`market.momentum` 缓存优先）。见 [ADR-0015](docs/decisions/0015-discovery-pillar.md)。
- **记：** `notes/` 提供与个股无关的 Markdown 长文、置顶、预览/编辑和 700ms 防抖自动保存；共享 Markdown 渲染器供研报、导入研报、笔记复用。
- **设置与基础设施：** 设置页管理 LLM 连接、角色指派、信源 key/config、源测试、全部体检、自动刷新、蒸馏深度和 token 用量。后端已做 SQLite WAL/busy_timeout、SSE 错误收尾、源健康度、毒批跳过、批量 LLM 并行化和本地端口 CORS。
- **当前优先级：** OpenAI/Gemini Deep Research 正式 API 接入（job 化、结果回流 Augur）；ChatGPT/Claude/Gemini 网页 Research 回流打磨；每股专属信源验证；催化日历；决策复盘闭环（反证雷达已落地，可继续接信念变化/过期复盘）；Tauri 桌面打包（✅ 首版已落地，见 [ADR-0019](docs/decisions/0019-package-as-macos-app.md)；后续：代码签名 + 瘦身）。

本地运行：后端 `cd backend && uv run uvicorn augur.main:app --reload --port 8788`；前端 `cd frontend && npm run dev`。密钥放 `backend/.env` 或设置页写入的 `data/config.local.json`，二者都不入 git。
