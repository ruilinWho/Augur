# Augur 回流 userscripts

把 ChatGPT / Claude **网页版** Deep Research 结果（订阅版无 API）取回 Augur 的辅助脚本。

## augur-capture.user.js

在 chatgpt.com / claude.ai 右下角加一个「📋 复制到 Augur」按钮：点它读取**当前这条对话**的同源内部 JSON（你自己的登录态、你自己的内容），转成 Markdown 写入剪贴板。然后回 Augur「研 → 导入研报 → ＋导入」粘贴正文、选来源引擎（ChatGPT/Claude）、贴上对话链接保存。

### 为什么是这条路（见 [ADR-0016](../../docs/decisions/0016-web-research-capture.md)）

- 实测：页面上下文直连 `localhost:8788` 被 ChatGPT/Gemini 的 CSP、Claude 的 CORS 拦死；同源读取内部 API 则完好（ChatGPT `/backend-api/conversation/{id}`、Claude `/api/organizations/{org}/chat_conversations/{id}` 都 200）。
- 所以脚本只做「同源读 → 写剪贴板」，**不向任何服务器发数据**（连 Augur 后端都不发）。这与「人工导出自己的内容」同级，区别于各家 ToS 明确禁止的「程序化驱动会话」（Playwright/CDP 自动提交——**不要做**，Anthropic 2026-01 起对此真实封号）。

### 安装

1. 装 Tampermonkey 或 Violentmonkey 浏览器扩展（需在 `chrome://extensions` 开启「允许用户脚本/开发者模式」，一次性）。
2. 新建脚本，粘贴 `augur-capture.user.js` 全文，保存。
3. 打开一条 ChatGPT/Claude 的 Deep Research 对话 → 点右下角按钮 → 回 Augur 粘贴。

### 状态与注意

- **未在本仓库 CI 中端到端验证**（安装需手动点浏览器原生「添加扩展」确认框，无法自动化）。各站内部 API 形态会随前端改版漂移；若按钮报错，看浏览器控制台 `[Augur capture]` 日志，按实际响应结构微调 `captureChatGPT`/`captureClaude` 的字段路径。
- Gemini 未做：Gemini Deep Research **已有正式 API**（`deep-research-preview-04-2026`），应直接接 API 而非回流网页（见 ADR-0016）。
- ChatGPT 内置「下载 Markdown」、各家「导出数据」也是零风险的批量兜底路径。
