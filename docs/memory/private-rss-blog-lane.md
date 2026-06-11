# 私有 RSS 博客板块

日期：2026-06-11

作者拿到一个带 token 的微信公众号 RSS，需要在「知 → 资讯 → 板块」里独立查看。接入原则：

- **带 token 的 RSS URL 不能写进 `resources/sources/feeds.yaml`**。那是版本化输入，会进 git；私有 URL 走 `data/config.local.json`。
- 设置页新增「微信公众号 RSS」信源，字段是 `WECHAT_BLOG_RSS_URL`，UI 标签显示为「RSS URL」。保存后会清 `sources.load_feeds()` 缓存，立即生效。
- 「配置分享」导入/导出必须同步该 URL：`WECHAT_BLOG_RSS_URL` 在 `source_registry.live_secret_names()` 白名单内，所以会随 API 配置 JSON 导出/导入；导入成功后也要清 `sources.load_feeds()` 缓存，避免必须重启后才出现博客 feed。
- `sources.load_feeds()` 会在读取版本化 `feeds.yaml` 后，追加运行时私有 feed：`source = "博客·微信公众号"`、`lang = "zh"`、`category = "blog"`。
- 前端「资讯 → 板块」的「博客」是**专属阅读卡视图**（`BlogLaneView` + `BlogList`，不走通用 `DayScopedNews`）：博客是低频长文，按单日切片几乎永远空（实测 5 篇分布在 6 天里、今天 0 篇），所以**不按单日、滚动近 30 天**聚成阅读清单（`useNewsFeed(120, { sourcePrefix:'博客·', days:30 })`）。卡片＝署名（从标题 `[公众号名]` 前缀抽出）+ 标题 + 摘要节选 3 行 + 关联标的 chip；**不做时间线/要点切换、不做主题过滤**（长文逐篇读才是博客的用法，聚类/过滤只会把已稀疏的清单进一步打空）。
- `generate_all()` 仍会预生成 `博客·` 要点（后端未动），但新的阅读卡视图不再展示要点——这部分聚类目前是 dead 输出，若要省这一次 cheap LLM 调用可从 `_SOURCE_LANES` 摘掉 `blogs`。无数据或 RSS URL 未配置时，相关步骤可失败但不阻断综合日报或其他板块。
- 博客条目仍走普通新闻的 relevance 过滤和标题翻译/传递链路：公众号长文可能含非投资内容，不能像社媒 lane 那样完全跳过过滤。

坑：

- 不要为了方便把完整 URL 写入 `resources/`、测试 fixture 或文档。
- 改「配置分享」白名单或导入逻辑时，确保 `WECHAT_BLOG_RSS_URL` 仍在导出/导入范围内，且导入后缓存被清理。
- 如果以后要支持多条私有博客 RSS，优先扩展运行时 source config 类型，不要回退到 `feeds.yaml`。
