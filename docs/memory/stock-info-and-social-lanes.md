# 看·个股资讯合并 + 社媒说人话 + 知社媒 lane 要点（2026-06-11）

作者用后反馈一批问题，集中改了「看」的个股资讯与「知」的社媒 lane。

## 看·个股资讯：合并成单一「相关资讯」

- 之前「相关资讯」「社媒热度」「叙事时间线」是 3 个割裂板块（叙事一度是独立 KanStack 模块）。作者要「傻瓜式、一眼看全」→ **合并成一个 `StockNews`「相关资讯」板块**：现状一句话 + 要点（带来源）+ 时间线 + 社媒热度，按小标题分区、不再分多卡。`KAN_MODULES` 去掉 `narrative`，删 `StockNarrativeCard.tsx`，时间线用共享 `NarrativeBody`（`NarrativeTimeline.tsx`）就地渲染 + 可生成。
- **复制 Prompt 抽成共享 `CopyPromptButton`**（`features/research/`），看页头部（`stock-head-actions`）与研页头部都用——看页也能一键复制技能/模板 prompt。

## 说人话 + 带引用（像新闻那样可点）

- brief / social / narrative 的 prompt 全部重写：**禁空话套话**（"持续推进/战略布局/市场关注"），要具体、带数字/客户/产品，像跟朋友说话。
- **要点带来源引用**：新增 `CitedPoint {text, refs:[{source,url}]}`（`schemas.py`）。`service._cited_points(raw, by_n, limit)` 把 LLM 输出的 `{text, refs:[n]}` 编号映射回原始条目链接（兼容纯字符串）。brief.points/risks、social.bull/bear/watch 都改成 CitedPoint；前端 `SourceChips` 渲染成可点小链接。narrative 时间线本就带 refs。

## 知·社媒 lane 要点「完全没实现」的真根因

- **不是前端问题**：各 lane 早有「生成要点」按钮、`generate_all` 却只为 news + `X·` 生成。
- **真根因**：社媒源（小红书/Threads/Reddit/微信/推特2）**关键词配置全空、且无内置默认** → TikHub 搜不到东西 → feed lane 零数据 → 要点无从生成。实测库里只有 `X·`（twtapi）数据。
- **修法**：① 加 `resources/sources/social_keywords.yaml` 内置默认关键词（贴合作者主题 AI/半导体/机器人/航天/新能源），`tikhub._keywords(source_id, platform)` read-with-fallback（设置里配的优先，空则回退默认）；② `generate_all` 与前端「一键刷新并生成」都补齐 5 个社媒 lane 的要点生成（`_SOCIAL_LANES`，无数据的 lane 抛错被吞、不影响其余）。
- 实测：默认关键词下 `search_xiaohongshu('英伟达')`、`search_threads('Nvidia')` 都能抓到数据。**作者要在设置·数据/信源里按需调整每个社媒源的关键词**；留空即用默认。

## 相关文件

- 前端：`features/news/StockNews.tsx`（合并卡）、`NarrativeTimeline.tsx`、`research/CopyPromptButton.tsx`、`kline/KLineView.tsx`（看页复制入口）。
- 后端：`news/service.py`（`_cited_points`、`_SOCIAL_LANES`、`generate_all`）、`news/tikhub.py`（`_keywords`/`_default_keywords`）、`resources/prompts/stock_news_brief.md`、`stock_narrative.md`、`resources/sources/social_keywords.yaml`。
