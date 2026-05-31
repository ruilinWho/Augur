"""watchlist 域的 Pydantic 模型（API 契约）。两级板块见 CLAUDE.md §8。"""

from __future__ import annotations

from pydantic import BaseModel


class ItemOut(BaseModel):
    id: int
    symbol: str  # MARKET:CODE
    note: str
    sort_order: int


class SectionOut(BaseModel):
    id: int
    name: str
    parent_id: int | None
    sort_order: int
    items: list[ItemOut] = []
    children: list[SectionOut] = []  # 仅一级板块有；二级恒为空（depth ≤ 2）


class SectionCreate(BaseModel):
    name: str
    parent_id: int | None = None


class SectionRename(BaseModel):
    name: str


class ItemCreate(BaseModel):
    symbol: str
    note: str = ""


class ReorderRequest(BaseModel):
    kind: str  # "section" | "item"
    ordered_ids: list[int]


SectionOut.model_rebuild()
