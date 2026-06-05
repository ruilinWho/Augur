# 信源测试诊断文案

> 记录于 2026-06-05。作者明确要求：信源测试后不要显示英文报错或异常类名，要直接说实际问题。

## 口径

- 设置页 `POST /settings/source/test` 的失败结果必须是作者能直接行动的中文诊断。
- 不要向 UI 返回 `RuntimeError:`、`HTTPStatusError:`、`TwtapiFatal:`、第三方英文错误正文，或大段接口原始返回。
- 优先归类为：
  - 没有配置：缺 API key / token / 账号。
- 没有接入：小红书这类只有配置槽、抓取适配器未实现。
- 雪球：已接轻量内容探活；如果返回 WAF/网页壳，说明当前填入的 Cookie 不足以访问讨论内容 JSON，优先提示复制完整 Cookie header（至少 `xq_a_token` + `u`）。
  - 没有额度：月度额度用完、余额/积分不足、频率限制。
  - 没有权限：key 有但套餐未开通该接口。
  - 网络问题：超时、代理/网络不可达、对方服务临时不可用。
  - 适配器需更新：接口地址、签名、反爬参数、返回格式变了。
- 公共 RSS 的 401/403 不要说“凭证无效”；大多数是源站拒绝访问、feed 下线、反爬或需要更新 UA/适配器。只有真正带 key/token 的源才归“凭证无效 / 权限不足”。

## 实现位置

- `backend/augur/news/source_test.py::diagnose_problem` 是统一兜底翻译层。
- `POST /settings/source/test-all` 与 `POST /settings/test-all` 复用同一套诊断结果；体检结果只返回状态/问题/key 获取链接，不回传 API key。
- `backend/augur/news/ingest.py::source_health` 会把旧健康记录里的公共 RSS 403 读时归一成“源站拒绝访问”，并在新抓取失败时存 `last_error`。
- 各适配器仍可抛更精确的中文问题，但不能依赖前端清洗。
- 前端信源详情页的 `.src2-tres` 必须覆盖 `.conn-test` 的紧凑徽标样式：全宽、可换行、不省略。模型连接卡可以保留 150px 省略，信源测试结果不行。
- 「设置 · 全部」的健康度列表默认只显示异常源；正常源通过“显示全部”展开，避免 90+ RSS 源把排障页面淹没。
- `backend/tests/test_pure.py` 有离线测试锁住典型文案，后续改信源测试时要一起更新。
