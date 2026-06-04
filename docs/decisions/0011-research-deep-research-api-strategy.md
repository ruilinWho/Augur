# ADR-0011 · 「研」采用官方 Deep Research 优先、自建编排兜底

## 状态

Accepted · 2026-06-04

## 背景

作者要求「研」使用最好的模型与真正的 Deep Research 能力，而不是普通长上下文补全。此前 Augur
默认把 `deep_research` 当作一个长上下文 LLM 角色，通过 litellm / OpenAI-compatible Chat
Completions 调用，输入 Augur 已收集的行情、基本面、财务趋势、新闻与申报。

官方资料核实后，OpenAI 已把 Deep Research 开到 API：通过 Responses API 使用
`o3-deep-research` / `o4-mini-deep-research`，并要求至少提供一种数据源工具（web search、
file search、remote MCP 等），可配 code interpreter，适合市场分析与大量来源综合。ChatGPT 里的
Deep Research 会先澄清与重写 prompt；API 不自动做这两步，需要开发者自己实现。

## 决策

「研」采用双轨：

1. **官方 Deep Research 轨（优先）**
   - 走 OpenAI Responses API，而不是 litellm Chat Completions。
   - 模型首选 `o3-deep-research`；成本/速度优先时用 `o4-mini-deep-research`。
   - 工具组合：web search + Augur 本地资料文件/向量库 + code interpreter。
   - 使用 background mode，前端展示后台研究状态、完成后取结果。
   - 把返回的 annotations / tool calls 转为 Augur 可点击来源。

2. **Augur 自建编排轨（兜底）**
   - 继续使用现有 `gather(symbol)` 收集本地确定性数据。
   - 用 `deep_research` 角色生成报告，支持国内中转 / Qwen 联网 / 自建检索。
   - 当 OpenAI key、Responses API、后台任务或 web search 不可用时自动退回。

## 后续实现切分

1. 设置页新增「研究引擎」：`official_openai_deep_research` / `augur_local_research`。
2. 后端新增 `research/jobs` 表，记录 `symbol/status/engine/openai_response_id/error/created_at`。
3. 后端新增 OpenAI Responses 客户端，不进入 litellm 网关；密钥仍走 gitignored runtime config。
4. 前端「研」从一次 SSE 改为 job 状态：创建 → 运行中 → 完成 → 报告。
5. 报告来源统一：OpenAI annotations + Augur 本地来源都进入 `research_reports.sources`。

## 边界

Augur 仍不执行交易，不替作者下单。研究输出必须可追溯，主动结论要给触发条件、反证条件与不确定性。

## 参考

- OpenAI API deep research guide: https://platform.openai.com/docs/guides/deep-research
- OpenAI `o3-deep-research` model page: https://platform.openai.com/docs/models/o3-deep-research
- OpenAI Responses API: https://platform.openai.com/docs/api-reference/responses/create
