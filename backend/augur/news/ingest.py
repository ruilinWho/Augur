"""RSS/Atom 摄取：拉取信源 → 归一化 → 落库（按 url 去重）。

CLAUDE.md §5：出站请求带超时/UA、容忍单源失败（限流是真的）。串行抓取，简单稳妥；
单源 12s 超时、最多取前 N 条。feedparser 解析 RSS+Atom。
"""

from __future__ import annotations

import calendar
import re
from datetime import UTC, datetime

import feedparser
import httpx

from ..storage import get_conn
from . import sources

_UA = "Mozilla/5.0 (Augur/0.1; local research tool)"
_TIMEOUT = 12.0
_PER_FEED_MAX = 30  # 每源最多取前 N 条，避免超大 feed 占满
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _parse_time(entry: dict) -> str | None:
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if not t:
        return None
    try:
        return datetime.fromtimestamp(calendar.timegm(t), tz=UTC).isoformat()
    except (ValueError, OverflowError, TypeError):
        return None


def _clean(s: str) -> str:
    s = _WS_RE.sub(" ", _TAG_RE.sub("", s or "")).strip()
    return s[:400]


def fetch_feed(feed: dict) -> list[dict]:
    """拉单源 → 归一化条目（不落库）。网络/解析失败抛异常，由上层捕获。"""
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
        items.append(
            {
                "source": feed["name"],
                "title": title[:500],
                "url": url,
                "summary": _clean(str(e.get("summary", ""))),
                "lang": feed.get("lang", ""),
                "category": feed.get("category", ""),
                "published_at": _parse_time(e),
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
            "(source, title, url, summary, lang, category, published_at) "
            "VALUES (:source, :title, :url, :summary, :lang, :category, :published_at)",
            items,
        )
        conn.commit()
        return conn.total_changes - before
    finally:
        conn.close()


def ingest_all() -> dict:
    """遍历所有信源 → 落库；返回统计（容忍单源失败）。"""
    feeds = sources.load_feeds()
    all_items: list[dict] = []
    ok = 0
    failures: list[str] = []
    for f in feeds:
        try:
            all_items.extend(fetch_feed(f))
            ok += 1
        except Exception:  # noqa: BLE001 — 单源失败不应中断整体
            failures.append(f["name"])
    inserted = _store(all_items)
    return {
        "fetched": len(all_items),
        "inserted": inserted,
        "sources_ok": ok,
        "sources_failed": len(failures),
        "failures": failures,
    }
