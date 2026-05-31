# 开发环境 / 启动（M1）

一句话：先起后端再起前端；前端用 npm（非 pnpm）；HMR 偶发卡死要重启 vite。

## 起服务
- 后端：`cd backend && uv run uvicorn augur.main:app --reload --port 8788`
- 前端：`cd frontend && npm run dev`（:5173，Vite 代理 `/market` `/watchlist` `/llm` → :8788）
- **必须先起后端**，前端才有数据。

## 工具链（本机实测 2026-06）
- uv 0.7.2 · Python 3.13.5 · Node 20.19.5 · npm 10.8.2（满足 Vite 8 的 Node ≥20.19）。
- **pnpm 装不上**：corepack 激活失败 + `npm i -g pnpm` 文件冲突（EEXIST）。**当前一律用 npm**。
  docs/ADR 写的是 pnpm，实际用 npm，lockfile = `package-lock.json`。日后能装 pnpm 再切。

## 坑
- **切 git 分支 + 快速连续编辑后，Vite HMR 会卡死**（控制台刷 `[vite] Failed to reload …`，页面渲染不出/0 行）。
  这不是代码错（`npm run build` 能过就说明代码没问题）。**解法：`pkill -f vite` 后重新 `npm run dev`**。
- 前端视图切换用 **Zustand**（非 TanStack Router）—— 本地应用无 URL 路由需求，Router 暂缓。
- K线颜色用 `KLineView` 里的 `PALETTE` 常量（镜像 index.css token），避免读 CSS 变量的 effect 时序问题。
- 设置（字号/行距/字体/主题/涨跌色）持久化在 localStorage `augur-ui`；**`selectedSymbol` 不持久化**（首开是空态，符合预期）。
- 截图自检用 Claude Preview MCP：`.claude/launch.json` 配 `frontend`（`npm --prefix frontend run dev`）；`.claude/` 已 gitignore。

## 验证清单（M1 / M1.5 已过）
- 四市场真实 K 线、两级分区、明暗双主题、四视图 → 截图验证。
- `npm run typecheck`、`npm run build`、后端 ruff、控制台零错。
