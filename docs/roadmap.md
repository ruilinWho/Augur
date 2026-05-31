# 路线图与状态 — Augur

> **实时状态板。** 里程碑一移动就更新这里。它回答"什么已存在、下一步是什么？"
> `CLAUDE.md §12` 指向这里。

图例：✅ 完成 · 🟡 进行中 · ⚪ 未开始

---

## 当前焦点

**M1 基础功能已跑通 ✅** —— 四市场真实 K 线、两级自选分区、LLM 网关骨架、顶栏外壳/设置全部端到端工作并已截图验证。下一步 **M2（单股深度分析）**。

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
- ⚪ `/market/search` —— 拆到 #9，待做

**前端**（Vite 8 + React 19 + Tailwind v4 + TanStack Query + Zustand + Zod）
- ✅ 脚手架 + 设计 token（纸感/蜡笔/Source Serif + 苹方）落进 `theme`
- ✅ 顶栏外壳（看/研/知 + 设置齿轮）+ 上下文面板 + 主舞台
- ✅ 设置：字号/行距/标题字体/主题/涨跌色习惯（实时 CSS 变量 + 持久化）+ LLM 角色状态
- ✅ 自选分区面板：市场过滤 + 两级树 + 内联新建/加标的 + 每行实时报价 + 点击选股
- ✅ K线（Lightweight Charts v5）：四市场真实数据、蜡笔纸感主题、明暗、周期切换、空态
- ⚪ dnd-kit 拖拽排序（后端 `/reorder` 已就绪，前端待接）

**已达成退出标准：** 点分区里的票 → 看到真实四市场 K 线；明暗/排版/涨跌色实时可调；各屏达设计师级完成度（已截图验证）。
**待补（不阻塞，挪入 M1.x / M2 期间）：** LLM 实时对话需主人在 `.env` 配 key；标的搜索 #9；前端拖拽排序；TanStack Router（当前用 Zustand 管视图，无 URL 路由需求暂缓）。

## M2 · 单股深度分析 ⚪

- ⚪ `research/` 编排器：规划 → 收集（行情+新闻+网络/Deep Research）→ 综合 → 引用
- ⚪ `POST /research/stock` SSE 流；报告持久化
- ⚪ akshare / yfinance / pykrx 深度适配器（基本面、财务）
- ⚪ 分析 UI：流式、结构化、带引用的报告；暴露不确定性

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
