# ADR-0017 — 可插拔 Skills：resources/skills/ 文件夹驱动的投研技能

日期：2026-06-10 · 状态：已采纳（MVP）

## 背景

作者提供了两个 Serenity 投研 Skill 包（`serenity-skill` 供应链卡点方法论 + `aleabito` 三件套），希望把方法论结合进 Augur 并做成**可插拔**的 Skills 投研功能。路线图也把"prompt 模板 → 未来 Skills 的基础"列为方向。

调研结论（两包精华映射）：方法论（8 步工作流 + 证据分级 + 默认 unverified 的 Buffett 闸门 + 输出契约）→「研」prompt 组装；radar.js 信号数学 →「寻」（已在 ADR-0015 落地）；scorecard.py（零依赖打分器）→ 后端可调用模块；follow-aleabito 的 X 抓取/iMessage/小红书发帖丢弃。

## 决策

1. **一个 Skill = `resources/skills/<slug>/SKILL.md`**：YAML frontmatter（name/summary/surface/slug）+ markdown 正文（含 `{STOCK}/{NAME}/{MARKET}/{SYMBOL}` 占位符，与「模板」同契约）。`resources/` 是版本化的作者输入（§3），Skill 属此类——区别于「模板」（用户 SQLite、随手增改）。**丢一个文件夹进去就多一个技能**（注册表按目录 mtime 缓存失效，无需重启）= 字面意义的可插拔。
2. **后端 `skills/` 域**：`registry` 扫描解析；`service` 管列举/渲染/启用；启用状态存 `runtime_config.prefs['skills_disabled']`（禁用 slug 列表，**默认全启用**——丢进去即可用）。端点 `GET /skills`、`GET /skills/{slug}`、`GET /skills/{slug}/render?symbol=`、`POST /skills/{slug}/enable`、`POST /skills/scorecard`、`GET /skills/scorecard/template`。
3. **scorecard.py 移植进后端**（`skills/scorecard.py`，零依赖）：8 因子加权（合计 100）− 8 惩罚项（×2）→ clamp[0,100] + 分级。打分由 LLM/人给，模块只做确定性汇总。全局端点 `POST /skills/scorecard`，技能正文引导使用。
4. **首个 Skill = `serenity-bottleneck`「供应链卡点研究」**（中文优先，A股语境友好）：把 Serenity 方法蒸馏成单股研究提示词——系统变化→产业链定位→稀缺层判定→第一性原理五杠杆→Buffett 闸门（默认未验证）→叙事卫生→输出表（卡住的环节/产业链位置/排序理由/证据/主要风险）+ 市场误判/重定价事件/下一步。
5. **接入「研」**：研页头部「复制 Prompt」下拉合并「技能（启用的 surface=yan）」+「模板」两组，选技能 → `render` 按标的填充 → 剪贴板（服务外部网页 Deep Research）。设置·模板页加「技能 · Skills」区（列表 + 启用/停用 Seg）。**今天的 Prompt 模板是 Skill 的退化形态**（仅正文、无方法论/脚本），二者共用研页复制入口。

## 后果

- 未来 Skill 可演进：`surface=xun` 的「候选生成器」Skill（serenity-radar 信号 + 闸门）喂「寻」；多步工作流（earnings prep、counter-evidence scan）；Skill 携带参考文件/输出 schema；「生成深度研究」按钮可选用某 Skill 作系统提示词。
- 评分卡当前是全局工具；后续可让 Skill 在 UI 里直接填表打分（前端表单 → `POST /skills/scorecard`）。
- 边界守住：Skill 输出仍是研究地图/排序，不给买卖评级（§11）；强结论要求一手证据 + 默认 unverified，正是反幻觉护栏。
- 新路由前缀已同步 `vite.config.ts` proxy（见 frontend-gotchas）。
