"""research 域纯逻辑（M2「研」）：单股深度研究。

口径（§11）：**只基于 Augur 已有的确定性数据**（行情/基本面/财务/已清洗新闻/SEC 申报）做综合，
不引入实时网络搜索/分析师预期（列为未来增强）；暴露不确定性、标注来源，服务决策级研究。
deep_research 角色（长上下文模型）流式生成 Markdown；一股一份、重生成覆盖、持久化。
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from ..config import get_settings
from ..llm import gateway
from ..market import fundamentals, search
from ..market import service as market_service
from ..market.symbols import parse_symbol
from ..news import edgar
from ..news import service as news_service
from ..storage import get_conn

_CUR_SYMBOL = {"USD": "$", "HKD": "HK$", "CNY": "¥", "KRW": "₩"}


def _yi(v: float | None, cur: str = "") -> str:
    """大数字 → 亿/万亿（本币）。None → —。"""
    if v is None:
        return "—"
    a = v / 1e8
    if abs(a) >= 10000:
        return f"{a / 10000:.2f}万亿{cur}"
    return f"{a:.1f}亿{cur}"


def _pct(v: float | None) -> str:
    return f"{v * 100:.1f}%" if v is not None else "—"


def _price_summary(sym) -> dict | None:
    try:
        df, _, _ = market_service.get_ohlcv(sym, "1d", "1y")
    except Exception:  # noqa: BLE001
        return None
    if df is None or df.empty:
        return None
    last = float(df.iloc[-1]["close"])
    first = float(df.iloc[0]["close"])
    return {
        "last": last,
        "chg_1y": (last / first - 1) * 100 if first else 0.0,
        "high_52w": float(df["high"].max()),
        "low_52w": float(df["low"].min()),
        "asof": df.index.max().strftime("%Y-%m-%d"),
    }


def gather(symbol: str) -> dict:
    """收集某标的的全部确定性数据 + 编号引用源（新闻 + SEC 申报）。"""
    sym = parse_symbol(symbol)
    name = search.display_name(sym.canonical)
    fund = fundamentals.get_fundamentals(sym.canonical)
    fin = fundamentals.get_financials(sym.canonical, "quarter")
    news = news_service.news_for_symbol(sym.canonical, limit=12)
    filings = edgar.filings_for(sym.canonical, limit=8)
    sources: list[dict] = []
    n = 0
    for it in news:
        n += 1
        sources.append(
            {
                "n": n,
                "title": it.get("title_zh") or it.get("title") or "",
                "source": it.get("source", ""),
                "url": it.get("url"),
                "date": (it.get("published_at") or "")[:10],
                "kind": "news",
            }
        )
    for f in filings:
        n += 1
        sources.append(
            {
                "n": n,
                "title": f.get("title", ""),
                "source": f"SEC {f.get('form', '')}".strip(),
                "url": f.get("url"),
                "date": f.get("filed_at") or "",
                "kind": "filing",
            }
        )
    return {
        "name": name,
        "symbol": sym.canonical,
        "market": sym.market,
        "currency": fund.get("currency", ""),
        "price": _price_summary(sym),
        "fundamentals": fund,
        "financials": fin,
        "sources": sources,
    }


def _format_data(d: dict) -> str:
    cur = d.get("currency", "")
    sign = _CUR_SYMBOL.get(cur, "")
    f = d["fundamentals"]
    lines: list[str] = []
    lines.append(f"公司：{d['name']}（{d['symbol']}）· {d['market']} 市场 · 币种 {cur}")
    p = d.get("price")
    if p:
        lines.append(
            f"价格（截至 {p['asof']}）：最新 {sign}{p['last']:.2f} · 近一年 {p['chg_1y']:+.1f}% · "
            f"52周区间 {sign}{p['low_52w']:.2f}–{sign}{p['high_52w']:.2f}"
        )
    pe = f.get("pe")
    pe_str = f"{pe:.1f}" if pe is not None else "—"
    lines.append(f"基本面快照：市值 {_yi(f.get('market_cap'), cur)} · P/E {pe_str}")
    lines.append(
        f"  营收 {_yi(f.get('revenue'), cur)} · 净利 {_yi(f.get('net_income'), cur)} · "
        f"净利率 {_pct(f.get('net_margin'))} · EPS "
        + (f"{f.get('eps'):.2f}" if f.get("eps") is not None else "—")
    )
    fin = d.get("financials") or {}
    periods = fin.get("periods") or []
    if periods:
        lines.append("财务趋势（季度，最新在前）：")
        for pr in periods:
            lines.append(
                f"  {pr.get('period', '?')}：营收 {_yi(pr.get('revenue'), cur)}"
                f"（同比 {_pct(pr.get('revenue_growth'))}）· 净利 {_yi(pr.get('net_income'), cur)}"
                f"（净利率 {_pct(pr.get('net_margin'))}）· EPS "
                + (f"{pr.get('eps'):.2f}" if pr.get("eps") is not None else "—")
                + f" · 自由现金流 {_yi(pr.get('fcf'), cur)}"
            )
    src = d.get("sources") or []
    news_src = [s for s in src if s["kind"] == "news"]
    fil_src = [s for s in src if s["kind"] == "filing"]
    if news_src:
        lines.append("近期相关新闻（供引用）：")
        for s in news_src:
            lines.append(f"  [{s['n']}] {s['source']} · {s['date']} {s['title']}")
    if fil_src:
        lines.append("SEC 近期申报（供引用）：")
        for s in fil_src:
            lines.append(f"  [{s['n']}] {s['source']} · {s['date']} {s['title']}")
    if not news_src and not fil_src:
        lines.append("近期新闻/申报：暂无")
    return "\n".join(lines)


def _load_prompt(name: str) -> str:
    return (get_settings().resources_dir / "prompts" / f"{name}.md").read_text(encoding="utf-8")


def _save(symbol: str, name: str, body: str, sources: list[dict], model: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO research_reports (symbol, name, body, sources, model) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(symbol) DO UPDATE SET name=excluded.name, body=excluded.body, "
            "sources=excluded.sources, model=excluded.model, created_at=datetime('now')",
            (symbol, name, body, json.dumps(sources, ensure_ascii=False), model),
        )
        conn.commit()
    finally:
        conn.close()


def get_report(symbol: str) -> dict | None:
    sym = parse_symbol(symbol)
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM research_reports WHERE symbol = ?", (sym.canonical,)
        ).fetchone()
        if not row:
            return None
        return {
            "symbol": row["symbol"],
            "name": row["name"],
            "body": row["body"],
            "sources": json.loads(row["sources"] or "[]"),
            "model": row["model"],
            "created_at": row["created_at"],
        }
    finally:
        conn.close()


def generate_stream(symbol: str, role: str = "deep_research") -> Iterator[str]:
    """生成单股深度研究：流式 Markdown；完成后落库（覆盖）。"""
    data = gather(symbol)
    prompt = (
        _load_prompt("research_stock")
        .replace("{{NAME}}", data["name"])
        .replace("{{SYMBOL}}", data["symbol"])
        .replace("{{MARKET}}", data["market"])
        .replace("{{DATA}}", _format_data(data))
    )
    _, model = gateway.resolve_role(role)
    buf: list[str] = []
    for delta in gateway.stream_chat([{"role": "user", "content": prompt}], role):
        buf.append(delta)
        yield delta
    body = "".join(buf).strip()
    if not body:
        # 模型返回空（限流空响应/被截/连接异常未抛）→ 抛错，让 router 的 sse 发 error 帧给前端，
        # 避免「点了生成→placeholder 一闪→回空态」的无反馈黑洞（§11 暴露不确定性）。
        raise ValueError("模型未返回内容，请重试或检查 deep_research 连接")
    # 落库的 sources 去掉内部 kind/date 细节无妨，保留 n/title/source/url 供前端引用
    srcs = [
        {"n": s["n"], "title": s["title"], "source": s["source"], "url": s.get("url")}
        for s in data["sources"]
    ]
    _save(data["symbol"], data["name"], body, srcs, model)


# ───────────────────────── 导入研报（他人写的 markdown，一股可多份）─────────────────────────


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
    """某股的导入研报（按 sort_order、再新→旧）。symbol 规范化，与 add/get_report 一致。"""
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
