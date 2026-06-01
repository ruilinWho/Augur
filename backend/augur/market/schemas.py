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
    name: str = ""  # 中文优先的展示名（如 SK海力士）
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


class Fundamentals(BaseModel):
    symbol: str
    market_cap: float | None = None  # 市值（本币原值）
    pe: float | None = None  # 滚动 P/E（亏损/缺失为 None）
    revenue: float | None = None  # 营收（TTM）
    net_income: float | None = None  # 净利润
    net_margin: float | None = None  # 净利润率
    eps: float | None = None  # 每股收益
    currency: str = ""  # USD/HKD/CNY/KRW


class FinancialPeriod(BaseModel):
    period: str  # 季度 '2026Q1' / 年度 '2025'
    revenue: float | None = None
    revenue_growth: float | None = None  # 同比
    net_income: float | None = None
    net_margin: float | None = None
    eps: float | None = None
    eps_growth: float | None = None
    fcf: float | None = None  # 自由现金流


class ReportLink(BaseModel):
    label: str
    url: str


class FinancialsTable(BaseModel):
    symbol: str
    period: str = "quarter"  # 'quarter' | 'annual'
    currency: str = ""
    periods: list[FinancialPeriod] = []  # 最新在前
    links: list[ReportLink] = []
