"""notes 域 Pydantic 模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Folder(BaseModel):
    """一级文件夹（目录）+ 笔记计数。"""

    id: int
    name: str = ""
    sort_order: int = 0
    note_count: int = 0
    created_at: str | None = None


class FolderCreate(BaseModel):
    name: str = Field(default="", max_length=100)


class FolderPatch(BaseModel):
    name: str | None = Field(default=None, max_length=100)


class NoteMeta(BaseModel):
    """列表项（不含全文，带预览）。"""

    id: int
    folder_id: int | None = None  # 归属文件夹；None=未归类
    title: str = ""
    preview: str = ""  # 正文前若干字
    pinned: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class Note(BaseModel):
    """单篇全文。"""

    id: int
    folder_id: int | None = None
    title: str = ""
    body: str = ""
    pinned: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class NoteCreate(BaseModel):
    title: str = Field(default="", max_length=200)
    body: str = ""
    folder_id: int | None = None  # 新建时归到某文件夹（如当前选中）


class NotePatch(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    body: str | None = None
    pinned: bool | None = None


class NoteMove(BaseModel):
    """移动归属——显式字段，区别于 NotePatch 的 None=不改语义。"""

    folder_id: int | None = None  # 目标文件夹；None=移到未归类
