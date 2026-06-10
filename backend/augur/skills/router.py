"""skills 域 HTTP 路由：可插拔投研技能。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from . import service
from .schemas import EnablePatch, Skill, SkillMeta

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("", response_model=list[SkillMeta])
async def list_skills(surface: str | None = None, enabled: bool = False) -> list[dict]:
    """技能列表（可按 surface 过滤、enabled=true 只看已启用）。"""
    return await run_in_threadpool(service.list_skills, surface, enabled)


@router.get("/scorecard/template")
async def scorecard_template() -> dict:
    """卡点评分卡输入模板。"""
    return await run_in_threadpool(service.scorecard_template)


@router.post("/scorecard")
async def run_scorecard(payload: dict[str, Any]) -> dict:
    """跑卡点评分卡（8 因子加权 − 惩罚 → 0-100 + 分级）。"""
    try:
        return await run_in_threadpool(service.run_scorecard, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{slug}", response_model=Skill)
async def get_skill(slug: str) -> dict:
    data = await run_in_threadpool(service.get_skill, slug)
    if data is None:
        raise HTTPException(status_code=404, detail="技能不存在")
    return data


@router.get("/{slug}/render")
async def render_skill(slug: str, symbol: str) -> dict:
    """按当前标的填充技能正文占位符（供「研·复制 Prompt」）。"""
    try:
        return await run_in_threadpool(service.render, slug, symbol)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{slug}/enable", response_model=Skill)
async def set_enabled(slug: str, body: EnablePatch) -> dict:
    try:
        return await run_in_threadpool(service.set_enabled, slug, body.enabled)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
