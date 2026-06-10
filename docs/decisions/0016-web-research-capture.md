# ADR-0016 — 网页版 Deep Research 回流：粘贴导入 + userscript，不做自动化驱动

日期：2026-06-10 · 状态：已采纳（MVP）

## 背景

作者有 ChatGPT Pro（GPT-5.x Deep Research）与 Claude Max（Opus Research）订阅，**两者网页版 Research 都无 API**，希望"调用网页 Research 并把结果存回 Augur"。本机实测（Chrome 149，作者真实登录态）厘清了技术与合规边界：

- **同源读取完好**：ChatGPT `/backend-api/conversation/{id}`、Claude `/api/organizations/{org}/chat_conversations/{id}` 在登录态页面上下文均返回 200 + 完整结构。所谓 Anthropic 反 harness 拦截**不**封锁登录态同源读取。
- **页面直连本地后端被拦**：页面上下文向 `127.0.0.1:8788` 的请求，ChatGPT/Gemini 被 **CSP `connect-src`** 拦、Claude 被 **CORS** 拦；**LNA 在 Chrome 149 未强制**。`GM_xmlhttpRequest`/扩展后台 fetch 跑在扩展特权上下文，不受页面 CSP/CORS——故**无需放宽 Augur 的 CORS 正则**。
- **合规分级**：「人工触发、导出自己的内容」（userscript 点按钮）与「程序化驱动会话」（Playwright/CDP 自动提交轮询）是两个风险等级。后者明确违反三家 ToS，Anthropic 2026-01 起**真实封号**（牵连作者 Max 订阅）。**不做后者。**
- **Gemini 例外**：Gemini Deep Research **已有正式 API**（`deep-research-preview-04-2026`，background 轮询，$1–3/次）。Gemini 这条线直接接 API，不走网页回流。

## 决策（MVP）

1. **落点复用「导入研报」**（`imported_reports`），不建平行表——CRUD/排序/卡片 UI 全现成。经 `_MIGRATIONS` 幂等补两列：`engine`（chatgpt/claude/gemini/other）、`source_url`（原始会话链接）。`add/update_imported` 与 router schema 接受这两个字段；前端导入表单加引擎下拉 + 来源链接，卡片显引擎徽标 + 「来源 ↗」链接。
2. **取回路径 = 同源读 → 剪贴板 → 人工粘贴**（`resources/userscripts/augur-capture.user.js`）。userscript 在 chatgpt.com/claude.ai 加按钮，读当前对话内部 JSON → Markdown → 写剪贴板；作者回 Augur「研·导入研报」粘贴、选引擎、贴链接。脚本**不向任何服务器发数据**（连 Augur 后端都不发，纯剪贴板），对 CSP/CORS/LNA 全免疫，ToS 风险最低。
3. **明确不做**：Playwright/CDP 驱动登录态会话自动提交轮询（ToS + 封号）；放宽 CORS 给三家 origin（被 CSP 先拦，无用且违背 §11）。

## 后果

- userscript **无法在 CI 端到端验证**（安装需手动点浏览器原生确认框）；作为「装后自检」的最佳起点交付，站点内部 API 形态漂移时按控制台日志微调字段路径。粘贴导入这条主路径已在浏览器验证。
- 后续可演进：把 `engine` 扩成 `web_chatgpt/web_claude/web_gemini` 的 research job 状态（`awaiting_paste`），与 ADR-0011 的官方 API 轨共用一张 jobs 表和前端状态 UI；citations 结构化后给导入研报的 `[n]` 上标接 sources。
- Gemini API 接入归入 ADR-0011 的 research engines 工作。
