# 标的检索的数据源（market/search.py · listings.py）

一句话：检索 = **本地目录索引（FDR + 别名种子）∪ 东方财富实时联想**，统一打分去重。
港股/A股/新股靠东财，美股英文名 + 韩股靠本地。下面是踩过的坑，别重蹈。

## 东方财富 suggest API —— 检索的主力
- 端点：`https://searchapi.eastmoney.com/api/suggest/get?input=<q>&type=14&token=D43BF722C8E33BDC906FB84D85E326E8&count=15`
- 回 JSON：`QuotationCodeTable.Data[]`，每条有 `Code / Name / PinYin / Classify / SecurityTypeName`。
- **覆盖最全最新**：港股 MiniMax(00100)、智谱(02513) 这类新股都搜得到；自带拼音（腾讯控股→TXKG、比亚迪→BYD）。
- `Classify` → 市场映射：`HK`→HK、`AStock`→CN、`UsStock`→US。**其余一律丢**（`LSE`英股、`OTCFUND`基金、期货、`BK`板块…）。
- **噪声很重**，必须过滤（见 search.py `_EM_NOISE` / `_map_em`）：
  - 杠杆/反向 ETF、票据（`ETF/ETN/做多/做空/两倍/三倍/Notes/Bond`）。
  - **港股认购/认沽证**名字含 `购`/`沽` → 丢；但**仅限港股过滤**——A股「苏宁易购」含「购」是正经公司，别误杀。
  - 人民币/二级计价柜台后缀 `-R/-WR/-WS`（与主柜台重复）→ 丢；但 `-W/-SW/-S`（同股不同权/二次上市）是主挂牌，**保留**（MiniMax-W 就是）。
  - 美股票据 `AAPL22/AAPL24`：US 代码含数字 → 丢。
- **东财没有韩股**：搜「三星/海力士」只会回 A股同名股 或 港股杠杆 ETF（南方两倍做多海力士），**不是** 真正的 KR:005930/000660。→ 韩股必须靠本地 FDR + 别名种子。
- 命中缓存：`search.py` 里按 query 做 30min TTL 缓存 + 4s 超时 + 失败静默降级到本地。别去掉（限流，AGENTS.md §4）。

## 代理怪癖（本机沙箱 2026-06 实测）
- `searchapi.eastmoney.com`（suggest）**可达** ✅；但 `push2.eastmoney.com`（akshare 行情/列表用）**被代理拦截**（`ProxyError: Unable to connect to proxy`）。
- 所以：**akshare 的港股列表 `stock_hk_spot_em()` 在本机必失败**（走 push2）。作者自己的 Mac（直连）多半 OK，但别依赖它——港股检索已由东财 suggest 兜底。
- httpx/requests 都吃环境代理；suggest 用 httpx，和 curl 一样能过。

## 本地目录（listings.py）—— 离线兜底 + 美股名 + 韩股
- 来源：US/CN/KR 用 `FinanceDataReader.StockListing`；CN 中文名用 `akshare.stock_info_a_code_name()`（一次调用 ~5500 条，可靠）。
- **FDR StockListing 很慢**：美股 NASDAQ+NYSE ~70s、会刷 tqdm 进度条。故缓存为 `data/cache/listings/{US,CN,KR}.parquet`，7 天 TTL；启动后台线程预热，过期也先用旧的再后台刷。
- `StockListing('HK')` → **NotImplementedError**（FDR 不支持港股列表）。港股本地目录恒空，靠东财 suggest + 别名种子。
- `StockListing('KOSPI'/'KOSDAQ')` 快(~3s)且带**韩文名**（삼성전자/SK하이닉스）——韩股列表用它，**不要用 pykrx 的 ticker 列表**（本机报 IndexError，坏的）。韩股 *行情* 仍走 pykrx（FDR naver 行情源失效，见 data-source-quirks.md）。
- US/CN 的 FDR 名字是**英文**；A股中文名靠 akshare 合并；美股中文俗名（英伟达/苹果）靠别名种子。

## 别名种子 `resources/sources/aliases.yaml`（版本化）
- 跨语言/俗名 → symbol 的人工映射。**海力士→KR:000660**、三星→KR:005930、英伟达→US:NVDA、腾讯→HK:00700…
- 它是「海力士搜得到」的唯一可靠途径（东财无韩股、FDR 韩股名是韩文）。也兜底港股（万一东财不可达）。
- 维护：只增不改地往下加；目录已有中文名的 A 股一般不必登记。

## 打分（统一）
- 本地 rec 与东财 rec 都转成同一个 `_Rec`（code + names_l，含拼音），用同一个 `_score` 排序，按 symbol 去重（本地优先级略高：含英文名/韩股/别名且离线可靠）。
- 规则：代码精确 > 名称精确 > 代码/名称前缀 > 子串（越靠前越短越优）> 英文词首 > 子序列。

## 展示名（`search.display_name(symbol)`）—— 中文优先
- 自选行 + 个股标题显示"看得懂的公司名"（**KR:000660 → SK海力士**，而非韩文 SK하이닉스 或数字 000660）。
- `get_quote` 调它，把 `name` 塞进 `/market/quote`；前端报价钩子顺带拿到名字（行 + K 线头都用 `quote.name`）。
- 顺序：本地 `_SYM_INDEX`（中文名 > 中文别名 sub > 本地名）→ 东财按代码反查（缓存 `_name_cache`）→ 退回代码。
- 「中文优先」靠 `_HAN`（`[一-鿿]`）判断：韩文 Hangul 不算汉字 → 落到别名里的中文（SK海力士）；美股无中文则用英文名（Rocket Lab Corp），可读即可。
