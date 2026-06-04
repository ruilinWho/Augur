"""notes 域 Pydantic 模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class NoteMeta(BaseModel):
    """列表项（不含全文，带预览）。"""

    id: int
    title: str = ""
    preview: str = ""  # 正文前若干字
    pinned: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class Note(BaseModel):
    """单篇全文。"""

    id: int
    title: str = ""
    body: str = ""
    pinned: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class NoteCreate(BaseModel):
    title: str = Field(default="", max_length=200)
    body: str = ""


class NotePatch(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    body: str | None = None
    pinned: bool | None = None
