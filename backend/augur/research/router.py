"""research 域 HTTP 路由（M2「研」）：导入研报 CRUD + 排序。

深度研究生成已移除——「研」改走外部网页 Deep Research + 导入回流（ADR-0011/0014/0016）。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from . import service

router = APIRouter(prefix="/research", tags=["research"])


# ───────────────────────── 导入研报（他人写的 markdown，一股可多份）─────────────────────────
@router.get("/imported")
async def list_imported(symbol: str) -> list[dict]:
    """某股的导入研报列表（按拖拽顺序）。"""
    return await run_in_threadpool(service.list_imported, symbol)


class _ImportIn(BaseModel):
    symbol: str
    title: str = ""
    body: str = ""
    engine: str = ""  # 网页 Deep Research 回流标注：chatgpt/claude/gemini/other
    source_url: str = ""


@router.post("/imported")
async def add_imported(body: _ImportIn) -> dict:
    """导入一份研报（粘贴 markdown）；engine/source_url 标注网页回流来源。"""
    try:
        return await run_in_threadpool(
            service.add_imported, body.symbol, body.title, body.body, body.engine, body.source_url
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class _ImportPatch(BaseModel):
    title: str | None = None
    body: str | None = None
    comment: str | None = None
    engine: str | None = None
    source_url: str | None = None


@router.patch("/imported/{report_id}")
async def update_imported(report_id: int, body: _ImportPatch) -> dict:
    """改某份研报的标题/正文/评论/来源。"""
    try:
        return await run_in_threadpool(
            service.update_imported,
            report_id,
            body.title,
            body.body,
            body.comment,
            body.engine,
            body.source_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/imported/{report_id}")
async def delete_imported(report_id: int) -> dict:
    try:
        await run_in_threadpool(service.delete_imported, report_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"ok": True}


class _ReorderIn(BaseModel):
    ordered_ids: list[int]


@router.post("/imported/reorder")
async def reorder_imported(body: _ReorderIn) -> dict:
    await run_in_threadpool(service.reorder_imported, body.ordered_ids)
    return {"ok": True}
