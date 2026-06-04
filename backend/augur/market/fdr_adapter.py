"""FinanceDataReader 适配器：美 / 中 / 港 基座（韩股见 pykrx_adapter）。

实测的原生格式（2026-05）：US='AAPL'、CN='SSE:600519'/'SZSE:000001'、HK='0700.HK'。
"""

from __future__ import annotations

import FinanceDataReader as fdr
import pandas as pd

from .base import OHLCV_COLUMNS, MarketAdapter
from .symbols import Symbol, cn_exchange


class FdrAdapter(MarketAdapter):
    name = "fdr"

    def to_native(self, sym: Symbol) -> str:
        m, code = sym.market, sym.code
        if m == "US":
            return code.upper()
        if m == "HK":
            # 港股 5 位代码 → 雅虎 4 位 + .HK（00700 → 0700.HK）
            digits = "".join(ch for ch in code if ch.isdigit())
            return f"{int(digits):04d}.HK"
        if m == "CN":
            # 沪(SSE)/深(SZSE)/北交所(BSE)——共享 cn_exchange，避免与 fundamentals 双份漂移
            return f"{cn_exchange(code)}:{code}"
        raise ValueError(f"FdrAdapter 不支持市场 {m!r}（韩股用 pykrx）")

    def get_ohlcv(self, sym: Symbol, start: str, end: str | None) -> pd.DataFrame:
        native = self.to_native(sym)
        try:
            df = fdr.DataReader(native, start, end)
        except NotImplementedError:
            # FDR 暂不支持的交易所（如北交所 BSE）→ 优雅降级为空（前端显「暂无数据」而非 500）
            return pd.DataFrame(columns=OHLCV_COLUMNS)
        if df is None or df.empty:
            return pd.DataFrame(columns=OHLCV_COLUMNS)
        df = df.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        df = df[[c for c in OHLCV_COLUMNS if c in df.columns]].copy()
        df.index = pd.to_datetime(df.index)
        df.index.name = "date"
        return df.dropna(subset=["close"])
