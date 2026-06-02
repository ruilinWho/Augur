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
