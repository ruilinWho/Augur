"""反证雷达服务：立论 CRUD + AI 起草 + 按每日挂钩新闻扫描反证/印证。

纯逻辑挡在 I/O 外（AGENTS.md §5）。监控 scope 复用 news 的 `news_item_symbols` 挂钩
（与分区日报同口径，零新增标股成本）。判定走 cheap 角色、conservative 宁缺勿滥避免噪音。
"""

from __future__ import annotations

import json
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..llm import gateway
from ..market import search
from ..market.symbols import parse_symbol
from ..news import service as news_service
from ..storage.db import get_conn

log = logging.getLogger("augur.theses")


class NotFound(ValueError):
    pass


_VALID_STANCE = {"bull", "bear", "watch"}
_VALID_POLARITY = {"refute", "support"}
_STANCE_ZH = {"bull": "看多", "bear": "看空", "watch": "观望"}
_SCAN_DAYS = 7  # 扫描窗口：近 7 天挂钩新闻（滚动，反证可见一周后自然老化）
_SCAN_WORKERS = 6  # 立论间并行度（纯 I/O 线程）
_MAX_CONDITIONS = 8
_MAX_ALERTS = 12


def _load_prompt(name: str) -> str:
    from ..config import get_settings

    return (get_settings().resources_dir / "prompts" / f"{name}.md").read_text(encoding="utf-8")


def _conditions_from_texts(texts: object) -> list[dict]:
    """作者传的纯文本条件 → [{id, text}]，按位置分配稳定 id（1..N）。"""
    out: list[dict] = []
    if not isinstance(texts, list):
        return out
    for t in texts:
        s = str(t or "").strip()[:200]
        if s:
            out.append({"id": len(out) + 1, "text": s})
        if len(out) >= _MAX_CONDITIONS:
            break
    return out


def _out(row: sqlite3.Row) -> dict:
    try:
        conditions = json.loads(row["conditions"] or "[]")
    except (json.JSONDecodeError, TypeError):
        conditions = []
    try:
        alerts = json.loads(row["alerts"] or "[]")
    except (json.JSONDecodeError, TypeError):
        alerts = []
    sym = row["symbol"]
    return {
        "id": row["id"],
        "symbol": sym,
        "name": search.display_name(sym),
        "market": sym.split(":", 1)[0],
        "stance": row["stance"],
        "thesis": row["thesis"],
        "conditions": conditions,
        "alerts": alerts,
        "status": row["status"],
        "last_scanned_at": row["last_scanned_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ───────────────────────── CRUD ─────────────────────────
def list_theses(symbol: str | None = None, status: str = "active") -> list[dict]:
    """立论列表（默认仅 active）。有反证的排前面，再按更新时间。symbol 给定则只列该股。"""
    conn = get_conn()
    try:
        if symbol:
            sym = parse_symbol(symbol).canonical
            rows = conn.execute(
                "SELECT * FROM theses WHERE symbol = ? ORDER BY updated_at DESC", (sym,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM theses ORDER BY updated_at DESC").fetchall()
    finally:
        conn.close()
    out = [_out(r) for r in rows]
    if status and status != "all":
        out = [t for t in out if t["status"] == status]

    def _rank(t: dict) -> int:
        pols = {a.get("polarity") for a in t["alerts"]}
        if "refute" in pols:
            return 0  # 被反证的立论最该看
        if "support" in pols:
            return 1
        return 2

    out.sort(key=_rank)  # 稳定排序：保 updated_at DESC 的次序
    return out


def create_thesis(
    symbol: str, stance: str = "bull", thesis: str = "", conditions: object = None
) -> dict:
    sym = parse_symbol(symbol).canonical
    st = stance if stance in _VALID_STANCE else "bull"
    conds = _conditions_from_texts(conditions)
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO theses (symbol, stance, thesis, conditions, alerts, status) "
            "VALUES (?, ?, ?, ?, '[]', 'active')",
            (sym, st, (thesis or "").strip()[:500], json.dumps(conds, ensure_ascii=False)),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM theses WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _out(row)
    finally:
        conn.close()


def update_thesis(
    thesis_id: int,
    stance: str | None = None,
    thesis: str | None = None,
    conditions: object = None,
    status: str | None = None,
) -> dict:
    sets: list[str] = []
    params: list[object] = []
    if stance is not None and stance in _VALID_STANCE:
        sets.append("stance = ?")
        params.append(stance)
    if thesis is not None:
        sets.append("thesis = ?")
        params.append(thesis.strip()[:500])
    if conditions is not None:
        sets.append("conditions = ?")
        params.append(json.dumps(_conditions_from_texts(conditions), ensure_ascii=False))
        sets.append("alerts = ?")  # 条件改了 → 旧告警作废（condition_id 可能错位），待重扫
        params.append("[]")
    if status is not None and status in {"active", "closed"}:
        sets.append("status = ?")
        params.append(status)
    conn = get_conn()
    try:
        if sets:
            sets.append("updated_at = datetime('now')")
            params.append(thesis_id)
            cur = conn.execute(f"UPDATE theses SET {', '.join(sets)} WHERE id = ?", params)
            conn.commit()
            if cur.rowcount == 0:
                raise NotFound(f"立论 {thesis_id} 不存在")
        row = conn.execute("SELECT * FROM theses WHERE id = ?", (thesis_id,)).fetchone()
        if row is None:
            raise NotFound(f"立论 {thesis_id} 不存在")
        return _out(row)
    finally:
        conn.close()


def delete_thesis(thesis_id: int) -> None:
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM theses WHERE id = ?", (thesis_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise NotFound(f"立论 {thesis_id} 不存在")
    finally:
        conn.close()


def thesis_flags() -> dict[str, str]:
    """symbol → 最严重告警极性（refute 覆盖 support）。供分区/看 inline 徽章，轻量读。"""
    conn = get_conn()
    try:
        rows = conn.execute("SELECT symbol, alerts FROM theses WHERE status = 'active'").fetchall()
    finally:
        conn.close()
    flags: dict[str, str] = {}
    for r in rows:
        try:
            alerts = json.loads(r["alerts"] or "[]")
        except (json.JSONDecodeError, TypeError):
            alerts = []
        pols = {a.get("polarity") for a in alerts if isinstance(a, dict)}
        pol = "refute" if "refute" in pols else ("support" if "support" in pols else None)
        if pol and flags.get(r["symbol"]) != "refute":
            flags[r["symbol"]] = pol
    return flags


# ───────────────────────── AI 起草 ─────────────────────────
def draft_thesis(symbol: str, role: str = "summarize") -> dict:
    """从某股近况（叙事主线 + 近一月挂钩资讯）AI 起草 stance/thesis/证伪条件。不落库。"""
    gateway.check_ready(role)
    sym = parse_symbol(symbol).canonical
    name = search.display_name(sym)
    items = news_service.items_for_symbol(sym, days=30, limit=20)
    lines: list[str] = []
    for it in items[:20]:
        day = (it.get("published_at") or it.get("fetched_at") or "")[:10]
        title = news_service._strip_inline_refs(it.get("title_zh") or it.get("title") or "")
        lines.append(f"- ({day or '日期不详'}) [{it.get('source', '')}] {title}")
    narrative = news_service.get_narrative(sym)
    nsum = (narrative or {}).get("summary", "") if narrative else ""
    prompt = (
        _load_prompt("thesis_draft")
        .replace("{{NAME}}", f"{name} / {sym}")
        .replace("{{NARRATIVE}}", nsum or "（暂无叙事）")
        .replace("{{NEWS}}", "\n".join(lines) or "（暂无近一月资讯）")
    )
    data = news_service._complete_json(prompt, role, "conditions")
    stance = data.get("stance", "bull")
    conds: list[str] = []
    for c in (data.get("conditions") or [])[:6]:
        text = c if isinstance(c, str) else (c.get("text", "") if isinstance(c, dict) else "")
        t = news_service._strip_inline_refs(str(text)).strip()[:200]
        if t:
            conds.append(t)
    return {
        "stance": stance if stance in _VALID_STANCE else "bull",
        "thesis": news_service._strip_inline_refs(str(data.get("thesis") or "")).strip()[:500],
        "conditions": conds,
    }


# ───────────────────────── 监控扫描（反证/印证）─────────────────────────
def _map_refs(ref_ns: object, by_n: dict[int, dict], cap: int = 3) -> list[dict]:
    """[n] 编号 → [{source, url}]（去重、封顶）。映射回扫描时喂进去的新闻。"""
    refs: list[dict] = []
    seen: set[str] = set()
    if not isinstance(ref_ns, list):
        return refs
    for nv in ref_ns:
        ok = isinstance(nv, int) or (isinstance(nv, str) and str(nv).isdigit())
        it = by_n.get(int(nv)) if ok else None
        url = (it or {}).get("url") or ""
        if it and url and url not in seen:
            seen.add(url)
            refs.append({"source": it.get("source") or "", "url": url})
        if len(refs) >= cap:
            break
    return refs


def _scan_one(t: dict, role: str) -> list[dict]:
    """对单个立论：把近 7 天挂钩新闻按其证伪条件判定 反证/印证 → alerts。无条件/无新闻 → []。"""
    conds = t.get("conditions") or []
    if not conds:
        return []
    sym = t["symbol"]
    items = news_service.items_for_symbol(sym, days=_SCAN_DAYS, limit=40)
    if not items:
        return []
    by_n: dict[int, dict] = {}
    lines: list[str] = []
    for i, it in enumerate(items, start=1):
        by_n[i] = it
        day = (it.get("published_at") or it.get("fetched_at") or "")[:10]
        title = news_service._strip_inline_refs(it.get("title_zh") or it.get("title") or "")
        summ = news_service._strip_inline_refs(str(it.get("summary") or "")).strip()
        lines.append(
            f"[{i}] ({day or '日期不详'}) [{it.get('source', '')}] {title}"
            + (f" — {summ[:160]}" if summ else "")
        )
    cond_block = "\n".join(f"[条件{c['id']}] {c['text']}" for c in conds if c.get("text"))
    prompt = (
        _load_prompt("thesis_scan")
        .replace("{{NAME}}", f"{search.display_name(sym)} / {sym}")
        .replace("{{STANCE}}", _STANCE_ZH.get(t.get("stance", ""), t.get("stance", "")))
        .replace("{{THESIS}}", t.get("thesis") or "（未填）")
        .replace("{{CONDITIONS}}", cond_block)
        .replace("{{NEWS}}", "\n".join(lines))
    )
    data = news_service._complete_json(prompt, role, "alerts")
    valid_ids = {c["id"] for c in conds}
    out: list[dict] = []
    for a in (data.get("alerts") or [])[:_MAX_ALERTS]:
        if not isinstance(a, dict):
            continue
        try:
            cid = int(a.get("condition_id"))
        except (TypeError, ValueError):
            continue
        pol = a.get("polarity")
        if cid not in valid_ids or pol not in _VALID_POLARITY:  # 零编造：condition_id 必须存在
            continue
        summary = news_service._strip_inline_refs(str(a.get("summary") or "")).strip()[:240]
        if not summary:
            continue
        out.append(
            {
                "condition_id": cid,
                "polarity": pol,
                "summary": summary,
                "refs": _map_refs(a.get("refs"), by_n),
            }
        )
    return out


def scan_all(role: str = "cheap") -> dict:
    """扫描全部 active 立论（并行）：滚动重算每个的 alerts。LLM 未配置 → 静默跳过。

    供「雷达」手动「扫描」按钮与 generate_all 自动调用（单一真相）。判定走 cheap 角色。
    """
    try:
        gateway.check_ready(role)
    except gateway.LLMNotConfigured:
        return {"scanned": 0, "triggered": 0, "skipped": True}
    theses = list_theses(status="active")
    if not theses:
        return {"scanned": 0, "triggered": 0}
    results: list[tuple[int, list[dict]]] = []
    with ThreadPoolExecutor(max_workers=min(_SCAN_WORKERS, len(theses))) as ex:
        futs = {ex.submit(_scan_one, t, role): t for t in theses}
        for fut in as_completed(futs):
            t = futs[fut]
            try:
                results.append((t["id"], fut.result()))
            except Exception:  # noqa: BLE001 — 单个立论失败不连累其余（§11）
                log.exception("thesis scan failed: %s", t["symbol"])
    conn = get_conn()
    try:
        for tid, alerts in results:
            conn.execute(
                "UPDATE theses SET alerts = ?, last_scanned_at = datetime('now') WHERE id = ?",
                (json.dumps(alerts, ensure_ascii=False), tid),
            )
        conn.commit()
    finally:
        conn.close()
    triggered = sum(1 for _, a in results if any(x["polarity"] == "refute" for x in a))
    return {"scanned": len(results), "triggered": triggered}
