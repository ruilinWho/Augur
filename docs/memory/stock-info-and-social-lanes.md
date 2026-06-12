# 看·个股资讯合并 + 社媒说人话 + 知社媒 lane 要点（2026-06-11）

作者用后反馈一批问题，集中改了「看」的个股资讯与「知」的社媒 lane。

## 看·个股资讯：合并成单一「相关资讯」

- 之前「相关资讯」「社媒热度」「叙事时间线」是 3 个割裂板块（叙事一度是独立 KanStack 模块）。作者要「傻瓜式、一眼看全」→ **合并成一个 `StockNews`「相关资讯」板块**：现状一句话 + 要点（带来源）+ 时间线 + 社媒热度，按小标题分区、不再分多卡。`KAN_MODULES` 去掉 `narrative`，删 `StockNarrativeCard.tsx`，时间线用共享 `NarrativeBody`（`NarrativeTimeline.tsx`）就地渲染 + 可生成。
- **复制 Prompt 抽成共享 `CopyPromptButton`**（`features/research/`），看页头部（`stock-head-actions`）与研页头部都用——看页也能一键复制技能/模板 prompt。

### 2026-06-12 后续：升级为「综合认知」

上述「相关资讯」形态已进一步被「综合认知」取代，详见 [[kan-cognition-timeline]]：旧的「相关资讯」与「判断日记」不再是两个 KanStack 模块，而是在 `StockNews.tsx` 内合成一条综合主线。近况/社媒仍保留为背景，但主循环变成：个人判断 → 后续公司披露/重大事件/价格 → LLM 事实反馈（印证/证伪/混合/尚未检验）。

## 说人话 + 带引用（像新闻那样可点）

- brief / social / narrative 的 prompt 全部重写：**禁空话套话**（"持续推进/战略布局/市场关注"），要具体、带数字/客户/产品，像跟朋友说话。
- **要点带来源引用**：新增 `CitedPoint {text, refs:[{source,url}]}`（`schemas.py`）。`service._cited_points(raw, by_n, limit)` 把 LLM 输出的 `{text, refs:[n]}` 编号映射回原始条目链接（兼容纯字符串）。brief.points/risks、social.bull/bear/watch 都改成 CitedPoint；前端 `SourceChips` 渲染成可点小链接。narrative 时间线本就带 refs。

## 知·社媒 lane 要点「完全没实现」的真根因

- **不是前端问题**：各 lane 早有「生成要点」按钮、`generate_all` 却只为 news + `X·` 生成。
- **真根因**：社媒源（小红书/Threads/Reddit/微信/推特2）**关键词配置全空、且无内置默认** → TikHub 搜不到东西 → feed lane 零数据 → 要点无从生成。实测库里只有 `X·`（twtapi）数据。
- **修法**：① 加 `resources/sources/social_keywords.yaml` 内置默认关键词（贴合作者主题 AI/半导体/机器人/航天/新能源），`tikhub._keywords(source_id, platform)` read-with-fallback（设置里配的优先，空则回退默认）；② `generate_all` 与前端「一键刷新并生成」都补齐 5 个社媒 lane 的要点生成（`_SOCIAL_LANES`，无数据的 lane 抛错被吞、不影响其余）。
- 实测：默认关键词下 `search_xiaohongshu('英伟达')`、`search_threads('Nvidia')` 都能抓到数据。**作者要在设置·数据/信源里按需调整每个社媒源的关键词**；留空即用默认。

## 傻瓜式 + 社媒投资过滤 + hover 链接 + 卡片化（2026-06-11 二轮）

作者补充原则与细化：**「傻瓜式使用」是长期原则——能自动就自动、少让用户按乱七八糟的按钮、用 LLM 把信息总结好直接呈现。**

- **时间线自动生成**：`StockNews` 挂载时若该股无叙事则自动生成一次（`_autoNar` Set 本会话每股只试一次，避免重复/失败死循环；生成后落库 cached）。去掉「生成时间线」按钮，整块只留一个「刷新」（重抓 + 重生成 brief/social/timeline）。
- **社媒只留投资相关**：`stock_social_heat` prompt 强制只看与股价多空/投资相关（业绩/产品/订单/竞争/监管/资金/估值/明确多空），**坚决丢掉**招聘/培训带货/职场吐槽/生活方式/追星八卦；筛完没信号就如实说「多是无关闲聊」。实测对 Meta/微软的小红书噪音（"培训拿高薪"）能正确滤掉。
- **链接不写出来**：要点文字本身就是 `<a class="cited-link">`（默认无下划线、hover 出下划线、点进原帖），不再显示「小红书·Meta ↗」这种 url 文字；多来源时附极小上标 `²³`。
- **社媒热度卡片化**：头部 heat/sentiment pill + 条数，偏多(绿)/反方(红)/观察 分列，底部平台计数。
- **卡片-内-卡片 + 子模块独立折叠**（作者二轮细化）：「相关资讯」外层是 KanStack 模块卡，里面 **近况 / 社媒热度 / 时间线** 各做成独立 `.srn-card`（surface-2 描边圆角），各有可点折叠头（`SubCard`，无三角、点标题切换，遵 [[no-collapse-chevrons]]），默认展开。**顺序＝近况 → 社媒热度 → 时间线**（时间线在社媒下面）。

## 资讯·总结/决策「接入所有信源」+ 相关资讯加深（2026-06-11 三轮）

作者四问：①微信能不能接；②总结/决策接入所有信源了吗；③复制 Prompt 在最右显示不全；④相关资讯不够美观、社媒太浅。改动：

- **社媒脉搏（social_pulse）已降级为兼容读接口**：早期曾用它把社媒 lane cluster 作为「总结/决策」里的独立小卡片展示；现在作者要求「总结/决策」必须是一张整体化综合日报，所以前端不再调用 `useSocialPulse`。当前入口见 [[integrated-daily-report]]：`digest_items_for_day()` 直接把新闻、博客、推特、小红书、Threads、Reddit 原始条目喂进同一篇日报。`GET /news/social-pulse` 暂留兼容/调试，不应作为新总结 UI 的拼图。
- **【关键 bug】cluster scope 中文前缀塌缩冲突**：`_scope_part` 用 `[^0-9A-Za-z_:-]+→_` 清洗，**全非 ASCII 的 `小红书·`/`微信·` 都塌成同一个 `_`** ⇒ 两个 lane 的要点写进同一 scope `src:_:all@1d` 互相覆盖，实测「微信」lane 显示的其实是「小红书」要点。修法：清洗后无 ASCII 信息时退回 `"h"+md5(原串)[:8]`，每个中文前缀拿到稳定唯一 scope。**改后 小红书/微信 旧 `src:_` 行成孤儿，需重生成**（小红书有数据→重生，微信无数据→正确空缺）。`X·/Threads·/Reddit·` 是 ASCII，scope 不变、数据不动。
- **社媒热度加深**（太浅→有料）：`stock_social_heat` 喂模型条数 24→40、bull/bear cap 3→5、watch 3→4、summary 140→240 字；prompt 改为「尽量多挖、bull/bear 各 2–5 条、给细节数字事件」。`tikhub.social_search_for_stock` 每源 limit 10→14、总 cap 36→60。实测微软社媒热度从「3 条」变成 48 源、多点偏多/反方带具体数字（资本开支同比 +73.6% 等）。
- **复制 Prompt 不再被切**：`.stock-head-actions` 改 `flex-direction:row + flex-wrap + justify-end`（按钮与周期 chip 同排、不再独占最右角）；`.tpl-pop` 由 `left:0` 改 `right:0;left:auto`（向左展开，不溢出视口右缘）。
- **相关资讯一致性**：`NarrativeBody` 加 `hideSummary`——「看·相关资讯」时间线子卡只留事件、不再渲染那段 `.narr-summary`（md 引用块样式），与近况/社媒的纯文本摘要统一；时间线子卡 `defaultOpen={false}` 默认收起（不再又长又乱）。

## 相关文件

- 前端：`features/news/StockNews.tsx`（合并卡）、`NarrativeTimeline.tsx`（`hideSummary`）、`research/CopyPromptButton.tsx`、`kline/KLineView.tsx`（看页复制入口）、`index.css`（`.stock-head-actions`/`.tpl-pop`）。历史上的 `KnowView` `SocialPulse`/`PulseRow` 与前端 `useSocialPulse` 已删除；总结/决策改走综合日报。
- 后端：`news/service.py`（`_cited_points`、`_SOCIAL_LANES`、`social_pulse`、`_scope_part` 哈希修复、`generate_all`、`stock_social_heat` 加深）、`news/tikhub.py`（`_keywords`/`_default_keywords`、`social_search_for_stock` 上限）、`news/router.py`（`/social-pulse`）、`resources/prompts/stock_news_brief.md`、`stock_narrative.md`、`resources/sources/social_keywords.yaml`。
- **微信源已删除**（紧接本轮）：TikHub `wechat_mp/web/*` 整组服务端长期 400（实测非我方问题），作者要求把微信功能（含前端）全删——所以上面 social_pulse 与各社媒列表都**只剩 推特/小红书/Threads/Reddit 四家**。详见 [[tikhub-source-quirks]]。`_scope_part` 哈希修复仍**保留**（小红书等全中文前缀仍需稳定唯一 scope）。
