"""反证雷达域的 Pydantic 模型（API 契约）。"""

from __future__ import annotations

from pydantic import BaseModel


class SourceRef(BaseModel):
    """一条告警背后的原始新闻链接（可点回核对）。"""

    source: str = ""
    url: str = ""


class Condition(BaseModel):
    """一条证伪条件（作者授权，可 AI 起草）。"""

    id: int
    text: str = ""


class Alert(BaseModel):
    """扫描产出的一条信号：某证伪条件被新闻反证 / 印证。"""

    condition_id: int
    polarity: str = "refute"  # refute 反证（条件正在发生）/ support 印证（条件明确未发生）
    summary: str = ""
    refs: list[SourceRef] = []


class Thesis(BaseModel):
    id: int
    symbol: str  # MARKET:CODE
    name: str = ""  # 展示名（读时计算）
    market: str = ""
    stance: str = "bull"  # bull看多 / bear看空 / watch观望
    thesis: str = ""  # 一句话立论
    conditions: list[Condition] = []
    alerts: list[Alert] = []  # 扫描滚动重算
    status: str = "active"  # active / closed
    last_scanned_at: str | None = None
    created_at: str
    updated_at: str


class ThesisCreate(BaseModel):
    symbol: str
    stance: str = "bull"
    thesis: str = ""
    conditions: list[str] = []  # 作者传纯文本，service 分配稳定 id


class ThesisUpdate(BaseModel):
    stance: str | None = None
    thesis: str | None = None
    conditions: list[str] | None = None  # 改了条件 → 旧告警作废，待重扫
    status: str | None = None


class ThesisDraft(BaseModel):
    """AI 起草草稿（不落库，作者审阅修改后再保存）。"""

    stance: str = "bull"
    thesis: str = ""
    conditions: list[str] = []
