"""discovery 域纯逻辑（「寻」）：聚合自选外的反复出现标的。

喂料来源 = news_item_symbols 里 matched_by='llm' 的挂钩（stock_tag 对相关新闻标股，**不限自选**）。
对它们按标的聚合提及次数/出现天数/证据，**排除当前自选**（按 symbol 精确 + 同名归并，
处理 GOOGL↔GOOG、A/H 同名双列等别名噪音），UPSERT 进 discovery_candidates。
作者拍板状态（dismissed/promoted）在重算时保留，不被复活。

重算时再批量过一遍 cheap-LLM：判每个候选「这些新闻是否说明它值得投资关注」+ 给一句话理由
（筛掉蹭热点/八卦/宏观顺带提一嘴的，留下有实质信号的）。LLM 未配置/失败则全保留、reason 空。

边界：与「机会」（news_opportunities，当日事件论点卡、每日覆盖）正交——这是标的轴、跨天累积。
"""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor

from .. import runtime_config
from ..llm import gateway
from ..market import search
from ..market import service as market_svc
from ..news import directed
from ..storage import get_conn

_MIN_MENTIONS = 2  # 默认门槛：至少出现 2 次才算候选（1 次多为噪音）
_MAX_EVIDENCE = 12  # 证据收集上界（实际展示条数由 discovery_news_n 配置；这里给收集留余量）


def _parse_json(raw: str) -> dict:
    """从 LLM 回复抽 JSON 对象（容忍代码围栏/前后杂字）→ dict；失败 → {}。"""
    s = (raw or "").strip()
    if "```" in s:
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.DOTALL)
        if m:
            s = m.group(1).strip()
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(0))
                return obj if isinstance(obj, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}


_JUDGE_CHUNK = 15  # 每次 LLM 判多少个候选（喂全部会让 prompt 过大、又慢又容易解析失败）
_JUDGE_MAX = 30  # 只判信号最强的前 N 个（其余弱信号长尾不进「关注中」——这就是「筛选」本身）
_REASON_REJUDGE_GROWTH = 3  # 提及数较上次涨了这么多才重判理由（小幅波动复用旧理由，省时）


def _fallback(cands: list[dict]) -> dict[str, dict]:
    return {c["symbol"]: {"worth": True, "reason": ""} for c in cands}


def _judge_chunk(chunk: list[dict]) -> dict[str, dict]:
    """判一个 chunk → {symbol: {worth, reason}}。失败/解析空 → 该 chunk 全 worth=True、reason=''。"""
    lines = [
        f'{i}. {c["name"]}（{c["symbol"]}）｜近 {c["count"]} 次提及｜证据：'
        + "；".join(e.get("title", "") for e in c["evidence"][:3])
        for i, c in enumerate(chunk, start=1)
    ]
    prompt = (
        "你在帮我做投资「发现」：下面是一批**不在我自选**、但最近被新闻反复提到的股票，"
        "每个带名字、提及次数、几条证据标题。\n\n"
        "对每一个判断：**这些新闻是否说明这支股票值得我纳入投资关注**——要有实质的"
        "催化/基本面/订单产能/产业链/政策信号才算值得；纯蹭热点、八卦、宏观背景里顺带提一嘴、"
        "与公司投资逻辑无关的，不算（worth=false）。拿不准就倾向值得（worth=true）。\n"
        "再给**一句话理由**：用大白话、具体说为什么（不）值得关注，别空话。\n\n"
        "只输出 JSON（键＝编号字符串）：\n"
        '{"1": {"worth": true, "reason": "具体一句话"}, "2": {"worth": false, "reason": "为什么不值得"}}\n\n'
        + "\n".join(lines)
    )
    try:
        raw = gateway.complete(
            [{"role": "user", "content": prompt}],
            role="cheap",
            response_format={"type": "json_object"},
        )
        data = _parse_json(raw)
    except Exception:  # noqa: BLE001 — 失败退回全保留，不挡 discovery
        return _fallback(chunk)
    if not data:
        return _fallback(chunk)
    out: dict[str, dict] = {}
    for i, c in enumerate(chunk, start=1):
        d = data.get(str(i)) if isinstance(data, dict) else None
        d = d if isinstance(d, dict) else {}
        worth = d.get("worth")
        out[c["symbol"]] = {
            "worth": True if worth is None else bool(worth),  # 缺判定→保留
            "reason": str(d.get("reason") or "")[:160],
        }
    return out


def _judge_and_reason(cands: list[dict]) -> dict[str, dict]:
    """批量 cheap-LLM：判每个候选「是否值得纳入投资关注」+ 一句话理由。

    切成 `_JUDGE_CHUNK` 个一批**并发**判（喂全部一次会又慢又容易解析失败）；输出
    {symbol: {worth, reason}}。LLM 未配置 → 全部 worth=True、reason=''（不挡「寻」，退回纯统计）。
    """
    if not cands:
        return {}
    try:
        gateway.check_ready("cheap")
    except gateway.LLMNotConfigured:
        return _fallback(cands)
    chunks = [cands[i : i + _JUDGE_CHUNK] for i in range(0, len(cands), _JUDGE_CHUNK)]
    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=min(4, len(chunks))) as ex:
        for res in ex.map(_judge_chunk, chunks):
            out.update(res)
    return out


def _norm_name(s: str) -> str:
    """归一化公司名做等价判断：去空白/标点/常见后缀、小写。用于自选别名剪枝与双列归并。"""
    s = (s or "").lower()
    s = re.sub(r"[\s.,\-_()（）·、]", "", s)
    return s


def _norm_title(s: str) -> str:
    """归一化标题做近重判定：去空白/标点、小写、截短——同一事件不同来源/措辞折叠成一条。"""
    return re.sub(r"[\s\W_]+", "", (s or "").lower())[:48]


def _dedup_aggregate(ev: list[dict], fresh: dict[int, dict]) -> list[dict]:
    """证据去重 + 多源聚合 + 翻译刷新：按归一标题把同一事件折叠成一条，合并报道来源。

    `fresh`（可空）= {news_id: {title, title_zh, source, url, pub}}：读时用最新译文/来源覆盖
    存量快照（接住物化之后才补上的中文翻译）。保持首次出现顺序（输入为新→旧）。幂等。
    """
    groups: dict[str, dict] = {}
    order: list[str] = []
    for e in ev:
        nid = e.get("news_id")
        f = (fresh.get(nid) if nid is not None else None) or {}
        title = (f.get("title_zh") or f.get("title") or e.get("title") or "").strip()
        source = (f.get("source") or e.get("source") or "").strip()
        url = (e.get("url") or f.get("url") or "").strip()
        date = (e.get("date") or (f.get("pub") or "")[:10] or "").strip()
        srcs = [s for s in (e.get("sources") or []) if s]
        if source and source not in srcs:
            srcs.insert(0, source)
        key = _norm_title(title) or url or str(nid)
        g = groups.get(key)
        if g is None:
            groups[key] = {
                "news_id": nid,
                "title": title[:200],
                "source": srcs[0] if srcs else source,
                "sources": list(dict.fromkeys(srcs)),
                "url": url,
                "date": date,
            }
            order.append(key)
        else:
            for s in srcs:
                if s not in g["sources"]:
                    g["sources"].append(s)
    return [groups[k] for k in order]


def _enrich_evidence(conn, cands: list[dict]) -> None:
    """读时清洗候选证据：批量拉最新 title_zh/来源，再 _dedup_aggregate（翻译跟进 + 去重 + 聚合）。

    自愈：把物化在 _dedup_aggregate 之前、仍带重复标题的存量证据当场清掉，无需重算。
    """
    ids = list(
        {e["news_id"] for c in cands for e in c.get("evidence", []) if e.get("news_id") is not None}
    )
    fresh: dict[int, dict] = {}
    for i in range(0, len(ids), 400):  # 避开 SQLite 变量上限
        chunk = ids[i : i + 400]
        qs = ",".join("?" * len(chunk))
        for r in conn.execute(
            f"SELECT id, title, title_zh, source, url, published_at AS pub "
            f"FROM news_items WHERE id IN ({qs})",
            tuple(chunk),
        ).fetchall():
            fresh[r["id"]] = {
                "title": r["title"],
                "title_zh": r["title_zh"],
                "source": r["source"],
                "url": r["url"],
                "pub": r["pub"],
            }
    for c in cands:
        c["evidence"] = _dedup_aggregate(c.get("evidence", []), fresh)


def _market(symbol: str) -> str:
    return symbol.partition(":")[0]


def refresh() -> dict:
    """重算候选池：聚合 llm 挂钩、排除自选、归并别名、UPSERT（保留作者状态）。"""
    conn = get_conn()
    try:
        wl_syms = set(directed.watchlist_symbols())
        wl_names = {_norm_name(search.display_name(s)) for s in wl_syms}
        ev_cap = runtime_config.get_discovery_news_n()  # 每候选收集/展示的证据条数（可配）

        # 跨语言/股份类别名归并：候选名经检索 top-2 解析出"等价 symbol 集"（如 谷歌→GOOGL+GOOG、
        # 阿里巴巴→09988+BABA），任一落在自选里即视作已覆盖。按归一名缓存，避免逐行重复检索。
        _equiv_cache: dict[str, bool] = {}

        def _covered_by_watchlist(name: str, nkey: str) -> bool:
            if nkey in wl_names:
                return True
            cached = _equiv_cache.get(nkey)
            if cached is not None:
                return cached
            hit = any(h["symbol"] in wl_syms for h in search.search(name, limit=2))
            _equiv_cache[nkey] = hit
            return hit

        rows = conn.execute(
            "SELECT nis.symbol AS symbol, nis.name AS name, ni.id AS nid, ni.title AS title, "
            "ni.title_zh AS title_zh, ni.source AS source, ni.url AS url, ni.published_at AS pub, "
            "ni.theme AS theme "
            "FROM news_item_symbols nis JOIN news_items ni ON ni.id = nis.news_id "
            "WHERE nis.matched_by = 'llm' "
            "ORDER BY ni.published_at DESC"
        ).fetchall()

        # 按"归一化名"聚合，把同名双重上市（A/H、ADR 同名）并到一个候选
        groups: dict[str, dict] = {}
        for r in rows:
            sym = r["symbol"]
            if sym in wl_syms:
                continue  # 已自选，跳过
            nm = r["name"] or search.display_name(sym)
            nkey = _norm_name(nm)
            if not nkey or _covered_by_watchlist(nm, nkey):
                continue  # 与某只自选股同名/同公司（GOOGL=GOOG、BABA=09988、A/H 双列）→ 已覆盖
            g = groups.get(nkey)
            if g is None:
                g = groups[nkey] = {
                    "name": nm,
                    "count": 0,
                    "days": set(),
                    "evidence": [],
                    "ev_urls": set(),
                    "sym_counts": {},
                    "themes": {},
                }
            g["count"] += 1
            g["sym_counts"][sym] = g["sym_counts"].get(sym, 0) + 1
            th = (r["theme"] or "").strip()
            if th and th != "other":
                g["themes"][th] = g["themes"].get(th, 0) + 1
            day = (r["pub"] or "")[:10]
            if day:
                g["days"].add(day)
            url = (r["url"] or "").strip()
            title = (r["title_zh"] or r["title"] or "").strip()
            # 只按 URL 去重收集（保留同事件不同来源的变体，供稍后聚合来源）；标题级去重 +
            # 多源聚合统一在 _dedup_aggregate 里做。多收一些给聚合留余量，封顶到 _MAX_EVIDENCE。
            if url and url not in g["ev_urls"] and len(g["evidence"]) < _MAX_EVIDENCE:
                g["ev_urls"].add(url)
                g["evidence"].append(
                    {
                        "news_id": r["nid"],
                        "title": title[:200],
                        "source": r["source"] or "",
                        "url": url,
                        "date": day,
                    }
                )

        # 物化过门槛的候选，再批量交给 cheap-LLM 判「是否值得关注」+ 一句话理由（筛选 ① + 理由 ②）
        candidates: list[dict] = []
        for g in groups.values():
            if g["count"] < _MIN_MENTIONS:
                continue
            # 主 symbol = 组内提及最多者（双列里取信号更强的那一边）
            symbol = max(g["sym_counts"].items(), key=lambda kv: kv[1])[0]
            theme = max(g["themes"].items(), key=lambda kv: kv[1])[0] if g["themes"] else ""
            # 去重 + 多源聚合 + 封顶：同一事件多源折叠成一条、合并报道来源
            evidence = _dedup_aggregate(g["evidence"], {})[:ev_cap]
            candidates.append(
                {
                    "symbol": symbol,
                    "name": g["name"],
                    "count": g["count"],
                    "days": sorted(g["days"]),
                    "theme": theme,
                    "evidence": evidence,
                }
            )
        # 只对信号最强的前 _JUDGE_MAX 个跑 LLM 判定（提及多/出现天数多优先）；其余弱信号长尾
        # 直接不进「关注中」——这正是作者要的「筛选：至少值得关注」。也把 LLM 量级压下来（原先
        # 一次喂 200+ 个又慢又解析失败）。
        candidates.sort(key=lambda c: (c["count"], len(c["days"])), reverse=True)
        candidates = candidates[:_JUDGE_MAX]
        # 复用上次理由：提及次数没变的候选不重判——LLM 慢，每次重算全量跑要好几分钟。只对**新出现**
        # 或**提及数变了**（有新料）的候选送 LLM，稳态下重算近乎瞬时。
        prev = {
            r["symbol"]: (r["mention_count"], r["reason"])
            for r in conn.execute(
                "SELECT symbol, mention_count, reason FROM discovery_candidates WHERE reason != ''"
            ).fetchall()
        }
        cached: dict[str, dict] = {}
        to_judge: list[dict] = []
        for c in candidates:
            p = prev.get(c["symbol"])
            # 提及数没怎么涨（<阈值）就复用旧理由——LLM 慢，没必要为 +1 条新闻重判整段理由
            if p and p[1] and c["count"] - p[0] < _REASON_REJUDGE_GROWTH:
                cached[c["symbol"]] = {"worth": True, "reason": p[1]}
            else:
                to_judge.append(c)
        verdicts = {**cached, **_judge_and_reason(to_judge)}  # {symbol: {worth, reason}}

        kept: set[str] = set()
        for c in candidates:
            v = verdicts.get(c["symbol"]) or {"worth": True, "reason": ""}
            if not v.get("worth", True):
                continue  # 筛掉：LLM 判定这些新闻不足以说明它值得关注
            symbol = c["symbol"]
            kept.add(symbol)
            days = c["days"]
            conn.execute(
                "INSERT INTO discovery_candidates "
                "(symbol, name, mention_count, day_span, first_seen_at, last_seen_at, evidence, "
                "theme, reason, status, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', datetime('now')) "
                "ON CONFLICT(symbol) DO UPDATE SET "
                "name=excluded.name, mention_count=excluded.mention_count, "
                "day_span=excluded.day_span, first_seen_at=excluded.first_seen_at, "
                "last_seen_at=excluded.last_seen_at, evidence=excluded.evidence, "
                "theme=excluded.theme, reason=excluded.reason, "
                "updated_at=datetime('now')",  # status 不覆盖：保留作者拍板
                (
                    symbol,
                    c["name"][:120],
                    c["count"],
                    len(days),
                    days[0] if days else None,
                    days[-1] if days else None,
                    json.dumps(c["evidence"], ensure_ascii=False),
                    c["theme"],
                    v.get("reason", ""),
                ),
            )

        # 清理本轮不再合格的 new 候选（被归并/剔除/跌破门槛）——只删 new，保留 dismissed/promoted
        existing_new = {
            r["symbol"]
            for r in conn.execute(
                "SELECT symbol FROM discovery_candidates WHERE status='new'"
            ).fetchall()
        }
        stale = existing_new - kept
        for s in stale:
            conn.execute("DELETE FROM discovery_candidates WHERE symbol=? AND status='new'", (s,))

        # 已加入自选的旧候选 → 标 promoted（保留发现轨迹，不删）
        if wl_syms:
            qs = ",".join("?" * len(wl_syms))
            conn.execute(
                f"UPDATE discovery_candidates SET status='promoted' "
                f"WHERE symbol IN ({qs}) AND status != 'promoted'",
                tuple(wl_syms),
            )
        conn.commit()
        return {"candidates": len(kept)}
    finally:
        conn.close()


def _out(row) -> dict:
    try:
        ev = json.loads(row["evidence"] or "[]")
    except (ValueError, TypeError):
        ev = []
    keys = row.keys()
    return {
        "symbol": row["symbol"],
        "name": row["name"],
        "market": _market(row["symbol"]),
        "mention_count": row["mention_count"],
        "day_span": row["day_span"],
        "first_seen_at": row["first_seen_at"],
        "last_seen_at": row["last_seen_at"],
        "evidence": ev,
        "theme": row["theme"] if "theme" in keys else "",
        "reason": row["reason"] if "reason" in keys else "",
        "status": row["status"],
    }


# ── 主题级偏好（屏蔽某主题——智能忽略：你不想看的整类不再出现）──
_MUTED_PREF = "discovery_muted_themes"


def muted_themes() -> list[str]:
    return list(runtime_config.get_pref(_MUTED_PREF, []) or [])


def set_theme_muted(theme: str, muted: bool) -> list[str]:
    theme = (theme or "").strip()
    if not theme:
        raise ValueError("主题不能为空")
    cur = set(muted_themes())
    if muted:
        cur.add(theme)
    else:
        cur.discard(theme)
    runtime_config.set_pref(_MUTED_PREF, sorted(cur))
    return sorted(cur)


# ── 市场级偏好（屏蔽某市场，如韩股——不想看的整个市场不再出现，可恢复）──
_MUTED_MKT_PREF = "discovery_muted_markets"
_MARKETS = (("US", "美股"), ("HK", "港股"), ("CN", "A股"), ("KR", "韩股"))


def muted_markets() -> list[str]:
    return list(runtime_config.get_pref(_MUTED_MKT_PREF, []) or [])


def set_market_muted(market: str, muted: bool) -> list[str]:
    market = (market or "").strip().upper()
    if not market:
        raise ValueError("市场不能为空")
    cur = set(muted_markets())
    if muted:
        cur.add(market)
    else:
        cur.discard(market)
    runtime_config.set_pref(_MUTED_MKT_PREF, sorted(cur))
    return sorted(cur)


def market_counts() -> list[dict]:
    """四市场 new 候选数 + 是否被屏蔽——供「偏好」面板按市场屏蔽。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT substr(symbol, 1, instr(symbol, ':') - 1) AS mkt, COUNT(*) AS n "
            "FROM discovery_candidates WHERE status='new' GROUP BY mkt"
        ).fetchall()
    finally:
        conn.close()
    counts = {r["mkt"]: r["n"] for r in rows}
    muted = set(muted_markets())
    return [
        {"market": m, "label": lbl, "count": counts.get(m, 0), "muted": m in muted}
        for m, lbl in _MARKETS
    ]


def list_candidates(status: str = "new", limit: int = 100) -> list[dict]:
    """按状态列候选，提及次数→出现天数降序。status='new' 时在 SQL 里剔除被屏蔽的主题/市场
    （必须 LIMIT 之前过滤，否则屏蔽会把列表截断到不足 limit）。"""
    where = ["status = ?"]
    args: list = [status]
    if status == "new":
        muted_t = [m for m in muted_themes() if m]
        if muted_t:
            where.append(f"theme NOT IN ({','.join('?' * len(muted_t))})")
            args += muted_t
        for mkt in (m for m in muted_markets() if m):
            where.append("symbol NOT LIKE ?")  # 屏蔽整个市场（symbol 形如 KR:005930）
            args.append(f"{mkt}:%")
    sql = (
        f"SELECT * FROM discovery_candidates WHERE {' AND '.join(where)} "
        "ORDER BY mention_count DESC, day_span DESC, last_seen_at DESC LIMIT ?"
    )
    args.append(limit)
    conn = get_conn()
    try:
        rows = conn.execute(sql, tuple(args)).fetchall()
        cands = [_out(r) for r in rows]
        _enrich_evidence(conn, cands)  # 读时去重 + 多源聚合 + 翻译跟进（自愈存量重复）
        return cands
    finally:
        conn.close()


def theme_counts() -> list[dict]:
    """各主题下 new 候选数 + 是否被屏蔽——供「偏好」面板展示与一键屏蔽。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT theme, COUNT(*) AS n FROM discovery_candidates "
            "WHERE status='new' AND theme != '' GROUP BY theme ORDER BY n DESC"
        ).fetchall()
    finally:
        conn.close()
    muted = set(muted_themes())
    # 含被屏蔽但当前无 new 候选的主题，仍要能在面板里取消屏蔽
    seen = {r["theme"] for r in rows}
    out = [{"theme": r["theme"], "count": r["n"], "muted": r["theme"] in muted} for r in rows]
    for t in muted:
        if t not in seen:
            out.append({"theme": t, "count": 0, "muted": True})
    return out


def set_status(symbol: str, status: str) -> dict:
    if status not in ("new", "dismissed", "promoted"):
        raise ValueError(f"非法状态：{status}")
    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE discovery_candidates SET status = ?, updated_at = datetime('now') "
            "WHERE symbol = ?",
            (status, symbol),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise ValueError(f"候选 {symbol} 不存在")
        row = conn.execute(
            "SELECT * FROM discovery_candidates WHERE symbol = ?", (symbol,)
        ).fetchone()
        out = _out(row)
        _enrich_evidence(conn, [out])
        return out
    finally:
        conn.close()


# ── 行情异动信号（近月大涨 + 放量）——懒加载、内存缓存，不拖慢重算/列表 ──
_signal_cache: dict[str, tuple[float, dict | None]] = {}
_SIGNAL_TTL = 1800.0  # 30 分钟（行情按日变，不必频繁回源）
_HOT_RET = 12.0  # 近月涨幅 ≥ 这个 % 才算「大涨」
_HOT_VOL = 1.4  # 放量比 ≥ 这个才算「放量」


def _signal_for(symbol: str) -> dict | None:
    now = time.time()
    hit = _signal_cache.get(symbol)
    if hit and now - hit[0] < _SIGNAL_TTL:
        return hit[1]
    sig = market_svc.momentum(symbol)
    _signal_cache[symbol] = (now, sig)
    return sig


def signals(limit: int = 60) -> dict[str, dict]:
    """当前「关注中」候选里「近月大涨且放量」的关键信号 → {symbol: {ret_pct, vol_ratio}}。

    并发取缓存优先的行情、30 分钟内存缓存；只回「值得标出」的（涨幅大且放量），其余不返回。
    与列表/重算解耦：前端拿到候选列表后再单独取信号叠加，互不阻塞。
    """
    syms = [c["symbol"] for c in list_candidates("new", limit)]
    if not syms:
        return {}
    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(_signal_for, syms))
    for sym, sig in zip(syms, results):
        if sig and sig["ret_pct"] >= _HOT_RET and sig["vol_ratio"] >= _HOT_VOL:
            out[sym] = sig
    return out
