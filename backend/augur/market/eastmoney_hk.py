"""港股历史 K 线兜底源：东财（akshare `stock_hk_hist`）。

为什么需要：FDR（雅虎源）对**回收代码**只吐最新 1 根——港股代码退市后会被回收
再分配（如 00100＝老 Clear Media 退市后、2026-01 分给 MiniMax-W）。雅虎把新旧历史
混在一起、只剩 1 行。东财作为中国数据商有完整港股历史，按 5 位代码取。

注意：东财 push2his 在部分网络（代理）下不可达——本模块**失败即返回 None**，由
service 回退到 FDR 结果，不影响主路径（见 docs/memory/search-data-sources.md）。
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from .base import OHLCV_COLUMNS

_HISTORY_DAYS = 365 * 5
_RENAME = {
    "日期": "date",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "收盘": "close",
    "成交量": "volume",
}


def hk_history(code: str) -> pd.DataFrame | None:
    """取港股日线全量（东财）。不可达 / 无数据 → None，交回 FDR 结果。"""
    try:
        import akshare as ak
    except Exception:
        return None
    digits = "".join(ch for ch in code if ch.isdigit()).zfill(5)
    start = (date.today() - timedelta(days=_HISTORY_DAYS)).strftime("%Y%m%d")
    try:
        df = ak.stock_hk_hist(
            symbol=digits,
            period="daily",
            start_date=start,
            end_date="22220101",
            adjust="",
        )
    except Exception:
        return None  # 东财不可达（push2 被代理拦截）等 → 静默回退
    if df is None or df.empty:
        return None
    df = df.rename(columns=_RENAME)
    if "date" not in df.columns or "close" not in df.columns:
        return None
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    df = df[[c for c in OHLCV_COLUMNS if c in df.columns]].copy()
    df.index.name = "date"
    return df.dropna(subset=["close"])
