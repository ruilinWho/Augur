"""自选股定向抓取 lane（CLAUDE.md §1 三支柱融合的地基）。

对**每只自选股**按 ticker 直接拉该公司新闻（雅虎逐-ticker API），落库为 `lane='ticker'`
并**确定性挂钩**到该 symbol（`matched_by='targeted'`——零幻觉，我们本就知道是哪只股）。

为什么需要：聚合 RSS + 按公司名匹配会漏掉**新股 / 冷门票**（CRWV/NBIS/ALAB 等本地目录
没有干净英文名 → linker 名字命中失败）。定向抓取按 ticker 直取、不依赖名字，补齐覆盖，
并为「标的叙事时间线」沉淀历史。这些条目**不进全局主题流 / 日报 / 要点**（靠 `lane` 区隔），
只服务个股视图——避免 28 只股 × 十几条把宏观策展流淹没。

翻译/相关性判定也按 `lane='feed'` 跳过本 lane（见 relevance/translate）：语言由个股视图的
LLM 清洗与「叙事」综合时处理，不额外烧 cheap 配额。
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..market import search
from ..storage import get_conn
from ..watchlist import service as wl
from . import classify, ticker_news

_PER_STOCK = 15  # 每只股取前 N 条（雅虎 .news 本就 ~10-20 条）
_MAX_WORKERS = 8  # 并发只数（雅虎逐-ticker，ticker_news 自带 3h 缓存）


def watchlist_symbols() -> list[str]:
    """自选分区树里的全部去重 symbol（保持稳定顺序）。"""
    out: list[str] = []
    seen: set[str] = set()

    def walk(node: dict) -> None:
        for it in node.get("items", []):
            s = it["symbol"]
            if s not in seen:
                seen.add(s)
                out.append(s)
        for ch in node.get("children", []):
            walk(ch)

    for root in wl.list_tree(None):
        walk(root)
    return out


def _store(symbol: str, name: str, items: list[dict]) -> int:
    """落库 lane='ticker' + 确定性挂钩到 symbol。返回新插入条数（已存在的只补挂钩）。"""
    if not items:
        return 0
    # lang 按市场推断（雅虎也会给港/A/韩股中文/韩文标题），别一律标 'en'
    market = symbol.partition(":")[0]
    lang = {"CN": "zh", "HK": "zh", "KR": "ko"}.get(market, "en")
    conn = get_conn()
    inserted = 0
    try:
        for it in items:
            url = (it.get("url") or "").strip()
            title = (it.get("title") or "").strip()
            if not url or not title:
                continue
            theme, topics = classify.classify_rule(title, "", "")
            before = conn.total_changes
            conn.execute(
                "INSERT OR IGNORE INTO news_items "
                "(source, title, url, summary, lang, category, published_at, "
                "theme, topics, classified_by, lane) "
                "VALUES (?, ?, ?, '', ?, '', ?, ?, ?, 'rule', 'ticker')",
                (
                    it["source"],
                    title[:500],
                    url,
                    lang,
                    it.get("published_at"),
                    theme,
                    json.dumps(topics, ensure_ascii=False),
                ),
            )
            inserted += conn.total_changes - before
            row = conn.execute("SELECT id FROM news_items WHERE url = ?", (url,)).fetchone()
            if not row:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO news_item_symbols "
                "(news_id, symbol, name, confidence, matched_by) "
                "VALUES (?, ?, ?, 'high', 'targeted')",
                (row["id"], symbol, name),
            )
            conn.execute("UPDATE news_items SET linked = 1 WHERE id = ?", (row["id"],))
        conn.commit()
        return inserted
    finally:
        conn.close()


def refresh_watchlist(symbols: list[str] | None = None) -> dict:
    """对全部（或给定）自选股定向抓取并落库挂钩。并发、容忍单只失败。"""
    syms = symbols if symbols is not None else watchlist_symbols()
    if not syms:
        return {"stocks": 0, "fetched": 0, "inserted": 0, "failed": 0}
    names = {s: search.display_name(s) for s in syms}
    fetched = inserted = failed = 0
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:
        futs = {ex.submit(ticker_news.ticker_news, s, _PER_STOCK): s for s in syms}
        for fut in as_completed(futs):
            sym = futs[fut]
            try:
                got = fut.result()
            except Exception:  # noqa: BLE001 — 单只失败不中断整体
                failed += 1
                continue
            fetched += len(got)
            inserted += _store(sym, names.get(sym, ""), got)
    return {"stocks": len(syms), "fetched": fetched, "inserted": inserted, "failed": failed}
