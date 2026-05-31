# 路线图与状态 — Augur

> **实时状态板。** 里程碑一移动就更新这里。它回答"什么已存在、下一步是什么？"
> `CLAUDE.md §12` 指向这里。

图例：✅ 完成 · 🟡 进行中 · ⚪ 未开始

---

## 当前焦点

**M1 — 基础设施 + 自选分区 + K线。** 搭脊梁：LLM 网关骨架、四市场数据适配器、两级板块、漂亮的图表外壳。其余一切都挂在这上面。

---

## M0 · 脚手架 ✅

- ✅ 仓库结构（`backend/ frontend/ resources/ data/ docs/`）
- ✅ `CLAUDE.md` 宪法（中文为主）、`.gitignore`（resources 入库 / data 忽略）、README
- ✅ 规划文档：架构、路线图、设计系统、ADR-0001/0002
- ✅ 项目记忆约定（`docs/memory/`）+ 前沿技术栈定稿

## M1 · 基础设施 + 自选分区 + K线 ⚪

**后端**
- ⚪ `uv` 项目 + 依赖装好；FastAPI 在 `:8788` 启动
- ⚪ `config.py` —— 从 `.env`/`config.local.toml` 读设置 + 厂商注册表
- ⚪ `llm/` —— litellm 网关：角色、自配 `base_url`、流式、用量记录
- ⚪ `market/` —— `MarketAdapter` 接口 + FinanceDataReader 适配器（四市场全覆盖），Parquet 缓存优先
- ⚪ `watchlist/` —— 两级分区 CRUD + 排序，强制 `depth ≤ 2`
- ⚪ 端点：`/market/ohlcv`、`/market/search`、`/market/quote`、`/watchlist/*`

**前端**
- ⚪ Vite 8 + React 19 + TS + Tailwind v4 脚手架；设计 token 接好（排版可调）
- ⚪ 自选分区主导航：两级树 + dnd-kit 拖拽组织
- ⚪ K线视图（Lightweight Charts v5）：标的搜索、市场切换（US/HK/CN/KR）、周期切换
- ⚪ App 外壳：布局、设置面板（厂商配置 + 排版控制）

**退出标准：** 在任一市场建板块（如 `半导体/GPU`）、把票拖进去、点击 → 看到丝滑好看的 K 线；LLM 网关能通过某个配置好的厂商回答一句测试 prompt。**且每一屏达到设计师级完成度（见 design-system.md 验收清单）。**

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
