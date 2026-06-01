"""market 域的 Pydantic 模型（API 契约）。"""

from __future__ import annotations

from pydantic import BaseModel


class Candle(BaseModel):
    time: str  # 'YYYY-MM-DD'（Lightweight Charts 日线用字符串日期）
    open: float
    high: float
    low: float
    close: float
    volume: float


class OHLCVResponse(BaseModel):
    symbol: str
    interval: str
    source: str
    cached: bool
    candles: list[Candle]


class Quote(BaseModel):
    symbol: str
    price: float
    change: float  # 较前收的绝对变动
    change_pct: float  # 百分比
    time: str
    source: str


class SearchHit(BaseModel):
    symbol: str  # MARKET:CODE
    market: str
    code: str
    name: str  # 主显示名（本地语优先）
    sub: str = ""  # 次要显示（英文名 / 中文别名）


class SearchResponse(BaseModel):
    query: str
    indexing: bool  # 索引仍在后台构建（首跑/刷新中）
    results: list[SearchHit] = []
