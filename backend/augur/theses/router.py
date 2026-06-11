"""反证雷达 HTTP 路由。SQLite（同步）调用走 threadpool。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from ..llm import gateway
from . import service
from .schemas import Thesis, ThesisCreate, ThesisDraft, ThesisUpdate

router = APIRouter(prefix="/theses", tags=["theses"])


@router.get("", response_model=list[Thesis])
async def list_theses(symbol: str | None = None, status: str = "active") -> list[dict]:
    """立论列表（默认仅 active，有反证的排前）。symbol 给定则只列该股。"""
    try:
        return await run_in_threadpool(service.list_theses, symbol, status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/flags")
async def flags() -> dict[str, str]:
    """symbol → 最严重告警极性（refute/support）。供分区/看 inline 徽章，零成本读。"""
    return await run_in_threadpool(service.thesis_flags)


@router.post("", response_model=Thesis, status_code=201)
async def create_thesis(body: ThesisCreate) -> dict:
    try:
        return await run_in_threadpool(
            service.create_thesis, body.symbol, body.stance, body.thesis, body.conditions
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/draft", response_model=ThesisDraft)
async def draft_thesis(symbol: str) -> dict:
    """AI 起草 stance/thesis/证伪条件（不落库；作者审阅修改后再保存）。"""
    try:
        return await run_in_threadpool(service.draft_thesis, symbol)
    except gateway.LLMNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/scan", response_model=list[Thesis])
async def scan(status: str = "active") -> list[dict]:
    """立即扫描全部 active 立论（每个并行判反证/印证，约 20–60s），返回更新后的列表。"""
    await run_in_threadpool(service.scan_all)
    return await run_in_threadpool(service.list_theses, None, status)


@router.patch("/{thesis_id}", response_model=Thesis)
async def update_thesis(thesis_id: int, body: ThesisUpdate) -> dict:
    try:
        return await run_in_threadpool(
            service.update_thesis, thesis_id, body.stance, body.thesis, body.conditions, body.status
        )
    except service.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.delete("/{thesis_id}", status_code=204)
async def delete_thesis(thesis_id: int) -> None:
    try:
        await run_in_threadpool(service.delete_thesis, thesis_id)
    except service.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
