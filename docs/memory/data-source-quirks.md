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
