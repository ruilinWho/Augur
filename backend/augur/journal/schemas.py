"""判断日记的 Pydantic 模型（API 契约）。"""

from __future__ import annotations

from pydantic import BaseModel


class JournalEntry(BaseModel):
    id: int
    symbol: str
    entry_date: str  # 'YYYY-MM-DD'
    body: str
    created_at: str
    updated_at: str


class JournalCreate(BaseModel):
    symbol: str
    entry_date: str
    body: str = ""


class JournalUpdate(BaseModel):
    entry_date: str | None = None
    body: str | None = None
