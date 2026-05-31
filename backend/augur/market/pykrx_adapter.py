"""pykrx 适配器：韩股（KRX）。FDR 的韩股源（naver）已失效，故用专门库。

pykrx 返回韩文列名：시가/고가/저가/종가/거래량 → open/high/low/close/volume。
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from pykrx import stock

from .base import OHLCV_COLUMNS, MarketAdapter
from .symbols import Symbol

_KR_COLS = {"시가": "open", "고가": "high", "저가": "low", "종가": "close", "거래량": "volume"}


class PykrxAdapter(MarketAdapter):
    name = "pykrx"

    def get_ohlcv(self, sym: Symbol, start: str, end: str | None) -> pd.DataFrame:
        s = start.replace("-", "")
        e = (end or date.today().isoformat()).replace("-", "")
        df = stock.get_market_ohlcv(s, e, sym.code)
        if df is None or df.empty:
            return pd.DataFrame(columns=OHLCV_COLUMNS)
        df = df.rename(columns=_KR_COLS)
        df = df[[c for c in OHLCV_COLUMNS if c in df.columns]].copy()
        df.index = pd.to_datetime(df.index)
        df.index.name = "date"
        return df.dropna(subset=["close"])
