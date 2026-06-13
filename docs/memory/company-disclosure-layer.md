# 公司披露层（财报 / 电话会 / 官方申报）

日期：2026-06-12。

作者提出：个股财报和电话会是公司最关键的信息披露时刻，应系统性进入 Augur，并与 LLM、新闻源和「看」页的判断反馈融合。

## 当前实现

- 后端新增 `news.service.stock_disclosures(symbol, limit)`，HTTP 入口：
  - `GET /news/disclosures?symbol=MARKET:CODE`
- 统一输出 `DisclosureEvent`：
  - `filing`：SEC EDGAR 高信号官方申报（10-Q/10-K/8-K 等）。
  - `financial_period`：yfinance financials 的季度期末日兜底。它不是正式披露日，只在没有真实披露事件时用于 marker。
  - `transcript`：电话会纪要披露类型（`DisclosureEvent.kind` 抽象保留）。**FMP 源已于 2026-06-13 移除**（见下），当前无 transcript 源、该类事件为空。
- ~~可选源 FMP 电话会~~ —— **2026-06-13 移除**：FMP earnings-call transcript 是付费档接口，作者免费 key 返回 `Restricted Endpoint`，且只支持美股。已删 `fmp.py`、`fmp_transcripts` 退注册表、`FMP_API_KEY` 移出 `source_registry.live_secret_names()`（启动 `prune_secrets` 自动清作者残留 key）。`transcript` 作为 `DisclosureEvent.kind` 抽象保留，待接其他源（港股 HKEXnews、A 股巨潮等）。见 [ADR-0018](../decisions/0018-remove-builtin-research-and-fmp.md)。

## 披露 Insight 升级（2026-06-12，作者反馈）

作者批评机械标签「重大事件 · 高管/董事变动」「财务报表与附件」是结构标签不是内容——"知道发生了披露但不导向决策；没信息量还不如不要"。改为 LLM 真读披露正文 → 投资洞察。

- **抓取正文**（`edgar.py`，复用 `_get`/`_throttle`，无新依赖；30 天内存缓存）：
  - earnings 类（8-K item 2.02 / 10-Q / 10-K）→ `exhibit_99_url` 拿 **Exhibit 99.1** 新闻稿原文（营收/EPS/指引）；**8-K 主文档是法律样板，真正数字在 99.1**。
  - 非财报 8-K（5.02 高管变动等）→ 抓主文档，`fetch_filing_text` 从 "Item X.XX" 处裁掉 XBRL 内联头 + 法律封面（锚 `current report`/`pursuant to section 13`，窗口 1800 字——SEC 字样可能落在 XBRL 头之后）。
  - 10-Q/10-K 全文不抓（太大 + XBRL），靠已有 `fundamentals.get_financials` 数字。
  - transcript → 已有 FMP content。
- **LLM 生成**（`news.service.enrich_disclosures`，`summarize` 角色，prompt `resources/prompts/disclosure_insight.md`）：每条输出 `{headline 具体标题, insight 投资洞察, impact 利好/利空/中性/存疑, confidence, importance, hidden}`；earnings 类附 financials 数字交叉校准防幻觉。
- **缓存**：filing 内容不可变 → 按 `(symbol, disc_key)`（filing=accession / transcript=period）落新表 `disclosure_insights` 永久缓存，刷新只对未缓存披露并行调 LLM（`ThreadPoolExecutor` 6 并发）；`stock_disclosures` 整体结果再按 symbol 缓存 30min（reflection / 个股摘要 / API 三处共用不重算）。prompt 迭代后手动 `DELETE FROM disclosure_insights WHERE symbol=?` 重算。
- **隐藏**：LLM 判 `hidden=true`（纯程序性：例行章程修订、被动 5% 持股、空 8.01）的披露在 `stock_disclosures` 输出层剔除（**唯一过滤点**），reflection / 摘要 / API 下游一致。
- **前端**（`StockNews.tsx` `TimelineEventCard` 披露分支）：主标题 = `headline`，下方 `insight` 句，`ImpactBadge`（利好=`var(--up)` / 利空=`var(--down)` / 中性 / 存疑，**随涨跌色惯例自动翻转，零 convention 判断**）+ 确定性小字；原机械标签降为右上弱化 form badge（`discFormLabel` 取 `·` 前类型）。
- **坑：两个 response_model 都要加字段。** 个股披露 API 走 `news/schemas.py::DisclosureEvent`，但**综合认知 reflection 走 `journal/schemas.py::ReflectionEvent`**——两个都要加 headline/insight/impact/confidence/hidden，否则 FastAPI response_model 静默剥掉、前端拿不到（实测踩过：只改了 news 的，reflection 端点仍吐机械标签）。前端 zod `reflectionEventSchema` / `disclosureEventSchema` 同理也要加（默认 strip）。

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
