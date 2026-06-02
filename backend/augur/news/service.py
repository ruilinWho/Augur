"""news 域纯逻辑：摄取触发、条目查询、趋势日报生成（LLM summarize 角色）。

I/O（网络在 ingest、磁盘在 storage、LLM 在 gateway）挡在外层，便于测试（CLAUDE.md §5）。
日报口径：只基于当日抓到的标题蒸馏，暴露不确定性、标注信源（§11）。一天一份，重生成覆盖。
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import datetime
from zoneinfo import ZoneInfo

from ..config import get_settings
from ..llm import gateway
from ..market import search
from ..storage import get_conn
from ..watchlist import service as wl
from . import edgar, ingest, relevance, ticker_news, translate

_DIGEST_INPUT_MAX = 100  # 喂给 LLM 的标题条数上限（控 token）

# 主题展示名与排序（前沿方向在前；与 classify.VALID_THEMES / 前端一致）
THEME_LABEL = {
    "ai": "大模型 / AI",
    "chips": "芯片 / 半导体",
    "robotics": "机器人",
    "space": "航天",
    "tech": "科技",
    "markets": "行情",
    "macro": "宏观 / 政策",
    "crypto": "加密",
    "world": "国际",
    "other": "其他",
}
THEME_ORDER = [
    "ai",
    "chips",
    "robotics",
    "space",
    "tech",
    "markets",
    "macro",
    "crypto",
    "world",
    "other",
]


def _item_out(row) -> dict:
    """row → dict，并把 topics(JSON 字符串) 反序列化为列表。"""
    d = dict(row)
    try:
        d["topics"] = json.loads(d.get("topics") or "[]")
    except (json.JSONDecodeError, TypeError):
        d["topics"] = []
    return d


def _today() -> str:
    return datetime.now(ZoneInfo(get_settings().tz)).strftime("%Y-%m-%d")


def refresh() -> dict:
    """抓取→翻译→投资相关性过滤（均 cheap 角色，失败降级不阻断）。"""
    result = ingest.ingest_all()
    try:
        result["translated"] = translate.translate_pending()
    except Exception:  # noqa: BLE001
        result["translated"] = 0
    try:
        result["filtered"] = relevance.judge_pending()  # cheap LLM 滤掉与投资无关的
    except Exception:  # noqa: BLE001
        result["filtered"] = {"judged": 0, "dropped": 0}
    return result


def recent_items(limit: int = 60, theme: str | None = None) -> list[dict]:
    """最近条目（按发布时间倒序，缺发布时间用抓取时间兜底）。可按 theme 过滤。"""
    conn = get_conn()
    try:
        # relevance != 2：滤掉 cheap LLM 判为"与投资无关"的（未判=0 仍显示，优雅降级）
        sql = "SELECT * FROM news_items WHERE relevance != 2"
        args: list = []
        if theme:
            sql += " AND theme = ?"
            args.append(theme)
        sql += " ORDER BY COALESCE(published_at, fetched_at) DESC LIMIT ?"
        args.append(limit)
        return [_item_out(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def _stock_terms(symbol: str) -> list[str]:
    """某标的的匹配词：中文展示名 + 英文名(首词)。用于在新闻标题里找相关资讯。"""
    terms: set[str] = set()
    market, _, code = symbol.partition(":")
    dn = search.display_name(symbol)
    if dn and len(dn) >= 2 and dn != code:
        terms.add(dn)
    hits = search.search(code, market=market, limit=1)
    if hits:
        for v in (hits[0].get("name"), hits[0].get("sub")):
            v = (v or "").strip()
            if len(v) >= 2:
                terms.add(v)
                tok = re.split(r"[\s,，]", v)[0]  # NVIDIA Corporation → NVIDIA
                if tok.isascii() and len(tok) >= 3:
                    terms.add(tok)
    return [t for t in terms if len(t) >= 2]


def _feed_matches(symbol: str, limit: int = 20) -> list[dict]:
    """聚合流里按公司名（中文展示名 + 英文名）匹配到的相关条目（含中文翻译）。"""
    terms = _stock_terms(symbol)
    if not terms:
        return []
    conn = get_conn()
    try:
        clause = " OR ".join(["title LIKE ? OR title_zh LIKE ?"] * len(terms))
        args: list = []
        for t in terms:
            like = f"%{t}%"
            args += [like, like]
        args.append(limit)
        rows = conn.execute(
            f"SELECT * FROM news_items WHERE ({clause}) AND relevance != 2 "
            "ORDER BY COALESCE(published_at, fetched_at) DESC LIMIT ?",
            args,
        ).fetchall()
        return [_item_out(r) for r in rows]
    finally:
        conn.close()


def _norm_url(u: str) -> str:
    return (u or "").split("?")[0].rstrip("/").lower()


def news_for_symbol(symbol: str, limit: int = 20) -> list[dict]:
    """个股相关新闻：雅虎逐-ticker API（更准、英文）∪ 聚合流按公司名匹配（中文翻译），
    url 去重、时间倒序。API 走 ticker_news（失败/空则只剩聚合流，优雅降级）。
    """
    out: list[dict] = []
    seen: set[str] = set()
    nid = -1
    for it in ticker_news.ticker_news(symbol, limit=limit):
        u = _norm_url(it["url"])
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(
            {
                "id": nid,  # API 条目无 DB id，给负数占位（前端只用作 key）
                "source": it["source"],
                "title": it["title"],
                "url": it["url"],
                "summary": "",
                "lang": "en",
                "category": "",
                "published_at": it["published_at"],
                "theme": "",
                "topics": [],
                "title_zh": None,
            }
        )
        nid -= 1
    for it in _feed_matches(symbol, limit):
        u = _norm_url(it["url"])
        if u in seen:
            continue
        seen.add(u)
        out.append(it)
    out.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    return out[:limit]


def stock_official(symbol: str, limit: int = 15) -> list[dict]:
    """某标的的官方一手文件（美股＝SEC EDGAR 申报；其他市场暂空）。

    "一条龙"骨架：未来在此并入官方 IR/新闻室 RSS、官方 X（凭桥接 key 启用）。
    """
    return edgar.filings_for(symbol, limit)


def get_report(report_date: str | None = None) -> dict | None:
    """取某日（默认最新一份）日报全文。"""
    conn = get_conn()
    try:
        if report_date:
            row = conn.execute(
                "SELECT * FROM news_reports WHERE report_date = ?", (report_date,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM news_reports ORDER BY report_date DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_reports(limit: int = 30) -> list[dict]:
    """日报列表（含 160 字预览，不含全文）。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT report_date, item_count, model, created_at, "
            "substr(body, 1, 160) AS preview "
            "FROM news_reports ORDER BY report_date DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _load_prompt(name: str) -> str:
    path = get_settings().resources_dir / "prompts" / f"{name}.md"
    return path.read_text(encoding="utf-8")


def _headlines_block(items: list[dict]) -> str:
    """按主题分组喂给 LLM（让日报在既定主题骨架内蒸馏，更稳、更省 token）。"""
    by_theme: dict[str, list[dict]] = {}
    for it in items:
        by_theme.setdefault(it.get("theme") or "other", []).append(it)
    lines: list[str] = []
    for th in THEME_ORDER:
        group = by_theme.get(th)
        if not group:
            continue
        lines.append(f"\n## {THEME_LABEL.get(th, th)}")
        lines.extend(f"- [{it['source']}] {it['title']}" for it in group)
    return "\n".join(lines).strip()


def _save_report(report_date: str, body: str, model: str, item_count: int) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO news_reports (report_date, body, model, item_count) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(report_date) DO UPDATE SET "
            "body = excluded.body, model = excluded.model, "
            "item_count = excluded.item_count, created_at = datetime('now')",
            (report_date, body, model, item_count),
        )
        conn.commit()
    finally:
        conn.close()


def generate_report_stream(
    report_date: str | None = None, role: str = "summarize"
) -> Iterator[str]:
    """生成当日趋势日报：流式产出文本增量；完成后落库（覆盖当天）。

    无新闻条目 → ValueError（前端提示先刷新）。
    """
    rd = report_date or _today()
    items = recent_items(limit=_DIGEST_INPUT_MAX)
    if not items:
        raise ValueError("暂无新闻条目，请先刷新（POST /news/refresh）")
    prompt = (
        _load_prompt("news_digest")
        .replace("{{DATE}}", rd)
        .replace("{{HEADLINES}}", _headlines_block(items))
    )
    _, model = gateway.resolve_role(role)
    buf: list[str] = []
    for delta in gateway.stream_chat([{"role": "user", "content": prompt}], role):
        buf.append(delta)
        yield delta
    body = "".join(buf).strip()
    if body:
        _save_report(rd, body, model, len(items))


# ───────────────────────── 今日投资机会（抽取 + 接地）─────────────────────────
_OPP_INPUT_MAX = 80


def _simplify(s: str) -> str:
    return re.sub(r"[\s\-_.,'\"·()（）]", "", s or "").lower()


def _parse_json_lenient(raw: str) -> dict:
    """剥围栏 + 取首个 {...}；失败 → {}（不抛 500）。"""
    s = (raw or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return {}
        return {}


def _items_block(items: list[dict]) -> tuple[str, dict[int, dict]]:
    """带 [n] 序号的条目块 + 序号→item 回查表（喂中文标题，LLM 读着更准）。"""
    lines: list[str] = []
    by_n: dict[int, dict] = {}
    for n, it in enumerate(items, start=1):
        by_n[n] = it
        cat = f"({it.get('theme')}) " if it.get("theme") else ""
        title = it.get("title_zh") or it["title"]
        lines.append(f"[{n}] {cat}[{it['source']}] {title}")
    return "\n".join(lines), by_n


def _watched() -> dict[str, list[str]]:
    """symbol → 所属分区路径列表（用于 in_watchlist 高亮）。遍历自选分区树。"""
    paths: dict[str, list[str]] = {}

    def walk(node: dict, prefix: str) -> None:
        here = f"{prefix}/{node['name']}" if prefix else node["name"]
        for it in node.get("items", []):
            paths.setdefault(it["symbol"], []).append(here)
        for ch in node.get("children", []):
            walk(ch, here)

    for root in wl.list_tree(None):
        walk(root, "")
    return paths


def _resolve_company(name: str, market: str, code_guess: str = "") -> tuple[str | None, str, bool]:
    """name+market → (symbol|None, 展示名, resolved)。

    防编造：ticker 只能来自本地目录∪东财的真实命中。先验证 LLM 的 code_guess，
    再按公司名强命中；弱模糊一律判未解析（只保留人读名）。
    """
    market = (market or "").upper()
    if market not in ("US", "HK", "CN", "KR"):
        return None, name, False
    cg = (code_guess or "").strip()
    if cg:
        hits = search.search(cg, market=market, limit=1)
        if hits and hits[0]["code"].lstrip("0").upper() == cg.lstrip("0").upper():
            sym = hits[0]["symbol"]
            return sym, search.display_name(sym), True
    if name:
        hits = search.search(name, market=market, limit=1)
        if hits:
            h = hits[0]
            q = _simplify(name)
            hn, hs = _simplify(h["name"]), _simplify(h.get("sub", ""))
            strong = bool(q) and (
                q in hn or hn in q or (hs and (q in hs or hs in q)) or h["code"].lstrip("0") == q
            )
            if strong:
                return h["symbol"], search.display_name(h["symbol"]), True
    return None, name, False


def _save_opportunities(rd: str, opps: list[dict], model: str) -> None:
    conn = get_conn()
    try:
        conn.execute("DELETE FROM news_opportunities WHERE report_date = ?", (rd,))
        conn.executemany(
            "INSERT INTO news_opportunities "
            "(report_date, rank, title, thesis, theme, confidence, caveats, "
            "related, evidence, model) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    rd,
                    i,
                    o["title"],
                    o["thesis"],
                    o["theme"],
                    o["confidence"],
                    o["caveats"],
                    json.dumps(o["related"], ensure_ascii=False),
                    json.dumps(o["evidence"], ensure_ascii=False),
                    model,
                )
                for i, o in enumerate(opps)
            ],
        )
        conn.commit()
    finally:
        conn.close()


def get_opportunities(report_date: str | None = None) -> dict | None:
    """取某日（默认今天）已生成的机会列表；无 → None。"""
    rd = report_date or _today()
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM news_opportunities WHERE report_date = ? ORDER BY rank", (rd,)
        ).fetchall()
        if not rows:
            return None
        opps = [
            {
                "title": r["title"],
                "thesis": r["thesis"],
                "theme": r["theme"],
                "confidence": r["confidence"],
                "caveats": r["caveats"],
                "related": json.loads(r["related"] or "[]"),
                "evidence": json.loads(r["evidence"] or "[]"),
            }
            for r in rows
        ]
        return {
            "report_date": rd,
            "model": rows[0]["model"],
            "item_count": 0,
            "created_at": rows[0]["created_at"],
            "opportunities": opps,
        }
    finally:
        conn.close()


def generate_opportunities(report_date: str | None = None, role: str = "summarize") -> dict:
    """阶段 A（LLM 抽取）+ 阶段 B（确定性接地到 MARKET:CODE + 交叉自选）。落库覆盖当天。"""
    rd = report_date or _today()
    items = recent_items(limit=_OPP_INPUT_MAX)
    if not items:
        raise ValueError("暂无新闻条目，请先刷新（POST /news/refresh）")
    block, by_n = _items_block(items)
    prompt = _load_prompt("news_opportunities").replace("{{DATE}}", rd).replace("{{ITEMS}}", block)
    _, model = gateway.resolve_role(role)
    raw = gateway.complete(
        [{"role": "user", "content": prompt}],
        role=role,
        response_format={"type": "json_object"},
    )
    data = _parse_json_lenient(raw)
    llm_opps = data.get("opportunities", []) if isinstance(data, dict) else []
    watched = _watched()
    out: list[dict] = []
    for o in llm_opps[:8]:
        related = []
        for c in o.get("companies") or []:
            sym, disp, resolved = _resolve_company(
                c.get("name", ""), c.get("market", ""), c.get("code_guess", "")
            )
            secs = watched.get(sym, []) if sym else []
            related.append(
                {
                    "symbol": sym,
                    "name": disp,
                    "market": (c.get("market") or "").upper(),
                    "resolved": resolved,
                    "in_watchlist": bool(secs),
                    "sections": secs,
                }
            )
        ev = []
        for n in o.get("evidence") or []:
            key = int(n) if isinstance(n, int) or (isinstance(n, str) and n.isdigit()) else None
            it = by_n.get(key) if key is not None else None
            if it:
                ev.append(
                    {
                        "news_id": it["id"],
                        "title": it.get("title_zh") or it["title"],
                        "source": it["source"],
                        "url": it["url"],
                    }
                )
        conf = o.get("confidence", "low")
        out.append(
            {
                "title": (o.get("title") or "")[:120],
                "thesis": o.get("thesis", ""),
                "theme": o.get("theme", ""),
                "confidence": conf if conf in ("low", "med", "high") else "low",
                "caveats": o.get("caveats", ""),
                "related": related,
                "evidence": ev,
            }
        )
    _save_opportunities(rd, out, model)
    return get_opportunities(rd) or {
        "report_date": rd,
        "model": model,
        "item_count": len(items),
        "created_at": None,
        "opportunities": [],
    }
