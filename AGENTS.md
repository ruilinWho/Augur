# AGENTS.md — Augur

> **Augur** 是一个本地优先、LLM 驱动的个人多市场投资**研究**工作台（macOS）。
> 本文件是**项目宪法**。**每次会话开始请完整读一遍。**
> 它会被自动载入上下文——请保持精炼、最新、高信噪比。
> **更新 `AGENTS.md` + `docs/` 是每次改动的一部分**，不是事后补的（见 §10）。

---

## 1. Augur 是什么 —— 以及不是什么

五根支柱 / five pillars：

1. **看 · View** —— 美股 / 港股 / A股 / 韩股的 K 线，以**极致美观**的方式渲染。
2. **研 · Research** —— 用 LLM + Deep Research 对单支股票做详尽、可用于主动决策的分析。
3. **知 · Know** —— 每天聚合全球顶级信源与社媒/论坛弱信号，由 LLM 蒸馏成**决策级日报 / 要事 / 机会 / 风险反证**，让作者在天级别与世界信息流同步并形成动作判断。
4. **寻 · Discover** —— 从「知」的信息流里发现**自选之外**反复出现的标的：聚合 LLM 标股（不限自选）、跨天累积提及次数与证据、作者拍板（加入自选 / 忽略）。区别于「机会」（当日事件论点卡）——这是标的轴、跨天累积的候选池（见 [ADR-0015](docs/decisions/0015-discovery-pillar.md)）。
5. **记 · Note** —— **与个股无关的自由长文笔记**（市场随想 / 方法论 / 复盘思考），markdown 长文、置顶、防抖自动保存。区别于绑定个股的「判断日记」「导入研报」。

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
│   └── augur/  market/ · watchlist/ · journal/ · llm/ · research/ · news/ · notes/ · storage/ · config.py · main.py
├── frontend/              ← React + Vite + TS 前端
├── resources/             ← 入库的静态资产（版本控制）
│   ├── fonts/             ← 自带字体
│   ├── prompts/           ← LLM 提示词模板（要版本化！）
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

- **看：** 四市场 K 线、报价头部、52 周位置、基本面、财报趋势、AI 相关资讯摘要、社媒热度摘要、**叙事时间线**（复用「知」的 `/news/narrative`，只读+可就地生成）、判断日记 marker。个股头部只展示决策相关字段，不暴露内部适配器名。ticker 新闻保留雅虎上游摘要、brief 喂正文加厚（见 [view-stock-info-hierarchy](docs/memory/view-stock-info-hierarchy.md)）。
- **研：** 单股研究走 `research.gather(symbol)` 收集本地确定性上下文，再由 `deep_research` 角色流式生成带引用 Markdown；支持导入外部研报、排序、编辑和写个人评论。官方 Deep Research job 化接入是当前优先方向，详见 [ADR-0011](docs/decisions/0011-research-deep-research-api-strategy.md)。**Prompt 模板**（`templates/` 域，SQLite）：设置·模板页管理，`{STOCK}/{NAME}/{MARKET}/{SYMBOL}` 占位符，研页头部「复制 Prompt」按当前标的填充进剪贴板——服务外部网页 Deep Research（ChatGPT/Claude 订阅版无 API），见 [ADR-0014](docs/decisions/0014-prompt-templates.md)。**网页 Research 回流**：导入研报带 `engine`/`source_url`（哪个引擎+原始会话链接），配 `resources/userscripts/augur-capture.user.js`（同源读取→剪贴板→人工粘贴，不驱动会话、不发数据）；Gemini 直接接官方 API。见 [ADR-0016](docs/decisions/0016-web-research-capture.md)。
- **知：** `feed` lane 聚合 RSS/API/X/Reddit/TikHub 等全局信源；`ticker` lane 服务自选股定向新闻和每股专属信源。刷新链路为摄取 → 翻译 → relevance → 确定性挂钩 → LLM 标股 → grounding。日报、要事、机会、决策页、个股叙事和某日快照都围绕可追溯引用与反证条件。
- **寻：** `discovery/` 域聚合 `news_item_symbols` 里 `matched_by='llm'` 的**自选外**挂钩，跨天累计提及次数/出现天数/证据，经 `search` top-2 做自选别名归并（跨语言/股份类/双重上市），落 `discovery_candidates`（状态机 new/dismissed/promoted，作者拍板保留）。零新增 LLM 成本。见 [ADR-0015](docs/decisions/0015-discovery-pillar.md)。
- **记：** `notes/` 提供与个股无关的 Markdown 长文、置顶、预览/编辑和 700ms 防抖自动保存；共享 Markdown 渲染器供研报、导入研报、笔记复用。
- **设置与基础设施：** 设置页管理 LLM 连接、角色指派、信源 key/config、源测试、全部体检、自动刷新、蒸馏深度和 token 用量。后端已做 SQLite WAL/busy_timeout、SSE 错误收尾、源健康度、毒批跳过、批量 LLM 并行化和本地端口 CORS。
- **当前优先级：** 研究任务 job 化；OpenAI/Gemini Deep Research 正式 API 接入；ChatGPT/Claude/Gemini 网页 Research 结果回流 Augur；Prompt 模板与未来 Skills；每股专属信源验证；分区级情报；反思/复盘闭环；Tauri 桌面打包。

本地运行：后端 `cd backend && uv run uvicorn augur.main:app --reload --port 8788`；前端 `cd frontend && npm run dev`。密钥放 `backend/.env` 或设置页写入的 `data/config.local.json`，二者都不入 git。
