"""notes 域纯逻辑：自由长文笔记 + 一级文件夹（目录）。

I/O（SQLite）在 storage；这里只做 SQL + 归一化。笔记置顶在前、再按更新时间倒序。
一篇笔记归属 ≤1 个文件夹（folder_id，NULL=未归类）；删文件夹时其下笔记回未归类。
"""

from __future__ import annotations

from ..storage import get_conn

_PREVIEW_LEN = 140


# ───────────────────────── 文件夹（一级目录）─────────────────────────
def _folder_out(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "sort_order": row["sort_order"],
        "note_count": row["note_count"] if "note_count" in row.keys() else 0,
        "created_at": row["created_at"],
    }


def list_folders() -> list[dict]:
    """全部文件夹（按 sort_order）+ 各自笔记数。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT f.id, f.name, f.sort_order, f.created_at, COUNT(n.id) AS note_count "
            "FROM note_folders f LEFT JOIN notes n ON n.folder_id = f.id "
            "GROUP BY f.id, f.name, f.sort_order, f.created_at "
            "ORDER BY f.sort_order, f.id"
        ).fetchall()
        return [_folder_out(r) for r in rows]
    finally:
        conn.close()


def create_folder(name: str = "") -> dict:
    conn = get_conn()
    try:
        n = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM note_folders"
        ).fetchone()["n"]
        cur = conn.execute(
            "INSERT INTO note_folders (name, sort_order) VALUES (?, ?)",
            (name.strip()[:100] or "未命名文件夹", n),
        )
        conn.commit()
        row = conn.execute(
            "SELECT *, 0 AS note_count FROM note_folders WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return _folder_out(row)
    finally:
        conn.close()


def rename_folder(folder_id: int, name: str) -> dict:
    conn = get_conn()
    try:
        row = conn.execute("SELECT id FROM note_folders WHERE id = ?", (folder_id,)).fetchone()
        if row is None:
            raise ValueError(f"文件夹 {folder_id} 不存在")
        conn.execute(
            "UPDATE note_folders SET name = ? WHERE id = ?",
            (name.strip()[:100] or "未命名文件夹", folder_id),
        )
        conn.commit()
        r = conn.execute(
            "SELECT f.*, (SELECT COUNT(*) FROM notes WHERE folder_id = f.id) AS note_count "
            "FROM note_folders f WHERE f.id = ?",
            (folder_id,),
        ).fetchone()
        return _folder_out(r)
    finally:
        conn.close()


def delete_folder(folder_id: int) -> None:
    """删文件夹；其下笔记回「未归类」（folder_id 置空），不删笔记。"""
    conn = get_conn()
    try:
        conn.execute("UPDATE notes SET folder_id = NULL WHERE folder_id = ?", (folder_id,))
        cur = conn.execute("DELETE FROM note_folders WHERE id = ?", (folder_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise ValueError(f"文件夹 {folder_id} 不存在")
    finally:
        conn.close()


# ───────────────────────── 笔记 ─────────────────────────
def _meta_out(row) -> dict:
    return {
        "id": row["id"],
        "folder_id": row["folder_id"],
        "title": row["title"],
        "preview": (row["body"] or "").strip().replace("\n", " ")[:_PREVIEW_LEN],
        "pinned": bool(row["pinned"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _note_out(row) -> dict:
    return {
        "id": row["id"],
        "folder_id": row["folder_id"],
        "title": row["title"],
        "body": row["body"],
        "pinned": bool(row["pinned"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_notes() -> list[dict]:
    """全部笔记元信息（置顶在前、再按更新时间倒序），带预览与 folder_id（不含全文）。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, folder_id, title, substr(body,1,200) AS body, "
            "pinned, created_at, updated_at "
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


def create_note(title: str = "", body: str = "", folder_id: int | None = None) -> dict:
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO notes (title, body, folder_id) VALUES (?, ?, ?)",
            (title.strip()[:200], body, folder_id),
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
    """改某篇的标题/正文/置顶（只改传入的字段）；任何改动刷新 updated_at。归属改动用 move_note。"""
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


def move_note(note_id: int, folder_id: int | None) -> dict:
    """把笔记移到某文件夹（folder_id=None → 未归类）。校验目标文件夹存在。"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT id FROM notes WHERE id = ?", (note_id,)).fetchone()
        if row is None:
            raise ValueError(f"笔记 {note_id} 不存在")
        if folder_id is not None:
            f = conn.execute("SELECT id FROM note_folders WHERE id = ?", (folder_id,)).fetchone()
            if f is None:
                raise ValueError(f"文件夹 {folder_id} 不存在")
        conn.execute("UPDATE notes SET folder_id = ? WHERE id = ?", (folder_id, note_id))
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
