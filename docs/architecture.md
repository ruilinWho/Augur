# 架构 — Augur

> [AGENTS.md](../AGENTS.md) §2 的详细配套文档。这里回答“各部分如何拼在一起”。

## 1. 系统形态

Augur 是一个**本地双进程应用**：Python/FastAPI 后端负责数据、LLM、调度和本地存储；React/Vite 前端负责交互、图表和流式呈现。开发期通过 localhost 上的 HTTP + SSE 通信；桌面打包方向是用 Tauri 2 把前端和 Python sidecar 包成 macOS `.app`。

```
浏览器 / Tauri webview
┌──────────────────────────────────────────────┐
│ frontend/ React 19 + TS + Vite 8              │
│ 看/研/知/记/设置 · 图表 · 设计 token · SSE UI  │
└───────────────────────┬──────────────────────┘
                        │ HTTP + SSE (:8788)
┌───────────────────────┴──────────────────────┐
│ backend/ FastAPI                               │
│ market/ watchlist/ journal/ llm/ research/     │
│ news/ notes/ settings/ storage/                │
└───────────────────────┬──────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │ data/ (gitignored)             │
        │ db/ SQLite · cache/ Parquet     │
        └───────────────────────────────┘
```

## 2. 后端模块

| 模块 | 职责 | 关键点 |
|---|---|---|
| `config.py` / `runtime_config.py` | 静态 env + UI 写入的运行时配置 | `data/config.local.json` 注入 env，即时生效，密钥不入 git |
| `storage/` | SQLite schema/migration + Parquet 行情缓存 | WAL + `busy_timeout`，适配请求线程和 APScheduler 并发写 |
| `market/` | 四市场 OHLCV、报价、搜索、基本面 | `MARKET:CODE` 归一化，FDR/akshare/yfinance/pykrx，多源缓存和港股兜底 |
| `watchlist/` | 两级自选分区 + 标的管理 + 排序 | 市场是过滤器，不是第三层；同层重名幂等 |
| `journal/` | 绑定个股的判断日记 | K 线 marker 和复盘记录 |
| `llm/` | litellm 网关 | 角色路由、动态连接、SSE、token 用量落库、可选联网检索 |
| `research/` | 单股深度研究 + 导入研报 | 确定性数据 gather → 带引用报告；导入 markdown 研报和评论 |
| `news/` | 信源摄取、翻译、过滤、日报、要点、机会、叙事、公司披露 insight | RSS/API/X/ticker lane；LLM 接地与 JSON 加固；披露读 SEC 正文产 insight、按 filing 缓存 |
| `notes/` | 与个股无关的自由长文笔记 | 置顶、markdown、防抖自动保存 |
| `settings_router.py` | 设置页 API | LLM 连接、信源 key/配置、测试端点、自动生成计划 |
| `main.py` | FastAPI app/lifespan | 初始化 DB、预热标的目录、启动/停止调度器、localhost CORS |

分层约定仍是：`router.py` 处理 HTTP，`service.py` 处理业务逻辑，适配器/存储层处理 I/O。可单测的纯逻辑尽量不要直接碰网络和磁盘。

## 3. 数据与存储

`resources/` 是版本化输入，`data/` 是运行时输出。

- `resources/prompts/`：LLM 提示词模板。
- `resources/sources/`：RSS/X/主题/别名等人工维护清单。
- `data/db/augur.db`：自选、日记、设置、LLM 用量、新闻、日报、机会、研究报告、导入研报、自由笔记。
- `data/cache/`：OHLCV、标的目录、基本面、新闻辅助缓存等可重建数据。

SQLite schema 在 [`backend/augur/storage/db.py`](../backend/augur/storage/db.py)；新增运行时字段要做幂等 migration，不能只改 `CREATE TABLE IF NOT EXISTS`。

## 4. 四条产品管线

### 看 · View

`GET /market/ohlcv` 和 `GET /market/quote` 走 `market.service`：

1. 解析 `MARKET:CODE`。
2. resolver 选择市场适配器。
3. Parquet/TTL 缓存优先，只抓缺口。
4. 前端 `KLineView` 用 Lightweight Charts v5 渲染蜡笔纸感 K 线。

K 线下方模块包括财报分析与「综合认知」，并支持拖拽重排。「综合认知」合并个人判断、公司披露、重大事件、新闻/社媒背景与 LLM 事实反馈；公司披露由 LLM 读 SEC 正文（财报抓 Exhibit 99.1 新闻稿）产出投资 insight（headline + 利好/利空/中性/存疑 + 确定性），程序性披露隐藏。K 线事件 marker（判/财/会）统一钉在价格轴底部对齐带。未自选标的可一键加入自选分区。

### 研 · Research

`POST /research/stock/generate` 是 SSE 流：

1. `gather(symbol)` 收集价格摘要、基本面、财报趋势、已清洗个股新闻、SEC 申报等确定性数据。
2. `_format_data` 拼成事实块和编号引用源。
3. `deep_research` 角色生成 markdown 报告。
4. 报告落 `research_reports`，一股一份，重生成覆盖。

导入研报走 `imported_reports`：一股多份，可排序、编辑正文、写“我的评论”。

### 知 · Know

`news/` 有两类 lane：

- `feed`：策展 RSS/API/X 聚合流，进入全局日报、要点、机会。
- `ticker`：按自选股 ticker 定向抓取，服务个股叙事和相关资讯，不淹没全局流。

刷新链路：

1. `ingest_all()` 并发抓取 RSS、Bloomberg、财联社、东财、X 等源。
2. `translate_pending()` 翻译标题。
3. `relevance.judge_pending()` 从严过滤非投资相关内容。
4. `linker.link_pending()` 确定性挂钩自选股。
5. `stock_tag.tag_pending()` LLM 识别上市公司，再用 `grounding` 接地到真实 `MARKET:CODE`。

蒸馏链路：

- `generate_report_stream()`：趋势日报。
- `generate_clusters()`：新闻/推特要点，支持按天、主题、账号分类。
- `generate_opportunities()`：今日机会，LLM 候选再经市场搜索接地。
- `generate_narrative()`：单股叙事时间线。
- `generate_all()`：刷新 + 日报/要事/推特要点/机会并行生成，是前端“一键刷新并生成”和白天自动任务的单一真相。

LLM JSON 输出统一做宽松解析和失败重试，避免推理模型在大输入下输出 `<think>` 或轻微畸形 JSON 导致空结果。

### 记 · Note

`notes/` 是第 4 支柱，不绑定个股。前端 `NotesNav` + `NotesView` 提供列表、置顶、编辑/预览、删除和 700ms 防抖自动保存。它与 `journal_entries`（个股判断日记）和 `imported_reports`（个股导入研报）保持边界清晰。

## 5. LLM 网关

所有 LLM 调用都走 `backend/augur/llm/gateway.py`。

- 连接列表：`{id, name, base_url, api_key, model, web_search}`，统一按 OpenAI compatible 调用。
- 角色：`chat`、`deep_research`、`summarize`、`cheap`。
- 设置页可动态增删连接、拖拽排序、测试单个/全部模型、指派角色。
- token 用量写 `llm_usage`。
- `web_search` 目前用于 Qwen/百炼类兼容接口，通过 `extra_body.enable_search` 注入；不支持的厂商可能忽略或报错。

## 6. 前端结构

```
frontend/src/
├── App.tsx                  顶栏 + 布局主入口
├── api.ts                   REST/SSE 客户端与 TanStack Query hooks
├── store.ts                 全局 UI 状态
├── components/              共享 UI：Markdown / Collapse / Toast / ErrorBoundary / GripDots
├── features/
│   ├── watchlist/           两级分区、Miller 列、加股、拖拽
│   ├── kline/               K 线主视图
│   ├── analysis/            财报分析面板
│   ├── journal/             判断日记
│   ├── research/            单股研究 + 导入研报
│   ├── news/                知：资讯/个股导航、日报、要点、机会、叙事、信源画像
│   ├── notes/               记：自由长文
│   └── settings/            外观、模型、数据信源、自动任务
└── theme/                   motion 等共享 token
```

信息架构：顶部 Tab 是 `看 / 研 / 知 / 记`，设置在右上角齿轮。下方是“上下文面板 + 主舞台”；`知` 使用 Miller 式多列导航，`看/研` 共享自选分区上下文。

## 7. 调度

APScheduler 在后端 lifespan 启动：

- 07:30：抓取 + 定向抓取 + 日报/要点/机会。
- 23:30：当天归档，保证历史日可回看。
- 白天整点：如果设置开启，执行 `generate_all(refresh_first=True)`，窗口默认 11:00-23:00，可在设置页调整。

所有后台任务失败只记日志，不阻断 app 启动；重任务内部有互斥/`max_instances=1`，避免堆叠打源。

## 8. 桌面打包方向

当前仍是本地开发形态。桌面版本计划用 Tauri 2 + PyInstaller sidecar 打包，数据迁移到 `~/Library/Application Support/Augur/`，密钥迁移到 macOS Keychain。
