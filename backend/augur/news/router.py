"""news 域 HTTP 路由（M3「知」）：信息流 / 结构化综合日报。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from ..llm import gateway
from . import ingest, linker, service, stock_sources
from .schemas import (
    ClustersResponse,
    Filing,
    NewsItem,
    NewsReadState,
    NewsReport,
    OpportunitiesResponse,
    RefreshResult,
    ReportMeta,
    SectionReportsResponse,
    StockNewsBrief,
    StockSocialHeat,
)

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/feed", response_model=list[NewsItem])
async def feed(
    limit: int = 60,
    theme: str | None = None,
    source_prefix: str | None = None,
    category: str | None = None,
    days: int | None = None,
    day: str | None = None,
) -> list[dict]:
    """最近新闻条目（theme 过滤 · source_prefix='X·' 取推特 · days 近 N 天 · day 取某一天）。"""
    return await run_in_threadpool(
        service.recent_items, limit, theme, source_prefix, category, days, day
    )


@router.post("/refresh", response_model=RefreshResult)
async def refresh() -> dict:
    """手动抓取所有信源并落库（容忍单源失败）。"""
    return await run_in_threadpool(service.refresh)


@router.get("/read-state", response_model=NewsReadState)
async def read_state() -> dict:
    """信息流已读基准与新增计数。刷新任务会自动推进基准。"""
    return await run_in_threadpool(service.news_read_state)


@router.get("/source-health")
async def source_health() -> list[dict]:
    """各信源健康度（成功/失败次数、最近条数、最近成功时间）——纯统计。"""
    return await run_in_threadpool(ingest.source_health)


@router.post("/relink")
async def relink() -> dict:
    """重挂全部新闻↔自选股 ticker（自选变动后用；确定性、零幻觉）。"""
    return await run_in_threadpool(linker.relink_all)


@router.get("/for", response_model=list[NewsItem])
async def news_for(symbol: str, limit: int = 20) -> list[dict]:
    """与某标的（MARKET:CODE）相关的新闻（标题里出现公司名）。"""
    return await run_in_threadpool(service.news_for_symbol, symbol, limit)


@router.get("/for/brief", response_model=StockNewsBrief)
async def news_for_brief(symbol: str, limit: int = 32) -> dict:
    """某标的相关资讯的 AI 摘要；看页只展示摘要，不直接铺新闻列表。"""
    try:
        return await run_in_threadpool(service.stock_news_brief, symbol, limit)
    except gateway.LLMNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.get("/social-heat", response_model=StockSocialHeat)
async def social_heat(symbol: str) -> dict:
    """TikHub 社媒弱信号摘要：推特 + 小红书；只返回 AI 结论，不返回原始帖子。"""
    return await run_in_threadpool(service.stock_social_heat, symbol)


@router.get("/official", response_model=list[Filing])
async def official(symbol: str, limit: int = 15) -> list[dict]:
    """某标的的官方一手文件（美股＝SEC EDGAR 申报；6h 缓存，失败降级空表）。"""
    return await run_in_threadpool(service.stock_official, symbol, limit)


# ───────── 个股：定向抓取 lane + 标的叙事时间线（知·个股）─────────
@router.post("/directed/refresh")
async def directed_refresh(symbol: str | None = None) -> dict:
    """自选股定向抓取（按 ticker 直取该公司新闻、落库挂钩）。symbol 省略=全部自选。"""
    syms = [symbol] if symbol else None
    return await run_in_threadpool(service.refresh_directed, syms)


@router.get("/stock", response_model=list[NewsItem])
async def stock_feed(symbol: str, days: int = 0, limit: int = 60) -> list[dict]:
    """某自选股持久化挂钩的新闻流（定向 lane ∪ 聚合挂钩），时间倒序。"""
    return await run_in_threadpool(service.items_for_symbol, symbol, days, limit)


@router.get("/narrative")
async def narrative(symbol: str) -> dict:
    """某股已生成的叙事（当前主线 + 时间线）；暂无 → 404。"""
    data = await run_in_threadpool(service.get_narrative, symbol)
    if data is None:
        raise HTTPException(status_code=404, detail="暂无叙事")
    return data


@router.post("/narrative/generate")
async def narrative_generate(symbol: str) -> dict:
    """生成/重生成某股叙事（LLM 融合定向抓取的近况）。"""
    try:
        return await run_in_threadpool(service.generate_narrative, symbol)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ───────── 每股专属信源画像（组件化信源：LLM 调研 + 作者策展 mark）─────────
@router.get("/sources")
async def stock_sources_list(symbol: str) -> list[dict]:
    """某股的专属信源清单（启用在前）。"""
    return await run_in_threadpool(stock_sources.list_sources, symbol)


@router.post("/sources/discover")
async def stock_sources_discover(symbol: str) -> dict:
    """LLM（deep_research 角色，最好联网）调研某股该看哪些信源 → 落库待确认。"""
    try:
        return await run_in_threadpool(stock_sources.discover, symbol)
    except gateway.LLMNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


class _SourceIn(BaseModel):
    kind: str
    name: str = ""
    ref: str = ""
    note: str = ""


@router.post("/sources")
async def stock_sources_add(symbol: str, body: _SourceIn) -> dict:
    """手动加一个信源（默认启用）。"""
    try:
        return await run_in_threadpool(
            stock_sources.add_source, symbol, body.kind, body.name, body.ref, body.note
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class _EnabledIn(BaseModel):
    enabled: bool


@router.patch("/sources/{source_id}")
async def stock_sources_toggle(source_id: int, body: _EnabledIn) -> dict:
    """启用/停用某信源（作者拍板）。"""
    try:
        await run_in_threadpool(stock_sources.set_enabled, source_id, body.enabled)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"ok": True}


@router.delete("/sources/{source_id}")
async def stock_sources_delete(source_id: int) -> dict:
    """删除某信源。"""
    try:
        await run_in_threadpool(stock_sources.delete_source, source_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"ok": True}


@router.get("/reports", response_model=list[ReportMeta])
async def reports(limit: int = 30) -> list[dict]:
    """日报列表（按日期倒序，带预览）。"""
    return await run_in_threadpool(service.list_reports, limit)


@router.get("/report", response_model=NewsReport)
async def report(date: str | None = None) -> dict:
    """某日（默认最新）趋势日报全文。"""
    data = await run_in_threadpool(service.get_report, date)
    if data is None:
        raise HTTPException(status_code=404, detail="暂无日报，先 POST /news/report/generate 生成")
    return data


@router.get("/opportunities", response_model=OpportunitiesResponse)
async def opportunities(date: str | None = None) -> dict:
    """某日（默认今天）已生成的投资机会列表（接地后含关联个股）。"""
    data = await run_in_threadpool(service.get_opportunities, date)
    if data is None:
        raise HTTPException(status_code=404, detail="暂无今日机会，先生成")
    return data


@router.post("/opportunities/generate", response_model=OpportunitiesResponse)
async def generate_opportunities(date: str | None = None) -> dict:
    """从当日新闻抽取投资机会 + 接地到 MARKET:CODE（阻塞，约 20–40s）。落库覆盖当天。"""
    try:
        gateway.check_ready("summarize")
    except gateway.LLMNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return await run_in_threadpool(service.generate_opportunities, date)


@router.get("/clusters", response_model=ClustersResponse)
async def clusters(
    theme: str | None = None,
    source_prefix: str | None = None,
    category: str | None = None,
    days: int = 1,
    date: str | None = None,
) -> dict:
    """某范围要点（新闻按 theme / 推特按 source_prefix+category；date 取某天快照）。无 → 404。"""
    data = await run_in_threadpool(service.get_clusters, theme, source_prefix, category, days, date)
    if data is None:
        raise HTTPException(status_code=404, detail="暂无要点，先生成")
    return data


@router.get("/social-pulse")
async def social_pulse(date: str | None = None) -> dict:
    """各社媒 lane 已生成要点的聚合（供「资讯·总结/决策」接入所有信源）。读已落库、零成本。"""
    return await run_in_threadpool(service.social_pulse, date)


@router.post("/clusters/generate", response_model=ClustersResponse)
async def generate_clusters(
    theme: str | None = None,
    source_prefix: str | None = None,
    category: str | None = None,
    days: int = 1,
    date: str | None = None,
) -> dict:
    """生成要点：LLM 去重聚类+按重要性排序（阻塞 ~20–40s）。落库覆盖 (report_date, scope)。"""
    try:
        gateway.check_ready("summarize")
    except gateway.LLMNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return await run_in_threadpool(
        service.generate_clusters, theme, source_prefix, category, days, "summarize", date
    )


@router.post("/report/generate", response_model=NewsReport)
async def generate(date: str | None = None) -> dict:
    """生成**结构化**综合日报：阻塞（一次结构化 LLM 调用 + 公司接地，约 20–40s），落库后返回。

    分层分点、个股「看/研」可点——取代旧的 markdown 长文流（作者：长文无法专注）。
    """
    try:
        gateway.check_ready("summarize")
    except gateway.LLMNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    try:
        return await run_in_threadpool(service.generate_report, date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/section-reports", response_model=SectionReportsResponse)
async def section_reports(date: str | None = None) -> dict:
    """某日（默认今天）自选**分区级日报**：每个一级分区一张板块卡（脉搏 + 逐股异动）。

    boards 空＝当天未生成（前端显生成入口）；零成本读已落库，不触发 LLM。
    """
    return await run_in_threadpool(service.get_section_reports, date)


@router.post("/section-reports/generate", response_model=SectionReportsResponse)
async def generate_section_reports(date: str | None = None) -> dict:
    """生成分区级日报：每个一级分区一次结构化 LLM 调用、分区间并行（阻塞 ~30–60s）。落库覆盖。"""
    try:
        gateway.check_ready("summarize")
    except gateway.LLMNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return await run_in_threadpool(service.generate_section_reports, date)
