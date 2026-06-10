"""templates 域 HTTP 路由：Prompt 模板 CRUD。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from . import service
from .schemas import Template, TemplateCreate, TemplatePatch

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[Template])
async def list_templates() -> list[dict]:
    return await run_in_threadpool(service.list_templates)


@router.post("", response_model=Template)
async def create_template(body: TemplateCreate) -> dict:
    return await run_in_threadpool(service.create_template, body.name, body.body)


@router.patch("/{template_id}", response_model=Template)
async def update_template(template_id: int, body: TemplatePatch) -> dict:
    try:
        return await run_in_threadpool(
            service.update_template, template_id, body.name, body.body
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/{template_id}")
async def delete_template(template_id: int) -> dict:
    try:
        await run_in_threadpool(service.delete_template, template_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"ok": True}
