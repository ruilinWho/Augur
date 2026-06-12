"""行情服务：缓存优先、只抓缺失尾巴、按需重采样/截取区间（AGENTS.md §7）。

纯逻辑层——HTTP 在 router.py，I/O（数据源/磁盘）在适配器/storage。
"""

from __future__ import annotations

import time
from datetime import date, timedelta

import pandas as pd

from ..storage import cache
from . import hk_backfill, search
from .resolver import get_adapter
from .symbols import Symbol, parse_symbol

_DEFAULT_HISTORY_DAYS = 365 * 5
_REFRESH_TTL_SEC = 600  # 同一标的最多每 10 分钟回源补尾，避免狂打数据源（AGENTS.md §11）
# 港股 FDR（雅虎源）若只吐极少几根，多半是**回收代码**历史损坏（如 00100=MiniMax-W）→
# 回退到东财补全。阈值取小：真新股本就稀疏、回退只在更多时才替换，误触发也无害。
_HK_THIN_ROWS = 10
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
        recently = now - _refresh_ts.get(sym.canonical, 0.0) < _REFRESH_TTL_SEC
        # 港股缓存异常稀疏（回收代码 FDR 只吐 1 根）→ 东财回填（带 TTL，不狂打）
        if sym.market == "HK" and len(cached) < _HK_THIN_ROWS and not recently:
            fb = hk_backfill.hk_history(sym.code)
            _refresh_ts[sym.canonical] = now
            if fb is not None and len(fb) > len(cached):
                cache.save(sym.market, sym.code, "1d", fb)
                return fb, "hk_backfill", False
        # 近期刚回源过，或已是最新交易日 → 直接用缓存，不打数据源
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
    source = adapter.name
    _refresh_ts[sym.canonical] = now
    # 港股首取若过于稀疏 → 东财兜底（修回收代码历史损坏）
    if sym.market == "HK" and (df is None or len(df) < _HK_THIN_ROWS):
        fb = hk_backfill.hk_history(sym.code)
        if fb is not None and (df is None or len(fb) > len(df)):
            df, source = fb, "hk_backfill"
    if df is not None and not df.empty:
        cache.save(sym.market, sym.code, "1d", df)
    return df, source, False


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
    # 周/月重采样：前端 4 个区间只发 interval='1d'，
    # 本路径仅经 /market/ohlcv?interval=1w|1M 公开 API 可达。
    if df.empty or interval == "1d":
        return df
    rule = _RESAMPLE_RULE.get(interval)
    if not rule:
        return df
    return df.resample(rule).agg(_AGG).dropna(subset=["close"])


def get_ohlcv(sym: Symbol, interval: str = "1d", rng: str = "2y") -> tuple[pd.DataFrame, str, bool]:
    df, source, cached = _fetch_daily(sym)
    return _resample(_apply_range(df, rng), interval), source, cached


def momentum(symbol: str) -> dict | None:
    """近月涨幅 + 放量比（基于缓存日线，缓存优先）。数据不足/失败 → None。

    ret_pct = 最近约 20 个交易日收益%；vol_ratio = 最近 5 日均量 / 之前约 20 日均量。
    供「寻」标出「近期大涨且放量」的关键信号。失败静默（不拖垮调用方）。
    """
    try:
        sym = parse_symbol(symbol)
        df, _, _ = get_ohlcv(sym, "1d", "3m")
    except Exception:  # noqa: BLE001 — 行情失败不该拖垮「寻」
        return None
    if df is None or len(df) < 12:
        return None
    closes = df["close"].astype(float)
    vols = df["volume"].astype(float)
    n = min(20, len(closes) - 1)
    base_close = float(closes.iloc[-1 - n])
    ret = (float(closes.iloc[-1]) / base_close - 1.0) * 100.0 if base_close else 0.0
    recent_v = float(vols.iloc[-5:].mean()) if len(vols) >= 5 else float(vols.iloc[-1])
    prev = vols.iloc[max(0, len(vols) - n - 5) : max(1, len(vols) - 5)]
    base_v = float(prev.mean()) if len(prev) else 0.0
    vol_ratio = (recent_v / base_v) if base_v else 0.0
    return {"ret_pct": round(ret, 1), "vol_ratio": round(vol_ratio, 1)}


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
