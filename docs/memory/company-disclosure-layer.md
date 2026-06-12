# 公司披露层（财报 / 电话会 / 官方申报）

日期：2026-06-12。

作者提出：个股财报和电话会是公司最关键的信息披露时刻，应系统性进入 Augur，并与 LLM、新闻源和「看」页的判断反馈融合。

## 当前实现

- 后端新增 `news.service.stock_disclosures(symbol, limit)`，HTTP 入口：
  - `GET /news/disclosures?symbol=MARKET:CODE`
- 统一输出 `DisclosureEvent`：
  - `filing`：SEC EDGAR 高信号官方申报（10-Q/10-K/8-K 等）。
  - `financial_period`：yfinance financials 的季度期末日兜底。它不是正式披露日，只在没有真实披露事件时用于 marker。
  - `transcript`：FMP earnings call transcript（需要 `FMP_API_KEY`）。
- 可选源：
  - `backend/augur/news/fmp.py`
  - 设置页源 id：`fmp_transcripts`
  - secret：`FMP_API_KEY`
  - 已进入 `source_registry.live_secret_names()`，会随「配置分享」导入/导出同步。

## 融合点

- **看 · K 线 marker**：
  - `判`：个人判断。
  - `财`：真实 SEC 财报/申报日优先；无披露时退回 financial period 期末日。
  - `会`：FMP 电话会 transcript 日期。
- **看 · 综合认知**：
  - disclosure event 作为独立 `kind="disclosure"` 进入主线，显示「披露」标签。
  - LLM 判断反馈证据池同时包含新闻事件与披露事件。
  - 电话会 transcript 摘要会作为 `body` 喂给 LLM，不把全文直接塞前端。
- **个股近况 / 重大事件**：
  - `stock_news_brief()` 现在会把 disclosure events 转成 news-like items，与新闻同一 prompt 合成。
  - `generate_narrative()` 也会把 disclosure events 并入重大事件输入。

## 事实优先级

- 公司披露是事实层，优先级高于普通新闻和社媒。
- 如果新闻与 SEC/IR/电话会材料冲突，LLM prompt 要求优先相信披露，并指出冲突。
- LLM 不负责计算价格反馈；价格反馈仍由行情数据确定性计算后喂给模型。

## 后续扩展

- 港股：HKEXnews / 披露易。
- A 股：巨潮 / 交易所公告。
- 韩股：DART。
- 公司 IR 页面：可作为补充，但格式不统一，不应替代结构化源。
