# 前端踩坑（frontend/）

一句话：折叠组件踩过两个坑——Tailwind 类名撞车 + motion 折叠动画不生效（2026-06）。

## ⚠️ 新增后端路由前缀必须同步 vite.config.ts 的 proxy 列表
- 开发期前端经 Vite 代理访问后端，`vite.config.ts` 的 `server.proxy` 是**按路径前缀逐个枚举**的
  （`/market`、`/notes`、`/templates`…），不是通配。
- 新开一个后端域（如 `/templates`）若忘了加 proxy 条目，请求会落到 Vite 自己手里 →
  **返回 200 + index.html**，zod parse 失败或 mutation 静默不生效，控制台还没有网络错误，极具迷惑性
  （2026-06 加 Prompt 模板时踩过：「添加」点了没反应，后端却一切正常）。
- **教训**：`augur/main.py` 每 include 一个新 router，就在 `vite.config.ts` proxy 里加同名前缀。

## ⚠️ 不要把 class 命名为 `.collapse`（撞 Tailwind v4 内置工具类）
- Tailwind v4 自带 `.collapse { visibility: collapse; }`（本是给表格行用的）。
- 我们自定义的折叠容器一度也叫 `.collapse` → **内容被 `visibility:collapse` 静默隐藏**：
  元素仍占布局高度（~175px 的空白），但**不绘制**，看起来像"折叠坏了/股票消失了"。
- 症状极具迷惑性：DOM 在、`getBoundingClientRect` 有高度、`data-open=true`，就是看不见。
  排查靠 `getComputedStyle(el).visibility === 'collapse'` 才发现。
- **教训**：自定义 class 避开 Tailwind 工具类名（`collapse`/`hidden`/`block`/`grid`/`flex`/`container`…）。
  我们的折叠容器现叫 **`.collapsible` / `.collapsible-inner`**（见 `src/components/Collapse.tsx`）。

## motion（motion/react）+ React 19：折叠别用 AnimatePresence / animate height
- 试过两种 motion 写法做"展开/收起"，在本项目（motion 12.x + React 19）**都不生效**、卡在展开态：
  1. `<AnimatePresence>{open && <motion.div exit={{height:0}} …>}` —— exit 不触发，子节点留在 animate 态。
  2. `<motion.div animate={{ height: open ? 'auto' : 0 }}>` —— 切到 `open=false` 时高度不动，仍 `height:auto`。
  （`open` 状态本身是对的——`data-open` 翻转正常；纯粹是 motion 没把高度动画跑起来。）
- **最终方案＝纯 CSS `grid-template-rows: 0fr ↔ 1fr`**（`.collapsible` + 内层 `overflow:hidden; min-height:0`）。
  最稳：即便浏览器不插值 `fr`，`0fr` 也能真折叠到 0。折叠处（财报/判断日记/自选分区/今日机会/今日要闻）统一走它。
- **同一个坑也咬过视图切换**：`App.tsx` 主舞台一度用 `<AnimatePresence mode="wait">` 包 `motion.div key={view}`。
  因 exit 不触发，旧视图（如「看」的 K 线）**永远退不出去 → 新视图（「知」）永不挂载**（左栏切了、舞台没切，极迷惑）。
  改成**裸 keyed `motion.div`（只 initial/animate 进场、不要 exit/AnimatePresence）**：换 key 即重挂载 + 淡入，干净可靠。
  **教训：本项目里凡是依赖 motion `exit` 的（AnimatePresence/mode="wait"）都不可靠，一律避开。**

## 调试折叠这类"状态对、画面不对"的问题
- 先确认 React 状态：给容器临时加 `data-open={String(open)}`，点一下读属性——能快速区分"点击没生效"还是"动画/样式没生效"。
- 本项目里 `element.click()`（preview_eval）能触发 React `onClick`（实测换选股能验证），所以点击层一般没问题，重点查样式层。

## lightweight-charts v5：图表 marker 用 createSeriesMarkers，不是 series.setMarkers
- v5（5.2.0）**移除了** v4 的 `series.setMarkers(...)` 实例方法。改成独立的 plugin 工厂：
  ```ts
  import { createSeriesMarkers } from 'lightweight-charts'
  const markers = createSeriesMarkers(series, [])   // 创建一次（挂在 series 上），存 ref
  markers.setMarkers([{ time, position:'belowBar', color, shape:'circle', text:'记' }])
  ```
- marker 的 `time` 必须落在时间轴上（日线＝`'YYYY-MM-DD'` 字符串）；**非交易日的日期**（周末/停牌）若不在 K 线数据里，
  直接喂会出问题——本项目（K 线叠判断日记 marker）做法：**把笔记日期吸附到 `<=` 该日期的最近一根 K 线**，
  再 `sort()`（字符串日期字典序＝时间序）+ 去重后 setMarkers。空数组要显式 `setMarkers([])` 清掉旧 marker。
- 类型：`ISeriesMarkersPluginApi<Time>`（存 ref 用）。卸载时连同 chart.remove() 一起置空 ref 即可。
