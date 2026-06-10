"""discovery 域纯逻辑（「寻」）：聚合自选外的反复出现标的。

喂料来源 = news_item_symbols 里 matched_by='llm' 的挂钩（stock_tag 对相关新闻标股，**不限自选**）。
对它们按标的聚合提及次数/出现天数/证据，**排除当前自选**（按 symbol 精确 + 同名归并，
处理 GOOGL↔GOOG、A/H 同名双列等别名噪音），UPSERT 进 discovery_candidates。
作者拍板状态（dismissed/promoted）在重算时保留，不被复活。零新增 LLM 成本。

边界：与「机会」（news_opportunities，当日事件论点卡、每日覆盖）正交——这是标的轴、跨天累积。
"""

from __future__ import annotations

import json
import re

from .. import runtime_config
from ..market import search
from ..news import directed
from ..storage import get_conn

_MIN_MENTIONS = 2  # 默认门槛：至少出现 2 次才算候选（1 次多为噪音）
_MAX_EVIDENCE = 6


def _norm_name(s: str) -> str:
    """归一化公司名做等价判断：去空白/标点/常见后缀、小写。用于自选别名剪枝与双列归并。"""
    s = (s or "").lower()
    s = re.sub(r"[\s.,\-_()（）·、]", "", s)
    return s


def _market(symbol: str) -> str:
    return symbol.partition(":")[0]


def refresh() -> dict:
    """重算候选池：聚合 llm 挂钩、排除自选、归并别名、UPSERT（保留作者状态）。"""
    conn = get_conn()
    try:
        wl_syms = set(directed.watchlist_symbols())
        wl_names = {_norm_name(search.display_name(s)) for s in wl_syms}

        # 跨语言/股份类别名归并：候选名经检索 top-2 解析出"等价 symbol 集"（如 谷歌→GOOGL+GOOG、
        # 阿里巴巴→09988+BABA），任一落在自选里即视作已覆盖。按归一名缓存，避免逐行重复检索。
        _equiv_cache: dict[str, bool] = {}

        def _covered_by_watchlist(name: str, nkey: str) -> bool:
            if nkey in wl_names:
                return True
            cached = _equiv_cache.get(nkey)
            if cached is not None:
                return cached
            hit = any(h["symbol"] in wl_syms for h in search.search(name, limit=2))
            _equiv_cache[nkey] = hit
            return hit

        rows = conn.execute(
            "SELECT nis.symbol AS symbol, nis.name AS name, ni.id AS nid, ni.title AS title, "
            "ni.title_zh AS title_zh, ni.source AS source, ni.url AS url, ni.published_at AS pub, "
            "ni.theme AS theme "
            "FROM news_item_symbols nis JOIN news_items ni ON ni.id = nis.news_id "
            "WHERE nis.matched_by = 'llm' "
            "ORDER BY ni.published_at DESC"
        ).fetchall()

        # 按"归一化名"聚合，把同名双重上市（A/H、ADR 同名）并到一个候选
        groups: dict[str, dict] = {}
        for r in rows:
            sym = r["symbol"]
            if sym in wl_syms:
                continue  # 已自选，跳过
            nm = r["name"] or search.display_name(sym)
            nkey = _norm_name(nm)
            if not nkey or _covered_by_watchlist(nm, nkey):
                continue  # 与某只自选股同名/同公司（GOOGL=GOOG、BABA=09988、A/H 双列）→ 已覆盖
            g = groups.get(nkey)
            if g is None:
                g = groups[nkey] = {
                    "name": nm,
                    "count": 0,
                    "days": set(),
                    "evidence": [],
                    "ev_urls": set(),
                    "sym_counts": {},
                    "themes": {},
                }
            g["count"] += 1
            g["sym_counts"][sym] = g["sym_counts"].get(sym, 0) + 1
            th = (r["theme"] or "").strip()
            if th and th != "other":
                g["themes"][th] = g["themes"].get(th, 0) + 1
            day = (r["pub"] or "")[:10]
            if day:
                g["days"].add(day)
            url = (r["url"] or "").strip()
            if url and url not in g["ev_urls"] and len(g["evidence"]) < _MAX_EVIDENCE:
                g["ev_urls"].add(url)
                g["evidence"].append(
                    {
                        "news_id": r["nid"],
                        "title": (r["title_zh"] or r["title"] or "")[:200],
                        "source": r["source"] or "",
                        "url": url,
                        "date": day,
                    }
                )

        kept: set[str] = set()
        for g in groups.values():
            if g["count"] < _MIN_MENTIONS:
                continue
            # 主 symbol = 组内提及最多者（双列里取信号更强的那一边）
            symbol = max(g["sym_counts"].items(), key=lambda kv: kv[1])[0]
            kept.add(symbol)
            days = sorted(g["days"])
            theme = max(g["themes"].items(), key=lambda kv: kv[1])[0] if g["themes"] else ""
            conn.execute(
                "INSERT INTO discovery_candidates "
                "(symbol, name, mention_count, day_span, first_seen_at, last_seen_at, evidence, "
                "theme, status, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new', datetime('now')) "
                "ON CONFLICT(symbol) DO UPDATE SET "
                "name=excluded.name, mention_count=excluded.mention_count, "
                "day_span=excluded.day_span, first_seen_at=excluded.first_seen_at, "
                "last_seen_at=excluded.last_seen_at, evidence=excluded.evidence, "
                "theme=excluded.theme, updated_at=datetime('now')",  # status 不覆盖：保留作者拍板
                (
                    symbol,
                    g["name"][:120],
                    g["count"],
                    len(days),
                    days[0] if days else None,
                    days[-1] if days else None,
                    json.dumps(g["evidence"], ensure_ascii=False),
                    theme,
                ),
            )

        # 清理本轮不再合格的 new 候选（被归并/剔除/跌破门槛）——只删 new，保留 dismissed/promoted
        existing_new = {
            r["symbol"]
            for r in conn.execute(
                "SELECT symbol FROM discovery_candidates WHERE status='new'"
            ).fetchall()
        }
        stale = existing_new - kept
        for s in stale:
            conn.execute("DELETE FROM discovery_candidates WHERE symbol=? AND status='new'", (s,))

        # 已加入自选的旧候选 → 标 promoted（保留发现轨迹，不删）
        if wl_syms:
            qs = ",".join("?" * len(wl_syms))
            conn.execute(
                f"UPDATE discovery_candidates SET status='promoted' "
                f"WHERE symbol IN ({qs}) AND status != 'promoted'",
                tuple(wl_syms),
            )
        conn.commit()
        return {"candidates": len(kept)}
    finally:
        conn.close()


def _out(row) -> dict:
    try:
        ev = json.loads(row["evidence"] or "[]")
    except (ValueError, TypeError):
        ev = []
    keys = row.keys()
    return {
        "symbol": row["symbol"],
        "name": row["name"],
        "market": _market(row["symbol"]),
        "mention_count": row["mention_count"],
        "day_span": row["day_span"],
        "first_seen_at": row["first_seen_at"],
        "last_seen_at": row["last_seen_at"],
        "evidence": ev,
        "theme": row["theme"] if "theme" in keys else "",
        "status": row["status"],
    }


# ── 主题级偏好（屏蔽某主题——智能忽略：你不想看的整类不再出现）──
_MUTED_PREF = "discovery_muted_themes"


def muted_themes() -> list[str]:
    return list(runtime_config.get_pref(_MUTED_PREF, []) or [])


def set_theme_muted(theme: str, muted: bool) -> list[str]:
    theme = (theme or "").strip()
    if not theme:
        raise ValueError("主题不能为空")
    cur = set(muted_themes())
    if muted:
        cur.add(theme)
    else:
        cur.discard(theme)
    runtime_config.set_pref(_MUTED_PREF, sorted(cur))
    return sorted(cur)


def list_candidates(status: str = "new", limit: int = 100) -> list[dict]:
    """按状态列候选，提及次数→出现天数降序。status='new' 时在 SQL 里剔除被屏蔽主题
    （必须 LIMIT 之前过滤，否则屏蔽会把列表截断到不足 limit）。"""
    sql = (
        "SELECT * FROM discovery_candidates WHERE status = ? "
        "ORDER BY mention_count DESC, day_span DESC, last_seen_at DESC"
    )
    args: list = [status]
    muted = [m for m in muted_themes() if m] if status == "new" else []
    if muted:
        placeholders = ",".join("?" * len(muted))
        sql = (
            f"SELECT * FROM discovery_candidates WHERE status = ? "
            f"AND theme NOT IN ({placeholders}) "
            "ORDER BY mention_count DESC, day_span DESC, last_seen_at DESC"
        )
        args = [status, *muted]
    sql += " LIMIT ?"
    args.append(limit)
    conn = get_conn()
    try:
        rows = conn.execute(sql, tuple(args)).fetchall()
        return [_out(r) for r in rows]
    finally:
        conn.close()


def theme_counts() -> list[dict]:
    """各主题下 new 候选数 + 是否被屏蔽——供「偏好」面板展示与一键屏蔽。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT theme, COUNT(*) AS n FROM discovery_candidates "
            "WHERE status='new' AND theme != '' GROUP BY theme ORDER BY n DESC"
        ).fetchall()
    finally:
        conn.close()
    muted = set(muted_themes())
    # 含被屏蔽但当前无 new 候选的主题，仍要能在面板里取消屏蔽
    seen = {r["theme"] for r in rows}
    out = [{"theme": r["theme"], "count": r["n"], "muted": r["theme"] in muted} for r in rows]
    for t in muted:
        if t not in seen:
            out.append({"theme": t, "count": 0, "muted": True})
    return out


def set_status(symbol: str, status: str) -> dict:
    if status not in ("new", "dismissed", "promoted"):
        raise ValueError(f"非法状态：{status}")
    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE discovery_candidates SET status = ?, updated_at = datetime('now') "
            "WHERE symbol = ?",
            (status, symbol),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise ValueError(f"候选 {symbol} 不存在")
        row = conn.execute(
            "SELECT * FROM discovery_candidates WHERE symbol = ?", (symbol,)
        ).fetchone()
        return _out(row)
    finally:
        conn.close()
