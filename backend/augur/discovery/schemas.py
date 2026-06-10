"""discovery 域 Pydantic 模型。"""

from __future__ import annotations

from pydantic import BaseModel


class DiscoveryEvidence(BaseModel):
    news_id: int
    title: str = ""
    source: str = ""
    url: str = ""
    date: str = ""


class Candidate(BaseModel):
    symbol: str
    name: str = ""
    market: str = ""
    mention_count: int = 0
    day_span: int = 0
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    evidence: list[DiscoveryEvidence] = []
    status: str = "new"


class StatusPatch(BaseModel):
    status: str  # new / dismissed / promoted
