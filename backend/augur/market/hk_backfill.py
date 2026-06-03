"""港股历史 K 线兜底源（修「回收代码只剩 1 根」）。

FDR/雅虎对**回收代码**只吐最新 1 根——港股代码退市后会被回收再分配（如 `00100`＝老
Clear Media 退市后、2026-01 给 MiniMax-W），雅虎把新旧历史搅在一起、只剩 1 行。

本模块按 5 位代码取完整日线：**腾讯**首选（直连、含当日），失败回退**新浪**
（akshare `stock_hk_daily`）。两者都**不走 `push2his`**（被部分网络代理拦截，见
docs/memory/search-data-sources.md）。不可达 / 无数据 → None，由 service 回退 FDR 结果。
"""

from __future__ import annotations

import httpx
import pandas as pd

from .base import OHLCV_COLUMNS

_TENCENT = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
_TIMEOUT = 12.0
_MAX_BARS = 1600  # ≈6 年交易日；老股取满、新股自然只回到上市日


def _from_tencent(digits: str) -> pd.DataFrame | None:
    """腾讯日线：data.hk<code>.qfqday = [[日期,开,收,高,低,量,...], ...]。"""
    try:
        r = httpx.get(
            _TENCENT,
            params={"param": f"hk{digits},day,,,{_MAX_BARS},qfq"},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        node = (r.json().get("data") or {}).get(f"hk{digits}") or {}
    except Exception:
        return None
    kl = node.get("qfqday") or node.get("day") or []
    rows: list[dict] = []
    for k in kl:
        if len(k) < 6:
            continue
        try:
            rows.append(
                {
                    "date": k[0],
                    "open": float(k[1]),
                    "close": float(k[2]),
                    "high": float(k[3]),
                    "low": float(k[4]),
                    "volume": float(k[5]),
                }
            )
        except (TypeError, ValueError):
            continue
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")[OHLCV_COLUMNS]
    df.index.name = "date"
    return df.dropna(subset=["close"])


def _from_sina(digits: str) -> pd.DataFrame | None:
    """新浪日线（akshare stock_hk_daily）：已是 date/open/high/low/close/volume 列。"""
    try:
        import akshare as ak

        df = ak.stock_hk_daily(symbol=digits, adjust="")
    except Exception:
        return None
    if df is None or df.empty or "date" not in df.columns:
        return None
    df = df.rename(columns=str.lower)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    df = df[[c for c in OHLCV_COLUMNS if c in df.columns]].copy()
    df.index.name = "date"
    return df.dropna(subset=["close"])


def hk_history(code: str) -> pd.DataFrame | None:
    """取港股完整日线（腾讯→新浪）。不可达/空 → None。"""
    digits = "".join(ch for ch in code if ch.isdigit()).zfill(5)
    df = _from_tencent(digits)
    if df is None or df.empty:
        df = _from_sina(digits)
    return df if (df is not None and not df.empty) else None
