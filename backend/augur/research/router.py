"""research 域 HTTP 路由（M2「研」）：单股深度研究——持久化报告 + SSE 流式生成。"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

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
