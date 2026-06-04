# Deep Research API

2026-06-04 核实：OpenAI 已有官方 Deep Research API。

- 入口：Responses API。
- 模型：`o3-deep-research`（质量优先）/ `o4-mini-deep-research`（速度/成本优先）。
- 至少需要一种数据源工具：web search、file search/vector store、remote MCP。
- 可加 code interpreter 做数据分析。
- 建议 background mode，因为任务可能运行很久。
- ChatGPT Deep Research 的“澄清问题 + prompt 重写”不由 API 自动完成；Augur 需要自己做前置重写。
- Augur 后续路线：官方 Deep Research 优先，自建 `gather → prompt → deep_research 角色` 兜底。见 ADR-0011。
