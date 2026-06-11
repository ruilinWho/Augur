"""news 域纯逻辑：摄取触发、条目查询、趋势日报生成（LLM summarize 角色）。

I/O（网络在 ingest、磁盘在 storage、LLM 在 gateway）挡在外层，便于测试（CLAUDE.md §5）。
日报口径：只基于当日抓到的标题蒸馏，暴露不确定性、标注信源（§11）。一天一份，重生成覆盖。
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .. import runtime_config
from ..config import get_settings
from ..llm import gateway
from ..market import search
from ..storage import get_conn
from ..watchlist import service as wl
from . import (
    directed,
    edgar,
    grounding,
    ingest,
    linker,
    relevance,
    sources,
    stock_tag,
    ticker_news,
    tikhub,
    translate,
)

log = logging.getLogger("augur.news")


def _cap_items(items: list[dict], scope: str) -> list[dict]:
    """喂给「要点/机会」LLM 的当日条目上限（可配，`runtime_config.get_cluster_input_max`，
    默认 1000，0=不限；日报不受此限）。超出会**记日志**，不静默丢覆盖（CLAUDE.md 准则：
    封顶必须可见）。条目按时间倒序，截断保留最新的若干条。"""
    cap = runtime_config.get_cluster_input_max()
    if cap and len(items) > cap:
        log.info(
            "news %s: capped %d→%d items (configurable cluster_input_max; older items dropped)",
            scope,
            len(items),
            cap,
        )
        return items[:cap]
    return items


# 主题展示名与排序（前沿方向在前；与 classify.VALID_THEMES / 前端一致）
THEME_LABEL = {
    "ai": "大模型 / AI",
    "chips": "芯片 / 半导体",
    "robotics": "机器人",
    "space": "航天",
    "tech": "科技",
    "markets": "行情",
    "macro": "宏观 / 政策",
    "crypto": "加密",
    "world": "国际",
    "other": "其他",
}
THEME_ORDER = [
    "ai",
    "chips",
    "robotics",
    "space",
    "tech",
    "markets",
    "macro",
    "crypto",
    "world",
    "other",
]


def _item_out(row) -> dict:
    """row → dict，并把 topics(JSON 字符串) 反序列化为列表。"""
    d = dict(row)
    try:
        d["topics"] = json.loads(d.get("topics") or "[]")
    except (json.JSONDecodeError, TypeError):
        d["topics"] = []
    return d


def _today() -> str:
    return datetime.now(ZoneInfo(get_settings().tz)).strftime("%Y-%m-%d")


_refresh_lock = threading.Lock()


def _utc_now_sql() -> str:
    """SQLite datetime() 友好的 UTC 时间戳。"""
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def mark_news_read() -> dict:
    """把「知」信息流已读基准推进到当前时刻。刷新任务成功跑完后自动调用。"""
    runtime_config.set_news_read_at(_utc_now_sql())
    return news_read_state()


def news_read_state() -> dict:
    """标题行的「自上次以来」状态。按 fetched_at 计数，覆盖新闻/博客/社媒/定向 lane。"""
    last = runtime_config.get_news_read_at()
    fresh = 0
    if last:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM news_items WHERE datetime(fetched_at) > datetime(?)",
                (last,),
            ).fetchone()
            fresh = int(row["n"] if row else 0)
    return {"last_read_at": last, "fresh_count": fresh}


def refresh() -> dict:
    """抓取→翻译→投资相关性过滤（均 cheap 角色，失败降级不阻断）。

    进程级互斥：手动 POST /refresh 与定时 job（或两次手动）撞上时，后到的不并行打源（§11 尊重
    限流），直接返回零结果（前端显「+0」无害）。
    """
    if not _refresh_lock.acquire(blocking=False):
        return {
            "fetched": 0,
            "inserted": 0,
            "sources_ok": 0,
            "sources_failed": 0,
            "failures": [],
        }
    try:
        result = ingest.ingest_all()
        try:
            result["translated"] = translate.translate_pending()
        except Exception:  # noqa: BLE001
            result["translated"] = 0
        try:
            result["filtered"] = relevance.judge_pending()  # cheap LLM 滤掉与投资无关的
        except Exception:  # noqa: BLE001
            result["filtered"] = {"judged": 0, "dropped": 0}
        try:
            result["linked"] = linker.link_pending()  # 确定性挂钩到自选股 ticker（零幻觉）
        except Exception:  # noqa: BLE001
            result["linked"] = {"linked": 0, "pairs": 0}
        try:
            # LLM 标股（不限自选，接地到真实代码）——让新闻卡显相关股，看到新闻就能去看那只票
            result["tagged"] = stock_tag.tag_pending()
        except Exception:  # noqa: BLE001
            result["tagged"] = {"tagged": 0, "pairs": 0}
        result["read_state"] = mark_news_read()
        return result
    finally:
        _refresh_lock.release()


# 社媒 lane 的 source 前缀（与 consts.ts SOURCE_LANES 对齐）。社媒在「知」里与新闻区别对待：
# ① 用户主动进社媒 lane 看原貌 → 不套用为新闻从严调的 relevance 过滤（否则带货/生活方式被全杀，
#    实测 87% 社媒帖被判 relevance=2）；② 新闻/日报/要点反过来排除社媒前缀，免社媒噪音污染；
# ③ 社媒按**抓取日 fetched_at** 归桶——搜索来的社媒「今天抓到的」归到「今天」才符合直觉
#    （否则按帖子发布日散落到过去几天，「今天」永远空）。
_SOCIAL_PREFIXES = ("X·", "小红书·", "Threads·", "Reddit·")


def _date_col(source_prefix: str | None) -> str:
    """归桶/排序日期列：社媒按抓取日 fetched_at，新闻按发布日（缺则抓取日兜底）。"""
    if source_prefix in _SOCIAL_PREFIXES:
        return "fetched_at"
    return "COALESCE(published_at, fetched_at)"


def _lane_where(source_prefix: str | None) -> tuple[str, list]:
    """relevance / 社媒隔离 WHERE 片段（接在 lane='feed' 之后，其 args 排在最前）。"""
    if source_prefix in _SOCIAL_PREFIXES:
        return "", []  # 社媒 lane：不按 relevance 过滤，看原貌
    if source_prefix is None:
        # 新闻/通用：保留 relevance!=2 + 排除社媒前缀（社媒不进新闻/日报/要点）
        frag = " AND relevance != 2" + " AND source NOT LIKE ?" * len(_SOCIAL_PREFIXES)
        return frag, [f"{p}%" for p in _SOCIAL_PREFIXES]
    return " AND relevance != 2", []


def recent_items(
    limit: int = 60,
    theme: str | None = None,
    source_prefix: str | None = None,
    category: str | None = None,
    days: int | None = None,
    day: str | None = None,
) -> list[dict]:
    """最近条目（按发布时间倒序，缺时间用抓取时间兜底）。可按 theme / source 前缀 / 近 days 天过滤。

    source_prefix 供「推特」视图取 X·<handle> 源（传 "X·"）；days 供时间范围（近 N 天，看历史）。
    day 给定 → 只取那个**日历日**（某天快照「当日要闻」），优先于 days。
    新闻一直持久化在 news_items（不按龄删除），day/days 让作者翻看已存历史而非只看当前。
    """
    if day:
        return linker.attach_symbols(items_for_day(day, theme, source_prefix, category)[:limit])
    conn = get_conn()
    try:
        # lane='feed'：全局流（RSS+社媒）；定向抓取（lane='ticker'）只服务个股视图。
        # relevance/社媒隔离与日期列按 lane 分（见 _lane_where/_date_col）。
        dc = _date_col(source_prefix)
        where, wargs = _lane_where(source_prefix)
        sql = f"SELECT * FROM news_items WHERE lane = 'feed'{where}"
        args: list = list(wargs)
        if theme:
            sql += " AND theme = ?"
            args.append(theme)
        if source_prefix:
            sql += " AND source LIKE ?"
            args.append(f"{source_prefix}%")
        if category:
            sql += " AND category = ?"
            args.append(category)
        if days and days > 0:
            lo, _ = _window_bounds_utc(days)
            sql += f" AND datetime({dc}) >= datetime(?)"
            args.append(lo)
        sql += f" ORDER BY {dc} DESC LIMIT ?"
        args.append(limit)
        items = [_item_out(r) for r in conn.execute(sql, args).fetchall()]
        return linker.attach_symbols(items)  # 挂上关联自选股 ticker chip
    finally:
        conn.close()


def _day_bounds_utc(day: str | None) -> tuple[str, str]:
    """某日（作者时区）的 [起,止) → UTC 'YYYY-MM-DD HH:MM:SS'（供 sqlite datetime() 比较）。"""
    tz = ZoneInfo(get_settings().tz)
    if day:
        start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=tz)
    else:
        start = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    utc = ZoneInfo("UTC")
    return (
        start.astimezone(utc).strftime("%Y-%m-%d %H:%M:%S"),
        (start + timedelta(days=1)).astimezone(utc).strftime("%Y-%m-%d %H:%M:%S"),
    )


def _window_bounds_utc(days: int) -> tuple[str, str]:
    """近 days 天（含今天，作者时区，日对齐）的 [起,止) → UTC 字符串。"""
    tz = ZoneInfo(get_settings().tz)
    end = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    start = end - timedelta(days=max(1, days))
    utc = ZoneInfo("UTC")
    return (
        start.astimezone(utc).strftime("%Y-%m-%d %H:%M:%S"),
        end.astimezone(utc).strftime("%Y-%m-%d %H:%M:%S"),
    )


def _items_between(
    lo: str,
    hi: str,
    theme: str | None = None,
    source_prefix: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """[lo, hi)（UTC 字符串）内的条目（lane='feed'），时间倒序。
    共享 SQL，供 items_for_window / items_for_day（唯一差别是时间边界来源）。
    relevance/社媒隔离与日期列按 lane 分（见 _lane_where/_date_col）：社媒不滤 relevance、按抓取日。
    """
    conn = get_conn()
    try:
        dc = _date_col(source_prefix)
        where, wargs = _lane_where(source_prefix)
        sql = (
            f"SELECT * FROM news_items WHERE lane = 'feed'{where} "
            f"AND datetime({dc}) >= datetime(?) AND datetime({dc}) < datetime(?)"
        )
        args: list = [*wargs, lo, hi]
        if theme:
            sql += " AND theme = ?"
            args.append(theme)
        if source_prefix:
            sql += " AND source LIKE ?"
            args.append(f"{source_prefix}%")
        if category:
            sql += " AND category = ?"
            args.append(category)
        sql += f" ORDER BY {dc} DESC"
        return [_item_out(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def items_for_window(
    days: int = 1,
    theme: str | None = None,
    source_prefix: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """近 days 天的相关条目（relevance!=2），时间倒序。供「要点」按时间范围/主题/推特聚类。"""
    lo, hi = _window_bounds_utc(days)
    return _items_between(lo, hi, theme, source_prefix, category)


def items_for_day(
    day: str | None = None,
    theme: str | None = None,
    source_prefix: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """某日（默认今天，作者时区）的相关条目（relevance!=2），时间倒序。

    theme/source_prefix/category 过滤同 items_for_window——供「资讯·某天·新闻/推特」按天取。
    """
    lo, hi = _day_bounds_utc(day)
    return _items_between(lo, hi, theme, source_prefix, category)


def _item_is_social(it: dict) -> bool:
    src = str(it.get("source") or "")
    return any(src.startswith(p) for p in _SOCIAL_PREFIXES)


def _item_sort_time(it: dict) -> str:
    """综合日报排序时间：社媒按抓取日，其余按发布时间（缺则抓取日）。"""
    if _item_is_social(it):
        return str(it.get("fetched_at") or "")
    return str(it.get("published_at") or it.get("fetched_at") or "")


def digest_items_for_day(day: str | None = None) -> list[dict]:
    """综合日报输入：普通新闻/RSS/博客 + 所有社媒 lane，一篇日报里统一蒸馏。

    普通新闻沿用 relevance 过滤；社媒沿用各自 lane 的规则（不套新闻 relevance、按抓取日归桶）。
    只在日报使用，避免污染「新闻」板块的单独时间线。
    """
    items = list(items_for_day(day))
    seen = {int(it["id"]) for it in items}
    for prefix in _SOCIAL_PREFIXES:
        for it in items_for_day(day, source_prefix=prefix):
            iid = int(it["id"])
            if iid not in seen:
                seen.add(iid)
                items.append(it)
    items.sort(key=_item_sort_time, reverse=True)
    return items


def items_for_symbol(symbol: str, days: int = 0, limit: int = 60) -> list[dict]:
    """某自选股**持久化挂钩**的新闻流（定向 lane ∪ 任何挂到它的聚合条目），时间倒序。

    供个股「标的叙事」与个股新闻流。不按 relevance 过滤——作者主动跟踪的票，全给他看。
    days>0 限近 N 天（日对齐，作者时区）。
    """
    conn = get_conn()
    try:
        sql = (
            "SELECT ni.* FROM news_items ni "
            "JOIN news_item_symbols nis ON nis.news_id = ni.id "
            "WHERE nis.symbol = ?"
        )
        args: list = [symbol]
        if days and days > 0:
            lo, _ = _window_bounds_utc(days)
            sql += " AND datetime(COALESCE(ni.published_at, ni.fetched_at)) >= datetime(?)"
            args.append(lo)
        sql += " ORDER BY COALESCE(ni.published_at, ni.fetched_at) DESC LIMIT ?"
        args.append(limit)
        return [_item_out(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def refresh_directed(symbols: list[str] | None = None) -> dict:
    """触发个股定向抓取：雅虎逐 ticker + 已启用的每股专属信源。"""
    from . import stock_sources

    syms = symbols if symbols is not None else directed.watchlist_symbols()
    base = directed.refresh_watchlist(syms)
    custom = stock_sources.refresh_many(syms)
    for sym in syms:
        _stock_clean_cache.pop(sym, None)
        _stock_brief_cache.pop(sym, None)
        _stock_social_cache.pop(sym, None)
    return {**base, "stock_sources": custom, "read_state": mark_news_read()}


def _stock_terms(symbol: str) -> list[str]:
    """某标的的匹配词：中文展示名 + 英文名(首词)。用于在新闻标题里找相关资讯。"""
    terms: set[str] = set()
    market, _, code = symbol.partition(":")
    dn = search.display_name(symbol)
    if dn and len(dn) >= 2 and dn != code:
        terms.add(dn)
    hits = search.search(code, market=market, limit=1)
    if hits:
        for v in (hits[0].get("name"), hits[0].get("sub")):
            v = (v or "").strip()
            if len(v) >= 2:
                terms.add(v)
                tok = re.split(r"[\s,，]", v)[0]  # NVIDIA Corporation → NVIDIA
                if tok.isascii() and len(tok) >= 3:
                    terms.add(tok)
    return [t for t in terms if len(t) >= 2]


def _feed_matches(symbol: str, limit: int = 20) -> list[dict]:
    """聚合流里按公司名（中文展示名 + 英文名）匹配到的相关条目（含中文翻译）。

    SQL LIKE 只做粗筛，再在 Python 侧用**词边界**二次过滤 ASCII 词（CJK 仍子串）——与 linker 同
    口径，避免 'Arm'→harm/farm、'AMD'→子串 等短英文 token 误配把无关新闻塞进个股相关资讯。
    """
    terms = _stock_terms(symbol)
    if not terms:
        return []
    ascii_t = [t.lower() for t in terms if t.isascii()]
    cjk_t = [t for t in terms if not t.isascii()]
    pat = re.compile(rf"\b(?:{'|'.join(re.escape(t) for t in ascii_t)})\b") if ascii_t else None
    conn = get_conn()
    try:
        clause = " OR ".join(["title LIKE ? OR title_zh LIKE ?"] * len(terms))
        args: list = []
        for t in terms:
            like = f"%{t}%"
            args += [like, like]
        # 多取些候选给 Python 词边界过滤后再截断（粗筛会带进 LIKE 误命中）
        args.append(limit * 4)
        rows = conn.execute(
            f"SELECT * FROM news_items WHERE ({clause}) AND relevance != 2 "
            "ORDER BY COALESCE(published_at, fetched_at) DESC LIMIT ?",
            args,
        ).fetchall()
    finally:
        conn.close()
    out: list[dict] = []
    for r in rows:
        text = f"{r['title']} {r['title_zh'] or ''}"
        if (pat and pat.search(text.lower())) or any(t in text for t in cjk_t):
            out.append(_item_out(r))
        if len(out) >= limit:
            break
    return out


def _norm_url(u: str) -> str:
    return (u or "").split("?")[0].rstrip("/").lower()


_stock_clean_cache: dict[str, tuple[float, list[dict]]] = {}
_STOCK_CLEAN_TTL = 3600.0  # 个股相关新闻 LLM 清洗结果缓存 1h
_stock_brief_cache: dict[str, tuple[float, dict]] = {}
_stock_social_cache: dict[str, tuple[float, dict]] = {}
_STOCK_SOCIAL_TTL = 1800.0


def _clean_stock_news_llm(items: list[dict]) -> list[dict]:
    """cheap 模型：去标题党/与投资无关、译非中文、去重。未配/失败/全空 → 原样返回。"""
    try:
        gateway.check_ready("cheap")
    except gateway.LLMNotConfigured:
        return items
    block = "\n".join(
        f"[{i + 1}] [{it['source']}] {it.get('title_zh') or it['title']}"
        for i, it in enumerate(items)
    )
    prompt = _load_prompt("stock_news_clean").replace("{{ITEMS}}", block)
    try:
        raw = gateway.complete(
            [{"role": "user", "content": prompt}],
            role="cheap",
            response_format={"type": "json_object"},
        )
        data = _parse_json_lenient(raw)
    except Exception:  # noqa: BLE001
        return items
    kept = data.get("kept") if isinstance(data, dict) else None
    if not isinstance(kept, list):
        return items
    out: list[dict] = []
    used: set[int] = set()
    for k in kept:
        if not isinstance(k, dict):
            continue
        try:
            idx = int(k.get("i")) - 1
        except (TypeError, ValueError):
            continue
        if idx < 0 or idx >= len(items) or idx in used:
            continue
        used.add(idx)
        it = dict(items[idx])
        zh = k.get("zh")
        if isinstance(zh, str) and zh.strip():
            it["title_zh"] = zh.strip()[:300]
        out.append(it)
    return out or items  # 全空 → 原样（防误清空）


def _clean_stock_news(symbol: str, items: list[dict]) -> list[dict]:
    """LLM 清洗个股相关新闻（缓存 1h）。"""
    if not items:
        return items
    now = time.time()
    hit = _stock_clean_cache.get(symbol)
    if hit and now - hit[0] < _STOCK_CLEAN_TTL:
        return hit[1]
    cleaned = _clean_stock_news_llm(items)
    _stock_clean_cache[symbol] = (now, cleaned)
    return cleaned


def news_for_symbol(symbol: str, limit: int = 20) -> list[dict]:
    """个股相关新闻：雅虎逐-ticker API ∪ 持久化挂钩流 ∪ 聚合流按公司名匹配，
    url 去重、时间倒序。持久化挂钩流包含每股专属信源、定向 lane 与 LLM/确定性挂钩条目。
    """
    out: list[dict] = []
    seen: set[str] = set()
    nid = -1
    for it in ticker_news.ticker_news(symbol, limit=limit):
        u = _norm_url(it["url"])
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(
            {
                "id": nid,  # API 条目无 DB id，给负数占位（前端只用作 key）
                "source": it["source"],
                "title": it["title"],
                "url": it["url"],
                "summary": it.get("summary") or "",
                "lang": "en",
                "category": "",
                "published_at": it["published_at"],
                "theme": "",
                "topics": [],
                "title_zh": None,
            }
        )
        nid -= 1
    for it in items_for_symbol(symbol, days=45, limit=limit):
        u = _norm_url(it["url"])
        if u in seen:
            continue
        seen.add(u)
        out.append(it)
    for it in _feed_matches(symbol, limit):
        u = _norm_url(it["url"])
        if u in seen:
            continue
        seen.add(u)
        out.append(it)
    out.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    return _clean_stock_news(symbol, out[:limit])


def stock_news_brief(symbol: str, limit: int = 32, role: str = "cheap") -> dict:
    """个股「相关资讯」摘要：AI 筛选+合成要点，前端不再铺直接新闻列表。

    原始资讯仍用于生成与来源计数，但 UI 只呈现 summary/points/risks。若模型未配置，让路由返回
    503；不要降级成直接新闻列表（作者明确要求“只能 AI 筛选 + 总结要点”）。
    """
    gateway.check_ready(role)
    now = time.time()
    hit = _stock_brief_cache.get(symbol)
    if hit and now - hit[0] < _STOCK_CLEAN_TTL:
        return hit[1]
    items = news_for_symbol(symbol, limit=limit)
    if not items:
        data = {
            "symbol": symbol,
            "summary": "",
            "points": [],
            "risks": [],
            "source_count": 0,
            "generated_at": datetime.now(ZoneInfo(get_settings().tz)).isoformat(),
        }
        _stock_brief_cache[symbol] = (now, data)
        return data
    lines: list[str] = []
    by_n: dict[int, dict] = {}
    for i, it in enumerate(items, start=1):
        by_n[i] = it
        day = (it.get("published_at") or it.get("fetched_at") or "")[:10]
        title = _strip_inline_refs(it.get("title_zh") or it["title"])
        src = it.get("source") or ""
        lines.append(f"[{i}] ({day or '日期不详'}) [{src}] {title}")
        # 有摘要就附一行正文——让模型有正文可总结，而非只有标题（个股资讯加厚的关键）
        summ = _strip_inline_refs(str(it.get("summary") or "")).strip()
        if summ:
            lines.append(f"    {summ[:280]}")
    prompt = (
        _load_prompt("stock_news_brief")
        .replace("{{SYMBOL}}", f"{search.display_name(symbol)} / {symbol}")
        .replace("{{ITEMS}}", "\n".join(lines))
    )
    data = _complete_json(prompt, role, "summary")
    out = {
        "symbol": symbol,
        "summary": _strip_inline_refs(str(data.get("summary") or ""))[:260]
        if isinstance(data, dict)
        else "",
        "points": _cited_points(data.get("points") if isinstance(data, dict) else [], by_n, 6),
        "risks": _cited_points(data.get("risks") if isinstance(data, dict) else [], by_n, 4),
        "source_count": len(items),
        "generated_at": datetime.now(ZoneInfo(get_settings().tz)).isoformat(),
    }
    _stock_brief_cache[symbol] = (now, out)
    return out


def _cited_points(raw: object, by_n: dict[int, dict], limit: int, max_refs: int = 3) -> list[dict]:
    """把 LLM 的 [{text, refs:[n]}]（或兼容纯字符串）转成带原始链接的要点。

    refs 编号映射回 by_n 的条目 → [{source, url}]，去重、上限 max_refs。说人话 + 可溯源。
    """
    out: list[dict] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if isinstance(item, str):
            text, ref_ns = item, []
        elif isinstance(item, dict):
            text = str(item.get("text") or "")
            ref_ns = item.get("refs") or []
        else:
            continue
        text = _strip_inline_refs(text).strip()[:200]
        if not text:
            continue
        refs: list[dict] = []
        seen: set[str] = set()
        for nv in ref_ns if isinstance(ref_ns, list) else []:
            ok = isinstance(nv, int) or (isinstance(nv, str) and str(nv).isdigit())
            key = int(nv) if ok else None
            it = by_n.get(key) if key is not None else None
            url = (it or {}).get("url") or ""
            if it and url and url not in seen:
                seen.add(url)
                refs.append({"source": it.get("source") or "", "url": url})
            if len(refs) >= max_refs:
                break
        out.append({"text": text, "refs": refs})
        if len(out) >= limit:
            break
    return out


def _platform_counts(items: list[dict]) -> dict[str, int]:
    counts = {"推特": 0, "小红书": 0, "Threads": 0, "Reddit": 0}
    for it in items:
        src = it.get("source") or ""
        if src.startswith("X·"):
            counts["推特"] += 1
        elif src.startswith("小红书·"):
            counts["小红书"] += 1
        elif src.startswith("Threads·"):
            counts["Threads"] += 1
        elif src.startswith("Reddit·"):
            counts["Reddit"] += 1
    return {k: v for k, v in counts.items() if v > 0}


def _social_heat_empty(symbol: str, configured: bool, status: str) -> dict:
    return {
        "symbol": symbol,
        "configured": configured,
        "status": status,
        "summary": "",
        "sentiment": "不明",
        "heat": "低",
        "bull_points": [],
        "bear_points": [],
        "watch": [],
        "source_count": 0,
        "platforms": {},
        "generated_at": datetime.now(ZoneInfo(get_settings().tz)).isoformat(),
    }


def stock_social_heat(symbol: str, role: str = "cheap") -> dict:
    """个股社媒热度：TikHub 多源搜索 → AI 摘要。

    这是投资判据里的弱信号层：只暴露观点分布、热度和反证方向，不把原始帖子洪流铺给作者。
    """
    now = time.time()
    hit = _stock_social_cache.get(symbol)
    if hit and now - hit[0] < _STOCK_SOCIAL_TTL:
        return hit[1]
    if not runtime_config.has_secret("TIKHUB_KEY"):
        out = _social_heat_empty(symbol, False, "待配置 TIKHUB_KEY")
        _stock_social_cache[symbol] = (now, out)
        return out

    try:
        items = tikhub.social_search_for_stock(_stock_terms(symbol))
    except Exception as e:  # noqa: BLE001 — 前端需要中文诊断，而不是 500
        from .source_test import diagnose_problem

        out = _social_heat_empty(symbol, True, diagnose_problem("tikhub_twitter", e))
        _stock_social_cache[symbol] = (now, out)
        return out

    counts = _platform_counts(items)
    if not items:
        out = _social_heat_empty(symbol, True, "近 7 天没有抓到可用社媒信号")
        _stock_social_cache[symbol] = (now, out)
        return out

    lines: list[str] = []
    by_n: dict[int, dict] = {}
    for i, it in enumerate(items[:40], start=1):
        by_n[i] = it
        day = (it.get("published_at") or "")[:10] or "日期不详"
        src = it.get("source") or ""
        title = _strip_inline_refs(it.get("title_zh") or it["title"])
        summary = _strip_inline_refs(it.get("summary") or "")
        lines.append(f"[{i}] ({day}) [{src}] {title}" + (f" - {summary}" if summary else ""))
    name = search.display_name(symbol)
    heading = (
        f"下面是小红书/推特/Reddit/Threads 上关于 {name} / {symbol} 的帖子（每条带编号 `[n]`、"
        "日期、平台、内容）。请用大白话告诉我「网上和这只股票投资相关的讨论与情绪」。"
    )
    prompt = f"""{heading}

**只看与股价多空/投资相关的**：业绩与指引、产品与技术、订单与产能、竞争与份额、监管与政策、
资金与持仓、估值、明确的看多/看空理由与情绪。**坚决丢掉**：招聘/求职/培训带货/职场吐槽、
生活方式、追星八卦、与这家公司投资逻辑无关的闲聊——这些不是投资信号，一条都不要进结论。

怎么写（要有深度，别敷衍）：
- **说人话、给细节**，像转述群里认真聊这只股票的人：具体到产品/客户/数字/事件，别用"市场情绪"
  "舆论关注"这种空话。同一论点多人提就说"不少人/多个帖子"，并把最有信息量的理由讲透。
- **尽量多挖**：把帖子里站得住的多空理由都列出来——bull/bear 各 **2–5 条**、watch **1–4 条**，
  宁可多给一条有料的，也别只丢三条就交差。每条聚焦一个点，不要把多件事塞进一句。
- 社媒是弱信号、噪音多：别当真，必须给出反方与需要观察的点；若多空分歧大，sentiment 填"分歧"。
- 每条都标注来自哪几条（`refs` 填编号，必须真实存在、可多个），我要能点回原帖核对。
- 不编价格、目标价、成交量。heat 只能填 低/中/高；sentiment 只能填 偏多/中性/偏空/分歧/不明。
- 如果筛完几乎没有投资相关讨论，summary 如实说「多是无关闲聊，没什么投资信号」，各列可空。

只输出 JSON（不要 Markdown）：
{{
  "summary": "2–3 句大白话：大家在热议这只股票的什么、分歧在哪、情绪偏哪边（只说投资相关的）",
  "heat": "低|中|高",
  "sentiment": "偏多|中性|偏空|分歧|不明",
  "bull_points": [{{"text": "有人看好什么——具体到理由/数字/事件", "refs": [2, 9]}}],
  "bear_points": [{{"text": "有人担心或唱空什么——具体点", "refs": [5]}}],
  "watch": [{{"text": "接下来值得盯的催化或验证点", "refs": [3]}}]
}}

帖子：
{chr(10).join(lines)}
"""
    try:
        data = _complete_json(prompt, role, "summary")
    except gateway.LLMNotConfigured:
        data = {}
    heat = str(data.get("heat") or "中") if isinstance(data, dict) else "中"
    if heat not in {"低", "中", "高"}:
        heat = "中"
    sentiment = str(data.get("sentiment") or "分歧") if isinstance(data, dict) else "分歧"
    if sentiment not in {"偏多", "中性", "偏空", "分歧", "不明"}:
        sentiment = "分歧"
    out = {
        "symbol": symbol,
        "configured": True,
        "status": "已生成",
        "summary": _strip_inline_refs(str(data.get("summary") or ""))[:240]
        if isinstance(data, dict)
        else "",
        "sentiment": sentiment,
        "heat": heat,
        "bull_points": _cited_points(
            data.get("bull_points") if isinstance(data, dict) else [], by_n, 5
        ),
        "bear_points": _cited_points(
            data.get("bear_points") if isinstance(data, dict) else [], by_n, 5
        ),
        "watch": _cited_points(data.get("watch") if isinstance(data, dict) else [], by_n, 4),
        "source_count": len(items),
        "platforms": counts,
        "generated_at": datetime.now(ZoneInfo(get_settings().tz)).isoformat(),
    }
    if not out["summary"]:
        out["summary"] = f"抓到 {len(items)} 条 TikHub 社媒信号，模型未配置或未能生成摘要。"
    _stock_social_cache[symbol] = (now, out)
    return out


def stock_official(symbol: str, limit: int = 15) -> list[dict]:
    """某标的的官方一手文件（美股＝SEC EDGAR 申报；其他市场暂空）。

    "一条龙"骨架：未来在此并入官方 IR/新闻室 RSS、官方 X（凭桥接 key 启用）。
    """
    return edgar.filings_for(symbol, limit)


def _report_out(row: dict) -> dict:
    """落库行 → 对外结构化日报形状。body 为结构化 JSON 则解析；旧 markdown 报告进 markdown 兜底。"""
    body = row.get("body") or ""
    out = {
        "report_date": row["report_date"],
        "verdict": "",
        "sections": [],
        "risks": [],
        "watch": [],
        "markdown": "",
        "model": row.get("model") or "",
        "item_count": row.get("item_count") or 0,
        "created_at": row.get("created_at"),
    }
    try:
        obj = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        obj = None
    if isinstance(obj, dict) and ("sections" in obj or "verdict" in obj):
        out["verdict"] = obj.get("verdict") or ""
        out["sections"] = obj.get("sections") or []
        out["risks"] = obj.get("risks") or []
        out["watch"] = obj.get("watch") or []
    else:
        out["markdown"] = body  # 旧 markdown 报告：前端回退 <Markdown> 渲染
    return out


def get_report(report_date: str | None = None) -> dict | None:
    """取某日（默认最新一份）结构化日报。"""
    conn = get_conn()
    try:
        if report_date:
            row = conn.execute(
                "SELECT * FROM news_reports WHERE report_date = ?", (report_date,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM news_reports ORDER BY report_date DESC LIMIT 1"
            ).fetchone()
        return _report_out(dict(row)) if row else None
    finally:
        conn.close()


def list_reports(limit: int = 30) -> list[dict]:
    """日报列表（含预览，不含全文）。预览取总判断（结构化）或正文首段（旧 markdown）。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT report_date, item_count, model, created_at, body "
            "FROM news_reports ORDER BY report_date DESC LIMIT ?",
            (limit,),
        ).fetchall()
        out: list[dict] = []
        for r in rows:
            d = dict(r)
            body = d.pop("body", "") or ""
            preview = ""
            try:
                obj = json.loads(body)
                if isinstance(obj, dict):
                    preview = obj.get("verdict") or ""
            except (json.JSONDecodeError, TypeError):
                preview = ""
            d["preview"] = (preview or body)[:160]
            out.append(d)
        return out
    finally:
        conn.close()


def _load_prompt(name: str) -> str:
    path = get_settings().resources_dir / "prompts" / f"{name}.md"
    return path.read_text(encoding="utf-8")


def _source_lane_label(source: str) -> str:
    if source.startswith("X·"):
        return "推特"
    if source.startswith("小红书·"):
        return "小红书"
    if source.startswith("Threads·"):
        return "Threads"
    if source.startswith("Reddit·"):
        return "Reddit"
    if source.startswith(sources.BLOG_SOURCE_PREFIX):
        return "博客"
    return "新闻"


def _save_report(report_date: str, body: str, model: str, item_count: int) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO news_reports (report_date, body, model, item_count) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(report_date) DO UPDATE SET "
            "body = excluded.body, model = excluded.model, "
            "item_count = excluded.item_count, created_at = datetime('now')",
            (report_date, body, model, item_count),
        )
        conn.commit()
    finally:
        conn.close()


def _digest_items_block(items: list[dict]) -> tuple[str, dict[int, dict]]:
    """带 [n] 编号、按主题分组、标来源类型的条目块 + 序号→item 回查表（喂结构化日报，便于
    分点引用 refs[n] 与公司接地）。"""
    by_theme: dict[str, list[dict]] = {}
    for it in items:
        by_theme.setdefault(it.get("theme") or "other", []).append(it)
    lines: list[str] = []
    by_n: dict[int, dict] = {}
    n = 0
    for th in THEME_ORDER:
        group = by_theme.get(th)
        if not group:
            continue
        lines.append(f"\n## {THEME_LABEL.get(th, th)}")
        for it in group:
            n += 1
            by_n[n] = it
            lane = _source_lane_label(str(it.get("source") or ""))
            title = (it.get("title_zh") or it.get("title") or "").strip()
            summ = (it.get("summary") or "").strip()
            tail = f"｜{summ[:160]}" if summ and summ != title else ""
            lines.append(f"[{n}] [{lane}｜{it.get('source', '')}] {title}{tail}")
    return "\n".join(lines).strip(), by_n


def _ground_related(companies: object, watched: dict, cap: int = 5) -> list[dict]:
    """LLM 给的公司名 → 确定性接地 MARKET:CODE（防编造，只信本地目录∪东财命中）+ 交叉自选，
    产出「看/研」chip 数据。与 generate_opportunities 同口径。"""
    out: list[dict] = []
    seen: set[str] = set()
    if not isinstance(companies, list):
        return out
    for c in companies:
        if not isinstance(c, dict):
            continue
        sym, disp, resolved = grounding.resolve_company(
            c.get("name", ""), c.get("market", ""), c.get("code_guess", "")
        )
        key = sym or disp
        if not key or key in seen:
            continue
        seen.add(key)
        secs = watched.get(sym, []) if sym else []
        out.append(
            {
                "symbol": sym,
                "name": disp,
                "market": (c.get("market") or "").upper(),
                "resolved": resolved,
                "in_watchlist": bool(secs),
                "sections": secs,
            }
        )
        if len(out) >= cap:
            break
    return out


def _assemble_report(data: dict, by_n: dict[int, dict]) -> dict:
    """LLM 结构化输出 → 接地公司 + 解析引用后的日报 dict（落库即此形状）。

    sections 按重要性稳定排序（同级保留 LLM 顺序）。headline 必填，空段丢弃。
    """
    watched = _watched()
    sections: list[dict] = []
    for s in (data.get("sections") or [])[:10]:
        if not isinstance(s, dict):
            continue
        headline = _strip_inline_refs(str(s.get("headline") or "")).strip()
        if not headline:
            continue
        imp = s.get("importance", "med")
        sections.append(
            {
                "headline": headline[:200],
                "importance": imp if imp in _IMP_ORDER else "med",
                "why": _strip_inline_refs(str(s.get("why") or "")).strip()[:220],
                "points": _cited_points(s.get("points"), by_n, 6),
                "related": _ground_related(s.get("companies"), watched),
            }
        )
    sections.sort(key=lambda s: _IMP_ORDER.get(s["importance"], 2))  # 稳定：同级保 LLM 顺序
    return {
        "verdict": _strip_inline_refs(str(data.get("verdict") or "")).strip()[:600],
        "sections": sections,
        "risks": _cited_points(data.get("risks"), by_n, 8),
        "watch": _cited_points(data.get("watch"), by_n, 8),
    }


def generate_report(report_date: str | None = None, role: str = "summarize") -> dict:
    """生成**结构化**综合日报：一次结构化 LLM 调用 → 接地公司 → 落库覆盖当天，返回结构化报告。

    分层分点、个股「看/研」可点——取代旧的 markdown 长文（作者：太长无法专注）。无新闻 → ValueError。
    """
    rd = report_date or _today()
    items = _cap_items(digest_items_for_day(rd), "digest")  # 当天全部来源：新闻/RSS/博客/社媒
    if not items:
        raise ValueError("今日暂无新闻，请先刷新（POST /news/refresh）")
    block, by_n = _digest_items_block(items)
    prompt = _load_prompt("news_digest").replace("{{DATE}}", rd).replace("{{ITEMS}}", block)
    _, model = gateway.resolve_role(role)
    data = _complete_json(prompt, role, "sections")  # 解析空/缺 sections 则重试
    report = _assemble_report(data, by_n)
    _save_report(rd, json.dumps(report, ensure_ascii=False), model, len(items))
    return get_report(rd) or {
        "report_date": rd,
        **report,
        "markdown": "",
        "model": model,
        "item_count": len(items),
        "created_at": None,
    }


# ───────────────────────── 今日投资机会（抽取 + 接地）─────────────────────────


def _extract_object(s: str) -> dict:
    """从第一个 '{' 起做**字符串感知的括号配平**，截出最外层 JSON 对象（容忍前言/后缀文字）。"""
    start = s.find("{")
    if start < 0:
        return {}
    depth = 0
    in_str = esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(s[start : i + 1])
                    return obj if isinstance(obj, dict) else {}
                except json.JSONDecodeError:
                    return {}
    return {}


def _parse_json_lenient(raw: str) -> dict:
    """从 LLM 回复里尽力抽出 JSON 对象 → dict；失败 → {}（不抛 500）。

    应对推理模型（如 MiMo）偶发把 `<think>` 推理块 / 自然语言前言写进 content、或裹代码围栏、
    或 JSON 前后带杂字——这些会让朴素 `json.loads` 与贪婪正则失败（实测大输入下偶发空结果）。
    """
    s = (raw or "").strip()
    # 去推理模型内联的 <think>...</think>
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.DOTALL | re.IGNORECASE).strip()
    # 去代码围栏（``` / ```json，可能不在串首）
    if "```" in s:
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.DOTALL)
        if m:
            s = m.group(1).strip()
    try:  # 1) 直接解析（最常见）
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    obj = _extract_object(s)  # 2) 括号配平截最外层对象（容忍前后杂字）
    if obj:
        return obj
    m = re.search(r"\{.*\}", s, re.DOTALL)  # 3) 兜底：贪婪 first{..last}
    if m:
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


_INLINE_REF_RE = re.compile(r"(?:\s*\[\d{1,5}\])+")


def _strip_inline_refs(s: str) -> str:
    """去掉 LLM 从输入编号泄漏到标题/理由里的裸引用，如 [47][51][478]。"""
    return _INLINE_REF_RE.sub("", s or "").strip()


def _complete_json(prompt: str, role: str, want_key: str, attempts: int = 2) -> dict:
    """调 LLM 拿 JSON 并解析；若解析为空 / 缺 want_key，最多重试 attempts 次。

    应对推理模型在大输入下**偶发**产出非 JSON 前言/畸形（实测 MiMo 聚类 488 条时偶尔解析空，
    重试即得正常结果）——作者 bug：一键生成后看不到今日要事/机会。每次重试都是新一轮采样。
    """
    data: dict = {}
    for _ in range(max(1, attempts)):
        raw = gateway.complete(
            [{"role": "user", "content": prompt}],
            role=role,
            response_format={"type": "json_object"},
        )
        data = _parse_json_lenient(raw)
        if isinstance(data, dict) and data.get(want_key):
            return data
    return data if isinstance(data, dict) else {}


def _items_block(items: list[dict]) -> tuple[str, dict[int, dict]]:
    """带 [n] 序号的条目块 + 序号→item 回查表（喂中文标题，LLM 读着更准）。"""
    lines: list[str] = []
    by_n: dict[int, dict] = {}
    for n, it in enumerate(items, start=1):
        by_n[n] = it
        cat = f"({it.get('theme')}) " if it.get("theme") else ""
        title = it.get("title_zh") or it["title"]
        lines.append(f"[{n}] {cat}[{it['source']}] {title}")
    return "\n".join(lines), by_n


def _watched() -> dict[str, list[str]]:
    """symbol → 所属分区路径列表（用于 in_watchlist 高亮）。遍历自选分区树。"""
    paths: dict[str, list[str]] = {}

    def walk(node: dict, prefix: str) -> None:
        here = f"{prefix}/{node['name']}" if prefix else node["name"]
        for it in node.get("items", []):
            paths.setdefault(it["symbol"], []).append(here)
        for ch in node.get("children", []):
            walk(ch, here)

    for root in wl.list_tree(None):
        walk(root, "")
    return paths


def _save_opportunities(rd: str, opps: list[dict], model: str) -> None:
    conn = get_conn()
    try:
        conn.execute("DELETE FROM news_opportunities WHERE report_date = ?", (rd,))
        conn.executemany(
            "INSERT INTO news_opportunities "
            "(report_date, rank, title, thesis, theme, confidence, caveats, "
            "related, evidence, model) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    rd,
                    i,
                    o["title"],
                    o["thesis"],
                    o["theme"],
                    o["confidence"],
                    o["caveats"],
                    json.dumps(o["related"], ensure_ascii=False),
                    json.dumps(o["evidence"], ensure_ascii=False),
                    model,
                )
                for i, o in enumerate(opps)
            ],
        )
        conn.commit()
    finally:
        conn.close()


def get_opportunities(report_date: str | None = None) -> dict | None:
    """取某日（默认今天）已生成的机会列表；无 → None。"""
    rd = report_date or _today()
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM news_opportunities WHERE report_date = ? ORDER BY rank", (rd,)
        ).fetchall()
        if not rows:
            return None
        opps = [
            {
                "title": r["title"],
                "thesis": r["thesis"],
                "theme": r["theme"],
                "confidence": r["confidence"],
                "caveats": r["caveats"],
                "related": json.loads(r["related"] or "[]"),
                "evidence": json.loads(r["evidence"] or "[]"),
            }
            for r in rows
        ]
        return {
            "report_date": rd,
            "model": rows[0]["model"],
            "item_count": 0,
            "created_at": rows[0]["created_at"],
            "opportunities": opps,
        }
    finally:
        conn.close()


def generate_opportunities(report_date: str | None = None, role: str = "summarize") -> dict:
    """阶段 A（LLM 抽取）+ 阶段 B（确定性接地到 MARKET:CODE + 交叉自选）。落库覆盖当天。"""
    rd = report_date or _today()
    items = _cap_items(items_for_day(rd), "opportunities")  # 当天全部（封顶 200，超出记日志）
    if not items:
        raise ValueError("今日暂无新闻，请先刷新（POST /news/refresh）")
    block, by_n = _items_block(items)
    prompt = _load_prompt("news_opportunities").replace("{{DATE}}", rd).replace("{{ITEMS}}", block)
    _, model = gateway.resolve_role(role)
    data = _complete_json(prompt, role, "opportunities")  # 解析空则重试（推理模型偶发非 JSON）
    llm_opps = data.get("opportunities", [])
    watched = _watched()
    out: list[dict] = []
    for o in llm_opps[:8]:
        related = []
        for c in o.get("companies") or []:
            sym, disp, resolved = grounding.resolve_company(
                c.get("name", ""), c.get("market", ""), c.get("code_guess", "")
            )
            secs = watched.get(sym, []) if sym else []
            related.append(
                {
                    "symbol": sym,
                    "name": disp,
                    "market": (c.get("market") or "").upper(),
                    "resolved": resolved,
                    "in_watchlist": bool(secs),
                    "sections": secs,
                }
            )
        ev = []
        for n in o.get("evidence") or []:
            key = int(n) if isinstance(n, int) or (isinstance(n, str) and n.isdigit()) else None
            it = by_n.get(key) if key is not None else None
            if it:
                ev.append(
                    {
                        "news_id": it["id"],
                        "title": it.get("title_zh") or it["title"],
                        "source": it["source"],
                        "url": it["url"],
                    }
                )
        conf = o.get("confidence", "low")
        out.append(
            {
                "title": (o.get("title") or "")[:120],
                "thesis": o.get("thesis", ""),
                "theme": o.get("theme", ""),
                "confidence": conf if conf in ("low", "med", "high") else "low",
                "caveats": o.get("caveats", ""),
                "related": related,
                "evidence": ev,
            }
        )
    _save_opportunities(rd, out, model)
    return get_opportunities(rd) or {
        "report_date": rd,
        "model": model,
        "item_count": len(items),
        "created_at": None,
        "opportunities": [],
    }


# ───────────────────────── 标的叙事时间线（个股，融合定向抓取 + 申报）─────────────────────────


def _save_narrative(
    symbol: str, name: str, summary: str, timeline: list[dict], model: str, n: int
) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO stock_narratives (symbol, name, summary, timeline, model, item_count) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(symbol) DO UPDATE SET "
            "name=excluded.name, summary=excluded.summary, timeline=excluded.timeline, "
            "model=excluded.model, item_count=excluded.item_count, created_at=datetime('now')",
            (symbol, name, summary, json.dumps(timeline, ensure_ascii=False), model, n),
        )
        conn.commit()
    finally:
        conn.close()


def get_narrative(symbol: str) -> dict | None:
    """取某股已生成的叙事；无 → None。"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM stock_narratives WHERE symbol = ?", (symbol,)).fetchone()
        if not row:
            return None
        return {
            "symbol": row["symbol"],
            "name": row["name"],
            "summary": row["summary"],
            "timeline": json.loads(row["timeline"] or "[]"),
            "model": row["model"],
            "item_count": row["item_count"],
            "created_at": row["created_at"],
        }
    finally:
        conn.close()


def generate_narrative(symbol: str, role: str = "summarize") -> dict:
    """把某股近况（定向抓取 ∪ 挂钩聚合条目）融成「当前主线 + 时间线」。落库覆盖。

    若该股暂无挂钩资讯 → 先触发一次定向抓取再读。仍无 → ValueError。
    """
    items = items_for_symbol(symbol, days=45, limit=80)
    if not items:
        try:
            directed.refresh_watchlist([symbol])  # 现抓一次该股
        except Exception:  # noqa: BLE001
            pass
        items = items_for_symbol(symbol, days=45, limit=80)
    if not items:
        raise ValueError("该标的暂无可用资讯（试试右上「↻ 抓取最新」或在「看」里确认已自选）")
    # 叙事需要日期建时间线 → 用带日期的条目块（[n] (YYYY-MM-DD) [source] 标题）
    by_n: dict[int, dict] = {}
    lines: list[str] = []
    for n, it in enumerate(items, start=1):
        by_n[n] = it
        day = (it.get("published_at") or it.get("fetched_at") or "")[:10]
        title = it.get("title_zh") or it["title"]
        lines.append(f"[{n}] ({day or '日期不详'}) [{it['source']}] {title}")
    block = "\n".join(lines)
    name = search.display_name(symbol)
    prompt = (
        _load_prompt("stock_narrative")
        .replace("{{NAME}}", name)
        .replace("{{SYMBOL}}", symbol)
        .replace("{{ITEMS}}", block)
    )
    _, model = gateway.resolve_role(role)
    data = _complete_json(prompt, role, "timeline")  # 解析空则重试（推理模型偶发非 JSON）
    summary = (data.get("summary") or "") if isinstance(data, dict) else ""
    timeline: list[dict] = []
    for ev in (data.get("timeline") or [])[:20] if isinstance(data, dict) else []:
        refs: list[dict] = []
        seen: set[int] = set()
        for nv in ev.get("refs") or []:
            key = int(nv) if isinstance(nv, int) or (isinstance(nv, str) and nv.isdigit()) else None
            it = by_n.get(key) if key is not None else None
            if it and it["id"] not in seen:
                seen.add(it["id"])
                refs.append(
                    {
                        "source": it["source"],
                        "title": it.get("title_zh") or it["title"],
                        "url": it["url"],
                    }
                )
        imp = ev.get("importance", "med")
        timeline.append(
            {
                "date": (ev.get("date") or "")[:10],
                "title": (ev.get("title") or "")[:200],
                "importance": imp if imp in _IMP_ORDER else "med",
                "refs": refs,
            }
        )
    _save_narrative(symbol, name, summary.strip()[:600], timeline, model, len(items))
    return get_narrative(symbol) or {
        "symbol": symbol,
        "name": name,
        "summary": "",
        "timeline": [],
        "model": model,
        "item_count": len(items),
        "created_at": None,
    }


# ───────────────────────── 新闻「要点」：去重聚类 + 按重要性排序 ─────────────────────────
# 4 级重要性（含「非常重要」critical），值越小越靠前
_IMP_ORDER = {"critical": 0, "high": 1, "med": 2, "low": 3}


def _scope_part(s: str | None) -> str:
    """scope 只能是稳定短串，避免不同 source lane 共用旧缓存。

    坑：全非 ASCII 的前缀（如小红书）经正则清洗会塌缩成同一个 `_`——多个这种前缀会写进同一个
    scope 互相覆盖（历史上「微信」lane 一度显示的其实是「小红书」要点，微信源后来已删）。对清洗后
    没有 ASCII 信息的串，退回到原串的短哈希，保证每个中文前缀拿到稳定且唯一的 scope。
    """
    if not s:
        return "all"
    cleaned = re.sub(r"[^0-9A-Za-z_:-]+", "_", s.strip().rstrip("·"))[:40].strip("_")
    if cleaned:
        return cleaned
    return "h" + hashlib.md5(s.strip().rstrip("·").encode("utf-8")).hexdigest()[:8]


def _cluster_scope(
    theme: str | None, source_prefix: str | None, category: str | None, days: int
) -> str:
    """聚类范围 → 唯一 scope 串（存进 theme 列）。

    旧实现把所有 `source_prefix` 都归为 `tw:*`，导致 Reddit/小红书要点可能读到
    推特旧缓存。这里按真实 source lane 分 scope：news / src:Reddit / src:X …
    """
    if source_prefix:
        base = f"src:{_scope_part(source_prefix)}:{_scope_part(category)}"
    else:
        base = f"news:{theme or 'all'}"
    return f"{base}@{int(days)}d"


def _save_clusters(scope: str, clusters: list[dict], model: str, n: int, rd: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO news_clusters (report_date, theme, body, model, item_count) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(report_date, theme) DO UPDATE SET "
            "body=excluded.body, model=excluded.model, item_count=excluded.item_count, "
            "created_at=datetime('now')",
            (rd, scope, json.dumps(clusters, ensure_ascii=False), model, n),
        )
        conn.commit()
    finally:
        conn.close()


def get_clusters(
    theme: str | None = None,
    source_prefix: str | None = None,
    category: str | None = None,
    days: int = 1,
    day: str | None = None,
) -> dict | None:
    """取某天（day，默认今天）某 scope 的要点；无 → None。

    day 让历史某天的要点可回看（修「写死今天」——昨天的要点不再不可达）。
    """
    rd = day or _today()
    scope = _cluster_scope(theme, source_prefix, category, days)
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM news_clusters WHERE report_date = ? AND theme = ?",
            (rd, scope),
        ).fetchone()
        if not row:
            return None
        return {
            "report_date": rd,
            "scope": scope,
            "days": days,
            "clusters": json.loads(row["body"] or "[]"),
            "model": row["model"],
            "item_count": row["item_count"],
            "created_at": row["created_at"],
        }
    finally:
        conn.close()


def generate_clusters(
    theme: str | None = None,
    source_prefix: str | None = None,
    category: str | None = None,
    days: int = 1,
    role: str = "summarize",
    day: str | None = None,
) -> dict:
    """LLM 把某范围新闻去重聚类 + 按重要性排序。落库覆盖 (report_date, scope)。

    day 给定（如「某天快照」）→ 锚定那个日历日（`items_for_day`，days 视为 1）；
    否则按近 days 天滚动窗口、锚定今天。
    """
    rd = day or _today()
    # 封顶 200（实测可在合理时延内完成；更大会拖慢「生成要点」）；超出记日志、不静默丢。
    if day:
        items = _cap_items(items_for_day(day, theme, source_prefix, category), "clusters")
    else:
        items = _cap_items(items_for_window(days, theme, source_prefix, category), "clusters")
    if not items:
        raise ValueError("该范围暂无新闻，请先刷新（POST /news/refresh）")
    block, by_n = _items_block(items)
    prompt = _load_prompt("news_clusters").replace("{{DATE}}", rd).replace("{{ITEMS}}", block)
    _, model = gateway.resolve_role(role)
    data = _complete_json(prompt, role, "clusters")  # 解析空则重试（推理模型偶发非 JSON）
    raw_clusters = data.get("clusters", [])
    out: list[dict] = []
    for c in raw_clusters:
        members: list[dict] = []
        seen: set[int] = set()
        for nv in c.get("members") or []:
            key = int(nv) if isinstance(nv, int) or (isinstance(nv, str) and nv.isdigit()) else None
            it = by_n.get(key) if key is not None else None
            if it and it["id"] not in seen:
                seen.add(it["id"])
                members.append(
                    {
                        "source": it["source"],
                        "title": it.get("title_zh") or it["title"],
                        "url": it["url"],
                    }
                )
        if not members:
            continue  # 丢弃空簇（序号全无效）
        imp = c.get("importance", "med")
        out.append(
            {
                "headline": _strip_inline_refs(c.get("headline") or members[0]["title"])[:200],
                "importance": imp if imp in _IMP_ORDER else "med",
                "why": _strip_inline_refs(c.get("why") or "")[:160],
                "members": members,
            }
        )
    out.sort(key=lambda c: _IMP_ORDER.get(c["importance"], 2))  # 稳定：同重要性保留 LLM 顺序
    scope = _cluster_scope(theme, source_prefix, category, days)
    _save_clusters(scope, out, model, len(items), rd)
    return get_clusters(theme, source_prefix, category, days, day) or {
        "report_date": rd,
        "scope": scope,
        "days": days,
        "clusters": [],
        "model": model,
        "item_count": len(items),
        "created_at": None,
    }


# 社媒 lane → source 前缀（与前端 consts.ts SOURCE_LANES 对齐）。要点 scope 按前缀分。
_SOCIAL_LANES = {
    "twitter": "X·",
    "reddit": "Reddit·",
    "xiaohongshu": "小红书·",
    "threads": "Threads·",
}

# 非社媒但需要独立「资讯·板块」与预生成要点的 source_prefix。
_SOURCE_LANES = {
    "blogs": sources.BLOG_SOURCE_PREFIX,
}

# 兼容旧 /news/social-pulse：展示名 → source 前缀（与各 lane 一致）。
_PULSE_LANES = (
    ("推特", "X·"),
    ("小红书", "小红书·"),
    ("Threads", "Threads·"),
    ("Reddit", "Reddit·"),
)


def social_pulse(date: str | None = None, per_lane: int | None = None) -> dict:
    """各社媒 lane 已生成要点的聚合。

    这是兼容旧 UI 的零成本读接口：只读 generate_all 已落库的社媒 cluster（不触发 LLM），
    每个 lane 取按重要性排在前的若干条并附代表链接。当前「总结/决策」不再调用它；
    综合日报直接通过 digest_items_for_day() 吃新闻、博客和所有社媒原始条目。
    """
    if per_lane is None:
        per_lane = runtime_config.get_social_pulse_n()
    rd = date or _today()
    lanes: list[dict] = []
    for label, prefix in _PULSE_LANES:
        data = get_clusters(None, prefix, None, 1, rd)
        if not data:
            continue
        clusters = data.get("clusters") or []
        items: list[dict] = []
        for c in clusters[:per_lane]:
            members = (c.get("members") or [])[:3]
            head = members[0] if members else {}
            items.append(
                {
                    "platform": label,
                    "headline": _strip_inline_refs(c.get("headline") or ""),
                    "importance": c.get("importance") or "med",
                    "why": _strip_inline_refs(c.get("why") or ""),
                    "url": head.get("url") or "",
                    "source": head.get("source") or label,
                }
            )
        if items:
            lanes.append({"platform": label, "total": len(clusters), "items": items})
    return {"report_date": rd, "lanes": lanes, "platform_count": len(lanes)}


# ───────────────────────── 全部生成（刷新 + 蒸馏当天全套）─────────────────────────
def generate_all(
    date: str | None = None, refresh_first: bool = True, role: str = "summarize"
) -> dict:
    """「全部生成」：刷新信源（RSS+社媒+自选定向）+ 蒸馏当天各板块要点/机会。

    **单一真相**——供前端「一键刷新并生成」按钮与白天每小时自动调度共用（CLAUDE.md §6/§12）。
    每步独立成败、失败不阻断其余（§11 优雅降级）；LLM 未配置 → 只刷新、静默跳过蒸馏。
    返回各步状态供 UI 状态点 / 调度日志展示。
    """
    rd = date or _today()
    out: dict = {"date": rd, "steps": {}}
    if refresh_first:
        # feed 刷新（含翻译/相关性/标股 LLM 流水线）与自选定向抓取（纯抓取、喂个股叙事）彼此
        # 独立 → **并发**：把定向抓取的网络耗时藏进 feed 刷新的 LLM 阶段之下（前端「一键刷新并
        # 生成」早已 Promise.allSettled 这么做，这里对齐）。两者各用独立连接写库、WAL 串行化写。
        with ThreadPoolExecutor(max_workers=2) as ex:
            f_refresh = ex.submit(refresh)  # 摄取+翻译+相关性过滤+挂钩自选+LLM 标股
            f_directed = ex.submit(refresh_directed)  # 自选股定向抓取（按 ticker 直取）
            try:
                out["refresh"] = f_refresh.result()
            except Exception:  # noqa: BLE001
                out["refresh"] = {"error": True}
            try:
                out["directed"] = f_directed.result()
            except Exception:  # noqa: BLE001
                out["directed"] = {"error": True}
    try:
        gateway.check_ready(role)
    except gateway.LLMNotConfigured:
        out["llm_ready"] = False
        return out
    out["llm_ready"] = True
    steps = out["steps"]

    def _digest() -> None:
        generate_report(rd, role)  # 结构化日报：落库覆盖当天

    # 各生成彼此独立 → **并发**跑（作者：尽量并行、不担心 token）。各写不同表/scope，
    # SQLite WAL 串行化写。要事＝新闻「全部」要点（同 scope）；每个社媒 lane 单独 scope。
    # 社媒 lane（推特/小红书/Reddit/Threads）此前从不预生成 → 要点常年空；这里补齐，
    # 无数据的 lane generate_clusters 抛 ValueError 被吞为 'err'，不影响其余（§11 优雅降级）。
    # 博客 RSS 不是社媒，但作为独立「资讯·板块」也在这里预生成要点。
    tasks = {
        "digest": _digest,
        "clusters": lambda: generate_clusters(None, None, None, 1, role, rd),
        "opportunities": lambda: generate_opportunities(rd, role),
    }
    for name, prefix in {**_SOCIAL_LANES, **_SOURCE_LANES}.items():
        tasks[name] = (lambda p: lambda: generate_clusters(None, p, None, 1, role, rd))(prefix)
    with ThreadPoolExecutor(max_workers=len(tasks)) as ex:
        futs = {ex.submit(fn): name for name, fn in tasks.items()}
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                fut.result()
                steps[name] = "ok"
            except Exception:  # noqa: BLE001 — 单步失败只记状态，不连累其余
                steps[name] = "err"
    return out
