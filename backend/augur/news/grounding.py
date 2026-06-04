"""把 LLM 给的「公司名 + 市场」**确定性接地**到真实 `MARKET:CODE`（防编造）。

ticker 只能来自本地目录∪东财的真实命中：先验 LLM 的 code_guess、再按公司名强命中；弱模糊一律
判未解析（只保留人读名）。供「今日机会」与「新闻自动标股」（stock_tag）复用——单一真相。
"""

from __future__ import annotations

import re

from ..market import search

_VALID_MARKETS = ("US", "HK", "CN", "KR")


def simplify(s: str) -> str:
    return re.sub(r"[\s\-_.,'\"·()（）]", "", s or "").lower()


def resolve_company(name: str, market: str, code_guess: str = "") -> tuple[str | None, str, bool]:
    """name+market → (symbol|None, 展示名, resolved)。弱模糊一律判未解析。"""
    market = (market or "").upper()
    if market not in _VALID_MARKETS:
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
            q = simplify(name)
            hn, hs = simplify(h["name"]), simplify(h.get("sub", ""))
            strong = bool(q) and (
                q in hn or hn in q or (hs and (q in hs or hs in q)) or h["code"].lstrip("0") == q
            )
            if strong:
                return h["symbol"], search.display_name(h["symbol"]), True
    return None, name, False
