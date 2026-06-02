# 数据源怪癖（market/）

一句话：四市场各有坑，原生符号格式与可用源已实测（2026-05/06）。

## 原生符号格式（适配器里转换）
- **US（FDR）**：直接用 ticker，`AAPL`。
- **CN（FDR）**：**必须带交易所前缀** `SSE:600519` / `SZSE:000001`；裸 `600519` 返回空。
  适配器按代码首位判：`6`/`9`→SSE，`0`/`3`→SZSE。
- **HK（FDR，走雅虎）**：5 位港股代码转 4 位补零 + `.HK`，如 `00700`→`0700.HK`。
- **KR（pykrx）**：6 位代码 `005930`。**FDR 的韩股默认源（naver fchart）已失效（SSLError）**，
  `KRX:` 前缀路径也报 400 —— 所以韩股一律走 **pykrx**，不要试图用 FDR。

## pykrx
- `stock.get_market_ohlcv(start, end, code)`，日期格式 `YYYYMMDD`。
- 返回**韩文列名** 시가/고가/저가/종가/거래량 → 映射 open/high/low/close/volume。
- 启动时打印 `KRX 로그인 실패…` 是**无害告警**（基础 OHLCV 无需登录）。
- pykrx 要求 **pandas < 3**（装它时把 pandas 从 3.0 降到 2.3）；FDR 在 2.x 同样工作，无冲突。

## 限流
- `market/service.py` 缓存优先 + 增量补尾 + **10min TTL 回源闸**；别去掉 TTL，否则每次请求都打源（违反护栏 §11）。

## 新闻 RSS 源（news/，2026-06 实测）
- 源清单在 `resources/sources/feeds.yaml`；`ingest.py` 用 **httpx 取字节 + feedparser.parse(bytes)**（不让 feedparser 自己抓，便于控超时/UA/重定向），单源失败只跳过不中断。
- 实测 12 源里 **11 源正常**（CNBC×2、Yahoo Finance、MarketWatch、The Verge、Ars Technica、Hacker News、TechCrunch、BBC World、NPR、36氪）；**Korea Herald 那条 RSS 解析到 0 条**（HTTP 200 但无 entries）——不算失败、但也没内容，要韩国新闻得换源。
- 去重靠 `news_items.url UNIQUE` + `INSERT OR IGNORE`；`published_parsed` 偶缺 → `published_at` 可空，排序用 `COALESCE(published_at, fetched_at)`。
- 日报只喂**标题**给 LLM（控 token，summarize 角色）；别把 summary 全文塞进去。
