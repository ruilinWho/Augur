"""llm 域 HTTP 路由：角色状态 + 流式对话（SSE）。"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from . import gateway
from .schemas import ChatRequest, RoleStatus

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/roles", response_model=list[RoleStatus])
async def roles() -> list[dict]:
    return gateway.roles_status()


@router.post("/chat")
async def chat(body: ChatRequest) -> StreamingResponse:
    try:
        gateway.check_ready(body.role)
    except gateway.LLMNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    messages = [m.model_dump() for m in body.messages]

    def sse():  # 同步生成器：Starlette 会在 threadpool 里迭代
        try:
            for delta in gateway.stream_chat(messages, body.role):
                yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:  # noqa: BLE001 — 流中途出错也要让前端收到
            err = json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)
            yield f"data: {err}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")
