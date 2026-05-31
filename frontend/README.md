# Augur 前端

React 19 + TypeScript + Vite 8。图表、深度分析、新闻日报、自选分区导航。
Anthropic 对齐、排版可调、**美观度极高**的 UI。
见 [../CLAUDE.md](../CLAUDE.md) §5、§9 与 [../docs/design-system.md](../docs/design-system.md)。

## 状态

✅ M1 基础功能已搭好（用 **npm**；corepack/pnpm 当前环境装不上，故用 npm）。

```bash
npm install     # 装依赖（已有 package.json / package-lock.json）
npm run dev     # dev server :5173，已代理 /market /watchlist /llm → 后端 :8788
npm run build   # 生产构建（tsc --noEmit + vite build）
npm run typecheck
```
> ⚠️ 需先起后端：`cd ../backend && uv run uvicorn augur.main:app --reload --port 8788`。

技术栈：**Vite 8 + React 19 + Tailwind v4 + TanStack Query + Zustand + Zod + Lightweight Charts v5**。
视图切换暂用 Zustand（无 URL 路由需求，TanStack Router 暂缓）；拖拽排序（dnd-kit）后端已就绪、前端待接。

> 字体：**英文衬线 Source Serif 4 + 中文苹方**（Anthropic 路子）；中文一律苹方（系统），不用中文宋体；数字 JetBrains Mono。详见 [../docs/design-system.md §3](../docs/design-system.md)。

## 结构（现状）

```
src/
├── main.tsx, App.tsx          外壳：顶栏 Tab(看/研/知)+设置齿轮 + 上下文面板 + 主舞台
├── store.ts                   Zustand：视图/选中标的/市场 + 排版主题设置（持久化）
├── api.ts                     fetch + Zod 校验 + TanStack Query 钩子/变更
├── index.css                  设计 token + 组件样式（移植自 design-preview）
└── features/
    ├── watchlist/             市场过滤 + 两级树 + 内联新建/加标的 + 实时报价
    ├── kline/                 Lightweight Charts v5（蜡笔纸感主题）
    ├── settings/              字号/行距/字体/主题/涨跌色 + LLM 角色状态
    └── misc/                  研/知 占位（M2/M3 接入）
```

## 不可妥协

- 组件里不硬编码颜色 / 字号 / 间距——消费设计 token / CSS 变量，让排版保持用户可调（CLAUDE.md §5）。
- **每一屏按资深产品设计师水准打磨**，达到 [design-system.md §1 验收清单](../docs/design-system.md) 才算完成。
