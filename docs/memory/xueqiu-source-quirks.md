# 雪球信源 Cookie 与风控

日期：2026-06-05。

## 结论

- 雪球没有稳定公开内容 API；Augur 只能走网页登录 Cookie 的非官方只读路径。
- 作者本机第一次填入的是一个 40 位纯 token 值，不是完整 Cookie header；它可让部分公开行情接口返回 JSON，但讨论/搜索内容接口会返回 WAF 网页壳。
- 第二次填入的 Cookie 已包含 `xq_a_token`、`u`、`xq_r_token`、`device_id`，但仍缺少浏览器通过主站风控后常见的 `acw_sc__v2`。本地探活结果：`stock.xueqiu.com` quote JSON 可达，`xueqiu.com` 首页/讨论搜索返回 `_waf_...` HTML，`stock.xueqiu.com` 新闻/搜索端点 403。结论：行情能通不等于内容源能通。
- `backend/augur/news/xueqiu.py` 已兼容纯 token：没有 `=` 时自动当作 `xq_a_token=<value>`。但这通常不足以通过雪球内容风控。
- 设置页测试必须打内容搜索 JSON，而不是只打宽松的行情接口；行情接口可达不代表论坛内容可达。

## 正确填写

- 推荐从浏览器 Network 里复制请求的完整 `Cookie` header，填入 `XUEQIU_TOKEN`。
- 至少应包含 `xq_a_token` 和 `u`；若同一请求里有 `acw_sc__v2`、`xq_r_token`、`device_id`、`s` 等辅助 cookie，也一并保留。
- 设置页的雪球输入框应显示为“完整 Cookie header”，placeholder 直接给出 `xq_a_token=...; u=...; acw_sc__v2=...; xq_r_token=...; device_id=...`，避免误导作者只填某个 token 值。
- 不要从浏览器 Application/Cookies 页逐项拼 Cookie；要从 Network 里某个真实 `xueqiu.com` 请求复制请求头里的整段 `Cookie`。如果页面刚被风控拦截，先在浏览器里正常打开雪球并通过挑战，再复制。
- 不要在日志、提交或文档里打印 cookie 原文。

## 产品边界

- 轻量测试只验证讨论搜索 JSON 可达，不读取持仓、组合或个人隐私接口。
- 在自动抓取关注用户/关键词前，需要再做限流、失败退避、账号隐私提示和源健康记录。
