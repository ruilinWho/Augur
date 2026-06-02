"""个股相关新闻——来自雅虎财经的**逐 ticker** 新闻 API（yfinance `.news`）。

主人问"个股相关新闻能否从 API 找"：能。yfinance 已是依赖、免费、覆盖四市场，按 ticker 直接
返回该公司新闻（比在聚合流里按公司名模糊匹配更准、更全）。归一化为
{source,title,url,published_at}，3h 内存缓存、失败降级 []。兼容 yfinance 新旧两种 `.news`
结构（新版用 `content` 包裹 + ISO 时间；旧版扁平 + epoch 时间）。复用 fundamentals 的
内部 `_yahoo_symbols` 做 MARKET:CODE → 雅虎代码映射。
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime

import yfinance as yf

from ..market.fundamentals import _yahoo_symbols

_CACHE: dict[str, tuple[float, list[dict]]] = {}
_LOCK = threading.Lock()
_TTL = 3 * 3600.0  # 个股新闻 3h 缓存（别频繁打雅虎）


def _norm(item: dict) -> dict | None:
    c = item.get("content") if isinstance(item.get("content"), dict) else item
    title = str(c.get("title") or "").strip()
    if not title:
        return None
    url = ""
    for k in ("canonicalUrl", "clickThroughUrl"):
        v = c.get(k)
        if isinstance(v, dict) and v.get("url"):
            url = str(v["url"])
            break
    url = url or str(c.get("link") or item.get("link") or "")
    prov = c.get("provider")
    source = (
        (prov.get("displayName") if isinstance(prov, dict) else None)
        or c.get("publisher")
        or item.get("publisher")
        or "Yahoo Finance"
    )
    published: str | None = None
    pub = c.get("pubDate") or c.get("displayTime")
    if isinstance(pub, str) and pub.strip():
        published = pub.strip()
    else:
        epoch = item.get("providerPublishTime") or c.get("providerPublishTime")
        if epoch:
            try:
                published = datetime.fromtimestamp(int(epoch), tz=UTC).isoformat()
            except (ValueError, OSError, OverflowError):
                published = None
    return {"source": str(source)[:60], "title": title[:500], "url": url, "published_at": published}


def ticker_news(symbol: str, limit: int = 15) -> list[dict]:
    """某标的的雅虎逐-ticker 新闻（归一化条目）。无 ticker / 失败 / 空 → []。"""
    now = time.time()
    with _LOCK:
        hit = _CACHE.get(symbol)
        if hit and now - hit[0] < _TTL:
            return hit[1][:limit]
    out: list[dict] = []
    seen: set[str] = set()
    for ysym in _yahoo_symbols(symbol):
        try:
            raw = yf.Ticker(ysym).news or []
        except Exception:  # noqa: BLE001 — 限流/网络 → 试下一个候选或留空
            continue
        for it in raw:
            n = _norm(it)
            if n and n["url"] and n["url"] not in seen:
                seen.add(n["url"])
                out.append(n)
        if out:  # 第一个有结果的雅虎代码即采用
            break
    with _LOCK:
        _CACHE[symbol] = (now, out)
    return out[:limit]
