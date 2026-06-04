"""notes 域 HTTP 路由（第 4 支柱「记」）：自由长文笔记 CRUD。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from . import service
from .schemas import Note, NoteCreate, NoteMeta, NotePatch

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("", response_model=list[NoteMeta])
async def list_notes() -> list[dict]:
    """全部笔记（置顶在前、再按更新时间倒序），带预览。"""
    return await run_in_threadpool(service.list_notes)


@router.get("/{note_id}", response_model=Note)
async def get_note(note_id: int) -> dict:
    data = await run_in_threadpool(service.get_note, note_id)
    if data is None:
        raise HTTPException(status_code=404, detail="笔记不存在")
    return data


@router.post("", response_model=Note)
async def create_note(body: NoteCreate) -> dict:
    return await run_in_threadpool(service.create_note, body.title, body.body)


@router.patch("/{note_id}", response_model=Note)
async def update_note(note_id: int, body: NotePatch) -> dict:
    try:
        return await run_in_threadpool(
            service.update_note, note_id, body.title, body.body, body.pinned
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/{note_id}")
async def delete_note(note_id: int) -> dict:
    try:
        await run_in_threadpool(service.delete_note, note_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"ok": True}
