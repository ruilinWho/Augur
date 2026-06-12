"""SEC EDGAR——美股「个股级一手」官方文件接入（AGENTS.md §7「一条龙」起步）。

给定内部符号 `US:TICKER`：ticker→CIK（官方 `company_tickers.json`，缓存 7 天）→
`data.sec.gov/submissions/CIK##########.json` → 按**高信号表单白名单**过滤 →
归一化为可读的「文件」条目（表单+8-K 事项给**确定性中文标签**，零 token、不幻觉）。

为何确定性而非 LLM 抓取（回应作者"基于 LLM 能做到吧"）：一手文件的**获取**要的是
**不编造**——官方 ticker→CIK→filings 的结构化 API 是金标准，LLM 抓网页会幻觉 URL/数字。
LLM 的价值在**读文件内容做综合**（留给 `research/` 多轮带引用），不在"找文件"。
标准化表单类型（8-K/10-Q…）和 8-K 事项码用固定中文对照表即可，比 LLM 更准更快。

SEC 公平获取：必须带可识别 UA（无则 403，UA 见 config.sec_user_agent）、≤10 req/s。
单股按需 1 个请求、6h 内存缓存。失败一律降级返回 []（暴露不确定性，不抛 500）。
港/A/韩官方披露（HKEXnews/cninfo/DART）口径不同，待后续。
"""

from __future__ import annotations

import html
import json
import re
import threading
import time

import httpx

from ..config import get_settings

_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
_TIMEOUT = 12.0
_TICKERS_TTL = 7 * 24 * 3600  # ticker→CIK 表缓存 7 天
_SUB_TTL = 6 * 3600  # 单股 submissions 内存缓存 6h
_MIN_GAP = 0.15  # 两次 SEC 请求最小间隔（守 ≤10 req/s）
_CONTENT_TTL = 30 * 24 * 3600  # filing 目录/正文不可变 → 长缓存（进程内）
_ARCHIVE_DIR = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/"
_content_cache: dict[str, tuple[float, str]] = {}  # doc_url → (ts, cleaned_text)
_index_cache: dict[str, tuple[float, list[dict]]] = {}  # acc_nodash → (ts, docs)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_BLOCK_RE = re.compile(r"(?is)<(script|style|head)[^>]*>.*?</\1>")

# 高信号表单白名单（前缀匹配，含 /A 修订）；Form 4 内部人交易量大噪音高，刻意不收。
_FORM_PREFIXES = (
    "8-K",
    "10-Q",
    "10-K",
    "20-F",
    "6-K",
    "S-1",
    "424B",
    "SC 13D",
    "SC 13G",
    "DEF 14A",
)

# 表单 → 中文短标签（一手文件类型是标准化的，固定对照即可）
_FORM_ZH = {
    "8-K": "重大事件",
    "10-Q": "季报",
    "10-K": "年报",
    "20-F": "年报·外国发行人",
    "6-K": "中期披露·外国发行人",
    "S-1": "IPO 注册",
    "424B": "招股说明书",
    "SC 13D": "5%+ 主动持股",
    "SC 13G": "5%+ 被动持股",
    "DEF 14A": "股东大会委托书",
}

# 8-K 事项码 → 中文（最常见者；缺失则原样保留）
_ITEM_ZH = {
    "1.01": "签订重大协议",
    "1.02": "终止重大协议",
    "2.01": "完成收购/处置",
    "2.02": "经营成果与财务状况（财报）",
    "2.03": "新增重大债务",
    "2.05": "重组/裁员费用",
    "1.05": "重大网络安全事件",
    "3.01": "退市/上市规则",
    "3.02": "股权发行",
    "4.01": "会计师变更",
    "4.02": "此前财报不可依赖",
    "5.01": "控制权变更",
    "5.02": "高管/董事变动",
    "5.03": "章程修订",
    "5.07": "股东投票结果",
    "7.01": "Regulation FD 披露",
    "8.01": "其他重大事件",
    "9.01": "财务报表与附件",
}

_sub_cache: dict[str, tuple[float, dict]] = {}
_tickers_cache: tuple[float, dict[str, str]] | None = None  # (加载时刻, 映射)
_lock = threading.Lock()
_last_req = 0.0


def _ua() -> str:
    return get_settings().sec_user_agent or "Augur/0.1 research non-commercial"


def _throttle() -> None:
    """守住 ≤10 req/s（进程内串行小间隔；单用户够用）。"""
    global _last_req
    with _lock:
        gap = time.monotonic() - _last_req
        if gap < _MIN_GAP:
            time.sleep(_MIN_GAP - gap)
        _last_req = time.monotonic()


def _get(url: str) -> httpx.Response:
    """GET 并内部 raise_for_status（与 cls/eastmoney 一致：get 即校验）。SEC 缺 UA→403、
    错 CIK→404 都以清晰的 HTTPStatusError 暴露，而非伪装成下游 JSONDecodeError。"""
    _throttle()
    headers = {"User-Agent": _ua(), "Accept-Encoding": "gzip, deflate"}
    with httpx.Client(timeout=_TIMEOUT, headers=headers, follow_redirects=True) as c:
        resp = c.get(url)
    resp.raise_for_status()
    return resp


def _load_tickers() -> dict[str, str]:
    """{TICKER(大写): CIK(10 位零填充)}。先用缓存文件（7 天），过期/缺失则拉官方 JSON。

    内存缓存也带时间戳（1 天）——否则长跑 --reload 进程一旦加载过就永不刷新，
    新上市/退市票的 CIK 查不到（恰是 directed「补齐新上市」的目标）。
    """
    global _tickers_cache
    if _tickers_cache is not None and time.time() - _tickers_cache[0] < _SUB_TTL * 4:
        return _tickers_cache[1]
    path = get_settings().cache_dir / "edgar_company_tickers.json"
    fresh = path.exists() and (time.time() - path.stat().st_mtime) < _TICKERS_TTL
    raw: dict | None = None
    if fresh:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raw = None
    if raw is None:
        try:
            raw = _get(_TICKERS_URL).json()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        except (httpx.HTTPError, json.JSONDecodeError, OSError):
            if path.exists():  # 拉取失败 → 退回陈旧缓存（暴露不确定性优于无数据）
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    raw = None
    mapping: dict[str, str] = {}
    if isinstance(raw, dict):
        for row in raw.values():
            try:
                tk = str(row["ticker"]).upper()
                mapping[tk] = f"{int(row['cik_str']):010d}"
            except (KeyError, ValueError, TypeError):
                continue
    # 仅在拿到非空映射时落内存缓存（拉取失败返回的空 dict 不该被缓存 1 天）
    if mapping:
        _tickers_cache = (time.time(), mapping)
    return mapping


def cik_for(symbol: str) -> str | None:
    """US:TICKER → CIK(10 位)。仅美股；未命中 → None。处理 BRK.B↔BRK-B 类后缀。"""
    market, _, code = symbol.partition(":")
    if market.upper() != "US" or not code:
        return None
    m = _load_tickers()
    tk = code.upper()
    return m.get(tk) or m.get(tk.replace(".", "-")) or m.get(tk.replace("-", "."))


def _keep(form: str) -> bool:
    return any(form.upper().startswith(p) for p in _FORM_PREFIXES)


def _form_zh(form: str) -> str:
    fu = form.upper()
    base = fu.split("/")[0].strip()
    amend = "·修订" if "/A" in fu else ""
    label = _FORM_ZH.get(base) or _FORM_ZH.get(fu)
    if not label:  # 前缀兜底：424B5/424B7→424B 等变体
        label = next((v for k, v in _FORM_ZH.items() if base.startswith(k)), None)
    return (label or base) + amend


def _items_zh(items: str) -> str:
    """'2.02,9.01' → '经营成果与财务状况（财报）；财务报表与附件'。"""
    out = [_ITEM_ZH.get(c.strip(), c.strip()) for c in (items or "").split(",") if c.strip()]
    return "；".join(out)


def filings_for(symbol: str, limit: int = 15) -> list[dict]:
    """某美股最近的高信号官方文件（归一化条目）。非美股 / 未命中 / 失败 → []。"""
    cik10 = cik_for(symbol)
    if not cik10:
        return []
    now = time.time()
    cached = _sub_cache.get(cik10)
    if cached and now - cached[0] < _SUB_TTL:
        data = cached[1]
    else:
        try:
            data = _get(_SUBMISSIONS_URL.format(cik10=cik10)).json()
            _sub_cache[cik10] = (now, data)
        except (httpx.HTTPError, json.JSONDecodeError):
            if cached:  # 失败退回陈旧缓存
                data = cached[1]
            else:
                return []
    rec = (data.get("filings") or {}).get("recent") or {}
    forms = rec.get("form") or []
    accs = rec.get("accessionNumber") or []
    docs = rec.get("primaryDocument") or []
    descs = rec.get("primaryDocDescription") or []
    dates = rec.get("filingDate") or []
    items_col = rec.get("items") or []
    cik_int = int(cik10)
    out: list[dict] = []
    for i, form in enumerate(forms):
        if not _keep(form):
            continue
        acc = accs[i] if i < len(accs) else ""
        doc = docs[i] if i < len(docs) else ""
        desc = (descs[i] if i < len(descs) else "") or ""
        date = dates[i] if i < len(dates) else None
        items = items_col[i] if i < len(items_col) else ""
        acc_nodash = acc.replace("-", "")
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{doc}"
            if doc
            else f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik10}"
        )
        items_label = _items_zh(items) if form.upper().startswith("8-K") else ""
        # 标题：中文表单标签 +（8-K 事项 / 文件描述）；滤掉与表单名重复的占位描述
        du = desc.upper().replace(" ", "")
        fu = form.upper().replace(" ", "")
        redundant = du in ("", fu, f"FORM{fu}")
        detail = items_label or ("" if redundant else desc)
        # form 作为独立字段（前端 badge）；标题只放中文标签 + 细节，避免重复
        title = _form_zh(form) + (f" · {detail}" if detail else "")
        out.append(
            {
                "form": form,
                "title": title,
                "url": url,
                "summary": items_label,
                "filed_at": date,
                "accession": acc,
                "cik": cik_int,
            }
        )
        if len(out) >= limit:
            break
    return out


def filing_documents(cik: int, accession: str) -> list[dict]:
    """某 filing 目录下的全部文档（含 EX-99.1 等附件）。失败 → []。目录不可变，长缓存。"""
    acc_nodash = accession.replace("-", "")
    now = time.time()
    cached = _index_cache.get(acc_nodash)
    if cached and now - cached[0] < _CONTENT_TTL:
        return cached[1]
    url = _ARCHIVE_DIR.format(cik=cik, acc=acc_nodash) + "index.json"
    try:
        data = _get(url).json()
    except (httpx.HTTPError, json.JSONDecodeError):
        return []
    items = ((data.get("directory") or {}).get("item")) or []
    docs = [
        {"name": str(it.get("name") or ""), "type": str(it.get("type") or "")}
        for it in items
        if isinstance(it, dict)
    ]
    _index_cache[acc_nodash] = (now, docs)
    return docs


def exhibit_99_url(cik: int, accession: str) -> str | None:
    """filing 里的 Exhibit 99.1（财报新闻稿正文所在）；优先 99.1，回退任意 EX-99。"""
    acc_nodash = accession.replace("-", "")
    base = _ARCHIVE_DIR.format(cik=cik, acc=acc_nodash)
    htmish = [
        d
        for d in filing_documents(cik, accession)
        if d["name"].lower().endswith((".htm", ".html"))
    ]

    def score(d: dict) -> int:
        t = d["type"].upper().replace(" ", "")
        n = d["name"].lower().replace("-", "").replace("_", "").replace(".", "")
        if t.startswith("EX-99.1") or "ex991" in n:
            return 2
        if t.startswith("EX-99") or "ex99" in n:
            return 1
        return 0

    best = max(htmish, key=score, default=None)
    return base + best["name"] if best and score(best) > 0 else None


def fetch_filing_text(url: str, max_chars: int = 4000) -> str:
    """抓 filing/exhibit HTML → 清洗成纯文本正文（去样板/标签/XBRL）。失败/空 → ""。"""
    now = time.time()
    cached = _content_cache.get(url)
    if cached and now - cached[0] < _CONTENT_TTL:
        return cached[1]
    try:
        raw = _get(url).text
    except httpx.HTTPError:
        return ""
    text = _BLOCK_RE.sub(" ", raw)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text).strip()
    # 8-K 主文档前部是 XBRL 内联数据 + 固定法律封面；真正内容在 "Item X.XX" 标题之后
    head = text[:1800].lower()
    if "current report" in head or "pursuant to section 13" in head:
        m = re.search(r"Item\s+\d+\.\d+", text)
        if m and m.start() > 100:
            text = text[m.start() :]
    text = text[:max_chars].strip()
    if text:
        _content_cache[url] = (now, text)
    return text


def disclosure_body(filing: dict, is_earnings: bool) -> str:
    """披露正文（喂 LLM）：财报类优先 EX-99.1 新闻稿；非财报 8-K 抓主文档；
    10-Q/K/20-F 不抓全文（靠 financials）。"""
    form = str(filing.get("form") or "").upper()
    cik = filing.get("cik")
    acc = str(filing.get("accession") or "")
    main_url = str(filing.get("url") or "")
    if is_earnings and cik and acc:
        ex = exhibit_99_url(int(cik), acc)
        if ex:
            body = fetch_filing_text(ex)
            if body:
                return body
    if form.startswith(("10-Q", "10-K", "20-F")):
        return ""
    return fetch_filing_text(main_url) if main_url else ""
