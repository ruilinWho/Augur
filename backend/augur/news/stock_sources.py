"""每股专属信源画像（CLAUDE.md §1 三支柱融合 · 知·个股）。

主人想法「组件化信源」：对某只股，先用 LLM（最好**联网**，如 Perplexity）调研「该看哪些
重要信源」（官网/IR/官方X/大V/Reddit/雪球/财经站），存为**待确认候选**，主人逐个
mark（启用/增删）。启用的源**后续**喂给定向抓取 lane（X→twtapi、RSS→feedparser、
Reddit→待加），汇入该股叙事。每只股一套、各不相同。

防幻觉（§11）：LLM 易编造句柄/URL → 候选默认 `enabled=0 verified=0`，由主人拍板；
能验证的后续验证（X 句柄过 twtapi、子版过 Reddit、URL 探活）。调研走 `deep_research`
角色——主人把它指到联网模型即准；未配则 `LLMNotConfigured`，端点转可读提示。
"""

from __future__ import annotations

from ..llm import gateway
from ..market import search
from ..storage import get_conn
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

    走 `deep_research` 角色（主人指到联网模型即准）；未配置 → 抛 LLMNotConfigured。
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
