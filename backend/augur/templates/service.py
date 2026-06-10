"""templates 域纯逻辑：Prompt 模板 CRUD。

占位符（{STOCK} 代码、{NAME} 名称、{MARKET} 市场、{SYMBOL} 市场:代码）由前端按
当前标的填充——后端只存原文，不做渲染（模板用于复制到外部 Deep Research，
不进入本地 LLM 调用链）。
"""

from __future__ import annotations

from ..storage import get_conn


def _out(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "body": row["body"],
        "sort_order": row["sort_order"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_templates() -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM prompt_templates ORDER BY sort_order, id"
        ).fetchall()
        return [_out(r) for r in rows]
    finally:
        conn.close()


def create_template(name: str = "", body: str = "") -> dict:
    conn = get_conn()
    try:
        nxt = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM prompt_templates"
        ).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO prompt_templates (name, body, sort_order) VALUES (?, ?, ?)",
            (name.strip()[:120], body, nxt),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM prompt_templates WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return _out(row)
    finally:
        conn.close()


def update_template(template_id: int, name: str | None = None, body: str | None = None) -> dict:
    """只改传入的字段；任何改动刷新 updated_at。"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM prompt_templates WHERE id = ?", (template_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"模板 {template_id} 不存在")
        new_name = row["name"] if name is None else name.strip()[:120]
        new_body = row["body"] if body is None else body
        conn.execute(
            "UPDATE prompt_templates SET name = ?, body = ?, updated_at = datetime('now') "
            "WHERE id = ?",
            (new_name, new_body, template_id),
        )
        conn.commit()
        return _out(
            conn.execute(
                "SELECT * FROM prompt_templates WHERE id = ?", (template_id,)
            ).fetchone()
        )
    finally:
        conn.close()


def delete_template(template_id: int) -> None:
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM prompt_templates WHERE id = ?", (template_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise ValueError(f"模板 {template_id} 不存在")
    finally:
        conn.close()
