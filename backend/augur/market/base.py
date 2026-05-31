"""MarketAdapter 接口：每个数据源一个实现，统一在此接口后（CLAUDE.md §7）。

适配器只做"取原始数据并归一化为标准 DataFrame"，不碰缓存、不碰 HTTP 层。
返回的 DataFrame：DatetimeIndex（名为 date）+ 列 open/high/low/close/volume。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from .symbols import Symbol

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


class MarketAdapter(ABC):
    name: str

    @abstractmethod
    def get_ohlcv(self, sym: Symbol, start: str, end: str | None) -> pd.DataFrame:
        """取日线 OHLCV。start/end 为 'YYYY-MM-DD'；end=None 表示到最新。

        返回标准化 DataFrame（DatetimeIndex + OHLCV_COLUMNS）。
        """
        raise NotImplementedError
