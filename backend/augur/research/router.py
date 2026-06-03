"""research 域 HTTP 路由（M2「研」）：单股深度研究——持久化报告 + SSE 流式生成。"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..llm import gateway
from . import service
from .schemas import ResearchReport

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/stock", response_model=ResearchReport)
async def get_report(symbol: str) -> dict:
    """某标的已生成的深度研究报告（含引用源）。无 → 404。"""
    data = await run_in_threadpool(service.get_report, symbol)
    if data is None:
        raise HTTPException(status_code=404, detail="暂无研究报告，先生成")
    return data


@router.post("/stock/generate")
async def generate(symbol: str) -> StreamingResponse:
    """生成某标的深度研究：SSE 流式产出 Markdown，完成后落库（覆盖）。"""
    try:
        gateway.check_ready("deep_research")
    except gateway.LLMNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    def sse():  # 同步生成器：Starlette 在 threadpool 里迭代（与 /news、/llm 一致）
        try:
            for delta in service.generate_stream(symbol):
                yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:  # noqa: BLE001 — 流中途出错也要让前端收到
            err = json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)
            yield f"data: {err}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")


# ───────────────────────── 导入研报（他人写的 markdown，一股可多份）─────────────────────────
@router.get("/imported")
async def list_imported(symbol: str) -> list[dict]:
    """某股的导入研报列表（按拖拽顺序）。"""
    return await run_in_threadpool(service.list_imported, symbol)


class _ImportIn(BaseModel):
    symbol: str
    title: str = ""
    body: str = ""


@router.post("/imported")
async def add_imported(body: _ImportIn) -> dict:
    """导入一份研报（粘贴 markdown）。"""
    try:
        return await run_in_threadpool(service.add_imported, body.symbol, body.title, body.body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class _ImportPatch(BaseModel):
    title: str | None = None
    body: str | None = None
    comment: str | None = None


@router.patch("/imported/{report_id}")
async def update_imported(report_id: int, body: _ImportPatch) -> dict:
    """改某份研报的标题/正文/评论。"""
    try:
        return await run_in_threadpool(
            service.update_imported, report_id, body.title, body.body, body.comment
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
