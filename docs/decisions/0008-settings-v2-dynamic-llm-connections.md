# ADR 0008 — 设置 v2：多页导航 + 动态 LLM 连接列表 + 支付优先级

- **状态：** 已接受
- **日期：** 2026-06-03
- **决策者：** 主人 + Claude

> 主人反馈（要点）：①「设置」左栏没用上，按大模块**分多页**；②学 Anthropic 设计；③LLM 加**测试连接**按钮（注意美观）；④LLM 应做成**可动态添加的 List**，每项可配 `base_url / api_key / model`，而非现在的固定格式；⑤个股相关新闻能否从 API 找（→ 已用 yfinance，见前）；⑥「知」仍有无关新闻，用便宜小模型筛（→ 已做 relevance.py）。另问：付费信源哪些支持微信/支付宝，优先这些。

## 背景

- 旧 LLM 配置 = 固定四厂商（anthropic/openai/deepseek/relay，写死 env 名）+ 四角色 `provider:model`。不灵活：换中转站/加模型要改 env 名、不能在 UI 里自由增删。
- 旧「设置」页 = 单页卡片网格；左栏只是装饰 navrow（主人：「根本没用上」）。
- 护栏：密钥永不入库/不打日志/UI 只脱敏（§11）；网关厂商无关（§6）；不破坏既有 news 功能（digest/translate/relevance/opportunities 都依赖网关）。

## 决策

### 1. LLM = 可动态增删的连接列表（替代固定厂商）

- 数据模型（`runtime_config`，gitignored `data/config.local.json`）：
  - `llm_connections`: `[{id, name, base_url, api_key, model}]` —— 增删改查。
  - `llm_roles`: `{chat|deep_research|summarize|cheap: connection_id}` —— 每角色指到一个连接。
- **一律 OpenAI 兼容**：`gateway` 用 `litellm.completion(model="openai/<model>", api_base, api_key)`。覆盖 DeepSeek / 各类中转站 / OpenRouter / 国产模型 / OpenAI 本身；原生 Anthropic 走中转站（主人现状）。
- **向后兼容迁移**：首次加载若无 `llm_connections`，`_seed_from_legacy` 从旧 `.env`（`AUGUR_ROLE_*` + 厂商 key/base）自动建连接 + 映射角色，**不中断主人现配置**（实测迁出 relay + deepseek 两连接、四角色就位）。
- 端点：`GET /settings/config`（连接脱敏列表 + 角色 + 信源）、`POST /settings/llm/connection`（upsert，key 留空不改）、`DELETE /settings/llm/connection/{id}`（并解除指向它的角色）、`POST /settings/llm/role`（指派）、`POST /settings/llm/test`（**测试连接**：发极小请求，回 `{ok, latency_ms, reply}` 或 `{ok:false, error}`）。

### 2. 测试连接按钮

每个连接卡一个「测试连接」：用该连接（或正在编辑的 base/key/model）发 `max_tokens` 极小请求，前端内联显示 `✓ 连通 · Xms · ok` / `✗ 报错`。实测：DeepSeek 1964ms、relay(Claude) 3336ms 通，伪 key 正确报 `Authentication Fails`。

### 3. 多页设置 + Anthropic 风格

- 左栏（App.tsx 上下文面板）变**真导航**：`外观 / 模型 / 数据信源`，state 存 `store.settingsPage`；`SettingsView` 只渲染选中页（解决「左栏没用上」）。
- Anthropic 风格：每行 = 左「标题 + 说明」/ 右控件 + 细分隔线（`.set2-row`）；分组标题；二选段控等宽对称；连接卡 + 角色下拉 + 信源 key/支付徽标。

### 4. 数据信源支付徽标 + 采购优先级（微信/支付宝优先）

- 调研（5-agent workflow）各付费源的中国支付方式，登记到 `source_registry` 的 `payment` 字段、设置页显示徽标。完整对照见 [docs/memory/payment-methods-sources.md](../memory/payment-methods-sources.md)。
- 结论：**LLM 优先 DeepSeek/国产模型/支付宝可充中转站**（都微信支付宝直付）；前沿模型走 OpenRouter（Stripe 支付宝）或 OhMyGPT 中转（+10%，敏感不走）；**X 桥无支付宝**，若上用「TwitterAPI.io + 加密 USDT」或虚拟卡（低优先）；金融数据吃免费层；中文机构终端全弃（太贵/对公）。

## 后果

- 主人可在 UI 里自由加连接（DeepSeek / 智谱 / Kimi / 硅基流动 / 中转站…全支付宝可充）、指派角色、一键测试，无需改 `.env`、无需重启。
- 网关收敛为单一 OpenAI 兼容路径，更简单；既有 news 功能（同走网关）不受影响。
- 旧 `.env`（`AUGUR_ROLE_*` + 厂商 key）仍是首次迁移的来源，之后以连接列表为准（UI 优先）。

## 备选与放弃

- **保留固定厂商 + 在其上加 List** — 放弃（两套模型并存、混乱）。
- **每连接探测厂商类型(anthropic/openai/…)** — 放弃（OpenAI 兼容一招覆盖主人全部场景，含 Claude 中转；原生 Anthropic 大陆本就不可直连）。
- **设置内部再做一个侧栏** — 放弃（主人要用**外层左栏**那一列；内部再加一栏会双侧栏冗余）。
- **密钥进 SQLite/日志** — 严禁（§11）；只进 gitignored `config.local.json`、脱敏回显。
