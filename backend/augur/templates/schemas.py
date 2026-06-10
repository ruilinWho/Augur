"""templates 域 Pydantic 模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Template(BaseModel):
    id: int
    name: str = ""
    body: str = ""
    sort_order: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class TemplateCreate(BaseModel):
    name: str = Field(default="", max_length=120)
    body: str = ""


class TemplatePatch(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    body: str | None = None
