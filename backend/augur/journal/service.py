"""判断日记服务：某标的在某日的决策笔记，供日后复盘（AGENTS.md §1）。

纯逻辑 + SQLite。日期校验为 'YYYY-MM-DD'。symbol 经 market.parse_symbol 归一化校验。
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime

import pandas as pd

from ..config import get_settings
from ..llm import gateway
from ..market import search
from ..market import service as market_service
from ..market.symbols import parse_symbol
from ..storage.db import get_conn


class NotFound(ValueError):
    pass


_VERDICTS = {"印证", "证伪", "混合", "尚未检验"}
_CONFIDENCE = {"low", "med", "high"}
_IMP_ORDER = {"critical": 0, "high": 1, "med": 2, "low": 3}


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


def _load_prompt(name: str) -> str:
    return (get_settings().resources_dir / "prompts" / f"{name}.md").read_text(encoding="utf-8")


def _parse_json_lenient(text: str) -> dict:
    """LLM JSON 解析：兼容代码围栏和前后缀说明。"""
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, flags=re.S)
        if not m:
            return {}
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return {}


def _reflection_row(row: sqlite3.Row) -> dict:
    return {
        "symbol": row["symbol"],
        "name": row["name"],
        "summary": row["summary"],
        "events": json.loads(row["events"] or "[]"),
        "model": row["model"],
        "journal_count": row["journal_count"],
        "news_count": row["news_count"],
        "created_at": row["created_at"],
    }


def _delete_reflection(symbol: str) -> None:
    conn = get_conn()
    try:
        conn.execute("DELETE FROM stock_reflection_timelines WHERE symbol = ?", (symbol,))
        conn.commit()
    finally:
        conn.close()


def _save_reflection(
    symbol: str,
    name: str,
    summary: str,
    events: list[dict],
    model: str,
    journal_count: int,
    news_count: int,
) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO stock_reflection_timelines "
            "(symbol, name, summary, events, model, journal_count, news_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(symbol) DO UPDATE SET "
            "name=excluded.name, summary=excluded.summary, events=excluded.events, "
            "model=excluded.model, journal_count=excluded.journal_count, "
            "news_count=excluded.news_count, created_at=datetime('now')",
            (
                symbol,
                name,
                summary,
                json.dumps(events, ensure_ascii=False),
                model,
                journal_count,
                news_count,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_reflection_timeline(symbol: str) -> dict | None:
    sym = parse_symbol(symbol)
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM stock_reflection_timelines WHERE symbol = ?", (sym.canonical,)
        ).fetchone()
        return _reflection_row(row) if row else None
    finally:
        conn.close()


def _price_feedback(symbol: str, entries: list[dict]) -> dict[int, str]:
    """每条判断的确定性价格反馈：判断日附近收盘 → 最新收盘。失败返回空，不阻断 LLM 复盘。"""
    if not entries:
        return {}
    try:
        sym = parse_symbol(symbol)
        df, _, _ = market_service.get_ohlcv(sym, "1d", "max")
    except Exception:  # noqa: BLE001
        return {}
    if df is None or df.empty or "close" not in df:
        return {}
    df = df.sort_index()
    latest_date = df.index.max()
    latest_close = float(df.iloc[-1]["close"])
    out: dict[int, str] = {}
    for e in entries:
        try:
            d = pd.Timestamp(e["entry_date"])
        except Exception:  # noqa: BLE001
            continue
        after = df[df.index >= d]
        if after.empty:
            continue
        base_date = after.index.min()
        base_close = float(after.loc[base_date]["close"])
        pct = ((latest_close / base_close) - 1.0) * 100.0 if base_close else 0.0
        out[int(e["id"])] = (
            f"{base_date.strftime('%Y-%m-%d')}收盘 {base_close:.2f} → "
            f"{latest_date.strftime('%Y-%m-%d')}收盘 {latest_close:.2f}，{pct:+.1f}%"
        )
    return out


def _ensure_narrative(symbol: str) -> dict:
    """取或生成现有个股重大资讯时间线。生成失败时返回空壳，综合认知仍能展示判断。"""
    from ..news import service as news_service

    data = news_service.get_narrative(symbol)
    if data:
        return data
    try:
        return news_service.generate_narrative(symbol)
    except Exception:  # noqa: BLE001
        return {
            "symbol": symbol,
            "name": search.display_name(symbol),
            "summary": "",
            "timeline": [],
            "model": "",
            "item_count": 0,
            "created_at": None,
        }


def _refs(raw: object) -> list[dict]:
    out: list[dict] = []
    if not isinstance(raw, list):
        return out
    for r in raw[:4]:
        if not isinstance(r, dict):
            continue
        out.append(
            {
                "source": str(r.get("source") or "")[:80],
                "title": str(r.get("title") or "")[:220],
                "url": str(r.get("url") or ""),
            }
        )
    return out


def _build_news_events(narrative: dict) -> tuple[list[dict], dict[int, dict]]:
    events: list[dict] = []
    by_n: dict[int, dict] = {}
    for i, ev in enumerate(narrative.get("timeline") or [], start=1):
        if not isinstance(ev, dict):
            continue
        imp = ev.get("importance") or "med"
        item = {
            "id": f"news-{i}",
            "kind": "news",
            "date": str(ev.get("date") or "")[:10],
            "title": str(ev.get("title") or "")[:220],
            "body": "",
            "importance": imp if imp in _IMP_ORDER else "med",
            "refs": _refs(ev.get("refs")),
            "assessment": None,
        }
        if item["title"]:
            by_n[i] = item
            events.append(item)
    return events, by_n


def _build_disclosure_events(disclosures: dict, start: int) -> tuple[list[dict], dict[int, dict]]:
    events: list[dict] = []
    by_n: dict[int, dict] = {}
    n = start
    for ev in (disclosures.get("events") or [])[:16]:
        if not isinstance(ev, dict):
            continue
        kind = str(ev.get("kind") or "")
        if kind == "financial_period":
            continue
        source = str(ev.get("source") or "公司披露")
        title = str(ev.get("title") or "")[:220]
        date = str(ev.get("date") or "")[:10]
        summary = str(ev.get("summary") or "")
        item = {
            "id": f"disclosure-{n}",
            "kind": "disclosure",
            "date": date,
            "title": title,
            "headline": str(ev.get("headline") or ""),
            "insight": str(ev.get("insight") or ""),
            "impact": str(ev.get("impact") or ""),
            "confidence": str(ev.get("confidence") or ""),
            "body": summary[:900] if kind == "transcript" else "",
            "importance": ev.get("importance") or "high",
            "refs": [
                {
                    "source": source,
                    "title": title,
                    "url": str(ev.get("url") or ""),
                }
            ],
            "assessment": None,
            "disclosure_kind": kind,
        }
        if title:
            by_n[n] = item
            events.append(item)
            n += 1
    return events, by_n


def _journal_prompt_block(entries: list[dict], prices: dict[int, str]) -> str:
    lines: list[str] = []
    for e in entries:
        eid = int(e["id"])
        lines.append(f"[j{eid}] {e['entry_date']} 价格反馈：{prices.get(eid) or '暂无价格反馈'}")
        lines.append(str(e.get("body") or "").strip()[:900])
    return "\n".join(lines)


def _news_prompt_block(news_by_n: dict[int, dict]) -> str:
    lines: list[str] = []
    for n, ev in news_by_n.items():
        refs = "；".join(
            f"{r.get('source')}: {r.get('title')}" for r in ev.get("refs") or [] if r.get("title")
        )
        title = ev.get("headline") or ev.get("title") or ""
        lines.append(
            f"[e{n}] {ev.get('date') or '日期不详'} {ev.get('importance') or 'med'} "
            f"{ev.get('kind') or 'event'} {title}"
        )
        body = str(ev.get("insight") or ev.get("body") or "").strip()
        if body:
            lines.append(f"    摘要：{body[:700]}")
        if refs:
            lines.append(f"    来源：{refs[:500]}")
    return "\n".join(lines) or "暂无重大资讯事件。"


def _assessments_from_llm(
    symbol: str,
    name: str,
    entries: list[dict],
    news_by_n: dict[int, dict],
    prices: dict[int, str],
    role: str,
) -> tuple[str, dict[int, dict], str]:
    if not entries:
        return "", {}, ""
    prompt = (
        _load_prompt("stock_reflection_timeline")
        .replace("{{NAME}}", name)
        .replace("{{SYMBOL}}", symbol)
        .replace("{{JOURNALS}}", _journal_prompt_block(entries, prices))
        .replace("{{EVENTS}}", _news_prompt_block(news_by_n))
    )
    _, model = gateway.resolve_role(role)
    raw = gateway.complete(
        [{"role": "user", "content": prompt}],
        role=role,
        response_format={"type": "json_object"},
    )
    data = _parse_json_lenient(raw)
    summary = str(data.get("summary") or "").strip()[:500] if isinstance(data, dict) else ""
    by_entry: dict[int, dict] = {}
    raw_items = data.get("assessments") if isinstance(data, dict) else None
    if not isinstance(raw_items, list):
        return summary, by_entry, model
    known_ids = {int(e["id"]) for e in entries}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        try:
            entry_id = int(item.get("entry_id"))
        except (TypeError, ValueError):
            continue
        if entry_id not in known_ids:
            continue
        verdict = str(item.get("verdict") or "尚未检验")
        confidence = str(item.get("confidence") or "low")
        refs: list[dict] = []
        seen_urls: set[str] = set()
        evidence = item.get("evidence") if isinstance(item.get("evidence"), list) else []
        for v in evidence[:4]:
            try:
                key = int(v)
            except (TypeError, ValueError):
                continue
            ev = news_by_n.get(key)
            if not ev:
                continue
            for r in ev.get("refs") or []:
                url = r.get("url") or ""
                if url and url in seen_urls:
                    continue
                seen_urls.add(url)
                refs.append(r)
            if not ev.get("refs"):
                refs.append({"source": "", "title": ev.get("title") or "", "url": ""})
        by_entry[entry_id] = {
            "verdict": verdict if verdict in _VERDICTS else "尚未检验",
            "confidence": confidence if confidence in _CONFIDENCE else "low",
            "text": str(item.get("text") or "").strip()[:420],
            "price": prices.get(entry_id, ""),
            "refs": refs[:4],
        }
    return summary, by_entry, model


def generate_reflection_timeline(symbol: str, role: str = "summarize") -> dict:
    """生成「看·综合认知」：个人判断 + 重大资讯/披露 + LLM 对判断的事实反馈。"""
    sym = parse_symbol(symbol)
    entries = list(reversed(list_entries(sym.canonical)))  # 旧 → 新，方便模型理解因果顺序
    narrative = _ensure_narrative(sym.canonical)
    name = narrative.get("name") or search.display_name(sym.canonical)
    news_events, news_by_n = _build_news_events(narrative)
    from ..news import service as news_service

    disclosures = news_service.stock_disclosures(sym.canonical, limit=20)
    disclosure_events, disclosure_by_n = _build_disclosure_events(disclosures, len(news_by_n) + 1)
    evidence_by_n = {**news_by_n, **disclosure_by_n}
    prices = _price_feedback(sym.canonical, entries)
    if entries:
        summary, assessments, model = _assessments_from_llm(
            sym.canonical, name, entries, evidence_by_n, prices, role
        )
    else:
        summary, assessments, model = (
            narrative.get("summary")
            or "还没有个人判断；先把判断写下来，后续新闻和价格变化才有复盘对象。",
            {},
            narrative.get("model") or "",
        )
    journal_events: list[dict] = []
    for e in entries:
        eid = int(e["id"])
        body = str(e.get("body") or "")
        journal_events.append(
            {
                "id": f"journal-{eid}",
                "kind": "journal",
                "date": e["entry_date"],
                "title": body.splitlines()[0][:80] or "个人判断",
                "body": body,
                "importance": "high",
                "journal_id": eid,
                "refs": [],
                "assessment": assessments.get(eid),
            }
        )
    events = journal_events + disclosure_events + news_events
    events.sort(
        key=lambda ev: (
            ev.get("date") or "",
            1 if ev.get("kind") == "journal" else 0,
            -_IMP_ORDER.get(ev.get("importance") or "med", 2),
        ),
        reverse=True,
    )
    _save_reflection(
        sym.canonical,
        name,
        summary,
        events,
        model,
        len(entries),
        len(news_events),
    )
    return get_reflection_timeline(sym.canonical) or {
        "symbol": sym.canonical,
        "name": name,
        "summary": summary,
        "events": events,
        "model": model,
        "journal_count": len(entries),
        "news_count": len(news_events),
        "created_at": None,
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
        out = _out(row)
    finally:
        conn.close()
    _delete_reflection(sym.canonical)
    return out


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
        prev = conn.execute(
            "SELECT symbol FROM journal_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if prev is None:
            raise NotFound(f"日记 {entry_id} 不存在")
        if sets:
            sets.append("updated_at = datetime('now')")
            params.append(entry_id)
            cur = conn.execute(f"UPDATE journal_entries SET {', '.join(sets)} WHERE id = ?", params)
            conn.commit()
            if cur.rowcount == 0:
                raise NotFound(f"日记 {entry_id} 不存在")
        row = conn.execute("SELECT * FROM journal_entries WHERE id = ?", (entry_id,)).fetchone()
        if row is None:
            raise NotFound(f"日记 {entry_id} 不存在")
        out = _out(row)
    finally:
        conn.close()
    _delete_reflection(str(prev["symbol"]))
    if out["symbol"] != prev["symbol"]:
        _delete_reflection(out["symbol"])
    return out


def delete_entry(entry_id: int) -> None:
    conn = get_conn()
    try:
        prev = conn.execute(
            "SELECT symbol FROM journal_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if prev is None:
            raise NotFound(f"日记 {entry_id} 不存在")
        cur = conn.execute("DELETE FROM journal_entries WHERE id = ?", (entry_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise NotFound(f"日记 {entry_id} 不存在")
    finally:
        conn.close()
    _delete_reflection(str(prev["symbol"]))
