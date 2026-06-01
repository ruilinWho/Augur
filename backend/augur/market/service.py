"""行情服务：缓存优先、只抓缺失尾巴、按需重采样/截取区间（CLAUDE.md §7）。

纯逻辑层——HTTP 在 router.py，I/O（数据源/磁盘）在适配器/storage。
"""

from __future__ import annotations

import time
from datetime import date, timedelta

import pandas as pd

from ..storage import cache
from . import search
from .resolver import get_adapter
from .symbols import Symbol

_DEFAULT_HISTORY_DAYS = 365 * 5
_REFRESH_TTL_SEC = 600  # 同一标的最多每 10 分钟回源补尾，避免狂打数据源（CLAUDE.md §11）
_refresh_ts: dict[str, float] = {}
_RANGE_UNIT_DAYS = {"y": 365, "m": 30, "w": 7, "d": 1}
_RESAMPLE_RULE = {"1w": "W", "1M": "ME"}
_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def _fetch_daily(sym: Symbol) -> tuple[pd.DataFrame, str, bool]:
    """取日线全量（缓存优先 + 增量追加尾巴）。返回 (df, source, cached)。"""
    adapter = get_adapter(sym.market)
    cached = cache.load(sym.market, sym.code, "1d")
    today = date.today()
    now = time.time()

    if cached is not None and not cached.empty:
        cached.index = pd.to_datetime(cached.index)
        # 近期刚回源过，或已是最新交易日 → 直接用缓存，不打数据源
        recently = now - _refresh_ts.get(sym.canonical, 0.0) < _REFRESH_TTL_SEC
        last = cached.index.max().date()
        if recently or last >= today - timedelta(days=1):
            return cached, adapter.name, True
        fresh = adapter.get_ohlcv(sym, (last + timedelta(days=1)).isoformat(), None)
        _refresh_ts[sym.canonical] = now
        if fresh is not None and not fresh.empty:
            merged = pd.concat([cached, fresh])
            merged = merged[~merged.index.duplicated(keep="last")].sort_index()
            cache.save(sym.market, sym.code, "1d", merged)
            return merged, adapter.name, False
        return cached, adapter.name, True

    start = (today - timedelta(days=_DEFAULT_HISTORY_DAYS)).isoformat()
    df = adapter.get_ohlcv(sym, start, None)
    _refresh_ts[sym.canonical] = now
    if df is not None and not df.empty:
        cache.save(sym.market, sym.code, "1d", df)
    return df, adapter.name, False


def _apply_range(df: pd.DataFrame, rng: str) -> pd.DataFrame:
    if df.empty or rng == "max":
        return df
    try:
        n, unit = int(rng[:-1]), rng[-1].lower()
    except ValueError:
        return df
    days = _RANGE_UNIT_DAYS.get(unit, 365) * n
    cutoff = df.index.max() - pd.Timedelta(days=days)
    return df[df.index >= cutoff]


def _resample(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    if df.empty or interval == "1d":
        return df
    rule = _RESAMPLE_RULE.get(interval)
    if not rule:
        return df
    return df.resample(rule).agg(_AGG).dropna(subset=["close"])


def get_ohlcv(sym: Symbol, interval: str = "1d", rng: str = "2y") -> tuple[pd.DataFrame, str, bool]:
    df, source, cached = _fetch_daily(sym)
    return _resample(_apply_range(df, rng), interval), source, cached


def get_quote(sym: Symbol) -> dict | None:
    df, source, _ = _fetch_daily(sym)
    if df is None or df.empty:
        return None
    price = float(df.iloc[-1]["close"])
    prev = float(df.iloc[-2]["close"]) if len(df) >= 2 else price
    change = price - prev
    return {
        "name": search.display_name(sym.canonical),
        "price": price,
        "change": change,
        "change_pct": (change / prev * 100.0) if prev else 0.0,
        "time": df.index.max().strftime("%Y-%m-%d"),
        "source": source,
    }
