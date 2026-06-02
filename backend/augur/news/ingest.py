"""RSS/Atom 摄取：并发拉取信源 → 归一化 → 落库（按 url 去重）。

CLAUDE.md §5：出站请求带超时/UA、容忍单源失败（限流是真的）。**并发**抓取（线程池），
单源 12s 超时、每源取前 N 条、按发布时间过滤近期（挡住归档源倒灌旧闻）。feedparser 解析 RSS+Atom。
"""

from __future__ import annotations

import calendar
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta

import feedparser
import httpx

from ..storage import get_conn
from . import classify, cls, eastmoney_news, sources
from . import filter as noise_filter

# 非 RSS 专用适配器（中文科技源）：source 名 → 抓取函数。其 source 名在 prune 时要豁免。
_ADAPTERS = {"财联社": cls.fetch_cls, "东方财富": eastmoney_news.fetch_eastmoney}

_UA = "Mozilla/5.0 (Augur/0.1; local research tool)"
_TIMEOUT = 12.0
_PER_FEED_MAX = 30  # 每源最多取前 N 条，避免超大/归档 feed 占满
_MAX_WORKERS = 12  # 并发抓取的线程数（≈源数，但有上限以尊重本机与限流）
_RECENCY_DAYS = 30  # 只收近 N 天的条目（无日期的保留）；挡归档源倒灌历史
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _published_dt(entry: dict) -> datetime | None:
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if not t:
        return None
    try:
        return datetime.fromtimestamp(calendar.timegm(t), tz=UTC)
    except (ValueError, OverflowError, TypeError):
        return None


def _clean(s: str) -> str:
    s = _WS_RE.sub(" ", _TAG_RE.sub("", s or "")).strip()
    return s[:400]


def fetch_feed(feed: dict, cutoff: datetime | None = None) -> list[dict]:
    """拉单源 → 归一化条目（不落库）。网络/解析失败抛异常，由上层捕获。

    cutoff：丢弃早于此时间的条目（无发布时间的保留）。
    """
    headers = {"User-Agent": _UA}
    with httpx.Client(timeout=_TIMEOUT, headers=headers, follow_redirects=True) as client:
        resp = client.get(feed["url"])
        resp.raise_for_status()
    parsed = feedparser.parse(resp.content)
    items: list[dict] = []
    for e in parsed.entries[:_PER_FEED_MAX]:
        url = str(e.get("link", "")).strip()
        title = _clean(str(e.get("title", "")))
        if not url or not title:
            continue
        if noise_filter.is_noise(title):
            continue  # 纯盘面/价格波动噪音 → 不落库
        dt = _published_dt(e)
        if cutoff is not None and dt is not None and dt < cutoff:
            continue  # 太旧 → 跳过（归档源保护）
        summary = _clean(str(e.get("summary", "")))
        cat = feed.get("category", "")
        theme, topics = classify.classify_rule(title, summary, cat)
        items.append(
            {
                "source": feed["name"],
                "title": title[:500],
                "url": url,
                "summary": summary,
                "lang": feed.get("lang", ""),
                "category": cat,
                "published_at": dt.isoformat() if dt else None,
                "theme": theme,
                "topics": json.dumps(topics, ensure_ascii=False),
                "classified_by": "rule",
            }
        )
    return items


def _store(items: list[dict]) -> int:
    if not items:
        return 0
    conn = get_conn()
    try:
        before = conn.total_changes
        conn.executemany(
            "INSERT OR IGNORE INTO news_items "
            "(source, title, url, summary, lang, category, published_at, "
            "theme, topics, classified_by) "
            "VALUES (:source, :title, :url, :summary, :lang, :category, :published_at, "
            ":theme, :topics, :classified_by)",
            items,
        )
        conn.commit()
        return conn.total_changes - before
    finally:
        conn.close()


def _prune_removed_sources(feed_names: set[str]) -> int:
    """删除已不在 feeds.yaml 里的信源的历史条目（主人移除某源后自愈，库与源清单一致）。"""
    conn = get_conn()
    try:
        rows = conn.execute("SELECT DISTINCT source FROM news_items").fetchall()
        gone = [(r["source"],) for r in rows if r["source"] not in feed_names]
        if gone:
            conn.executemany("DELETE FROM news_items WHERE source = ?", gone)
            conn.commit()
        return len(gone)
    finally:
        conn.close()


def ingest_all() -> dict:
    """并发遍历所有信源 → 落库；返回统计（容忍单源失败）。"""
    feeds = sources.load_feeds()
    # prune 时豁免专用适配器 source，否则其条目（不在 feeds.yaml）会被当"已移除源"删掉
    _prune_removed_sources({f["name"] for f in feeds} | set(_ADAPTERS))
    cutoff = datetime.now(UTC) - timedelta(days=_RECENCY_DAYS)
    all_items: list[dict] = []
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:
        futures: dict = {ex.submit(fetch_feed, f, cutoff): f["name"] for f in feeds}
        for name, fn in _ADAPTERS.items():  # 中文科技适配器并发同抓
            futures[ex.submit(fn, cutoff)] = name
        for fut in as_completed(futures):
            try:
                all_items.extend(fut.result())
            except Exception:  # noqa: BLE001 — 单源失败不应中断整体
                failures.append(futures[fut])
    inserted = _store(all_items)
    classify.backfill_rules()  # 给历史未分类条目补规则分类（幂等、只扫未分类行）
    total = len(feeds) + len(_ADAPTERS)
    return {
        "fetched": len(all_items),
        "inserted": inserted,
        "sources_ok": total - len(failures),
        "sources_failed": len(failures),
        "failures": failures,
    }
