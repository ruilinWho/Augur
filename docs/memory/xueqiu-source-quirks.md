# 雪球信源 Cookie 与风控

日期：2026-06-05。

## 结论

- 雪球没有稳定公开内容 API；Augur 只能走网页登录 Cookie 的非官方只读路径。
- 作者本机这次填入的是一个 40 位纯 token 值，不是完整 Cookie header；它可让部分公开行情接口返回 JSON，但讨论/搜索内容接口会返回 WAF 网页壳。
- `backend/augur/news/xueqiu.py` 已兼容纯 token：没有 `=` 时自动当作 `xq_a_token=<value>`。但这通常不足以通过雪球内容风控。
- 设置页测试必须打内容搜索 JSON，而不是只打宽松的行情接口；行情接口可达不代表论坛内容可达。

## 正确填写

- 推荐从浏览器 Network 里复制请求的完整 `Cookie` header，填入 `XUEQIU_TOKEN`。
- 至少应包含 `xq_a_token` 和 `u`；若同一请求里有 `xq_r_token`、`device_id`、`s` 等辅助 cookie，也一并保留。
- 不要在日志、提交或文档里打印 cookie 原文。

## 产品边界

- 轻量测试只验证讨论搜索 JSON 可达，不读取持仓、组合或个人隐私接口。
- 在自动抓取关注用户/关键词前，需要再做限流、失败退避、账号隐私提示和源健康记录。
