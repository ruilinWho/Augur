# ADR 0004 — LLM 网关接通 · 基本面（yfinance）· LongBridge 调研结论

- **状态：** 已接受
- **日期：** 2026-06-01
- **决策者：** 主人 + Claude

> M2 起步：主人给了 DeepSeek + OhMyGPT 中转 key，要接通 LLM；要个股关键基本面（市值/营收/利润/P-E）+ 一个可折叠的「财报分析」面板（后接 LLM）；并让我调研 LongBridge API 是否更好。

## 背景

- M1 的 `llm/gateway.py` 早就写好（litellm，角色路由，自配 base_url），但**从没真正接通**——provider key 没进 `os.environ`（pydantic-settings 只认 `AUGUR_` 前缀）。
- 个股页此前只有 K 线 + 判断日记，缺基本面与财报视角。
- 数据源现状：FDR/akshare/东财/pykrx（行情+检索），无统一基本面源。

## 决策

**1. LLM 接通（`.env` + load_dotenv）**
- `config.py` 加 `load_dotenv(backend/.env)`：把 `DEEPSEEK_API_KEY`、`RELAY_API_KEY/RELAY_BASE_URL` 灌进 `os.environ`，供 gateway/litellm `os.getenv` 读取。`.env` 已 gitignore，**密钥永不入库**（§11）。
- 角色路由：`chat`/`deep_research` → 中转 `claude-sonnet-4-20250514`（Anthropic 对齐）；`summarize`/`cheap` → `deepseek-chat`（便宜）。
- 实测可用：`deepseek-chat`、`relay:gpt-4o`、`relay:gpt-4o-mini`、`relay:claude-sonnet-4-20250514`；此中转上 `claude-3-5-sonnet`/`gemini-2.0-flash` 报 Args validation failed（暂不用）。`/llm/chat` SSE 流式端到端验证通过。

**2. 基本面 = yfinance（`market/fundamentals.py`）**
- 一库覆盖四市场（雅虎）：市值/营收(TTM)/净利润/P-E（+EPS）。符号→雅虎代码：US 原样、HK `0700.HK`、CN `.SS/.SZ`、KR 试 `.KS/.KQ`。
- 数字为**本币原值**，前端按 亿/万亿 + 币种符号格式化。雅虎缺 trailingPE（韩股常见）→ 用 `市值/净利润` 兜底。6h 内存缓存。缺数据 → null → 前端「—」。

**3. 「财报分析」面板（K 线下方、可折叠）**
- 现在：4 张指标卡（市值/营收/利润/P-E）+ **AI 解读** 按钮 → 前端组 prompt 调 `/llm/chat`（role=deep_research）流式生成简评，要求纯文本、暴露不确定性、不构成投资建议。
- 这是「研」支柱的第一步落地；后续接 `research/` 做更深的多轮研究。

**4. LongBridge OpenAPI —— 调研后暂不采用**

## 考虑过的替代方案

- **LongBridge / LongPort OpenAPI（主人提议）** —— 调研后**暂不采用**：
  - 优点：实时行情 + K 线，统一覆盖 港/美/A（+新加坡），含中文名；基础行情**无需券商账户**（注册拿 App Key/Secret/Token，纸面交易档即给真实行情）。
  - 不采用的理由：① 它**本质是交易 API**（下单/持仓），Augur 是研究工具、**永不交易**（§1），只会用其行情模块，价值打折；② 需主人的 App Key/Secret/Access Token + token 刷新，**比免费免认证源摩擦大**；③ 实时行情对「天级研究」**非刚需**，现有免费源够用；④ 高级行情（Level 2 / 真实时）要买 market card；⑤ **基本面（营收/利润）覆盖薄**，它是行情导向。
  - 结论：作为**可选的未来适配器**保留（主人若要实时 + 统一港美A 且愿配凭证，再加一个只读「行情」适配器）。当前基本面用 yfinance（免费、免账号、覆盖四市场）。
- **基本面用 akshare 分市场** —— 否决：四市场各一套函数、韩股基本面弱；yfinance 一库到位更简单。
- **基本面用东财 push2** —— 否决（本机代理拦截，无法自测；雅虎可达）。
- **财报分析现在就接 `research/` 多轮编排** —— 暂缓：先用一次性 `/llm/chat` 简评把面板跑通，多轮研究放 M2 续。

## 后果

**正面**：LLM 真接通（聊天/研究/摘要/AI 解读）；个股有了基本面 + AI 财报简评；密钥安全（.env + .env.example 模板）。
**代价 / 风险**：yfinance `.info` 慢且偶限流（已 6h 缓存 + 缺数据降级）；中转模型名/限流依赖第三方（key 在 .env，失效改一处）；AI 简评仅一次性、未引用来源（M2 续补 `research/`）。
