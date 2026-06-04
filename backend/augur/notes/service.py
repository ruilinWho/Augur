"""notes 域纯逻辑：自由长文笔记 CRUD（与个股无关）。

I/O（SQLite）在 storage；这里只做 SQL + 归一化。置顶在前、再按更新时间倒序。
"""

from __future__ import annotations

from ..storage import get_conn

_PREVIEW_LEN = 140


def _meta_out(row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "preview": (row["body"] or "").strip().replace("\n", " ")[:_PREVIEW_LEN],
        "pinned": bool(row["pinned"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _note_out(row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "body": row["body"],
        "pinned": bool(row["pinned"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_notes() -> list[dict]:
    """全部笔记元信息（置顶在前、再按更新时间倒序），带预览不含全文。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, title, substr(body,1,200) AS body, pinned, created_at, updated_at "
            "FROM notes ORDER BY pinned DESC, updated_at DESC, id DESC"
        ).fetchall()
        return [_meta_out(r) for r in rows]
    finally:
        conn.close()


def get_note(note_id: int) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return _note_out(row) if row else None
    finally:
        conn.close()


def create_note(title: str = "", body: str = "") -> dict:
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO notes (title, body) VALUES (?, ?)",
            (title.strip()[:200], body),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _note_out(row)
    finally:
        conn.close()


def update_note(
    note_id: int,
    title: str | None = None,
    body: str | None = None,
    pinned: bool | None = None,
) -> dict:
    """改某篇的标题/正文/置顶（只改传入的字段）；任何改动刷新 updated_at。"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        if row is None:
            raise ValueError(f"笔记 {note_id} 不存在")
        new_title = row["title"] if title is None else title.strip()[:200]
        new_body = row["body"] if body is None else body
        new_pinned = row["pinned"] if pinned is None else int(pinned)
        conn.execute(
            "UPDATE notes SET title = ?, body = ?, pinned = ?, updated_at = datetime('now') "
            "WHERE id = ?",
            (new_title, new_body, new_pinned, note_id),
        )
        conn.commit()
        return _note_out(conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone())
    finally:
        conn.close()


def delete_note(note_id: int) -> None:
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise ValueError(f"笔记 {note_id} 不存在")
    finally:
        conn.close()
