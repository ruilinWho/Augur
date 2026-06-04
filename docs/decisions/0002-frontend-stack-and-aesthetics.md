# ADR 0002 — 前端技术栈细化 + 美学优先原则

- **状态：** 已接受
- **日期：** 2026-05-31
- **决策者：** 作者 + Claude

> 取代 ADR-0001 中"前端"一行的笼统描述，给出 M1 要用的具体库与版本策略，并把"美学优先"确立为硬约束。

## 背景

ADR-0001 定了"React + TS + Vite"的大方向。M1 要落地，需要确定具体的路由/状态/样式/图表/拖拽/动效库。两条额外约束：

1. **作者明确要求用前沿技术**（主流稳定的最新大版本）。
2. **作者对前端美观度要求极高，并把它与投资的理智性直接挂钩**——所以美观不是"加分项"，是验收门槛。

版本现状已于 2026-05 核实：Vite 8（`@vitejs/plugin-react` v6 用 Oxc）、Lightweight Charts v5（35KB、多窗格）、Tailwind v4（CSS-first）、Python 3.13。

## 决策

**前端栈（前沿且稳定）：**

| 关注点 | 选择 | 理由 |
|---|---|---|
| 框架 | **React 19** | 最新稳定；生态最大 |
| 构建 | **Vite 8** + `@vitejs/plugin-react` v6（Oxc） | 当前最快、ESM 原生 |
| 语言 | **TypeScript**（strict） | 端到端类型 |
| 样式 | **Tailwind CSS v4**（`@tailwindcss/vite`，CSS-first `@theme`） | 现代、快；配合自定义 token |
| 路由 | **TanStack Router** | 类型安全路由 |
| 服务端状态 | **TanStack Query** | 缓存/重试/失效一把梭 |
| 客户端状态 | **Zustand** | 轻、无样板 |
| 校验 | **Zod** | 运行时校验 + 类型推导（API 边界） |
| 图表 | **Lightweight Charts v5** + **KLineChart** | 丝滑主图 + A股指标 |
| 拖拽 | **dnd-kit** | 自选分区拖拽组织，无障碍友好 |
| 动效 | **Motion**（原 Framer Motion） | 克制顺滑 |
| 无头组件 | **Radix UI** primitives | 无障碍/交互正确，视觉我们自己上妆 |
| 包管理 | **pnpm** | 快、磁盘友好 |

**美学优先原则（硬约束）：**
- 每一屏按**资深产品设计师**水准打磨，对齐 Anthropic 暖色纸感美学。
- 完成门槛 = [design-system.md §1 验收清单](../design-system.md)。达不到不算完成。
- 波动数据冷静呈现；平静、克制、低噪音优先于功能堆叠。

## 考虑过的替代方案

- **Next.js / TanStack Start（全栈/SSR）** —— 否决：本地单用户应用，SSR/服务端路由无收益，反增复杂度。我们要的是 SPA + 本地 FastAPI。
- **React Router 7 而非 TanStack Router** —— 都可；选 TanStack 因为端到端类型安全更强，与 TanStack Query 同源。
- **shadcn/ui 直接用** —— 不直接套其默认视觉：我们有自己的 Anthropic 设计系统，改用 **Radix primitives 自己上妆**以完全掌控美学（可借鉴 shadcn 的结构）。
- **Redux Toolkit** —— 否决：对单用户本地应用过重，Zustand 足够。
- **CSS-in-JS（styled/emotion）** —— 否决：Tailwind v4 + CSS 变量更快、更契合"排版走变量"的诉求。
- **Recharts / visx 做 K 线** —— 否决：通用图表库画专业 K 线吃力；金融专用库（Lightweight Charts / KLineChart）体验更好。

## 后果

**正面**
- 端到端类型安全（Router + Query + Zod + TS）。
- 全部主流前沿、社区活跃、文档好、对 LLM 开发友好。
- 美学作为硬约束写进流程，不会"先能用再说"地交付糙界面。

**代价 / 风险**
- Tailwind v4 / Vite 8 较新，个别周边插件可能需要跟进——但都是官方主推方向。
- 多库组合（Router/Query/Zustand/Zod）有一点学习与装配成本；缓解：都是同代主流，配方成熟。
- 自己用 Radix 上妆比直接抄组件慢——但这正是达到美学门槛的代价，值得。
