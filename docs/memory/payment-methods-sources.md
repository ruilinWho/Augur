# 付费信源的支付方式（中国用户视角，微信/支付宝优先）

> 调研于 2026-06（5-agent workflow + 官方页核查）。口径：**A 微信/支付宝直付 > B 银联/国内卡 > C 仅国际信用卡（需虚拟卡/加密/中转）**。给 Augur 作者买 key 时按此优先级。

## A 层 · 微信/支付宝直付（最友好）

| 信源 | 类别 | 支付 | 价位 | 备注/坑 |
|---|---|---|---|---|
| **DeepSeek** | LLM API | 支付宝·微信·银联·对公 | 按 token 预充，门槛低 | Augur 现用主力；需实名（身份证）；国内直连 ✅ |
| **智谱 GLM**(open.bigmodel.cn) | LLM API | 支付宝·微信 | 注册送 2000 万 token | 国内直连 ✅ |
| **Kimi/Moonshot** | LLM API | 支付宝·微信·对公 | 即充即用 | 需实名；域名迁 platform.kimi.com |
| **硅基流动 SiliconFlow** | LLM 聚合 | 支付宝·微信 | 人民币、注册送 token | 必须实名才充值；国内直连 ✅ |
| **火山方舟**（火山引擎） | LLM API | 支付宝·微信 | 费用中心充值、OpenAI SDK 兼容 | 需火山引擎+实名 |
| **OpenRouter** | LLM 聚合(海外) | 信用卡·**支付宝/微信**(Stripe)·USDC | 充 credits 按量 | 微信藏在「More payment methods」；**需梯子**；数据出境注意 |
| **OhMyGPT / 中转聚合站** | LLM 中转 | 支付宝·微信·部分卡/加密 | 官方价 **+约 10%** | Augur `.env` 现用；密钥/数据经第三方→**与 §11 隐私有张力**，仅作前沿模型补充 |
| **Tushare Pro** | 中文金融数据 | 微信/支付宝（赞助+付费入群） | 积分制，几十~几百元 | 个人最划算的 A 股数据 |
| **迅投 xtquant/QMT** | 量化/行情 | 微信·支付宝·银行 | **券商版开户后免费** | 个人省钱关键 |
| MiniMax(仅微信确证)、阿里云百炼(支付宝/**银联**)、聚宽、米筐(≈3k–1万/年) | LLM/量化 | 消费级支付宝/微信(partial) | — | 页面 JS 渲染未逐字核实 |

## C 层 · 仅国际信用卡（需虚拟卡/加密/中转）

| 信源 | 支付 | 国内可行路径 |
|---|---|---|
| **OpenAI** | 仅 USD 国际卡 | 大陆卡常被拒 → 野卡 WildCard 虚拟卡（微信/支付宝充）或中转站 |
| **Anthropic** | Visa/MC（含虚拟卡） | **官方不支持中国大陆/香港区域**→通常靠中转站 |
| **twtapi**(X 桥·**作者选定**) | 月付套餐+**免费试用** | **作者定用此桥**：免国际卡（TwitterAPI.io 要国际卡办不了）；有免费试用先试 |
| ~~TwitterAPI.io~~(X 桥·弃) | 信用卡(Stripe)·加密(USDT) | 纯按量更省，但**需国际银行卡，作者办不了** → 弃，改用 twtapi（ADR-0007 §5）|
| **apidance**(最便宜 X 桥) | 仅加密 | 卖家中文个人，或可私聊支付宝代充（非官方） |
| SocialData / RSS.app / 官方 X API | 信用卡(Stripe)/PayPal | 虚拟卡；官方 X API 最不友好 |
| Finnhub / Polygon / Alpha Vantage / Marketaux / Tiingo | 信用卡为主 | 虚拟卡/PayPal；**优先吃免费层 + 既有 yfinance/akshare/FDR** |
| Bloomberg / LSEG(Reuters) | 信用卡/企业 invoice/对公 | 太贵/对公，**弃** |

## 弃用 · 中文机构终端
万得 Wind(≈¥3.8万/年·对公)、同花顺 iFinD(≈¥10–15万/年)、东财 Choice(标价¥3.8万)、财联社官方 API(议价对公)——虽部分支持支付宝，但**太贵+多需对公**，与单用户本地工具不匹配。Augur 已有东财免费联想 + 财联社/东财免费资讯适配器，**不采购**。

## 采购优先级（结论）
1. **LLM**：以 **DeepSeek**（支付宝、现用）为主；**便宜角色**(summarize/cheap/翻译/相关性筛选) 路由到 **智谱/Kimi/硅基流动/MiniMax**（都支付宝可充、多送免费额度）；**前沿模型**(GPT/Claude) 走 **OpenRouter**（Stripe 支付宝，需梯子）或 **OhMyGPT 中转**（+10%，敏感内容不走）。**避免**直连 OpenAI/Anthropic 官方充值。
2. **X 桥**：**作者选定 twtapi**（有免费试用 + 月付，免国际卡；TwitterAPI.io 要国际卡故弃）。配 `TWTAPI_KEY` 启用（ADR-0007 §5）。
3. **金融数据**：吃免费层 + 既有开源栈；付费走虚拟卡/PayPal，非刚需。
4. **中文终端**：全弃。
