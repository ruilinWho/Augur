"""research 域纯逻辑（M2「研」）：导入研报管理。

「研」不再自建深度研究生成——研究改走外部网页 Deep Research（ChatGPT/Claude/Gemini），
经「复制 Prompt」+「导入研报」回流（见 ADR-0011/0014/0016）。本模块只管导入研报的
CRUD/排序：他人写的 markdown，一股可多份、可拖排序，各带我的评论与回流来源标注。
"""

from __future__ import annotations

from ..market.symbols import parse_symbol
from ..storage import get_conn


def _imported_out(row) -> dict:
    keys = row.keys()
    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "title": row["title"],
        "body": row["body"],
        "comment": row["comment"],
        # 老库迁移前可能无该列（用 keys 探测，read-with-fallback）
        "engine": row["engine"] if "engine" in keys else "",
        "source_url": row["source_url"] if "source_url" in keys else "",
        "sort_order": row["sort_order"],
        "created_at": row["created_at"],
    }


def list_imported(symbol: str) -> list[dict]:
    """某股的导入研报（按 sort_order、再新→旧）。symbol 规范化。"""
    sym = parse_symbol(symbol).canonical
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM imported_reports WHERE symbol = ? "
            "ORDER BY sort_order, created_at DESC, id DESC",
            (sym,),
        ).fetchall()
        return [_imported_out(r) for r in rows]
    finally:
        conn.close()


def add_imported(
    symbol: str, title: str = "", body: str = "", engine: str = "", source_url: str = ""
) -> dict:
    """导入一份研报（新建排到末尾）。标题截断到 200 字、可空（前端用 placeholder 呈现空标题）。

    engine/source_url 用于网页 Deep Research 回流标注（哪个引擎、原始会话链接）。
    """
    sym = parse_symbol(symbol).canonical
    conn = get_conn()
    try:
        n = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM imported_reports WHERE symbol = ?",
            (sym,),
        ).fetchone()["n"]
        cur = conn.execute(
            "INSERT INTO imported_reports (symbol, title, body, engine, source_url, sort_order) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (sym, title.strip()[:200], body, engine.strip()[:20], source_url.strip()[:500], n),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM imported_reports WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return _imported_out(row)
    finally:
        conn.close()


def update_imported(
    report_id: int,
    title: str | None = None,
    body: str | None = None,
    comment: str | None = None,
    engine: str | None = None,
    source_url: str | None = None,
) -> dict:
    """改某份导入研报的标题/正文/评论/来源（只改传入的字段）。"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM imported_reports WHERE id = ?", (report_id,)).fetchone()
        if row is None:
            raise ValueError(f"研报 {report_id} 不存在")
        new_title = row["title"] if title is None else title.strip()[:200]
        new_body = row["body"] if body is None else body
        new_comment = row["comment"] if comment is None else comment
        new_engine = row["engine"] if engine is None else engine.strip()[:20]
        new_url = row["source_url"] if source_url is None else source_url.strip()[:500]
        conn.execute(
            "UPDATE imported_reports SET title = ?, body = ?, comment = ?, engine = ?, "
            "source_url = ? WHERE id = ?",
            (new_title, new_body, new_comment, new_engine, new_url, report_id),
        )
        conn.commit()
        return _imported_out(
            conn.execute("SELECT * FROM imported_reports WHERE id = ?", (report_id,)).fetchone()
        )
    finally:
        conn.close()


def delete_imported(report_id: int) -> None:
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM imported_reports WHERE id = ?", (report_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise ValueError(f"研报 {report_id} 不存在")
    finally:
        conn.close()


def reorder_imported(ordered_ids: list[int]) -> None:
    """按给定顺序写回 sort_order（拖拽后调用）。"""
    conn = get_conn()
    try:
        conn.executemany(
            "UPDATE imported_reports SET sort_order = ? WHERE id = ?",
            [(idx, rid) for idx, rid in enumerate(ordered_ids)],
        )
        conn.commit()
    finally:
        conn.close()
