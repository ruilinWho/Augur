# 信源健康度与 API 体检

> 记录于 2026-06-05。作者要求把“哪些 API 未接通、去哪里拿 key、哪些信源今天断了”集中解决。

## 产品口径

- 「设置 · 全部」是排障入口，不是又一个说明页。默认显示四个指标：接通、待配置、信源正常、信源异常。
- 点击「全部体检」才会测试 LLM 连接与信源 API；进入页面只读取本地健康表，不自动消耗 LLM token。
- 待处理 API 按问题展示：未配置、额度、权限/余额、未接入、异常。每行给可行动中文诊断和凭证/文档文本链接；不要把这些信息入口做成散落按钮。
- 信源健康度默认只列异常源；正常源可点「显示全部」展开，避免 90+ RSS 源淹没排障重点。

## 实现位置

- `POST /settings/test-all`：LLM 连接 + 信源 API + 最近健康度的合并体检。
- `POST /settings/source/test-all`：只批量测试登记信源；缺 key/token 的源不打外网，直接标未配置。
- `news/source_registry.py`：登记 `key_url/docs_url/official_url`，当前主要是 TikHub 系（推特/小红书/Threads/Reddit，共用 `TIKHUB_KEY`）；twtapi、Tushare Pro、必盈、iTick、雪球、微信均已退役/移除，不在体检注册里（twtapi 仅每股专属 X 信源仍用，不登记为全局源）。
- LLM 连接的凭证入口由 `settings_router._llm_key_url` 推断：常见厂商走控制台精确 URL；未知自定义中转退回 `base_url` 根域，避免空链接。
- `source_health.last_error`：抓取失败时保存中文原因；`GET /news/source-health` 返回该字段。
- 前端 `SettingsView.tsx::AllPage`：指标卡、待处理 API、健康度异常列表。

## 注意事项

- `/settings/config` 按作者要求仍会给本地 UI 回显明文 key；但 `/settings/test-all` 体检结果不返回 key。
- 公共 RSS 的 401/403 多数不是“凭证无效”，应显示为“源站拒绝访问 / 反爬 / 下线 / UA 需更新”。
- 小红书/Threads/Reddit/推特现都经 TikHub 真实接入（共用 `TIKHUB_KEY`，搜索型端点）；缺 key 显「未配置」，key 无效/额度不足按 TikHub 诊断分类。（雪球 2026-06-06 退役、微信 2026-06-11 删除，均从注册与体检移除。）
