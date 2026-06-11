"""TikHub adapter for secondary social/forum sources.

TikHub is a paid, unofficial bridge used here as a shared provider for sources that do not
offer convenient public research APIs. All entries are normalized into `news_items` and still go
through Augur's relevance, translation, linker, and stock-tag pipeline.

Configured sources:
- Twitter 第二源: accounts and keyword search, source prefix `X·`
- 小红书: note keyword search, source prefix `小红书·`
- Threads: top-content keyword search, source prefix `Threads·`
- Reddit · TikHub: keyword search, source prefix `Reddit·TikHub·`
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from functools import lru_cache
from typing import Any
from urllib.parse import quote_plus

import httpx
import yaml

from .. import runtime_config
from . import classify
from ._http import UA as _UA
from .filter import is_noise

_DEFAULT_BASES = ("https://api.tikhub.io", "https://api.tikhub.dev")
_TIMEOUT = 20.0
_PER_QUERY = 16
_PROBE_QUERY = "NVDA"
_MAX_TEXT = 500
_WS_RE = re.compile(r"\s+")
_TAG_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"https?://\S+")


class TikhubError(RuntimeError):
    """TikHub adapter error that can be shown through the shared diagnostics layer."""


class TikhubFatal(TikhubError):
    """Auth/billing/permission errors; do not swallow as a per-query miss."""


def _key() -> str:
    return (runtime_config.get_secret("TIKHUB_KEY") or os.environ.get("TIKHUB_KEY") or "").strip()


def _headers() -> dict[str, str]:
    key = _key()
    if not key:
        raise TikhubFatal("未配置 TIKHUB_KEY")
    return {"Authorization": f"Bearer {key}", "User-Agent": _UA}


def _bases() -> tuple[str, ...]:
    custom = os.environ.get("TIKHUB_BASE_URL", "").strip().rstrip("/")
    return (custom,) if custom else _DEFAULT_BASES


def _api_message(data: Any) -> str:
    if not isinstance(data, dict):
        return str(data)[:300]
    detail = data.get("detail")
    if isinstance(detail, dict):
        return _api_message(detail)
    if isinstance(detail, list):
        parts: list[str] = []
        for item in detail[:3]:
            if isinstance(item, dict):
                parts.append(str(item.get("msg") or item.get("message") or item))
            else:
                parts.append(str(item))
        if parts:
            return "；".join(parts)[:300]
    return str(
        data.get("message_zh")
        or data.get("message")
        or data.get("msg")
        or data.get("error")
        or detail
        or data
    )[:300]


def _params(params: dict[str, Any] | None) -> dict[str, Any]:
    return {k: v for k, v in (params or {}).items() if v is not None}


def _request(path: str, params: dict[str, Any] | None = None, *, retries: int = 1) -> dict:
    """GET TikHub JSON with small retry and user-facing billing/auth diagnostics."""
    if not path.startswith("/"):
        path = f"/{path}"
    last_exc: Exception | None = None
    for base in _bases():
        for attempt in range(retries + 1):
            try:
                with httpx.Client(timeout=_TIMEOUT, headers=_headers(), follow_redirects=True) as c:
                    resp = c.get(f"{base}{path}", params=_params(params))
                if resp.status_code in (401, 403):
                    raise TikhubFatal(f"TIKHUB_KEY 无效或无权限（HTTP {resp.status_code}）")
                if resp.status_code == 402:
                    raise TikhubFatal("TikHub 余额不足，或当前套餐没有开通这个接口")
                if resp.status_code == 404:
                    raise TikhubFatal("TikHub 接口地址不可用，适配器需要更新")
                if resp.status_code == 429:
                    raise TikhubFatal("TikHub 额度或频率限制已触发")
                if resp.status_code in (400, 422):
                    try:
                        msg = _api_message(resp.json())
                    except ValueError:
                        msg = resp.text[:300]
                    if resp.status_code == 422:
                        raise TikhubError(f"TikHub 请求参数不符合文档，适配器需要更新：{msg}")
                    last_exc = TikhubError(f"TikHub 端点当前失败（服务端返回 400，未扣费）：{msg}")
                    if attempt < retries:
                        time.sleep(0.5 * (2**attempt))
                        continue
                    break
                if resp.status_code >= 500:
                    last_exc = TikhubError("TikHub 服务临时不可用")
                    if attempt < retries:
                        time.sleep(0.5 * (2**attempt))
                        continue
                    break
                resp.raise_for_status()
                data = resp.json()
                if not isinstance(data, dict):
                    raise TikhubError("TikHub 返回格式变了，需要更新适配器")
                code = data.get("code")
                if code not in (None, 0, 200, "0", "200"):
                    msg = _api_message(data)
                    lower = msg.lower()
                    if code in (401, 403) or "unauthorized" in lower or "permission" in lower:
                        raise TikhubFatal(f"TIKHUB_KEY 无效或无权限：{msg}")
                    if code in (402,) or "余额" in msg or "balance" in lower or "quota" in lower:
                        raise TikhubFatal(f"TikHub 余额或接口权限不足：{msg}")
                    if code in (429,) or "rate" in lower or "频率" in msg or "限流" in msg:
                        raise TikhubFatal(f"TikHub 额度或频率限制已触发：{msg}")
                    raise TikhubError(f"TikHub 返回错误：{msg}")
                return data
            except TikhubFatal:
                raise
            except (httpx.TransportError, httpx.TimeoutException) as e:
                last_exc = e
                if attempt < retries:
                    time.sleep(0.5 * (2**attempt))
                    continue
                break
    raise TikhubError(str(last_exc or "TikHub 请求失败"))


def _clean(s: Any, *, max_len: int = _MAX_TEXT) -> str:
    text = _TAG_RE.sub("", str(s or ""))
    text = _URL_RE.sub("", text)
    return _WS_RE.sub(" ", text).strip()[:max_len]


def _norm_query(q: Any) -> str:
    return _clean(q, max_len=80)


@lru_cache(maxsize=1)
def _default_keywords() -> dict[str, list[str]]:
    """内置默认社媒关键词（resources/sources/social_keywords.yaml）；缺失 → {}。"""
    from ..config import get_settings

    path = get_settings().resources_dir / "sources" / "social_keywords.yaml"
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    return {k: list(v or []) for k, v in data.items() if isinstance(v, list)}


def _tags(source_id: str, field: str, fallback: list[str] | None = None) -> list[str]:
    raw = runtime_config.get_source_config(source_id, field, fallback or []) or []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        q = _norm_query(item)
        if q and q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out[:60]


def _keywords(source_id: str, platform: str) -> list[str]:
    """生效关键词：作者在设置里配的优先，否则回退到内置默认（按平台）。"""
    cfg = runtime_config.get_source_config(source_id, "keywords")
    if cfg:
        return _tags(source_id, "keywords")
    return _tags(source_id, "keywords", _default_keywords().get(platform, []))


def twitter_accounts() -> list[dict]:
    raw = runtime_config.get_source_config("tikhub_twitter", "accounts", []) or []
    out: list[dict] = []
    seen: set[str] = set()
    for a in raw:
        if not isinstance(a, dict):
            continue
        sn = str(a.get("screen_name", "")).strip().lstrip("@")[:30]
        if not sn or sn.lower() in seen:
            continue
        seen.add(sn.lower())
        cat = str(a.get("category", "tech")).strip().lower() or "tech"
        out.append({"screen_name": sn, "category": cat})
    return out[:60]


def twitter_keywords() -> list[str]:
    return _keywords("tikhub_twitter", "twitter")


def xiaohongshu_keywords() -> list[str]:
    return _keywords("xiaohongshu", "xiaohongshu")


def threads_keywords() -> list[str]:
    return _keywords("tikhub_threads", "threads")


def reddit_keywords() -> list[str]:
    return _keywords("tikhub_reddit", "reddit")


def source_names() -> set[str]:
    names: set[str] = set()
    for a in twitter_accounts():
        names.add(f"X·@{a['screen_name']}")
    for q in twitter_keywords():
        names.add(f"X·搜索·{q}")
    for q in xiaohongshu_keywords():
        names.add(f"小红书·{q}")
    for q in threads_keywords():
        names.add(f"Threads·{q}")
    for q in reddit_keywords():
        names.add(f"Reddit·TikHub·{q}")
    return names


def _iter_dicts(obj: Any, *, depth: int = 0) -> Iterable[dict]:
    if depth > 18:
        return
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _iter_dicts(v, depth=depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_dicts(v, depth=depth + 1)


def _find_value(obj: Any, keys: set[str], *, depth: int = 0) -> Any:
    if depth > 8:
        return None
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in keys and v not in (None, "", []):
                return v
        for v in obj.values():
            found = _find_value(v, keys, depth=depth + 1)
            if found not in (None, "", []):
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_value(v, keys, depth=depth + 1)
            if found not in (None, "", []):
                return found
    return None


def _find_user_name(obj: Any) -> str:
    v = _find_value(
        obj,
        {
            "screen_name",
            "username",
            "user_name",
            "unique_id",
            "nickname",
            "nick_name",
            "name",
            "author",
            "author_name",
            "user",
        },
    )
    if isinstance(v, dict):
        return _find_user_name(v)
    return _clean(v, max_len=80)


def _parse_dt(v: Any) -> datetime | None:
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        try:
            ts = float(v)
            if ts > 10_000_000_000:
                ts /= 1000.0
            dt = datetime.fromtimestamp(ts, tz=UTC)
        except (ValueError, OSError, OverflowError):
            return None
        return None if dt > datetime.now(UTC) + timedelta(hours=1) else dt
    s = str(v).strip()
    if not s:
        return None
    if s.isdigit():
        return _parse_dt(int(s))
    for raw in (s, s.replace("Z", "+00:00")):
        try:
            dt = datetime.fromisoformat(raw).astimezone(UTC)
            return None if dt > datetime.now(UTC) + timedelta(hours=1) else dt
        except ValueError:
            pass
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        dt = dt.astimezone(UTC)
    except (TypeError, ValueError, OverflowError):
        return None
    return None if dt > datetime.now(UTC) + timedelta(hours=1) else dt


def _best_text(obj: dict) -> str:
    v = _find_value(
        obj,
        {
            "full_text",
            "tweet_text",
            "text",
            "raw_text",
            "content",
            "desc",
            "description",
            "title",
            "display_title",
            "note_display_title",
            "article_title",
            "post_title",
            "subject",
        },
    )
    if isinstance(v, dict):
        return _best_text(v)
    if isinstance(v, list):
        return _clean(" ".join(str(x) for x in v), max_len=_MAX_TEXT)
    return _clean(v)


def _best_summary(obj: dict, title: str) -> str:
    v = _find_value(
        obj,
        {
            "summary",
            "selftext",
            "body",
            "article_content",
            "note_content",
            "long_text",
            "abstract",
            "snippet",
        },
    )
    text = _clean(v, max_len=700)
    if not text or text == title:
        return ""
    return text


def _best_id(obj: dict) -> str:
    v = _find_value(
        obj,
        {
            "tweet_id",
            "rest_id",
            "note_id",
            "article_id",
            "post_id",
            "submission_id",
            "id",
            "mid",
            "item_id",
            "url",
            "share_url",
            "link",
            "permalink",
        },
    )
    return _clean(v, max_len=180)


def _best_url(obj: dict, platform: str, item_id: str) -> str:
    v = _find_value(
        obj,
        {
            "url",
            "share_url",
            "link",
            "permalink",
            "article_url",
            "note_url",
            "web_url",
            "expanded_url",
        },
    )
    if isinstance(v, dict):
        v = _find_value(v, {"url", "expanded_url"})
    url = str(v or "").strip()
    if url.startswith("//"):
        url = f"https:{url}"
    if url.startswith("http"):
        return url[:1000]
    if platform == "twitter" and item_id:
        return f"https://x.com/i/status/{quote_plus(item_id)}"
    if platform == "xhs" and item_id:
        return f"https://www.xiaohongshu.com/explore/{quote_plus(item_id)}"
    if platform == "reddit" and url.startswith("/"):
        return f"https://www.reddit.com{url}"
    return ""


def _best_dt(obj: dict) -> datetime | None:
    v = _find_value(
        obj,
        {
            "created_at",
            "create_time",
            "creation_time",
            "publish_time",
            "pub_time",
            "timestamp",
            "time",
            "created_utc",
            "date",
        },
    )
    return _parse_dt(v)


def _candidate_score(d: dict) -> int:
    score = 0
    if _best_text(d):
        score += 3
    if _best_id(d):
        score += 2
    if _best_dt(d):
        score += 1
    if _find_user_name(d):
        score += 1
    return score


def _items_from_response(
    data: dict,
    *,
    source: str,
    platform: str,
    lang: str,
    category: str,
    cutoff: datetime | None,
    limit: int = _PER_QUERY,
) -> list[dict]:
    """Extract best-effort content items from TikHub's nested, platform-specific payloads."""
    if platform == "reddit":
        return _reddit_items_from_response(
            data, source=source, lang=lang, category=category, cutoff=cutoff, limit=limit
        )

    items: list[dict] = []
    seen: set[str] = set()
    candidates = [d for d in _iter_dicts(data.get("data", data)) if _candidate_score(d) >= 4]
    for d in candidates:
        title = _best_text(d)
        if not title or len(title) < 3 or is_noise(title):
            continue
        dt = _best_dt(d)
        if cutoff is not None and dt is not None and dt < cutoff:
            continue
        item_id = _best_id(d)
        url = _best_url(d, platform, item_id)
        key = url or f"{source}:{item_id or title[:120]}"
        if not key or key in seen:
            continue
        seen.add(key)
        author = _find_user_name(d)
        summary = _best_summary(d, title)
        if author and author not in title[:120]:
            summary = f"{author} · {summary}" if summary else author
        theme, topics = classify.classify_rule(title, summary, category)
        items.append(
            {
                "source": source,
                "title": title[:500],
                "url": url or f"https://www.tikhub.io/search?q={quote_plus(title[:80])}",
                "summary": summary[:700],
                "lang": lang,
                "category": category,
                "published_at": dt.isoformat() if dt else None,
                "theme": theme,
                "topics": json.dumps(topics, ensure_ascii=False),
                "classified_by": "rule",
            }
        )
        if len(items) >= limit:
            break
    return items


def _as_dict(obj: Any) -> dict:
    return obj if isinstance(obj, dict) else {}


def _reddit_children(data: dict) -> Iterable[dict]:
    root = _as_dict(data.get("data"))
    search = _as_dict(root.get("search"))
    dynamic = _as_dict(search.get("dynamic"))
    components = _as_dict(dynamic.get("components"))
    main = _as_dict(components.get("main"))
    for edge in main.get("edges") or []:
        node = _as_dict(_as_dict(edge).get("node"))
        for child in node.get("children") or []:
            d = _as_dict(child)
            if d.get("__typename") == "SearchPost" and isinstance(d.get("post"), dict):
                yield d


def _reddit_items_from_response(
    data: dict,
    *,
    source: str,
    lang: str,
    category: str,
    cutoff: datetime | None,
    limit: int,
) -> list[dict]:
    """Parse TikHub Reddit's app search shape and ignore UI chrome/filter labels."""
    items: list[dict] = []
    seen: set[str] = set()
    for child in _reddit_children(data):
        post = _as_dict(child.get("post"))
        title = _clean(post.get("postTitle") or post.get("title"))
        if not title or len(title) < 3 or is_noise(title):
            continue
        dt = _parse_dt(post.get("createdAt") or post.get("created_at"))
        if cutoff is not None and dt is not None and dt < cutoff:
            continue
        item_id = _clean(post.get("id"), max_len=80)
        url = str(post.get("url") or "").strip()
        if url.startswith("/"):
            url = f"https://www.reddit.com{url}"
        if not url.startswith("http"):
            url = _best_url(post, "reddit", item_id)
        content = _as_dict(post.get("content"))
        summary = _clean(
            content.get("markdown")
            or content.get("text")
            or content.get("html")
            or content.get("preview"),
            max_len=700,
        )
        behaviors = _as_dict(child.get("behaviors"))
        community = _clean(_as_dict(behaviors.get("community")).get("name"), max_len=80)
        author = _clean(_as_dict(behaviors.get("profile")).get("name"), max_len=80)
        meta = " · ".join(x for x in (community, author) if x)
        if meta:
            summary = f"{meta} · {summary}" if summary else meta
        key = item_id or url or f"{source}:{title[:120]}"
        if key in seen:
            continue
        seen.add(key)
        theme, topics = classify.classify_rule(title, summary, category)
        items.append(
            {
                "source": source,
                "title": title[:500],
                "url": url or f"https://www.reddit.com/search/?q={quote_plus(title[:80])}",
                "summary": summary[:700],
                "lang": lang,
                "category": category,
                "published_at": dt.isoformat() if dt else None,
                "theme": theme,
                "topics": json.dumps(topics, ensure_ascii=False),
                "classified_by": "rule",
            }
        )
        if len(items) >= limit:
            break
    return items


def _fetch_search(
    path: str,
    *,
    params: dict[str, Any],
    source: str,
    platform: str,
    lang: str,
    category: str,
    cutoff: datetime | None,
    retries: int = 1,
) -> list[dict]:
    data = _request(path, params, retries=retries)
    return _items_from_response(
        data, source=source, platform=platform, lang=lang, category=category, cutoff=cutoff
    )


def _fetch_queries(
    queries: list[str],
    *,
    path: str,
    base_params: dict[str, Any],
    param_name: str,
    source_prefix: str,
    platform: str,
    lang: str,
    category: str,
    cutoff: datetime | None,
    retries: int = 1,
) -> list[dict]:
    out: list[dict] = []
    for q in queries:
        params = {**base_params, param_name: q}
        got = _fetch_search(
            path,
            params=params,
            source=f"{source_prefix}{q}",
            platform=platform,
            lang=lang,
            category=category,
            cutoff=cutoff,
            retries=retries,
        )
        out.extend(got)
    return out


def _fetch_queries_limited(
    queries: list[str],
    *,
    limit: int,
    path: str,
    base_params: dict[str, Any],
    param_name: str,
    source_prefix: str,
    platform: str,
    lang: str,
    category: str,
    cutoff: datetime | None,
    retries: int = 1,
) -> list[dict]:
    """Fetch enough results for one source, then stop to keep stock-page probes cheap."""
    out: list[dict] = []
    for q in queries:
        params = {**base_params, param_name: q}
        got = _fetch_search(
            path,
            params=params,
            source=f"{source_prefix}{q}",
            platform=platform,
            lang=lang,
            category=category,
            cutoff=cutoff,
            retries=retries,
        )
        out.extend(got)
        if len(out) >= limit:
            break
    return out[:limit]


def fetch_twitter(cutoff: datetime | None = None) -> list[dict]:
    out: list[dict] = []
    for a in twitter_accounts():
        got = _fetch_search(
            "/api/v1/twitter/web/fetch_user_post_tweet",
            params={"screen_name": a["screen_name"], "cursor": "undefined"},
            source=f"X·@{a['screen_name']}",
            platform="twitter",
            lang="en",
            category=a.get("category") or "tech",
            cutoff=cutoff,
        )
        out.extend(got)
    out.extend(
        _fetch_queries(
            twitter_keywords(),
            path="/api/v1/twitter/web/fetch_search_timeline",
            # search_type 必须 'Top'；'Latest'/cursor='undefined' 都会 400（实测 2026-06-11）
            base_params={"search_type": "Top"},
            param_name="keyword",
            source_prefix="X·搜索·",
            platform="twitter",
            lang="en",
            category="markets",
            cutoff=cutoff,
        )
    )
    return out


def fetch_xiaohongshu(cutoff: datetime | None = None) -> list[dict]:
    return _fetch_queries(
        xiaohongshu_keywords(),
        path="/api/v1/xiaohongshu/app_v2/search_notes",
        base_params={
            "page": 1,
            "sort_type": "time_descending",
            "note_type": "不限",
            "time_filter": "一周内",
            "source": "explore_feed",
            "ai_mode": 0,
        },
        param_name="keyword",
        source_prefix="小红书·",
        platform="xhs",
        lang="zh",
        category="forum",
        cutoff=cutoff,
    )


def fetch_threads(cutoff: datetime | None = None) -> list[dict]:
    return _fetch_queries(
        threads_keywords(),
        path="/api/v1/threads/web/search_top",
        base_params={"end_cursor": "undefined"},
        param_name="query",
        source_prefix="Threads·",
        platform="threads",
        lang="en",
        category="forum",
        cutoff=cutoff,
    )


def fetch_reddit(cutoff: datetime | None = None) -> list[dict]:
    return _fetch_queries(
        reddit_keywords(),
        path="/api/v1/reddit/app/fetch_dynamic_search",
        base_params={
            "search_type": "post",
            "sort": "NEW",
            "time_range": "week",
            "safe_search": "unset",
            "allow_nsfw": "0",
            "after": "",
            "need_format": "false",
        },
        param_name="query",
        source_prefix="Reddit·TikHub·",
        platform="reddit",
        lang="en",
        category="forum",
        cutoff=cutoff,
    )


def ping_source(source_id: str) -> int:
    """Lightweight source test. Uses a tiny keyword request; raises user-facing errors."""
    cutoff = datetime.now(UTC) - timedelta(days=30)
    if source_id == "tikhub_twitter":
        return len(
            _fetch_search(
                "/api/v1/twitter/web/fetch_search_timeline",
                params={"keyword": _PROBE_QUERY, "search_type": "Top"},
                source="X·测试",
                platform="twitter",
                lang="en",
                category="markets",
                cutoff=cutoff,
            )
        )
    if source_id == "xiaohongshu":
        return len(
            _fetch_search(
                "/api/v1/xiaohongshu/app_v2/search_notes",
                params={
                    "keyword": "英伟达",
                    "page": 1,
                    "sort_type": "time_descending",
                    "note_type": "不限",
                    "time_filter": "一周内",
                    "source": "explore_feed",
                    "ai_mode": 0,
                },
                source="小红书·测试",
                platform="xhs",
                lang="zh",
                category="forum",
                cutoff=cutoff,
            )
        )
    if source_id == "tikhub_threads":
        return len(
            _fetch_search(
                "/api/v1/threads/web/search_top",
                params={"query": "NVIDIA", "end_cursor": "undefined"},
                source="Threads·测试",
                platform="threads",
                lang="en",
                category="forum",
                cutoff=cutoff,
            )
        )
    if source_id == "tikhub_reddit":
        return len(
            _fetch_search(
                "/api/v1/reddit/app/fetch_dynamic_search",
                params={
                    "query": _PROBE_QUERY,
                    "search_type": "post",
                    "sort": "NEW",
                    "time_range": "week",
                    "safe_search": "unset",
                    "allow_nsfw": "0",
                    "after": "",
                    "need_format": "false",
                },
                source="Reddit·TikHub·测试",
                platform="reddit",
                lang="en",
                category="forum",
                cutoff=cutoff,
            )
        )
    raise TikhubError(f"{source_id}：没有接入这个 TikHub 信源")


# ── 每股专属信源用：单关键词/单账号抓取（供 stock_sources 的 TikHub kind 调用）──
_STOCK_SOURCE_LIMIT = 12


def search_xiaohongshu(
    query: str, cutoff: datetime | None = None, limit: int = _STOCK_SOURCE_LIMIT
) -> list[dict]:
    """某股的小红书关键词笔记（每股专属信源 kind=xiaohongshu）。失败抛 Tikhub*。"""
    q = _norm_query(query)
    if not q:
        return []
    return _fetch_queries_limited(
        [q],
        limit=limit,
        path="/api/v1/xiaohongshu/app_v2/search_notes",
        base_params={
            "page": 1,
            "sort_type": "time_descending",
            "note_type": "不限",
            "time_filter": "一周内",
            "source": "explore_feed",
            "ai_mode": 0,
        },
        param_name="keyword",
        source_prefix="小红书·",
        platform="xhs",
        lang="zh",
        category="forum",
        cutoff=cutoff,
    )


def search_threads(
    query: str, cutoff: datetime | None = None, limit: int = _STOCK_SOURCE_LIMIT
) -> list[dict]:
    """某股的 Threads 关键词热门帖（每股专属信源 kind=threads）。失败抛 Tikhub*。"""
    q = _norm_query(query)
    if not q:
        return []
    return _fetch_queries_limited(
        [q],
        limit=limit,
        path="/api/v1/threads/web/search_top",
        base_params={"end_cursor": "undefined"},
        param_name="query",
        source_prefix="Threads·",
        platform="threads",
        lang="en",
        category="forum",
        cutoff=cutoff,
    )


def search_reddit(
    query: str, cutoff: datetime | None = None, limit: int = _STOCK_SOURCE_LIMIT
) -> list[dict]:
    """某股的 Reddit 关键词讨论（经 TikHub——Reddit 直连公共 JSON 已被 403 封）。失败抛 Tikhub*。

    直连 reddit.com 在本环境被按 IP 封（连 /r/<sub>/new.json 都 403），所以每股「最丰富的 Reddit
    相关讨论」改走 TikHub 的 Reddit 关键词搜索，用股名/ticker 当查询词。
    """
    q = _norm_query(query)
    if not q:
        return []
    return _fetch_queries_limited(
        [q],
        limit=limit,
        path="/api/v1/reddit/app/fetch_dynamic_search",
        base_params={
            "search_type": "post",
            "sort": "NEW",
            "time_range": "month",
            "safe_search": "unset",
            "allow_nsfw": "0",
            "after": "",
            "need_format": "false",
        },
        param_name="query",
        source_prefix="Reddit·",
        platform="reddit",
        lang="en",
        category="forum",
        cutoff=cutoff,
    )


_SUBREDDIT_RE = re.compile(r"^[A-Za-z0-9_]{2,40}$")


def search_subreddit_typeahead(query: str, limit: int = 10) -> list[str]:
    """TikHub Reddit 自动补全 → 子版名列表（去 `r/` 前缀，按相关性）。用于解析某股专属子板块。

    替代 reddit.com 直连搜索（已被 403 封）。失败/无结果 → []。
    """
    q = _norm_query(query)
    if not q:
        return []
    try:
        data = _request("/api/v1/reddit/app/fetch_search_typeahead", {"query": q})
    except TikhubError:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for d in _iter_dicts(data.get("data", data)):
        for k in ("name", "prefixedName", "display_name"):
            v = d.get(k)
            if not isinstance(v, str) or not v:
                continue
            name = v.strip().removeprefix("/r/").removeprefix("r/").strip("/")
            if _SUBREDDIT_RE.match(name) and name.lower() not in seen:
                seen.add(name.lower())
                out.append(name)
        if len(out) >= limit:
            break
    return out[:limit]


def _subreddit_feed_items(
    data: dict, *, sub: str, lang: str, category: str, cutoff: datetime | None, limit: int
) -> list[dict]:
    """从子版 feed 的 GraphQL（结构按子版/排序略有差异）里抽帖子。

    **只认帖子节点本身**：dict 直接带 `title` + (`permalink` 或 `createdAt`)，不用递归的 `_best_*`
    （那会把同一帖在容器/子节点里反复抽出、还混进 gif/头像等资源 url）。按归一标题去重。
    """
    source = f"Reddit·r/{sub}"
    items: list[dict] = []
    seen: set[str] = set()
    for d in _iter_dicts(data.get("data", data)):
        title = d.get("title")
        if not isinstance(title, str):
            continue
        title = _clean(title)
        if not title or len(title) < 6 or is_noise(title):
            continue
        permalink = d.get("permalink") if isinstance(d.get("permalink"), str) else ""
        created = d.get("createdAt") or d.get("created_utc") or d.get("created")
        pid = d.get("id") if isinstance(d.get("id"), str) else ""
        if not (permalink or created or pid):
            continue  # 不是帖子节点（容器/资源节点没有直接的 permalink/时间/id）
        tkey = _WS_RE.sub("", title.lower())[:60]
        if tkey in seen:
            continue
        dt = _parse_dt(created)
        if cutoff is not None and dt is not None and dt < cutoff:
            continue
        seen.add(tkey)
        if permalink.startswith("/"):
            url = f"https://www.reddit.com{permalink}"
        elif permalink.startswith("http"):
            url = permalink
        else:
            url = f"https://www.reddit.com/r/{sub}"
        author = ""
        ai = d.get("authorInfo")
        if isinstance(ai, dict):
            author = _clean(ai.get("name") or "", max_len=80)
        if not author and isinstance(d.get("author"), str):
            author = _clean(d.get("author"), max_len=80)
        body = _clean(d.get("selftext") or d.get("body") or "", max_len=400)
        summary = " · ".join(x for x in (author, body) if x)
        theme, topics = classify.classify_rule(title, summary, category)
        items.append(
            {
                "source": source,
                "title": title[:500],
                "url": url,
                "summary": summary[:700],
                "lang": lang,
                "category": category,
                "published_at": dt.isoformat() if dt else None,
                "theme": theme,
                "topics": json.dumps(topics, ensure_ascii=False),
                "classified_by": "rule",
            }
        )
        if len(items) >= limit:
            break
    return items


def fetch_subreddit_feed(
    subreddit_name: str,
    cutoff: datetime | None = None,
    limit: int = _STOCK_SOURCE_LIMIT,
    sort: str = "HOT",
) -> list[dict]:
    """抓某个子版（专属子板块）的帖子流——TikHub 代理 Reddit（reddit.com 直连已被 IP 封 403）。

    sort: BEST/HOT/NEW/TOP/CONTROVERSIAL/RISING。失败抛 Tikhub*；子版名非法 → []。
    """
    sub = (subreddit_name or "").strip().removeprefix("r/").strip("/")
    if not _SUBREDDIT_RE.match(sub):
        return []
    data = _request(
        "/api/v1/reddit/app/fetch_subreddit_feed",
        {"subreddit_name": sub, "sort": sort, "need_format": "false"},
    )
    return _subreddit_feed_items(
        data, sub=sub, lang="en", category="forum", cutoff=cutoff, limit=limit
    )


def user_tweets(
    screen_name: str, cutoff: datetime | None = None, limit: int = _STOCK_SOURCE_LIMIT
) -> list[dict]:
    """某 X 账号的推文（TikHub 通道，作 twtapi 不可用时的每股 X 源回退）。失败抛 Tikhub*。"""
    handle = (screen_name or "").strip().lstrip("@")
    if not handle:
        return []
    got = _fetch_search(
        "/api/v1/twitter/web/fetch_user_post_tweet",
        params={"screen_name": handle, "cursor": "undefined"},
        source=f"X·@{handle}",
        platform="twitter",
        lang="en",
        category="stock",
        cutoff=cutoff,
    )
    return got[:limit]


def social_search_for_stock(terms: list[str], cutoff: datetime | None = None) -> list[dict]:
    """Twitter 第二源 + 小红书 stock-opinion search for the stock page.

    Returns normalized items but does not store them. The frontend only receives an AI/distilled
    heat summary from `service.stock_social_heat`, never the raw post list.
    """
    queries: list[str] = []
    seen: set[str] = set()
    for t in terms:
        q = _norm_query(t)
        if q and q.lower() not in seen:
            seen.add(q.lower())
            queries.append(q)
        if len(queries) >= 3:
            break
    if not queries:
        return []
    cutoff = cutoff or datetime.now(UTC) - timedelta(days=7)
    out: list[dict] = []
    jobs = [
        {
            "path": "/api/v1/twitter/web/fetch_search_timeline",
            "base_params": {"search_type": "Top"},  # 'Latest'/cursor 会 400（见 fetch_twitter）
            "param_name": "keyword",
            "source_prefix": "X·搜索·",
            "platform": "twitter",
            "lang": "en",
            "category": "markets",
            "retries": 0,
        },
        {
            "path": "/api/v1/xiaohongshu/app_v2/search_notes",
            "base_params": {
                "page": 1,
                "sort_type": "time_descending",
                "note_type": "不限",
                "time_filter": "一周内",
                "source": "explore_feed",
                "ai_mode": 0,
            },
            "param_name": "keyword",
            "source_prefix": "小红书·",
            "platform": "xhs",
            "lang": "zh",
            "category": "forum",
            "retries": 0,
        },
        {
            "path": "/api/v1/threads/web/search_top",
            "base_params": {"end_cursor": "undefined"},
            "param_name": "query",
            "source_prefix": "Threads·",
            "platform": "threads",
            "lang": "en",
            "category": "forum",
            "retries": 0,
        },
        {
            "path": "/api/v1/reddit/app/fetch_dynamic_search",
            "base_params": {
                "search_type": "post",
                "sort": "NEW",
                "time_range": "week",
                "safe_search": "unset",
                "allow_nsfw": "0",
                "after": "",
                "need_format": "false",
            },
            "param_name": "query",
            "source_prefix": "Reddit·TikHub·",
            "platform": "reddit",
            "lang": "en",
            "category": "forum",
            "retries": 0,
        },
    ]
    results: dict[int, list[dict]] = {}
    fatal: TikhubFatal | None = None
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = {
            pool.submit(_fetch_queries_limited, queries, cutoff=cutoff, limit=14, **job): idx
            for idx, job in enumerate(jobs)
        }
        for fut in as_completed(futures):
            try:
                results[futures[fut]] = fut.result()
            except TikhubFatal as e:
                fatal = e
            except TikhubError:
                # Stock-page heat is cross-source; one bad endpoint should not hide other sources.
                # Per-source settings tests still expose the exact failure.
                continue
    if fatal is not None and not any(results.values()):
        raise fatal
    for idx in range(len(jobs)):
        out.extend(results.get(idx, []))
    seen_urls: set[str] = set()
    deduped: list[dict] = []
    for it in out:
        url = it.get("url") or f"{it.get('source')}:{it.get('title')}"
        if url in seen_urls:
            continue
        seen_urls.add(url)
        deduped.append(it)
    return deduped[:60]
