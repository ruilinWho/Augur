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
pnpm add @fontsource/source-serif-4 @fontsource/jetbrains-mono # 字体（中文苹方用系统，无需安装）
pnpm add -D tailwindcss @tailwindcss/vite           # Tailwind v4（CSS-first）
# 无头组件按需：pnpm add @radix-ui/react-*（自己上妆，不套默认视觉）
pnpm dev                                            # dev server，代理 /api → :8788
```

> 字体：**英文衬线 Source Serif 4 + 中文苹方**（Anthropic 路子）；中文一律苹方（系统），不用中文宋体；数字 JetBrains Mono。详见 [../docs/design-system.md §3](../docs/design-system.md)。

## 计划结构

```
src/
├── app/        外壳：顶栏 Tab 导航(看/研/知/设置) + 上下文面板 + 主舞台、路由、布局
├── features/   watchlist · kline · analysis · news · settings（Meta 设置集中于此）
├── components/ 共享 UI 原子件
├── theme/      设计 token + CSS 变量 + 排版控制
└── lib/        api 客户端（REST + SSE）、hooks、格式化
```

## 不可妥协

- 组件里不硬编码颜色 / 字号 / 间距——消费设计 token / CSS 变量，让排版保持用户可调（CLAUDE.md §5）。
- **每一屏按资深产品设计师水准打磨**，达到 [design-system.md §1 验收清单](../docs/design-system.md) 才算完成。
