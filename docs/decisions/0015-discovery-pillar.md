# ADR-0015 — 「寻」：从新闻流发现自选外的新标的

日期：2026-06-10 · 状态：已采纳

## 背景

第五支柱「寻」：以「知」的信息流为源、发现 watchlist 之外反复出现的标的。作者希望把"看到新闻去看相应的股票，即使不在自选"系统化——这正是 `news/stock_tag.py` 模块 docstring 写下的原始意图（LLM 标股**不限自选**）。

运行库实测（augur.db，2026-06-10）确认地基已就绪：`news_item_symbols` 中 `matched_by='llm'` 的挂钩仅 5 天就沉淀了 552 个非自选去重 symbol，其中 ≥2 次提及且仍可 join 现存新闻的有 188 个。冷启动是"上百候选"量级，无需给管线加额外喂料。

## 决策

1. **喂料零新增 LLM 成本**：聚合既有 `news_item_symbols`（`matched_by='llm'`），不引入新的 LLM 调用。
2. **新表 `discovery_candidates`**（symbol 主键 / name / mention_count / day_span / first_seen / last_seen / evidence JSON / status / 时间戳）。新表直接进 `db.py` SCHEMA（`CREATE TABLE IF NOT EXISTS` 幂等），无需 `_MIGRATIONS`。
3. **自选别名归并**（实测踩坑）：纯 symbol 排除不够——`US:GOOGL`（中文名"谷歌"）≠ 自选 `US:GOOG`（"Alphabet"），跨语言名对不上。解法：候选名经 `search.search(name, limit=2)` 解析出"等价 symbol 集"，任一落在自选即剔除（"谷歌"→{GOOGL,GOOG}、"阿里巴巴"→{09988,BABA} 都能命中自选）。同名双重上市（A/H）按归一名合并到一个候选、取提及最多的 symbol。按归一名缓存避免逐行检索。
4. **状态机**：`new`（待看）/ `dismissed`（忽略）/ `promoted`（已入自选）。重算时**保留作者状态**（`ON CONFLICT` 不覆盖 status；只删除本轮不再合格的 `new` 行）；已加入自选的候选自动标 `promoted` 并移出列表（保留发现轨迹，不删）。
5. **「寻」是新顶栏 Tab**（看/研/知/**寻**/记），全宽单栏候选列表。候选卡复用 `AddToWatchlist`（加入自选）+「看」/「研」直通 + 「忽略」。排序 = 提及次数 → 出现天数。

## 边界：寻 vs 机会

- **机会**（`news_opportunities`）= 当日事件论点卡，事件轴、每日覆盖、thesis 驱动、不跨天累积。
- **寻**（`discovery_candidates`）= 标的轴、跨天累积出现次数与证据、带作者拍板状态机。
- 机会卡里 `resolved 且 not in_watchlist` 的公司可作为「寻」的第二喂料源（带 thesis 上下文），留待后续。

## 智能忽略与主题偏好（2026-06-11 增补）

作者反馈交互太简单（只能单标的忽略），且前端粗糙。改进：

- **主题级偏好**：候选落 `theme`（从证据新闻的 `theme` 多数表决，排除 other）。`runtime_config.prefs['discovery_muted_themes']` 存被屏蔽主题；`list_candidates(status='new')` **在 SQL 里**剔除被屏蔽主题（必须 LIMIT 之前过滤，否则屏蔽会把列表截断到不足 limit）。端点 `GET /discovery/themes`（各主题 new 候选数 + 是否屏蔽）、`POST /discovery/themes/mute`。
- **三态视图**：前端「关注中 / 已忽略」分段；候选卡操作行统一为 `.cand-btn`（对齐、同字号），含 ＋自选 / 看 / 研 / 屏蔽「主题」/ 忽略；已忽略视图给「恢复」。「偏好」面板用主题芯片（点亮=在看、置灰删除线=已屏蔽）一键切换。
- **前端重做**：候选卡改 `.cand-top`（名+代码+市场+主题芯片左，提及/天数右对齐 tabular）、证据行分列对齐（日期 3em 单行 / 来源 8.5em / 标题省略号），修「日期排两行、按钮不对齐、字号不一」。

## 后果

- 候选质量第二排序键（独立信源数 / 提及天数跨度）、接地失败实体（symbol=null 候选）、Skills 化的"候选生成器"（serenity-radar 信号数学移植）都可在此表上演进。
- 主题屏蔽是「智能忽略」的第一步：忽略整类而非逐个；后续可从忽略历史进一步学习偏好（如自动降权某类信源/市场）。
- 已知 MVP 局限：跨语言+跨市场 ADR（如不同名的双重上市）若 `search` top-2 不召回关联 symbol 仍可能漏并；作者 `dismissed` 一次即永久压制，可接受。
- 孤儿 `news_item_symbols`（指向已删 news_id）会被 JOIN 自然过滤，不污染统计。
