"""discovery 域 HTTP 路由（「寻」）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from . import service
from .schemas import Candidate, StatusPatch

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.get("", response_model=list[Candidate])
async def list_candidates(status: str = "new", limit: int = 100) -> list[dict]:
    """候选标的列表（默认 status=new，提及次数降序）。"""
    return await run_in_threadpool(service.list_candidates, status, limit)


@router.post("/refresh")
async def refresh() -> dict:
    """重算候选池（聚合自选外的 LLM 标股，零新增 LLM 成本）。"""
    return await run_in_threadpool(service.refresh)


@router.patch("/{market}/{code}", response_model=Candidate)
async def set_status(market: str, code: str, body: StatusPatch) -> dict:
    """改候选状态（new/dismissed/promoted）。symbol 拆成 market/code 走路径避免冒号转义。"""
    try:
        return await run_in_threadpool(service.set_status, f"{market}:{code}", body.status)
    except ValueError as e:
        # 状态非法 → 400；候选不存在 → 404
        code_ = 404 if "不存在" in str(e) else 400
        raise HTTPException(status_code=code_, detail=str(e)) from e
