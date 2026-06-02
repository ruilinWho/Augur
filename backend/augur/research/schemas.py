"""research 域 Pydantic 模型（M2「研」）。"""

from __future__ import annotations

from pydantic import BaseModel


class ResearchSource(BaseModel):
    n: int
    title: str
    source: str = ""
    url: str | None = None


class ResearchReport(BaseModel):
    symbol: str
    name: str = ""
    body: str
    sources: list[ResearchSource] = []
    model: str = ""
    created_at: str | None = None
