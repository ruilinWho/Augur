"""market 域 HTTP 路由。同步数据调用丢进 threadpool（CLAUDE.md §5）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from . import service
from .schemas import Candle, OHLCVResponse, Quote
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
