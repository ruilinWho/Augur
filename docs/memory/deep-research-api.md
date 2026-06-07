# Deep Research API

2026-06-04 核实：OpenAI 已有官方 Deep Research API。

- 入口：Responses API。
- 模型：`o3-deep-research`（质量优先）/ `o4-mini-deep-research`（速度/成本优先）。
- 至少需要一种数据源工具：web search、file search/vector store、remote MCP。
- 可加 code interpreter 做数据分析。
- 建议 background mode，因为任务可能运行很久。
- ChatGPT Deep Research 的“澄清问题 + prompt 重写”不由 API 自动完成；Augur 需要自己做前置重写。
- Augur 后续路线：官方 Deep Research 优先，自建 `gather → prompt → deep_research 角色` 兜底。见 ADR-0011。

2026-06-07 补充核实：

- Gemini Deep Research Agent 已有 API 预览，入口是 Gemini Interactions API，不走普通 `generate_content`；任务必须用 `background=true` 异步执行，可轮询或流式更新。公开 agent 名包括 `deep-research-preview-04-2026` 与 `deep-research-max-preview-04-2026`。
- Claude 的 `Research` 当前公开文档描述为 Claude web / Desktop / Mobile 上的付费功能；没有稳定的独立 Research API。Claude API 可通过普通模型 + web search / MCP / Augur 自建多步 loop 近似实现，但不应在产品里伪称为 Claude.ai Research。
- 对 ChatGPT / Claude / Gemini 订阅网页端的 Research，优先设计“Augur 生成 prompt + 用户在网页端运行 + 浏览器 companion/粘贴导入保存回 Augur”的半自动闭环；不优先做 headless 自动登录和点击网页按钮，避免账号风控、DOM 改版和条款风险。
