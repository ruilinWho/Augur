# 总结/决策可折叠 + 计数可配 + 寻·LLM 筛选与理由（2026-06-11 四轮）

作者反馈一批「资讯/寻/决策」细节，集中改。

> 历史说明：本文件记录的是早期「总结」由日报/今日要事/社媒热度多卡片组成时的配置与 UI 调整。当前「总结/决策」已改成单张综合日报，见 [integrated-daily-report](integrated-daily-report.md)；不要按本文的旧 `MorningBrief` / `SocialPulse` 拼卡方式继续扩展总结页。

## 资讯·总结：各 section 可折叠 + 社媒热度铺满列宽
- **可折叠**：`DigestBlock`(趋势日报)、`MorningBrief`(今日要事)、`SocialPulse`(社媒热度) 都加 `open` 状态 +
  点 `sec-head`(role=button) 折叠 + `Collapse` 包体（`OpportunitiesPanel` 本就可折叠）。生成按钮 `stopPropagation`
  且点了先展开。遵 [[no-collapse-chevrons]]（无三角，hover+点发现）。
- **社媒热度伸缩铺满**：`.social-pulse-sec .sp-lanes` 由 `grid auto-fill minmax(260px,1fr)`（会留空轨道、右侧
  空一块）改 **flex + `.sp-lane{flex:1 1 240px}`**，平台卡片伸缩铺满整行（宽屏 4 列、窄屏自动 2×2）。遵 [[full-width-over-measure]]。

## 计数可配（设置·生成「蒸馏深度」组）
- 新增两个 runtime_config pref + ScheduleIn 字段 + 设置下拉：**`social_pulse_n`**（社媒热度每平台条数，默认 4）、
  **`discovery_news_n`**（寻每候选证据条数，默认 6）。模式照搬 `brief_top_n`。`service.social_pulse(per_lane=None→读配置)`；
  前端 `SocialPulse` 不再 `slice(0,3)` 直接显全部；`discovery.refresh` 用 `ev_cap=get_discovery_news_n()` 收集证据，
  `DiscoveryView` 显全部。

## 决策：删无信息量的计分行 + 关联标的就近内联
- **删 `.decision-score`**（「23 要事 / 8 机会 / 18 标的 / 38 信源」——作者：没信息量）。
- **关联标的不再单列**：删掉「关联标的」面板；改成把挂钩自选股**就近挂到每条要事/反证/催化下面**。
  `DecisionView` 用 `feed` 建 `url→symbols` 映射，`clusterSyms(c)` 按 cluster 成员 url 收集去重，传给 `ClusterCard`
  的可选 `related` prop（其它处不传→不显示）渲染 `.cl-syms` chip（复用 `.dsym` 样式）。机会卡本就内联 `o.related`。

## 寻：LLM 筛选「值得关注」+ 一句话理由（不再只堆新闻）
作者：① 列出的股至少要**值得关注** ② 顺便给**为什么值得关注**的理由。
- `discovery_candidates` 加 **`reason` 列**（schema + 迁移 + `Candidate` 模型 + `_out`）。
- `refresh()` 物化过门槛候选后，**按信号强度（提及数/天数）排序取前 `_JUDGE_MAX`(30)**，批量 cheap-LLM
  `_judge_and_reason`（切 `_JUDGE_CHUNK`(15) 并发）判 `{worth, reason}`：有实质催化/基本面/产业链/政策才算值得，
  蹭热点/八卦/宏观顺带提一嘴的 worth=false 直接不进「关注中」（**这就是筛选**，226→约 30 条）。`reason` 展示在
  候选卡（`.cand-reason`，左陶土竖条标注、无啰嗦标签，遵 [[concise-ui-copy]]）。
- **LLM 未配置/失败 → 全保留、reason 空**（不挡寻，退回纯统计）。
- **性能坑**：cheap 模型**串行**（疑似本地单实例），判 30 个 ≈ 2–4 分钟，并发 `ThreadPoolExecutor` 也不提速。
  缓解：① 只判前 30（不是全部 226）；② `reason` 按 symbol 缓存、提及数涨幅 `<_REASON_REJUDGE_GROWTH`(3) 复用旧理由
  （刷新新闻后小幅波动不重判）。**首次/大变动重算仍需等几分钟（有「重算中…」指示）；这是 LLM 质量换的，可接受**。
  若要更快：换更快的 cheap 模型，或把判定改成后台异步填充。

## 相关文件
- 后端：`runtime_config.py`（`social_pulse_n`/`discovery_news_n`）、`settings_router.py`（ScheduleIn+snapshot+apply）、
  `news/service.py`（`social_pulse` 读配置）、`discovery/service.py`（`_judge_and_reason`/`_judge_chunk`/排序封顶/缓存/`ev_cap`/`reason`）、
  `discovery/schemas.py`、`storage/db.py`（`reason` 列 + 迁移）。
- 前端：`api.ts`（schedule 加 2 字段、Candidate 加 `reason`）、`settings/SettingsView.tsx`（2 个下拉）、
  `news/KnowView.tsx`（DigestBlock/MorningBrief/SocialPulse 折叠、SocialPulse 显全部、DecisionView 删 score+关联标的面板+`clusterSyms`、ClusterCard `related`/`.cl-syms`）、
  `discovery/DiscoveryView.tsx`（`.cand-reason` + 证据显全部）、`index.css`（`.social-pulse-sec .sp-lanes` flex、`.cl-syms`、`.cand-reason`）。
