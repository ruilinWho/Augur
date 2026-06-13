"""notes 域 HTTP 路由（第 4 支柱「记」）：一级文件夹 + 自由长文笔记 CRUD。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from . import service
from .schemas import (
    Folder,
    FolderCreate,
    FolderPatch,
    Note,
    NoteCreate,
    NoteMeta,
    NoteMove,
    NotePatch,
)

router = APIRouter(prefix="/notes", tags=["notes"])


# ───────────────────────── 文件夹（一级目录）─────────────────────────
# 注：/folders 静态路由必须在 /{note_id} 动态段之前声明，否则会被动态段抢匹配。
@router.get("/folders", response_model=list[Folder])
async def list_folders() -> list[dict]:
    """全部文件夹（按 sort_order）+ 各自笔记数。"""
    return await run_in_threadpool(service.list_folders)


@router.post("/folders", response_model=Folder)
async def create_folder(body: FolderCreate) -> dict:
    return await run_in_threadpool(service.create_folder, body.name)


@router.patch("/folders/{folder_id}", response_model=Folder)
async def rename_folder(folder_id: int, body: FolderPatch) -> dict:
    try:
        return await run_in_threadpool(service.rename_folder, folder_id, body.name or "")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: int) -> dict:
    """删文件夹；其下笔记回「未归类」（不删笔记）。"""
    try:
        await run_in_threadpool(service.delete_folder, folder_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"ok": True}


# ───────────────────────── 笔记 ─────────────────────────
@router.get("", response_model=list[NoteMeta])
async def list_notes() -> list[dict]:
    """全部笔记（置顶在前、再按更新时间倒序），带预览与 folder_id。"""
    return await run_in_threadpool(service.list_notes)


@router.post("", response_model=Note)
async def create_note(body: NoteCreate) -> dict:
    return await run_in_threadpool(service.create_note, body.title, body.body, body.folder_id)


@router.get("/{note_id}", response_model=Note)
async def get_note(note_id: int) -> dict:
    data = await run_in_threadpool(service.get_note, note_id)
    if data is None:
        raise HTTPException(status_code=404, detail="笔记不存在")
    return data


@router.patch("/{note_id}", response_model=Note)
async def update_note(note_id: int, body: NotePatch) -> dict:
    try:
        return await run_in_threadpool(
            service.update_note, note_id, body.title, body.body, body.pinned
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/{note_id}/folder", response_model=Note)
async def move_note(note_id: int, body: NoteMove) -> dict:
    """把笔记移到某文件夹（folder_id=null → 未归类）。"""
    try:
        return await run_in_threadpool(service.move_note, note_id, body.folder_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/{note_id}")
async def delete_note(note_id: int) -> dict:
    try:
        await run_in_threadpool(service.delete_note, note_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"ok": True}
