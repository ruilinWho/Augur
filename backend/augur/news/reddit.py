"""Reddit public JSON adapter.

Reddit is useful as a weak-signal community lane: it is noisy, but often catches retail
positioning, product complaints, and meme momentum before mainstream feeds. This adapter
uses public subreddit JSON endpoints, keeps requests small, and stores entries as
`Reddit·r/<subreddit>` so the frontend can filter the lane by source prefix.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from .. import runtime_config
from . import classify
from ._http import get as http_get
from .filter import is_noise

_DEFAULT_SUBREDDITS = [
    "stocks",
    "investing",
    "SecurityAnalysis",
    "ValueInvesting",
    "wallstreetbets",
    "StockMarket",
    "NVDA_Stock",
]
_SUB_RE = re.compile(r"^[A-Za-z0-9_]{2,40}$")
_PER_SUB_MAX = 25


def subreddits() -> list[str]:
    """Configured subreddit list, with built-in defaults as fallback."""
    raw = runtime_config.get_source_config("reddit", "subreddits", _DEFAULT_SUBREDDITS) or []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        sub = str(item).strip().removeprefix("r/").strip("/")
        if not _SUB_RE.match(sub):
            continue
        key = sub.lower()
        if key not in seen:
            seen.add(key)
            out.append(sub)
    return out[:40]


def source_names() -> set[str]:
    return {f"Reddit·r/{s}" for s in subreddits()}


def _dt(created_utc) -> datetime | None:
    try:
        return datetime.fromtimestamp(float(created_utc), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


def _fetch_subreddit(sub: str, cutoff: datetime | None) -> list[dict]:
    resp = http_get(
        f"https://www.reddit.com/r/{sub}/new.json?limit={_PER_SUB_MAX}&raw_json=1",
        timeout=12,
        retries=1,
    )
    data = json.loads(resp.text or "{}")
    children = ((data.get("data") or {}).get("children") or []) if isinstance(data, dict) else []
    items: list[dict] = []
    for child in children:
        d = (child or {}).get("data") or {}
        title = str(d.get("title") or "").strip()
        if not title or is_noise(title):
            continue
        dt = _dt(d.get("created_utc"))
        if cutoff is not None and dt is not None and dt < cutoff:
            continue
        permalink = str(d.get("permalink") or "").strip()
        url = (
            f"https://www.reddit.com{permalink}"
            if permalink.startswith("/")
            else str(d.get("url") or "")
        )
        if not url:
            continue
        summary = str(d.get("selftext") or "").strip().replace("\n", " ")[:400]
        cat = "forum"
        theme, topics = classify.classify_rule(title, summary, cat)
        items.append(
            {
                "source": f"Reddit·r/{sub}",
                "title": title[:500],
                "url": url,
                "summary": summary,
                "lang": "en",
                "category": cat,
                "published_at": dt.isoformat() if dt else None,
                "theme": theme,
                "topics": json.dumps(topics, ensure_ascii=False),
                "classified_by": "rule",
            }
        )
    return items


def fetch_reddit(cutoff: datetime | None = None) -> list[dict]:
    """Fetch configured subreddits. Per-subreddit failures are ignored."""
    out: list[dict] = []
    for sub in subreddits():
        try:
            out.extend(_fetch_subreddit(sub, cutoff))
        except Exception:
            continue
    return out
