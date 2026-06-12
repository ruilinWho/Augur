"""market 域 HTTP 路由。同步数据调用丢进 threadpool（AGENTS.md §5）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from . import fundamentals as fundamentals_mod
from . import search as search_mod
from . import service
from .schemas import (
    Candle,
    FinancialsTable,
    Fundamentals,
    OHLCVResponse,
    Quote,
    SearchResponse,
)
from .symbols import parse_symbol

router = APIRouter(prefix="/market", tags=["market"])


def _to_candles(df) -> list[Candle]:
    return [
        Candle(
            time=idx.strftime("%Y-%m-%d"),
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            volume=float(row.volume),
        )
        for idx, row in df.iterrows()
    ]


@router.get("/ohlcv", response_model=OHLCVResponse)
async def get_ohlcv(symbol: str, interval: str = "1d", range: str = "2y") -> OHLCVResponse:
    try:
        sym = parse_symbol(symbol)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        df, source, cached = await run_in_threadpool(service.get_ohlcv, sym, interval, range)
    except Exception as e:  # 数据源故障/限流
        raise HTTPException(status_code=502, detail=f"行情获取失败：{type(e).__name__}: {e}") from e
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"无数据：{sym.canonical}")
    return OHLCVResponse(
        symbol=sym.canonical,
        interval=interval,
        source=source,
        cached=cached,
        candles=_to_candles(df),
    )


@router.get("/search", response_model=SearchResponse)
async def search(q: str, market: str | None = None, limit: int = 20) -> SearchResponse:
    """模糊检索标的：代码/中文/英文/韩文/拼音/别名；market 限定范围（AGENTS.md §7）。"""
    hits = await run_in_threadpool(search_mod.search, q, market, min(limit, 50))
    return SearchResponse(query=q, indexing=not search_mod.ready(), results=hits)


@router.get("/fundamentals", response_model=Fundamentals)
async def fundamentals(symbol: str) -> Fundamentals:
    """基本面：市值 / 营收 / 利润 / P-E（yfinance，本币原值；缺失为 null）。"""
    try:
        sym = parse_symbol(symbol)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    data = await run_in_threadpool(fundamentals_mod.get_fundamentals, sym.canonical)
    return Fundamentals(symbol=sym.canonical, **data)


@router.get("/financials", response_model=FinancialsTable)
async def financials(symbol: str, period: str = "quarter") -> FinancialsTable:
    """历史财报趋势表（最新在前）：营收/增长/净利/净利率/EPS/自由现金流 + 财报链接。
    period：`quarter`（季度，默认，~5–7 期）| `annual`（年度，~4–5 年）。"""
    try:
        sym = parse_symbol(symbol)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    data = await run_in_threadpool(fundamentals_mod.get_financials, sym.canonical, period)
    return FinancialsTable(symbol=sym.canonical, **data)


@router.get("/quote", response_model=Quote)
async def get_quote(symbol: str) -> Quote:
    try:
        sym = parse_symbol(symbol)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        q = await run_in_threadpool(service.get_quote, sym)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"报价获取失败：{type(e).__name__}: {e}") from e
    if q is None:
        raise HTTPException(status_code=404, detail=f"无数据：{sym.canonical}")
    return Quote(symbol=sym.canonical, **q)
