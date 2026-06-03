"""判断日记 HTTP 路由。SQLite（同步）调用走 threadpool。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from . import service
from .schemas import JournalCreate, JournalEntry, JournalUpdate

router = APIRouter(prefix="/journal", tags=["journal"])


@router.get("/entries", response_model=list[JournalEntry])
async def list_entries(symbol: str) -> list[dict]:
    try:
        return await run_in_threadpool(service.list_entries, symbol)
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
