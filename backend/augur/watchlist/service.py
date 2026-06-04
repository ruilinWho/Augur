"""自选分区服务：两级板块 + 标的（CLAUDE.md §8）。

硬约束：depth ≤ 2 —— 二级板块不能再有子级，在 create/move 时强校验。
市场（US/HK/CN/KR）是查询过滤器（正交），不是第三层。
"""

from __future__ import annotations

import sqlite3

from ..market.symbols import parse_symbol
from ..storage.db import get_conn


class DepthError(ValueError):
    """违反"最多两级"不变量。"""


class NotFound(ValueError):
    pass


class Duplicate(ValueError):
    """同层已有同名板块（重命名会造成"分叉"——两个同名分区）。"""


def _item_out(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "note": row["note"],
        "sort_order": row["sort_order"],
    }


def list_tree(market: str | None = None) -> list[dict]:
    conn = get_conn()
    try:
        sections = conn.execute("SELECT * FROM sections ORDER BY sort_order, id").fetchall()
        items = conn.execute("SELECT * FROM watchlist_items ORDER BY sort_order, id").fetchall()
    finally:
        conn.close()

    keep_all = not market or market.upper() == "ALL"

    def keep(symbol: str) -> bool:
        return keep_all or symbol.split(":", 1)[0].upper() == market.upper()

    items_by_section: dict[int, list[sqlite3.Row]] = {}
    all_by_section: dict[int, int] = {}  # 各分区标的总数（不分市场）——判定"真正空分区"
    for it in items:
        all_by_section[it["section_id"]] = all_by_section.get(it["section_id"], 0) + 1
        if keep(it["symbol"]):
            items_by_section.setdefault(it["section_id"], []).append(it)

    subs_by_parent: dict[int, list[sqlite3.Row]] = {}
    for s in sections:
        if s["parent_id"] is not None:
            subs_by_parent.setdefault(s["parent_id"], []).append(s)

    def has_any_stock(sid: int) -> bool:
        """该分区或其子分区是否有任何标的（不分市场）。"""
        if all_by_section.get(sid):
            return True
        return any(has_any_stock(ch["id"]) for ch in subs_by_parent.get(sid, []))

    # 分区按"标的所在市场"显示（CLAUDE.md §8）：选了具体市场时，只露出在该市场有标的的分区+该
    # 市场的标的；**有标的但本市场无的**分区剪掉（防 大模型 污染韩股）。但**真正的空分区**（任何
    # 市场都没标的）在所有市场都显示——它无市场归属，便于在任何视图里就地创建并填充（作者反馈）。
    def to_out(s: sqlite3.Row) -> dict | None:
        items_out = [_item_out(i) for i in items_by_section.get(s["id"], [])]
        children: list[dict] = []
        for ch in subs_by_parent.get(s["id"], []):
            c = to_out(ch)
            if c is not None:
                children.append(c)
        if not keep_all and not items_out and not children and has_any_stock(s["id"]):
            return None
        return {
            "id": s["id"],
            "name": s["name"],
            "parent_id": s["parent_id"],
            "sort_order": s["sort_order"],
            "items": items_out,
            "children": children,
        }

    roots: list[dict] = []
    for s in sections:
        if s["parent_id"] is None:
            out = to_out(s)
            if out is not None:
                roots.append(out)
    return roots


def _section_out(s: sqlite3.Row) -> dict:
    return {
        "id": s["id"],
        "name": s["name"],
        "parent_id": s["parent_id"],
        "sort_order": s["sort_order"],
        "items": [],
        "children": [],
    }


def create_section(name: str, parent_id: int | None = None) -> dict:
    name = name.strip()
    conn = get_conn()
    try:
        if parent_id is not None:
            parent = conn.execute(
                "SELECT parent_id FROM sections WHERE id = ?", (parent_id,)
            ).fetchone()
            if parent is None:
                raise NotFound(f"父板块 {parent_id} 不存在")
            if parent["parent_id"] is not None:
                raise DepthError("最多两级：二级板块下不能再建子级")
        # 幂等：同层（同 parent_id）已存在同名板块 → 返回既有，避免重复提交造成"两个大模型"
        dup = conn.execute(
            "SELECT * FROM sections WHERE name = ? AND parent_id IS ?", (name, parent_id)
        ).fetchone()
        if dup is not None:
            return _section_out(dup)
        if parent_id is None:
            n = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n "
                "FROM sections WHERE parent_id IS NULL"
            ).fetchone()["n"]
        else:
            n = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM sections WHERE parent_id = ?",
                (parent_id,),
            ).fetchone()["n"]
        cur = conn.execute(
            "INSERT INTO sections (name, parent_id, sort_order) VALUES (?, ?, ?)",
            (name, parent_id, n),
        )
        conn.commit()
        s = conn.execute("SELECT * FROM sections WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _section_out(s)
    finally:
        conn.close()


def rename_section(section_id: int, name: str) -> None:
    """按 id 重命名（市场无关，单实体）。拒绝空名 + 同层重名（防"分叉"出两个同名分区）。"""
    name = name.strip()
    if not name:
        raise ValueError("板块名不能为空")
    conn = get_conn()
    try:
        row = conn.execute("SELECT parent_id FROM sections WHERE id = ?", (section_id,)).fetchone()
        if row is None:
            raise NotFound(f"板块 {section_id} 不存在")
        dup = conn.execute(
            "SELECT 1 FROM sections WHERE name = ? AND parent_id IS ? AND id != ?",
            (name, row["parent_id"], section_id),
        ).fetchone()
        if dup is not None:
            raise Duplicate(f"同层已有同名板块「{name}」")
        conn.execute("UPDATE sections SET name = ? WHERE id = ?", (name, section_id))
        conn.commit()
    finally:
        conn.close()


def delete_section(section_id: int) -> None:
    """删除板块；FK ON DELETE CASCADE 连带删除其二级板块与所有标的。"""
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM sections WHERE id = ?", (section_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise NotFound(f"板块 {section_id} 不存在")
    finally:
        conn.close()


def add_item(section_id: int, symbol: str, note: str = "") -> dict:
    sym = parse_symbol(symbol)  # 校验并归一化
    conn = get_conn()
    try:
        if conn.execute("SELECT 1 FROM sections WHERE id = ?", (section_id,)).fetchone() is None:
            raise NotFound(f"板块 {section_id} 不存在")
        n = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n "
            "FROM watchlist_items WHERE section_id = ?",
            (section_id,),
        ).fetchone()["n"]
        try:
            cur = conn.execute(
                "INSERT INTO watchlist_items (section_id, symbol, note, sort_order) "
                "VALUES (?, ?, ?, ?)",
                (section_id, sym.canonical, note, n),
            )
        except sqlite3.IntegrityError as e:
            raise ValueError(f"{sym.canonical} 已在此板块") from e
        conn.commit()
        row = conn.execute(
            "SELECT * FROM watchlist_items WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return _item_out(row)
    finally:
        conn.close()


def move_item(item_id: int, section_id: int) -> dict:
    """把标的移动到另一个板块（拖拽换区）。追加到目标板块末尾，再由 reorder 精排位置。"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM watchlist_items WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            raise NotFound(f"标的项 {item_id} 不存在")
        if conn.execute("SELECT 1 FROM sections WHERE id = ?", (section_id,)).fetchone() is None:
            raise NotFound(f"板块 {section_id} 不存在")
        if row["section_id"] == section_id:
            return _item_out(row)  # 同区 → 交给 reorder 处理顺序
        n = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n "
            "FROM watchlist_items WHERE section_id = ?",
            (section_id,),
        ).fetchone()["n"]
        try:
            conn.execute(
                "UPDATE watchlist_items SET section_id = ?, sort_order = ? WHERE id = ?",
                (section_id, n, item_id),
            )
        except sqlite3.IntegrityError as e:
            raise ValueError(f"{row['symbol']} 已在目标板块") from e
        conn.commit()
        moved = conn.execute("SELECT * FROM watchlist_items WHERE id = ?", (item_id,)).fetchone()
        return _item_out(moved)
    finally:
        conn.close()


def remove_item(item_id: int) -> None:
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM watchlist_items WHERE id = ?", (item_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise NotFound(f"标的项 {item_id} 不存在")
    finally:
        conn.close()


def reorder(kind: str, ordered_ids: list[int]) -> None:
    """按给定顺序写回 sort_order（dnd-kit 拖拽后调用）。

    板块（section）：前端可能只传**当前市场可见**的子集（list_tree 按市场剪枝）。
    为不扰动隐藏兄弟的相对位置——只在「被拖动子集占据的槽位」内重排，其余原地不动。
    标的（item）：直接按传入顺序写 0..n-1。
    """
    if kind == "section":
        _reorder_sections(ordered_ids)
        return
    if kind != "item":
        raise ValueError(f"未知 kind {kind!r}，应为 'section' 或 'item'")
    conn = get_conn()
    try:
        conn.executemany(
            "UPDATE watchlist_items SET sort_order = ? WHERE id = ?",
            [(idx, _id) for idx, _id in enumerate(ordered_ids)],
        )
        conn.commit()
    finally:
        conn.close()


def _reorder_sections(ordered_ids: list[int]) -> None:
    """同列（同 parent）板块重排，未参与的隐藏兄弟保持原位。"""
    if not ordered_ids:
        return
    conn = get_conn()
    try:
        first = conn.execute(
            "SELECT parent_id FROM sections WHERE id = ?", (ordered_ids[0],)
        ).fetchone()
        if first is None:
            raise NotFound(f"板块 {ordered_ids[0]} 不存在")
        parent_id = first["parent_id"]
        if parent_id is None:
            sibs = conn.execute(
                "SELECT id FROM sections WHERE parent_id IS NULL ORDER BY sort_order, id"
            ).fetchall()
        else:
            sibs = conn.execute(
                "SELECT id FROM sections WHERE parent_id = ? ORDER BY sort_order, id",
                (parent_id,),
            ).fetchall()
        sib_ids = [r["id"] for r in sibs]
        valid = {i for i in ordered_ids if i in set(sib_ids)}
        moving = iter(i for i in ordered_ids if i in valid)
        # 被拖动子集按新顺序填回它们原先占据的槽位；其余兄弟原地不动
        merged = [next(moving) if sid in valid else sid for sid in sib_ids]
        conn.executemany(
            "UPDATE sections SET sort_order = ? WHERE id = ?",
            [(idx, sid) for idx, sid in enumerate(merged)],
        )
        conn.commit()
    finally:
        conn.close()
