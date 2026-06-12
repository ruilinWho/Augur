"""Financial Modeling Prep：电话会 transcript（可选付费源）。

SEC EDGAR 给美股官方申报，但不提供 earnings call transcript。电话会内容需要第三方结构化源；
这里接 FMP 的 stable earnings call transcript endpoints。没有 key 时静默返回空，让 Augur 仍靠
SEC/新闻/财报表工作。
"""

from __future__ import annotations

import threading
import time

import httpx

from .. import runtime_config

FMP_SECRET = "FMP_API_KEY"
_BASE = "https://financialmodelingprep.com/stable"
_TIMEOUT = 15.0
_TTL = 6 * 3600.0
_LOCK = threading.Lock()
_CACHE: dict[str, tuple[float, object]] = {}


def clear_cache() -> None:
    with _LOCK:
        _CACHE.clear()


def configured() -> bool:
    return runtime_config.has_secret(FMP_SECRET)


def _fmp_symbol(symbol: str) -> str | None:
    market, _, code = symbol.partition(":")
    if market.upper() != "US" or not code:
        return None
    return code.upper().replace(".", "-")


def _get(path: str, params: dict[str, object]) -> object:
    key = runtime_config.get_secret(FMP_SECRET)
    if not key:
        return []
    p = dict(params)
    p["apikey"] = key
    url = f"{_BASE}/{path.lstrip('/')}"
    with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as c:
        resp = c.get(url, params=p)
    resp.raise_for_status()
    return resp.json()


def _cached(cache_key: str, loader) -> object:
    now = time.time()
    with _LOCK:
        hit = _CACHE.get(cache_key)
        if hit and now - hit[0] < _TTL:
            return hit[1]
    try:
        data = loader()
    except Exception:  # noqa: BLE001 — 第三方 transcript 失败不拖垮「看」
        data = []
    with _LOCK:
        _CACHE[cache_key] = (now, data)
    return data


def transcript_dates(symbol: str, limit: int = 6) -> list[dict]:
    """最近电话会 transcript 日期元数据。无 key/非美股/失败 → []。"""
    fmp_symbol = _fmp_symbol(symbol)
    if not fmp_symbol or not configured():
        return []

    def load() -> object:
        return _get("earning-call-transcript-dates", {"symbol": fmp_symbol})

    raw = _cached(f"dates:{fmp_symbol}", load)
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        year = row.get("year") or row.get("fiscalYear")
        quarter = row.get("quarter") or row.get("fiscalQuarter")
        date = row.get("date") or row.get("publishedDate") or row.get("calendarYear")
        try:
            y = int(year)
            q = int(str(quarter).replace("Q", ""))
        except (TypeError, ValueError):
            continue
        if q < 1 or q > 4:
            continue
        out.append({"symbol": fmp_symbol, "year": y, "quarter": q, "date": str(date or "")[:10]})
        if len(out) >= limit:
            break
    return out


def transcript(symbol: str, year: int, quarter: int) -> dict | None:
    """一季电话会 transcript。返回精简字典；失败/缺失 → None。"""
    fmp_symbol = _fmp_symbol(symbol)
    if not fmp_symbol or not configured():
        return None

    def load() -> object:
        return _get(
            "earning-call-transcript",
            {"symbol": fmp_symbol, "year": int(year), "quarter": int(quarter)},
        )

    raw = _cached(f"transcript:{fmp_symbol}:{year}:Q{quarter}", load)
    row = raw[0] if isinstance(raw, list) and raw else raw
    if not isinstance(row, dict):
        return None
    content = str(row.get("content") or row.get("transcript") or "").strip()
    if not content:
        return None
    date = str(row.get("date") or row.get("publishedDate") or "")[:10]
    return {
        "symbol": fmp_symbol,
        "year": int(year),
        "quarter": int(quarter),
        "date": date,
        "title": str(row.get("title") or f"{fmp_symbol} {year} Q{quarter} Earnings Call"),
        "content": content,
    }


def transcripts_for(symbol: str, limit: int = 3, include_content: bool = True) -> list[dict]:
    """最近 N 次电话会 transcript。content 会截断，避免喂 LLM 过长。"""
    out: list[dict] = []
    for d in transcript_dates(symbol, limit=limit):
        item = transcript(symbol, d["year"], d["quarter"]) if include_content else None
        if item is None:
            item = {
                "symbol": d["symbol"],
                "year": d["year"],
                "quarter": d["quarter"],
                "date": d.get("date") or "",
                "title": f"{d['symbol']} {d['year']} Q{d['quarter']} Earnings Call",
                "content": "",
            }
        item["content"] = str(item.get("content") or "")[:6000]
        out.append(item)
    return out
