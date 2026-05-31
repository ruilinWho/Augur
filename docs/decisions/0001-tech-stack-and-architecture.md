# ADR 0001 — 技术栈与总体架构

- **状态：** 已接受
- **日期：** 2026-05-31
- **决策者：** 主人 + Claude（初始规划会话）

> ADR 只增不改。要修订某决策，新增一篇 ADR 来取代它。

## 背景

Augur 是一个单用户、本地优先、LLM 驱动的投资**研究**工作台（macOS），三大特性支柱（四市场 K 线、单股深度分析、每日新闻趋势日报），加一个贯穿全局的**自选分区（两级板块）**导航、一个厂商无关的 LLM 网关、以及一个贴合 Anthropic 的精致 UI。它几乎全程由 LLM 协助构建，所以技术栈必须对 LLM 友好且文档完备。关键约束：

1. **美股 + 港股 + A股 + 韩股的免费数据** 是最硬的约束。
2. 美观、丝滑、**排版可调**的 UI（且美观度被主人视为影响决策理智性的硬指标）。
3. 统一接入任意 LLM 厂商，可自配 `base_url`。
4. 自包含项目；源码 / 资源 / 缓存 清晰分离。

## 决策

| 方面 | 决策 |
|---|---|
| 后端 | **Python 3.13 / FastAPI**，**uv** 管理 |
| LLM 网关 | **litellm** —— 一个接口、自配 `base_url`、角色→厂商路由 |
| 行情数据 | **FinanceDataReader** 作基座（覆盖四市场）+ **akshare**（A股深度）+ **yfinance**（美/全球）+ **pykrx**（韩深度），统一在 `MarketAdapter` 后 |
| 存储 | **SQLite**（关系状态）+ **Parquet/pyarrow**（行情缓存），都在被忽略的 `data/` 下 |
| 自选分区 | 后端 `watchlist/` 模块，两级板块（`depth ≤ 2`），SQLite `sections`+`watchlist_items` |
| 前端 | **React 19 + TypeScript + Vite 8**（细化见 ADR-0002） |
| 图表 | **Lightweight Charts v5**（主）+ **KLineChart**（A股指标） |
| 样式 | **Tailwind v4** + 自定义设计 token（Anthropic 对齐，排版走 CSS 变量） |
| 桌面 | **Tauri 2** + PyInstaller Python sidecar —— **推迟到 Phase 2** |
| 分阶段 | **先 Web**（两个本地 dev server），之后再用 Tauri 包。前端代码两种形态一致。 |

## 考虑过的替代方案

- **用 Node/TS 后端而非 Python** —— 否决：免费、可靠的多市场数据库（尤其 A股 + 韩股）只有 Python 生态有。这一条约束直接决定后端语言。
- **原生 SwiftUI 应用** —— 否决：图表生态弱，难做到可调排版 + Anthropic 的 Web 美学，对 LLM 开发不友好，且 Python 数据库仍需桥接。
- **Electron 而非 Tauri** —— 打包上否决：~100MB+ 体积、更高内存 vs Tauri 原生 webview（<10MB）。Electron 全 JS 的简化对我们没用，因为无论如何都需要一个 Python 进程。
- **直连 OpenAI/Anthropic SDK 而非 litellm** —— 否决：会重复造厂商/base_url 路由，并失去统一的流式/用量界面。litellm 正是为此而生。
- **一开始就 Tauri** —— *暂时*否决：Rust 外壳 + PyInstaller 打包是功能建设期不需要的摩擦。先 Web 迭代快；包它时前端不变。
- **只用一个图表库** —— 保留两个：Lightweight Charts 做丝滑默认；KLineChart 因为 A股用户期待丰富的内置指标（MA/BOLL/MACD）与红涨绿跌习惯。

## 后果

**正面**
- 一种后端语言（Python）掌管所有硬骨头：数据、LLM、调度。
- `FinanceDataReader` 把"四市场"收敛成一个基座依赖。
- litellm 让厂商/中转站靠配置切换——加厂商不改代码。
- 先 Web → 迭代快；之后 Tauri → 不重写也有原生感。
- 从第一天就定下 `resources/`（入库）vs `data/`（忽略）的清晰分离。

**代价 / 风险**
- 到 Phase 2 会有三种语言（Python + TS + 一点 Rust 写 Tauri 外壳）。缓解：Rust 只做外壳；逻辑在 Python/TS。
- 免费数据源有限流 / 偶发不准。缓解：缓存优先、重试退避、新鲜度标注、回退适配器。
- PyInstaller + Tauri sidecar 打包是未来最棘手的一步。缓解：推迟到 M4，靠 HTTP 边界与功能代码隔离。
