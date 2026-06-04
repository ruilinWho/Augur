"""新闻↔标的挂钩（linker）——把每条新闻**确定性**接地到自选股 `MARKET:CODE`。

三支柱融合地基（CLAUDE.md §1）。**零幻觉**：只用「自选股的中文展示名 / 英文名(首词) / 代码 / 别名」
对新闻标题（含中文译题）做**子串/词边界命中**，不调 LLM。命中即写 `news_item_symbols`。
增量：只处理 `linked=0` 的近条目、幂等（INSERT OR IGNORE）；自选变动 → `relink_all` 重置重挂。
范围聚焦**作者自选股**（最高价值、可控），而非全市场（避免噪音与误配）。
"""

from __future__ import annotations

import re

from ..market import search
from ..storage import get_conn
from ..watchlist import service as wl

_MAX_PER_RUN = 800


def _watchlist_symbols() -> set[str]:
    syms: set[str] = set()

    def walk(node: dict) -> None:
        for it in node.get("items", []):
            syms.add(it["symbol"])
        for ch in node.get("children", []):
            walk(ch)

    for root in wl.list_tree(None):
        walk(root)
    return syms


def _index() -> list[tuple[re.Pattern | None, set[str], str, str]]:
    """每只自选股 → (ascii 词边界正则|None, CJK 子串集, symbol, 展示名)。"""
    out: list[tuple[re.Pattern | None, set[str], str, str]] = []
    for sym in _watchlist_symbols():
        name = search.display_name(sym)
        terms: set[str] = set()
        if name and len(name) >= 2:
            terms.add(name)
        market, _, code = sym.partition(":")
        hits = search.search(code, market=market, limit=1)
        if hits:
            for v in (hits[0].get("name"), hits[0].get("sub")):
                v = (v or "").strip()
                if len(v) >= 2:
                    terms.add(v)
                    tok = re.split(r"[\s,，]", v)[0]  # NVIDIA Corp → NVIDIA
                    if tok.isascii() and len(tok) >= 3:
                        terms.add(tok)
        ascii_t = [t.lower() for t in terms if t.isascii()]
        cjk_t = {t for t in terms if not t.isascii() and len(t) >= 2}
        alt = "|".join(re.escape(t) for t in ascii_t)
        pat = re.compile(rf"\b(?:{alt})\b") if ascii_t else None
        out.append((pat, cjk_t, sym, name))
    return out


def link_pending(limit: int = _MAX_PER_RUN) -> dict:
    """把 linked=0 的近条目对自选股做命中并写挂钩；标记 linked=1。幂等。"""
    idx = _index()
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, title, COALESCE(title_zh,'') tz FROM news_items "
            "WHERE linked = 0 ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        pairs = 0
        for r in rows:
            text = f"{r['title']} {r['tz']}"
            low = text.lower()
            for pat, cjk, sym, name in idx:
                if (pat and pat.search(low)) or any(t in text for t in cjk):
                    conn.execute(
                        "INSERT OR IGNORE INTO news_item_symbols "
                        "(news_id, symbol, name, confidence, matched_by) "
                        "VALUES (?, ?, ?, 'high', 'term')",
                        (r["id"], sym, name),
                    )
                    pairs += 1
            conn.execute("UPDATE news_items SET linked = 1 WHERE id = ?", (r["id"],))
        conn.commit()
        return {"linked": len(rows), "pairs": pairs}
    finally:
        conn.close()


def relink_all() -> dict:
    """自选变动后重挂全部（重置 linked=0 再跑）。"""
    conn = get_conn()
    try:
        conn.execute("DELETE FROM news_item_symbols WHERE matched_by = 'term'")
        conn.execute("UPDATE news_items SET linked = 0")
        conn.commit()
    finally:
        conn.close()
    return link_pending(limit=1_000_000)


def attach_symbols(items: list[dict]) -> list[dict]:
    """给一批 news_item dict 批量挂上 symbols=[{symbol,name,in_watchlist}]（一次 IN 查询）。

    symbols 含**自选股挂钩**（linker，term/code/targeted）∪**LLM 标股**（stock_tag，不限自选）；
    `in_watchlist` 区分二者，前端可对自选股加陶土点、其余作"可发现的机会"展示。
    """
    ids = [it["id"] for it in items if it.get("id") is not None]
    if not ids:
        for it in items:
            it["symbols"] = []
        return items
    watched = _watchlist_symbols()
    conn = get_conn()
    try:
        ph = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT news_id, symbol, name FROM news_item_symbols WHERE news_id IN ({ph})",
            ids,
        ).fetchall()
    finally:
        conn.close()
    by_id: dict[int, list[dict]] = {}
    for r in rows:
        by_id.setdefault(r["news_id"], []).append(
            {"symbol": r["symbol"], "name": r["name"], "in_watchlist": r["symbol"] in watched}
        )
    for it in items:
        it["symbols"] = by_id.get(it["id"], [])
    return items
