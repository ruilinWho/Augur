"""判断日记服务：某标的在某日的决策笔记，供日后复盘（CLAUDE.md §1）。

纯逻辑 + SQLite。日期校验为 'YYYY-MM-DD'。symbol 经 market.parse_symbol 归一化校验。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from ..market.symbols import parse_symbol
from ..storage.db import get_conn


class NotFound(ValueError):
    pass


def _validate_date(s: str) -> str:
    s = s.strip()
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"日期须为 YYYY-MM-DD，收到 {s!r}") from e
    return s


def _out(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "entry_date": row["entry_date"],
        "body": row["body"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_entries(symbol: str) -> list[dict]:
    sym = parse_symbol(symbol)
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM journal_entries WHERE symbol = ? "
            "ORDER BY entry_date DESC, created_at DESC",
            (sym.canonical,),
        ).fetchall()
        return [_out(r) for r in rows]
    finally:
        conn.close()


def create_entry(symbol: str, entry_date: str, body: str = "") -> dict:
    sym = parse_symbol(symbol)
    d = _validate_date(entry_date)
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO journal_entries (symbol, entry_date, body) VALUES (?, ?, ?)",
            (sym.canonical, d, body),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM journal_entries WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return _out(row)
    finally:
        conn.close()


def update_entry(entry_id: int, entry_date: str | None = None, body: str | None = None) -> dict:
    sets: list[str] = []
    params: list[object] = []
    if entry_date is not None:
        sets.append("entry_date = ?")
        params.append(_validate_date(entry_date))
    if body is not None:
        sets.append("body = ?")
        params.append(body)
    conn = get_conn()
    try:
        if sets:
            sets.append("updated_at = datetime('now')")
            params.append(entry_id)
            cur = conn.execute(
                f"UPDATE journal_entries SET {', '.join(sets)} WHERE id = ?", params
            )
            conn.commit()
            if cur.rowcount == 0:
                raise NotFound(f"日记 {entry_id} 不存在")
        row = conn.execute(
            "SELECT * FROM journal_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if row is None:
            raise NotFound(f"日记 {entry_id} 不存在")
        return _out(row)
    finally:
        conn.close()


def delete_entry(entry_id: int) -> None:
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM journal_entries WHERE id = ?", (entry_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise NotFound(f"日记 {entry_id} 不存在")
    finally:
        conn.close()
