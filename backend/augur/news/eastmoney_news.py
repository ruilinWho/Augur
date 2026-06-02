"""东方财富——免费关键词科技资讯（search-api-web JSONP；CLAUDE.md §1 / ADR-0007）。

按主人关注的前沿关键词检索、按时间排序，聚合多家媒体的科技报道（与现有东财检索同源）。
免费、无需 key。失败降级 []。归一化为 news_items 同形条目，复用 classify + 噪音过滤；
中文无需翻译。source 固定为「东方财富」（聚合器；保证 ingest 的 prune 不误删，见 ingest.py）。
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

from . import classify
from . import filter as noise_filter

_UA = "Mozilla/5.0 (Augur/0.1; local research tool)"
_TIMEOUT = 12.0
_PER_KW = 12  # 每关键词取前 N 条
_KEYWORDS = ["人工智能", "半导体", "算力", "机器人", "大模型", "芯片"]
_API = "https://search-api-web.eastmoney.com/search/jsonp?cb=cb&param="
_EM_RE = re.compile(r"</?em>")
_CST = ZoneInfo("Asia/Shanghai")


def _query(keyword: str) -> list[dict]:
    param = {
        "keyword": keyword,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "param": {"cmsArticleWebOld": {"pageIndex": 1, "pageSize": 20, "sort": "time"}},
    }
    url = _API + quote(json.dumps(param, separators=(",", ":")))
    headers = {"User-Agent": _UA, "Referer": "https://so.eastmoney.com/"}
    with httpx.Client(timeout=_TIMEOUT, headers=headers, follow_redirects=True) as c:
        r = c.get(url)
        r.raise_for_status()
    txt = r.text.strip()
    body = txt[txt.index("(") + 1 : txt.rindex(")")]  # 剥 JSONP 外壳 cb(...)
    data = json.loads(body)
    return (data.get("result") or {}).get("cmsArticleWebOld") or []


def _parse_dt(s: str) -> datetime | None:
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=_CST)
    except (ValueError, AttributeError):
        return None


def fetch_eastmoney(cutoff: datetime | None = None) -> list[dict]:
    """东财多关键词科技资讯 → 归一化条目（按 url 去重）。单关键词失败不影响其余。"""
    out: list[dict] = []
    seen: set[str] = set()
    for kw in _KEYWORDS:
        try:
            rows = _query(kw)
        except Exception:  # noqa: BLE001 — 单关键词失败容忍
            continue
        for a in rows[:_PER_KW]:
            url = str(a.get("url") or "").strip()
            title = _EM_RE.sub("", str(a.get("title") or "")).strip()
            if not url or not title or url in seen:
                continue
            if noise_filter.is_noise(title):
                continue
            seen.add(url)
            dt = _parse_dt(str(a.get("date") or ""))
            if cutoff is not None and dt is not None and dt < cutoff:
                continue
            summary = _EM_RE.sub("", str(a.get("content") or ""))[:400]
            theme, topics = classify.classify_rule(title, summary, "tech")
            out.append(
                {
                    "source": "东方财富",
                    "title": title[:500],
                    "url": url,
                    "summary": summary,
                    "lang": "zh",
                    "category": "tech",
                    "published_at": dt.astimezone(ZoneInfo("UTC")).isoformat() if dt else None,
                    "theme": theme,
                    "topics": json.dumps(topics, ensure_ascii=False),
                    "classified_by": "rule",
                }
            )
    return out
