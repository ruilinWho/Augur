# 反证雷达（Counter-evidence radar）

日期：2026-06-12

「资讯·板块」新增**「雷达」lane**（`InfoSection='radar'`，与「总结」「分区」同属 `digest` 导航组——三者是**三种决策视图**：总结＝世界今天怎么了 · 分区＝我的盘子今天怎么了 · 雷达＝我的判断有没有被新证据挑战）。

对持有观点的票记下**立论（看多/看空/观望）+ 证伪条件**，系统按每天挂钩新闻盯每条证伪条件，一旦**正在发生**就标「⚡反证」、**明确没发生/反向**就标「印证」。这是 CLAUDE.md §1「输出必须给反证条件」的工程化，也是「决策复盘闭环」的第一块。

## 新域 `augur/theses/`

- **单表 `theses(id, symbol, stance, thesis, conditions, alerts, status, last_scanned_at, ...)`**：
  - `conditions` JSON `[{id,text}]`＝作者授权的证伪条件（位置分配稳定 id，alert 按 id 引用）；改条件即清空旧 alerts（id 可能错位）、待重扫。
  - `alerts` JSON `[{condition_id, polarity, summary, refs}]`＝扫描**滚动重算覆盖**（非累积），永远反映近 7 天状态。
  - stance ∈ bull/bear/watch；status ∈ active/closed。
- **CRUD + AI 起草 + 扫描**（`service.py`）：
  - `draft_thesis(symbol)`：从该股近一月挂钩资讯 + 叙事主线，cheap→**summarize 角色**起草 stance/thesis/3–5 条证伪条件（不落库，作者审阅后保存）。复用 `news_service._complete_json/_strip_inline_refs`。
  - `scan_all(role='cheap')`：每个 active 立论一次 LLM 判定、**立论间并行**（`ThreadPoolExecutor`）。把近 7 天挂钩新闻（`news_service.items_for_symbol`，复用分区日报同口径的 `news_item_symbols` scope）按每条证伪条件判 refute/印证。**零编造**：alert 的 `condition_id` 必为该立论现有条件、`polarity` 必合法，否则丢弃；refs 编号映射回喂进去的新闻。prompt `thesis_scan.md` 强调**宁缺勿滥**避免噪音。
  - `thesis_flags()`：symbol → 最严重极性（refute 覆盖 support），供 inline 徽章轻量读。
- **接进 `generate_all` 的并行 tasks**（`thesis_scan`，**懒导入**避免循环——theses 顶层 import news.service，news.service 只在 generate_all 内部懒 import theses）→ 调度器每次刷新自动滚动重扫，雷达常新。
- router 注册：**新域的 `__init__.py` 必须 `from .router import router`**（否则 `main.include_router` 收到的是模块而非 APIRouter，整个 app 起不来）；main.py `include_router(theses_router)`。**新后端域还须在 `frontend/vite.config.ts` proxy 里加路径前缀**（`/theses`），否则前端请求被 SPA fallback 成 index.html、zod 解析失败、列表静默空。两个坑都踩过。

## 前端

- `RadarView.tsx`：头（`N 反证` pill + `↻ 扫描` + `＋ 立论`）+ 立论卡（`ThesisCard`：立场徽章〔看多=涨色/看空=跌色/观望=中性，随作者涨跌色习惯〕· 名字→看 · ⚡N反证 · 研/✎/× · 一句话立论 · 编号证伪条件，每条下挂 refute/印证 `AlertRow`，summary 即 `CitedText` 可点回原文）+ 编辑器（`ThesisEditor`：标的选择/立场段控/`✨ AI 起草`/立论输入/证伪条件 textarea 一行一条）。
- **告警配色随作者涨跌色习惯**：反证＝`var(--down)`（作者的「坏」色）、印证＝`var(--up)`（「好」色）——对 bull/bear 立论都成立（polarity 相对**立论**而非股价方向）。
- **跨功能缝合**：分区日报的 mover 用 `useThesisFlags()`，该股有 refute → 显 `⚡反证` inline 徽章（点击跳雷达）。雷达信号长在你每天读的盘子里——丝滑、不割裂。
- 三处 schema 同步（service dict → `theses/schemas.py` Pydantic → `api.ts` zod）。

## 未来改动注意

- scan 用 **cheap 角色**（频繁、判定型任务，§6 设计的「筛选」角色）；draft 用 summarize。作者「宁愿多次调用 LLM」，但 scan 有「该股近 7 天有挂钩新闻」的确定性门槛、无新闻秒回。
- 与 [section-level-daily-report](section-level-daily-report.md) 共用 `news_item_symbols` 挂钩 scope；与 [integrated-daily-report](integrated-daily-report.md) 同结构化机器（`_cited_points`/`_complete_json`）。
- 下一步可接：看页 per-stock 雷达模块（在 K 线旁立论，紧邻判断日记）；从判断日记/研报一键起草立论；reflection loop（过期未复盘、信念变化）。
- 测试守 `_conditions_from_texts`（id 分配/封顶/去空）+ `_map_refs`（编号映射/去重/跳非法）两个纯函数（`tests/test_pure.py`）。
