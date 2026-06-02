"""news 域 Pydantic 模型（M3「知」）。"""

from __future__ import annotations

from pydantic import BaseModel


class NewsItem(BaseModel):
    id: int
    source: str
    title: str
    url: str
    summary: str = ""
    lang: str = ""
    category: str = ""
    published_at: str | None = None
    theme: str = ""  # 主题主类（ai/chips/robotics/space/tech/markets/crypto/world/other）
    topics: list[str] = []  # 细标签（多值）
    title_zh: str | None = None  # 中文标题（cheap 翻译；None=未翻，前端回退原文）


class Filing(BaseModel):
    """个股官方一手文件（SEC EDGAR 申报）。标题/事项已给中文标签。"""

    form: str  # 8-K / 10-Q / 10-K / DEF 14A …
    title: str  # 「重大事件（8-K） · 经营成果与财务状况（财报）」
    url: str
    summary: str = ""  # 8-K 事项中文（如有）
    filed_at: str | None = None  # 'YYYY-MM-DD'


class NewsReport(BaseModel):
    report_date: str  # 'YYYY-MM-DD'
    body: str
    model: str = ""
    item_count: int = 0
    created_at: str | None = None


class ReportMeta(BaseModel):
    """日报列表项（不含全文，带摘要预览）。"""

    report_date: str
    item_count: int = 0
    model: str = ""
    created_at: str | None = None
    preview: str = ""


class RefreshResult(BaseModel):
    fetched: int  # 本次抓到的条目总数（含重复）
    inserted: int  # 实际新增（去重后）
    sources_ok: int
    sources_failed: int
    failures: list[str] = []  # 失败的信源名
    translated: int = 0  # 本次翻译成中文的标题数
    filtered: dict = {}  # 投资相关性过滤：{judged, dropped}


# ───────────────────────── 今日投资机会（接地后对外形状）─────────────────────────
class RelatedSymbol(BaseModel):
    symbol: str | None = None  # MARKET:CODE；未解析为 None（防编造，只信本地索引命中）
    name: str
    market: str
    resolved: bool = False
    in_watchlist: bool = False
    sections: list[str] = []  # 若已关注，所属分区路径，如 半导体/GPU


class Evidence(BaseModel):
    news_id: int | None = None
    title: str
    source: str
    url: str | None = None


class Opportunity(BaseModel):
    title: str
    thesis: str = ""
    theme: str = ""
    confidence: str = "low"  # low/med/high
    caveats: str = ""
    related: list[RelatedSymbol] = []
    evidence: list[Evidence] = []


class OpportunitiesResponse(BaseModel):
    report_date: str
    model: str = ""
    item_count: int = 0
    created_at: str | None = None
    disclaimer: str = "研究辅助，非投资建议；基于所列新闻，可能有误，请回看原文核实。"
    opportunities: list[Opportunity] = []
