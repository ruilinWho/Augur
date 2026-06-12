"""news 域 Pydantic 模型（M3「知」）。"""

from __future__ import annotations

from pydantic import BaseModel


class LinkedSymbol(BaseModel):
    symbol: str  # MARKET:CODE
    name: str = ""


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
    symbols: list[LinkedSymbol] = []  # 挂钩的自选股 ticker（linker.py，确定性接地）


class SourceRef(BaseModel):
    """一条要点背后的原始链接（像新闻一样可点回看）。"""

    source: str = ""
    url: str = ""


class CitedPoint(BaseModel):
    """带原始链接引用的要点（说人话 + 可溯源）。"""

    text: str = ""
    refs: list[SourceRef] = []


class StockNewsBrief(BaseModel):
    symbol: str
    summary: str = ""
    points: list[CitedPoint] = []
    risks: list[CitedPoint] = []
    source_count: int = 0
    generated_at: str | None = None


class StockSocialHeat(BaseModel):
    symbol: str
    configured: bool = False
    status: str = ""
    summary: str = ""
    sentiment: str = "不明"
    heat: str = "低"
    bull_points: list[CitedPoint] = []
    bear_points: list[CitedPoint] = []
    watch: list[CitedPoint] = []
    source_count: int = 0
    platforms: dict[str, int] = {}
    generated_at: str | None = None


class Filing(BaseModel):
    """个股官方一手文件（SEC EDGAR 申报）。标题/事项已给中文标签。"""

    form: str  # 8-K / 10-Q / 10-K / DEF 14A …
    title: str  # 「重大事件（8-K） · 经营成果与财务状况（财报）」
    url: str
    summary: str = ""  # 8-K 事项中文（如有）
    filed_at: str | None = None  # 'YYYY-MM-DD'


class DisclosureEvent(BaseModel):
    """公司披露层事件：财报/SEC/电话会/IR 材料等一手或准一手事实源。"""

    id: str
    kind: str  # filing / transcript / financial_period
    date: str = ""  # 披露日；financial_period 兜底为期末日
    title: str = ""
    source: str = ""
    url: str = ""
    summary: str = ""
    importance: str = "high"
    form: str = ""
    period: str = ""
    year: int | None = None
    quarter: int | None = None


class StockDisclosures(BaseModel):
    symbol: str
    configured: dict[str, bool] = {}
    events: list[DisclosureEvent] = []
    generated_at: str | None = None


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


class NewsReadState(BaseModel):
    last_read_at: str | None = None
    fresh_count: int = 0


# ───────────────────────── 今日投资机会（接地后对外形状）─────────────────────────
class RelatedSymbol(BaseModel):
    symbol: str | None = None  # MARKET:CODE；未解析为 None（防编造，只信本地索引命中）
    name: str
    market: str
    resolved: bool = False
    in_watchlist: bool = False
    sections: list[str] = []  # 若已关注，所属分区路径，如 半导体/GPU


# ───────────────────────── 结构化综合日报（卡片化、分点、个股挂钩）─────────────────────────
class ReportSection(BaseModel):
    """日报的一个主题卡：重要性徽章 + 小标题 + 为什么重要 + 分点 + 关联标的（看/研 chip）。"""

    headline: str
    importance: str = "med"  # high/med/low → 非常重要/重要/留意
    why: str = ""
    points: list[CitedPoint] = []
    related: list[RelatedSymbol] = []


class NewsReport(BaseModel):
    """结构化综合日报：总判断 + 主题卡 + 风险/反证 + 明天继续看。markdown 仅为旧报告兜底渲染。"""

    report_date: str  # 'YYYY-MM-DD'
    verdict: str = ""  # 总判断（开篇 2–4 句）
    sections: list[ReportSection] = []
    risks: list[CitedPoint] = []  # 风险 / 反证
    watch: list[CitedPoint] = []  # 明天继续看
    markdown: str = ""  # 旧版 markdown 全文（结构化缺失时前端回退渲染）
    model: str = ""
    item_count: int = 0
    created_at: str | None = None


# ───────────────────────── 自选分区级日报（按一级分区切片、逐股异动）─────────────────────────
class SectionMover(BaseModel):
    """分区里某只今日有动静的票：重要性 + 一句话发生了什么 + 分点（可点引用）。看/研 可点。"""

    symbol: str  # MARKET:CODE（必为该分区自选股之一，确定性，不让 LLM 编）
    name: str = ""
    market: str = ""
    sub: str = ""  # 所属二级板块名（若挂在二级下），否则空
    importance: str = "med"  # critical/high/med/low → 非常重要/重要/留意/次要
    headline: str = ""  # 一句话：这只票今天发生了什么
    points: list[CitedPoint] = []


class SectionBoard(BaseModel):
    """一个一级分区的当日板块卡：板块脉搏 + 逐股异动 + 安静（无动静）的票。"""

    section_id: int
    section_name: str = ""
    sort_order: int = 0
    pulse: str = ""  # 板块脉搏（1–2 句共同主线；无则空）
    importance: str = "low"  # 聚合重要性（= 最热 mover），供徽章/排序
    movers: list[SectionMover] = []
    quiet: list[str] = []  # 今日无明显动静的票（展示名），低噪音页脚
    item_count: int = 0


class SectionReportsResponse(BaseModel):
    """某日全部一级分区的板块卡（按 有动静→重要性→分区顺序 排好）。boards 空＝当日未生成。"""

    report_date: str
    boards: list[SectionBoard] = []
    model: str = ""
    created_at: str | None = None


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
    disclaimer: str = "决策级研究材料；基于所列新闻，可能有误，请回看原文核实。"
    opportunities: list[Opportunity] = []


class ClusterMember(BaseModel):
    source: str = ""
    title: str = ""
    url: str = ""


class NewsCluster(BaseModel):
    headline: str
    importance: str = "med"  # high/med/low
    why: str = ""
    members: list[ClusterMember] = []


class ClustersResponse(BaseModel):
    report_date: str
    scope: str = ""
    days: int = 1
    model: str = ""
    item_count: int = 0
    created_at: str | None = None
    clusters: list[NewsCluster] = []
