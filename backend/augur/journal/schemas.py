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


class ReflectionRef(BaseModel):
    source: str = ""
    title: str = ""
    url: str = ""


class ReflectionAssessment(BaseModel):
    verdict: str = "尚未检验"  # 印证 / 证伪 / 混合 / 尚未检验
    confidence: str = "low"  # low / med / high
    text: str = ""
    price: str = ""
    refs: list[ReflectionRef] = []


class ReflectionEvent(BaseModel):
    id: str
    kind: str  # journal / news / disclosure
    date: str
    title: str
    headline: str = ""  # 披露：LLM 具体标题（前端优先于 title 显示）
    insight: str = ""  # 披露：1-2 句投资洞察
    impact: str = ""  # 披露：利好/利空/中性/存疑
    confidence: str = ""  # 披露：high/med/low
    body: str = ""
    importance: str = "med"
    journal_id: int | None = None
    refs: list[ReflectionRef] = []
    assessment: ReflectionAssessment | None = None


class ReflectionTimeline(BaseModel):
    symbol: str
    name: str = ""
    summary: str = ""
    events: list[ReflectionEvent] = []
    model: str = ""
    journal_count: int = 0
    news_count: int = 0
    created_at: str | None = None
