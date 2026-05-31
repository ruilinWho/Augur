# Augur 前端

React 19 + TypeScript + Vite 8。图表、深度分析、新闻日报、自选分区导航。
Anthropic 对齐、排版可调、**美观度极高**的 UI。
见 [../CLAUDE.md](../CLAUDE.md) §5、§9 与 [../docs/design-system.md](../docs/design-system.md)。

## 状态

⚪ 尚未搭建 —— 在 **M1** 创建。计划引导（用 pnpm）：

```bash
pnpm create vite@latest . --template react-ts      # Vite 8 + React 19 + TS
pnpm add lightweight-charts klinecharts             # 图表
pnpm add @tanstack/react-router @tanstack/react-query zustand zod  # 路由/状态/校验
pnpm add @dnd-kit/core @dnd-kit/sortable motion     # 拖拽 + 动效
pnpm add -D tailwindcss @tailwindcss/vite           # Tailwind v4（CSS-first）
# 无头组件按需：pnpm add @radix-ui/react-*（自己上妆，不套默认视觉）
pnpm dev                                            # dev server，代理 /api → :8788
```

## 计划结构

```
src/
├── features/   watchlist（主导航）· kline · analysis · news
├── components/ 共享 UI 原子件
├── theme/      设计 token + CSS 变量 + 排版控制
├── lib/        api 客户端（REST + SSE）、hooks、格式化
└── app/        路由(TanStack Router)、布局、设置
```

## 不可妥协

- 组件里不硬编码颜色 / 字号 / 间距——消费设计 token / CSS 变量，让排版保持用户可调（CLAUDE.md §5）。
- **每一屏按资深产品设计师水准打磨**，达到 [design-system.md §1 验收清单](../docs/design-system.md) 才算完成。
