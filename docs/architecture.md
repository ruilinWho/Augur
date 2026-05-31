# 架构 — Augur

> [CLAUDE.md](../CLAUDE.md) §2 的详细配套文档。这是"各部分如何拼在一起"的文档。

## 1. 系统形态

Augur 是一个**本地双进程应用**：一个 Python 后端（数据 + LLM + 调度）和一个 Web 前端（UI + 图表），在 localhost 上用 HTTP/SSE 通信。Phase 2 用 Tauri 外壳把两者包成原生 `.app`——前端代码在浏览器（开发期）和 Tauri webview（打包后）里完全一致，所以我们可以**先不打包、零返工**。

```
                    ┌─────────────────────────────────────┐
   浏览器 / Tauri    │           前端（Vite 8）              │
   webview          │  features/ kline · watchlist · …      │
                    │  theme token · Lightweight Charts v5  │
                    └───────────────┬─────────────────────┘
                                    │  REST + SSE  (localhost:8788)
                    ┌───────────────┴─────────────────────┐
                    │          后端（FastAPI）              │
                    │                                       │
   外部库      ◄────┤  market/    → MarketAdapter resolver   │
   （数据源）        │  watchlist/ → 两级分区 (sections+items)│
   LLM 厂商    ◄────┤  llm/       → litellm 网关（角色路由）  │
   RSS/新闻 API ◄───┤  research/  → deep-research 编排        │
                    │  news/      → 摄取 + APScheduler        │
                    │  storage/   → SQLite + Parquet 缓存     │
                    │  config.py  → 厂商、路径、设置          │
                    └───────────────┬─────────────────────┘
                                    │
                         ┌──────────┴──────────┐
                         │  data/（被忽略）      │
                         │  cache/ db/ logs/    │
                         └─────────────────────┘
```

端口 `8788` 是后端默认端口（随意、好记；可配置）。

## 2. 后端模块

| 模块 | 职责 | 关键依赖 |
|---|---|---|
| `config.py` | 从 env/`config.local.toml` 加载设置 + 厂商注册表；解析 `data/`、`resources/` 路径 | pydantic-settings |
| `market/` | 四市场 OHLCV/报价/搜索，统一在 `MarketAdapter` 后；缓存优先 | FinanceDataReader, akshare, yfinance, pykrx, pyarrow |
| `watchlist/` | 自选分区（两级板块）的增删改查 + 拖拽排序；强制 `depth ≤ 2` | sqlite/SQLModel |
| `llm/` | 单一 litellm 网关；角色→厂商路由；流式；用量记录 | litellm |
| `research/` | Deep-research 编排：规划 → 收集（行情+新闻+网络）→ 综合 → 引用 | litellm, market, news |
| `news/` | 信源注册表摄取（RSS/API）、去重、存储、定时日报 | feedparser, APScheduler |
| `storage/` | SQLite（分区、自选、设置、用量、新闻、日报）+ Parquet 行情缓存 | sqlite3/SQLModel, pyarrow |
| `main.py` | FastAPI app、路由装配、lifespan（启动调度器）、开发期 CORS | fastapi, uvicorn |

**分层规则：** `router.py`（HTTP）→ `service.py`（纯逻辑）→ 适配器/存储（I/O）。让纯逻辑无需网络/磁盘即可单测。

## 3. 三条特性管线 + 自选分区

### 自选分区 · Watchlist（贯穿全局的导航）
两级板块树（一级如 `半导体`、二级如 `半导体/GPU`），是"看/研/知"的入口。**市场（美/港/A/韩/全部）是正交的过滤器，不是第三层**（面板顶部分段控件）。详见 [CLAUDE.md §8](../CLAUDE.md)。
- `GET /watchlist/sections` 返回带标的的分区树
- `POST /watchlist/sections {name, parent_id?}` 建板块（校验 `depth ≤ 2`）
- `POST /watchlist/sections/{id}/items {symbol, note?}` 加标的
- `PATCH`/`DELETE` + 排序端点（拖拽）

### 看 · View（K线）
`GET /market/ohlcv?symbol=US:AAPL&interval=1d&range=2y`
→ resolver 选适配器 → 缓存优先（Parquet）→ 抓缺失尾巴 → 归一化 OHLCV JSON → 前端用 Lightweight Charts 渲染。A股风格指标（MA/BOLL/MACD）用 KLineChart 变体。

### 研 · Research（单股深度）
`POST /research/stock {symbol}`（SSE 流）：
1. **规划** —— LLM 起草分析提纲（基本面、技术面、新闻、风险）。
2. **收集** —— 拉价格历史（market/）、近期新闻（news/），并用网络搜索/Deep Research 找财报、情绪、行业背景。
3. **综合** —— LLM 写出结构化、**带引用**的报告；暴露不确定性。
4. 报告存 `data/db`；各小节完成即流式推给 UI。

### 知 · Know（每日趋势日报）
APScheduler 定时任务（每天，按主人时区）：
1. 摄取 `resources/sources/*.yaml` 里所有信源（RSS/API）。
2. 去重 + 按主题聚类。
3. LLM 逐簇摘要 + 判断跨主题趋势 → 一份**趋势日报**。
4. 存储 + 通知 UI。主人打开 Augur 读"今天世界上发生了什么"。

## 4. LLM 网关设计（`llm/`）

- 在 **litellm** 上薄薄一层封装。Feature 调 `gateway.complete(role=..., messages=..., stream=True)`。
- **厂商注册表**（配置）：`name → { model, api_base, api_key_env, extra }`。自配 `base_url` 让 OpenAI/DeepSeek/中转站/Anthropic 可互换。
- **角色**把意图与厂商解耦：`chat`、`deep_research`、`summarize`、`cheap`。主人在设置里重映射角色→厂商，无需改代码（如把 `summarize` 指向便宜模型）。
- 用量（token、成本估算、延迟）记到 SQLite，供未来成本面板。

## 5. 存储与缓存

- **SQLite**（`data/db/augur.db`）：自选分区、自选标的、用户设置（含排版）、厂商配置缓存、新闻条目、日报、研究报告、LLM 用量。
- **Parquet**（`data/cache/ohlcv/<MARKET>/<CODE>/<interval>.parquet`）：列式行情缓存；只追加尾巴；加载上万根 K 线很快。
- **为何分开：** SQLite 管关系型/可查询状态；Parquet 管大块数值时间序列。两者都在 `data/` 下，可丢弃可重建——在 git 里永不是真相来源。

## 6. 配置与密钥

- **开发期：** `backend/.env`（被忽略）+ 可选 `config.local.toml` 放厂商注册表与信源覆盖。`.env.example` 入库做模板。
- **打包后（P2）：** 密钥移到 **macOS Keychain**；设置/数据放 `~/Library/Application Support/Augur/`。
- 密钥永不进 git 或日志（见 CLAUDE.md §11）。

## 7. 前端结构

**导航外壳（信息架构）：** **功能切换在顶栏**（`Augur` 一行横向 Tab 看/研/知 + 右上齿轮设置），下方两栏 `上下文面板(~260px) | 主舞台`。面板随 Tab 变（自选分区树含市场切换 / 日报列表 / 设置分类）；主舞台占满剩余宽度。详见 [design-system.md §7](design-system.md)。

```
frontend/src/
├── app/            外壳：顶栏 Tab 导航(看/研/知/设置) + 上下文面板 + 主舞台、路由(TanStack Router)、布局
├── features/
│   ├── watchlist/  两级分区树、拖拽组织(dnd-kit)、标的管理（看/研 的上下文面板）
│   ├── kline/      图表（蜡笔纸感）、标的搜索、市场切换、指标
│   ├── analysis/   深度研究视图、流式报告、引用
│   ├── news/       每日日报、信源管理、主题聚类
│   └── settings/   排版 / 主题与色彩 / 数据与市场 / LLM 厂商（所有 Meta 设置集中于此）
├── components/     共享 UI 原子件（Button, Card, Panel, …）
├── theme/          设计 token、CSS 变量、排版控制
└── lib/            api 客户端（REST + SSE）、格式化、hooks
```
- **排版是数据，不是写死的。** 一个设置 store（`settings/`）驱动 CSS 变量（`--font-serif` Source Serif 4、`--font-sans` 苹方、`--text-base`、`--leading`、`--measure`）。组件只读 token。
- 服务端状态用 **TanStack Query**，客户端 UI 状态用 **Zustand**，校验用 **Zod**。
- LLM/研究输出走 SSE 流式、增量渲染。
- **每一屏按资深设计师水准打磨**（见 [design-system.md](design-system.md)）。

## 8. 分阶段与打包

- **Phase 1（现在 → M3）：** 后端 + 前端两个本地 dev server 跑。迭代最快，专注把功能建全。
- **Phase 2（M4）：** Tauri 2 外壳。Python 后端用 **PyInstaller** 打成单可执行文件，作为 **sidecar** 放进 `src-tauri/bin/`；Tauri 启动它、在原生 webview 里服务构建好的前端、处理窗口/菜单/Keychain。目标安装包 <10MB + 自带的 Python 可执行文件。

里程碑拆分见 [roadmap.md](roadmap.md)；每个选型的理由见 [decisions/](decisions/)。
