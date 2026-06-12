"""判断日记 HTTP 路由。SQLite（同步）调用走 threadpool。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from ..llm import gateway
from . import service
from .schemas import JournalCreate, JournalEntry, JournalUpdate, ReflectionTimeline

router = APIRouter(prefix="/journal", tags=["journal"])


@router.get("/entries", response_model=list[JournalEntry])
async def list_entries(symbol: str) -> list[dict]:
    try:
        return await run_in_threadpool(service.list_entries, symbol)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/reflection", response_model=ReflectionTimeline)
async def reflection(symbol: str) -> dict:
    """某股已生成的综合认知；暂无 → 404。"""
    try:
        data = await run_in_threadpool(service.get_reflection_timeline, symbol)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if data is None:
        raise HTTPException(status_code=404, detail="暂无综合认知")
    return data


@router.post("/reflection/generate", response_model=ReflectionTimeline)
async def reflection_generate(symbol: str) -> dict:
    """生成/重生成某股综合认知：个人判断 + 重大资讯/披露 + LLM 反馈。"""
    try:
        return await run_in_threadpool(service.generate_reflection_timeline, symbol)
    except gateway.LLMNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/entries", response_model=JournalEntry, status_code=201)
async def create_entry(body: JournalCreate) -> dict:
    try:
        return await run_in_threadpool(
            service.create_entry, body.symbol, body.entry_date, body.body
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.patch("/entries/{entry_id}", response_model=JournalEntry)
async def update_entry(entry_id: int, body: JournalUpdate) -> dict:
    try:
        return await run_in_threadpool(service.update_entry, entry_id, body.entry_date, body.body)
    except service.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.delete("/entries/{entry_id}", status_code=204)
async def delete_entry(entry_id: int) -> None:
    try:
        await run_in_threadpool(service.delete_entry, entry_id)
    except service.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
