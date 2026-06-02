"""watchlist 域 HTTP 路由。SQLite（同步）调用走 threadpool。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from . import service
from .schemas import (
    ItemCreate,
    ItemMove,
    ItemOut,
    ReorderRequest,
    SectionCreate,
    SectionOut,
    SectionRename,
)

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("/sections", response_model=list[SectionOut])
async def list_sections(market: str | None = None) -> list[dict]:
    return await run_in_threadpool(service.list_tree, market)


@router.post("/sections", response_model=SectionOut, status_code=201)
async def create_section(body: SectionCreate) -> dict:
    try:
        return await run_in_threadpool(service.create_section, body.name, body.parent_id)
    except service.DepthError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except service.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/sections/{section_id}", status_code=204)
async def rename_section(section_id: int, body: SectionRename) -> None:
    try:
        await run_in_threadpool(service.rename_section, section_id, body.name)
    except service.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except service.Duplicate as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.delete("/sections/{section_id}", status_code=204)
async def delete_section(section_id: int) -> None:
    try:
        await run_in_threadpool(service.delete_section, section_id)
    except service.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/sections/{section_id}/items", response_model=ItemOut, status_code=201)
async def add_item(section_id: int, body: ItemCreate) -> dict:
    try:
        return await run_in_threadpool(service.add_item, section_id, body.symbol, body.note)
    except service.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.patch("/items/{item_id}", response_model=ItemOut)
async def move_item(item_id: int, body: ItemMove) -> dict:
    try:
        return await run_in_threadpool(service.move_item, item_id, body.section_id)
    except service.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.delete("/items/{item_id}", status_code=204)
async def remove_item(item_id: int) -> None:
    try:
        await run_in_threadpool(service.remove_item, item_id)
    except service.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/reorder", status_code=204)
async def reorder(body: ReorderRequest) -> None:
    try:
        await run_in_threadpool(service.reorder, body.kind, body.ordered_ids)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
