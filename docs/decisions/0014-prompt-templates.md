# ADR-0014 — Prompt 模板：SQLite 存储 + 前端占位符填充

日期：2026-06-10 · 状态：已采纳

## 背景

作者要在「研」做外部网页 Deep Research（ChatGPT Pro / Claude Max 订阅版无 API，见 ADR-0011 与 roadmap「External Research capture」）。第一步是把高质量提示词沉淀为可复用模板：设置页管理、个股页按当前标的一键填充复制，粘进外部网页。示例模板见 `resources/template.txt`（巴菲特×林奇框架）。

## 决策

1. **存储 = SQLite（`prompt_templates` 表）**，不放 `resources/prompts/`、不放 `runtime_config`。
   - `resources/prompts/` 是**入库的内部管线提示词**（按名加载进代码路径）；用户模板是**运行时随手增改的个人数据**，与 notes/journal 同类 → 进 `data/db`（gitignore，符合 §3「运行时生成→data/」）。
   - 不放 `runtime_config`（config.local.json）：那是密钥/连接等**配置**，长文本多行编辑不合适。
2. **占位符在前端填充**（`api.ts fillTemplate`），后端只存原文。契约四个：`{STOCK}` 代码、`{NAME}` 显示名、`{MARKET}` 市场中文名、`{SYMBOL}` MARKET:CODE。前端填充因为显示名/市场标签本来就在前端语境里（quote 数据），且模板**不进本地 LLM 调用链**——复制即终点。
3. **入口**：设置页新「模板」分类（CRUD、700ms 防抖自动保存，与「记」一致）；「研」页头部「复制 Prompt」按钮——单模板直接复制，多模板下拉选择；无模板则不显示按钮（不投喂教学文案）。

## 后果

- 未来「研究模板与工作流」（roadmap Active Work #2）可在此表上加列（变量声明、输出契约、engine 绑定），不需迁移存储。
- 模板是 Deep Research 回流闭环的前半段；后半段（外部结果保存回 Augur）走「导入研报」既有路径，后续浏览器伴侣方案另行 ADR。
- 坑：新路由前缀要同步 `vite.config.ts` proxy（见 docs/memory/frontend-gotchas.md）。
