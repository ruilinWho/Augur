"""每股专属信源画像（CLAUDE.md §1 三支柱融合 · 知·个股）。

作者想法「组件化信源」：对某只股，先用 LLM（最好**联网**，如 Qwen/Deep Research）调研「该看哪些
重要信源」（官网/IR/官方X/大V/Reddit/雪球/财经站），存为**待确认候选**，作者逐个
mark（启用/增删）。启用的源会喂给定向抓取 lane（X→twtapi、Reddit→public JSON、
RSS/Atom→feedparser），汇入该股叙事与「看·相关资讯」。每只股一套、各不相同。

防幻觉（§11）：LLM 易编造句柄/URL → 候选默认 `enabled=0 verified=0`，由作者拍板；
能验证的后续验证（X 句柄过 twtapi、子版过 Reddit、RSS/Atom URL 探活）。调研走 `deep_research`
角色——作者把它指到联网模型即准；未配则 `LLMNotConfigured`，端点转可读提示。
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from ..llm import gateway
from ..market import search
from ..storage import get_conn
from . import classify, ingest, reddit, twtapi
from .service import _load_prompt, _parse_json_lenient

_VALID_KINDS = {
    "official",
    "ir",
    "official_x",
    "influencer_x",
    "reddit",
    "forum",
    "fin_site",
}
_HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{1,30}$")
_SUB_RE = re.compile(r"^[A-Za-z0-9_]{2,40}$")
_MAX_WORKERS = 6
_RECENT_DAYS = 30
_KIND_ORDER = {
    k: i
    for i, k in enumerate(
        ["official", "ir", "official_x", "influencer_x", "reddit", "forum", "fin_site"]
    )
}


def _row_out(r) -> dict:
    return {
        "id": r["id"],
        "symbol": r["symbol"],
        "kind": r["kind"],
        "name": r["name"],
        "ref": r["ref"],
        "note": r["note"],
        "enabled": bool(r["enabled"]),
        "verified": bool(r["verified"]),
        "added_by": r["added_by"],
    }


def list_sources(symbol: str) -> list[dict]:
    """某股的信源清单（启用在前，再按类别、id）。"""
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM stock_sources WHERE symbol = ?", (symbol,)).fetchall()
    finally:
        conn.close()
    out = [_row_out(r) for r in rows]
    out.sort(key=lambda s: (not s["enabled"], _KIND_ORDER.get(s["kind"], 9), s["id"]))
    return out


def enabled_sources(symbol: str) -> list[dict]:
    """某股已启用的专属信源。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM stock_sources WHERE symbol = ? AND enabled = 1", (symbol,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_out(r) for r in rows]


def _upsert(symbol: str, rows: list[tuple[str, str, str, str]], added_by: str) -> int:
    """批量插入候选（INSERT OR IGNORE：不覆盖已有的启用状态/人工编辑）。返回新插入数。"""
    if not rows:
        return 0
    conn = get_conn()
    try:
        before = conn.total_changes
        conn.executemany(
            "INSERT OR IGNORE INTO stock_sources (symbol, kind, name, ref, note, added_by) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(symbol, k, n, ref, note, added_by) for (k, n, ref, note) in rows],
        )
        conn.commit()
        return conn.total_changes - before
    finally:
        conn.close()


def discover(symbol: str, role: str = "deep_research") -> dict:
    """LLM 调研某股该看哪些信源 → 落库为待确认候选。返回 {discovered, sources}。

    走 `deep_research` 角色（作者指到联网模型即准）；未配置 → 抛 LLMNotConfigured。
    """
    gateway.check_ready(role)
    name = search.display_name(symbol)
    prompt = _load_prompt("stock_sources").replace("{{NAME}}", name).replace("{{SYMBOL}}", symbol)
    raw = gateway.complete(
        [{"role": "user", "content": prompt}],
        role=role,
        response_format={"type": "json_object"},
    )
    data = _parse_json_lenient(raw)
    cand = data.get("sources", []) if isinstance(data, dict) else []
    rows: list[tuple[str, str, str, str]] = []
    for c in cand:
        if not isinstance(c, dict):
            continue
        kind = (c.get("kind") or "").strip()
        if kind not in _VALID_KINDS:
            continue
        nm = (c.get("name") or "").strip()[:120]
        ref = (c.get("ref") or "").strip()[:300]
        if not nm and not ref:
            continue
        rows.append((kind, nm, ref, (c.get("note") or "").strip()[:120]))
    inserted = _upsert(symbol, rows, added_by="llm")
    return {"symbol": symbol, "discovered": inserted, "sources": list_sources(symbol)}


def add_source(symbol: str, kind: str, name: str, ref: str = "", note: str = "") -> dict:
    """手动加一个信源（默认启用）。返回更新后的清单。"""
    kind = kind.strip()
    if kind not in _VALID_KINDS:
        raise ValueError(f"未知信源类别 {kind!r}")
    name = name.strip()[:120]
    ref = ref.strip()[:300]
    if not name and not ref:
        raise ValueError("信源名与地址不能都为空")
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO stock_sources (symbol, kind, name, ref, note, enabled, added_by) "
            "VALUES (?, ?, ?, ?, ?, 1, 'manual') "
            "ON CONFLICT(symbol, kind, ref) DO UPDATE SET name=excluded.name, "
            "note=excluded.note, enabled=1",
            (symbol, kind, name, ref, note.strip()[:120]),
        )
        conn.commit()
    finally:
        conn.close()
    return {"symbol": symbol, "sources": list_sources(symbol)}


def set_enabled(source_id: int, enabled: bool) -> None:
    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE stock_sources SET enabled = ? WHERE id = ?",
            (1 if enabled else 0, source_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise ValueError(f"信源 {source_id} 不存在")
    finally:
        conn.close()


def delete_source(source_id: int) -> None:
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM stock_sources WHERE id = ?", (source_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise ValueError(f"信源 {source_id} 不存在")
    finally:
        conn.close()


def _x_handle(ref: str) -> str:
    r = (ref or "").strip().lstrip("@")
    if not r:
        return ""
    if r.startswith("http"):
        u = urlparse(r)
        host = u.netloc.lower()
        if host.endswith(("x.com", "twitter.com")):
            r = u.path.strip("/").split("/")[0]
    r = r.lstrip("@")
    return r if _HANDLE_RE.match(r) else ""


def _subreddit(ref: str) -> str:
    r = (ref or "").strip()
    if not r:
        return ""
    if r.startswith("http"):
        u = urlparse(r)
        host = u.netloc.lower()
        parts = [p for p in u.path.split("/") if p]
        if host.endswith("reddit.com") and len(parts) >= 2 and parts[0].lower() == "r":
            r = parts[1]
    r = r.removeprefix("r/").strip("/")
    return r if _SUB_RE.match(r) else ""


def _feed_url(ref: str) -> str:
    r = (ref or "").strip()
    if not r:
        return ""
    u = urlparse(r)
    if u.scheme not in {"http", "https"} or not u.netloc:
        return ""
    if u.netloc.lower().endswith(("x.com", "twitter.com", "reddit.com")):
        return ""
    return r


def _fetch_one(s: dict, cutoff: datetime) -> tuple[dict, list[dict], str]:
    """拉一个已启用源。返回 (source, items, problem)。problem 非空表示未支持/失败。"""
    kind = s["kind"]
    ref = s.get("ref") or s.get("name") or ""
    if kind in {"official_x", "influencer_x"}:
        handle = _x_handle(ref)
        if not handle:
            return s, [], "无法解析 X 账号"
        return s, twtapi.fetch_accounts([{"screen_name": handle, "category": "stock"}], cutoff), ""
    if kind == "reddit":
        sub = _subreddit(ref)
        if not sub:
            return s, [], "无法解析 Reddit 子版"
        return s, reddit.fetch_subreddits([sub], cutoff), ""
    url = _feed_url(ref)
    if url:
        items = ingest.fetch_feed(
            {"name": s.get("name") or ref, "url": url, "category": "stock_source"}, cutoff
        )
        return s, items, "" if items else "RSS/Atom 可达但没有新条目"
    return s, [], "暂只支持 X 账号、Reddit 子版、RSS/Atom URL"


def _store_items(symbol: str, stock_name: str, items: list[dict]) -> int:
    """把专属信源条目落入 ticker lane，并确定性挂到 symbol。"""
    if not items:
        return 0
    conn = get_conn()
    inserted = 0
    try:
        for it in items:
            url = (it.get("url") or "").strip()
            title = (it.get("title") or "").strip()
            if not url or not title:
                continue
            theme = it.get("theme") or ""
            topics = it.get("topics")
            if not theme:
                theme, parsed_topics = classify.classify_rule(
                    title, it.get("summary") or "", it.get("category") or "stock_source"
                )
                topics = json.dumps(parsed_topics, ensure_ascii=False)
            elif isinstance(topics, list):
                topics = json.dumps(topics, ensure_ascii=False)
            before = conn.total_changes
            conn.execute(
                "INSERT OR IGNORE INTO news_items "
                "(source, title, url, summary, lang, category, published_at, "
                "theme, topics, classified_by, lane) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ticker')",
                (
                    it.get("source") or "专属信源",
                    title[:500],
                    url,
                    (it.get("summary") or "")[:400],
                    it.get("lang") or "en",
                    it.get("category") or "stock_source",
                    it.get("published_at"),
                    theme,
                    topics if isinstance(topics, str) else "[]",
                    it.get("classified_by") or "rule",
                ),
            )
            inserted += conn.total_changes - before
            row = conn.execute("SELECT id FROM news_items WHERE url = ?", (url,)).fetchone()
            if not row:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO news_item_symbols "
                "(news_id, symbol, name, confidence, matched_by) "
                "VALUES (?, ?, ?, 'high', 'stock_source')",
                (row["id"], symbol, stock_name),
            )
            conn.execute("UPDATE news_items SET linked = 1 WHERE id = ?", (row["id"],))
        conn.commit()
        return inserted
    finally:
        conn.close()


def _mark_verified(source_id: int, ok: bool) -> None:
    if not ok:
        return
    conn = get_conn()
    try:
        conn.execute("UPDATE stock_sources SET verified = 1 WHERE id = ?", (source_id,))
        conn.commit()
    finally:
        conn.close()


def refresh_symbol(symbol: str) -> dict:
    """刷新某股已启用专属信源，并把条目挂到该股。"""
    sources = enabled_sources(symbol)
    if not sources:
        return {
            "symbol": symbol,
            "sources": 0,
            "fetched": 0,
            "inserted": 0,
            "failed": 0,
            "unsupported": 0,
        }
    cutoff = datetime.now(UTC) - timedelta(days=_RECENT_DAYS)
    stock_name = search.display_name(symbol)
    fetched = inserted = failed = unsupported = 0
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:
        futs = {ex.submit(_fetch_one, s, cutoff): s for s in sources}
        for fut in as_completed(futs):
            try:
                source, got, problem = fut.result()
            except Exception:  # noqa: BLE001
                failed += 1
                continue
            if problem and not got:
                unsupported += 1
                continue
            fetched += len(got)
            if got:
                inserted += _store_items(symbol, stock_name, got)
                _mark_verified(source["id"], True)
    return {
        "symbol": symbol,
        "sources": len(sources),
        "fetched": fetched,
        "inserted": inserted,
        "failed": failed,
        "unsupported": unsupported,
    }


def refresh_many(symbols: list[str]) -> dict:
    """刷新多只股票的启用专属信源。"""
    out = {
        "stocks": len(symbols),
        "sources": 0,
        "fetched": 0,
        "inserted": 0,
        "failed": 0,
        "unsupported": 0,
    }
    for sym in symbols:
        r = refresh_symbol(sym)
        out["sources"] += int(r.get("sources") or 0)
        out["fetched"] += int(r.get("fetched") or 0)
        out["inserted"] += int(r.get("inserted") or 0)
        out["failed"] += int(r.get("failed") or 0)
        out["unsupported"] += int(r.get("unsupported") or 0)
    return out
