# 雪球信源 —— 已退役（不要再尝试接入）

日期：2026-06-06 退役（原 Cookie/风控记录：2026-06-05）。

## 结论：雪球已从 Augur 整体移除

作者实测确认**雪球的网页登录 Cookie 抓取已不可用**：风控墙（`acw_sc__v2` 等 WAF Cookie + `_waf_` 网页壳）会拦掉讨论/搜索内容 JSON。即便填入包含 `xq_a_token`、`u`、`xq_r_token`、`device_id` 的完整 Cookie header，也只能打通宽松的行情接口，打不通内容接口。雪球没有稳定的一手公共内容 API，唯一的非官方 Cookie 路线又被风控封死，因此 **2026-06-06 将雪球整体退役**。

移除范围（单一真相，未来排查比对用）：

- 删适配器 `backend/augur/news/xueqiu.py`。
- `news/source_registry.py`：移除 `xueqiu` 信源条目、config getters、`XUEQIU_TOKEN` 配置槽（保留一行退役说明注释）。
- `news/source_test.py`：移除探活分支与雪球专用 WAF 诊断。
- 前端：`consts.ts`（`SourceLaneId`/`INFO_SECTIONS`/`SOURCE_LANES`）与 `store.ts`（`InfoSection`）移除「雪球」资讯 lane。
- `backend/.env.example` 去 `XUEQIU_TOKEN`；`backend/tests/test_pure.py` 去雪球测试。
- 每股专属信源（`stock_sources.py` / `storage/db.py` 注释 / `resources/prompts/stock_sources.md`）举例不再提雪球，避免 LLM 给某股推荐抓不到的雪球页。

## 为什么不要再接

- 行情接口可达 ≠ 内容源可达：`stock.xueqiu.com` 的 quote JSON 能通，但 `xueqiu.com` 首页/讨论搜索返回 `_waf_...` HTML、内容搜索端点 403。
- Cookie 路线会绑定作者真实账号足迹、token 周级失效（违 §11 隐私/可追溯精神），赌风控不是稳定能力。
- 若未来要重新接入，门槛是**雪球官方/合规的内容接口**，而不是再赌 Cookie 风控。除非作者明确要求，否则不要重建 Cookie 抓取。

A/H/中概的社区情绪与反证线索，短期改用其他已接入 lane（Reddit、X）覆盖。
