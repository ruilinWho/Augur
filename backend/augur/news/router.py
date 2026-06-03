"""news 域 HTTP 路由（M3「知」）：信息流 / 趋势日报（生成走 SSE 流式）。"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from ..llm import gateway
from . import service
from .schemas import (
    ClustersResponse,
    Filing,
    NewsItem,
    NewsReport,
    OpportunitiesResponse,
    RefreshResult,
    ReportMeta,
)

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/feed", response_model=list[NewsItem])
async def feed(
    limit: int = 60, theme: str | None = None, source_prefix: str | None = None
) -> list[dict]:
    """最近新闻条目（可按 theme=ai/chips/... 过滤；source_prefix='X·' 取推特源）。"""
    return await run_in_threadpool(service.recent_items, limit, theme, source_prefix)


@router.post("/refresh", response_model=RefreshResult)
async def refresh() -> dict:
    """手动抓取所有信源并落库（容忍单源失败）。"""
    return await run_in_threadpool(service.refresh)


@router.get("/for", response_model=list[NewsItem])
async def news_for(symbol: str, limit: int = 20) -> list[dict]:
    """与某标的（MARKET:CODE）相关的新闻（标题里出现公司名）。"""
    return await run_in_threadpool(service.news_for_symbol, symbol, limit)


@router.get("/official", response_model=list[Filing])
async def official(symbol: str, limit: int = 15) -> list[dict]:
    """某标的的官方一手文件（美股＝SEC EDGAR 申报；6h 缓存，失败降级空表）。"""
    return await run_in_threadpool(service.stock_official, symbol, limit)


@router.get("/reports", response_model=list[ReportMeta])
async def reports(limit: int = 30) -> list[dict]:
    """日报列表（按日期倒序，带预览）。"""
    return await run_in_threadpool(service.list_reports, limit)


@router.get("/report", response_model=NewsReport)
async def report(date: str | None = None) -> dict:
    """某日（默认最新）趋势日报全文。"""
    data = await run_in_threadpool(service.get_report, date)
    if data is None:
        raise HTTPException(status_code=404, detail="暂无日报，先 POST /news/report/generate 生成")
    return data


@router.get("/opportunities", response_model=OpportunitiesResponse)
async def opportunities(date: str | None = None) -> dict:
    """某日（默认今天）已生成的投资机会列表（接地后含关联个股）。"""
    data = await run_in_threadpool(service.get_opportunities, date)
    if data is None:
        raise HTTPException(status_code=404, detail="暂无今日机会，先生成")
    return data


@router.post("/opportunities/generate", response_model=OpportunitiesResponse)
async def generate_opportunities(date: str | None = None) -> dict:
    """从当日新闻抽取投资机会 + 接地到 MARKET:CODE（阻塞，约 20–40s）。落库覆盖当天。"""
    try:
        gateway.check_ready("summarize")
    except gateway.LLMNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return await run_in_threadpool(service.generate_opportunities, date)


@router.get("/clusters", response_model=ClustersResponse)
async def clusters(theme: str | None = None, date: str | None = None) -> dict:
    """某日（默认今天）某主题（默认全部）的新闻要点（去重聚类+重要性排序）。无 → 404。"""
    data = await run_in_threadpool(service.get_clusters, date, theme)
    if data is None:
        raise HTTPException(status_code=404, detail="暂无要点，先生成")
    return data


@router.post("/clusters/generate", response_model=ClustersResponse)
async def generate_clusters(theme: str | None = None, date: str | None = None) -> dict:
    """生成新闻要点：LLM 去重聚类+按投资重要性排序（阻塞，约 20–40s）。落库覆盖。"""
    try:
        gateway.check_ready("summarize")
    except gateway.LLMNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return await run_in_threadpool(service.generate_clusters, date, theme)


@router.post("/report/generate")
async def generate(date: str | None = None) -> StreamingResponse:
    """生成当日趋势日报：SSE 流式产出，完成后落库（覆盖当天）。"""
    try:
        gateway.check_ready("summarize")
    except gateway.LLMNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    def sse():  # 同步生成器：Starlette 在 threadpool 里迭代（与 /llm/chat 一致）
        try:
            for delta in service.generate_report_stream(date):
                yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:  # noqa: BLE001 — 流中途出错也要让前端收到
            err = json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)
            yield f"data: {err}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")
