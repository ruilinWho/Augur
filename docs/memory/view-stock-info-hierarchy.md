# 看·个股头部信息层级

日期：2026-06-05。

作者反馈：`看` 页头部把日内高低、更新时间、数据源、52 周区间、市值、市盈率、净利率分散在不同字体和位置，显得杂乱。

## 当前原则

- 头部只保留能帮助第一眼判断的高信号信息：
  - 当前价与涨跌幅：发生了什么。
  - 52 周位置：当前价处在一年区间的相对位置。
  - 市值：规模。
  - 市盈率：估值。
  - 净利率：盈利质量。
  - 更新时间：低权重的新鲜度。
- 不在 UI 里展示内部适配器名，例如 `fdr`、`yfinance`、`hk_backfill`。这些是工程实现，不是用户决策信息。
- 日内高/低不放在头部；它对主动投资判断的信息密度低，容易让页面像交易终端而不是研究工作台。
- 52 周不展示冗长的最低/最高价格区间，也不再展示底部刻度/位置条；默认只显示位置百分比，让它和市值、市盈率等指标保持同一视觉形态。
- 标签、数值必须在同一个信息带里，用统一字体、间距和权重；不要再拆成多个视觉层级。

## 实现

- `frontend/src/features/kline/KLineView.tsx`：`keyStats` 统一组织头部指标。
- `frontend/src/index.css`：`.stock-keyline` / `.key-stat` 负责统一视觉。

## 加厚个股资讯（2026-06-10）

作者反馈「看·个股资讯太少太简单」。实测根因不在数据量在展示/合成层，但有一个数据层硬伤：
- **ticker lane 的 `summary`/`title_zh` 填充率曾是 0%**（feed lane 95.9%/100%）。根因：`ticker_news.py` 的 `_norm` 丢弃了雅虎 `content.summary`、`directed.py` 的 `_store` 落库硬编码空串。两处已修：`_norm` 提取 `summary`/`description`，`_store` 落库带摘要。注意**存量 ~1682 条 ticker 新闻无法回填**（雅虎逐-ticker 只回最近 ~10-20 条），只有新摄取条目带摘要。
- **brief 加厚**：条数上限 16→32，prompt 把摘要正文（标题行下缩进）一并喂入让模型有正文可总结，输出放宽到 summary≤260 字 / points 3-6 / risks 0-4。
- **「看」新增「叙事时间线」模块**（`StockNarrativeCard`）：复用「知」已建的 `/news/narrative`，只读 + 可就地生成。叙事正文 JSX 抽到共享 `features/news/NarrativeTimeline.tsx`（导出 `IMP` + `NarrativeBody`），KnowView 与看页共用，单一真相。
- 仍未接：已写好但全站没用的 EDGAR hook（`useStockOfficial` + `/news/official`），美股可低成本补「官方申报」块（留待后续）。
