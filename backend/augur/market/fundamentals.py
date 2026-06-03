"""基本面（市值/营收/利润/P-E）via yfinance（CLAUDE.md §7）。

yfinance 一库覆盖四市场（雅虎财经）。`.info` 较慢且偶发限流 → 内存 TTL 缓存（基本面是慢变量）。
数字为各自**本币**（USD/HKD/CNY/KRW），单位是「元」级原值，前端再按亿/万亿格式化。
缺数据（如亏损股无 P/E）一律置 None，前端显示「—」（暴露不确定性，§11）。
"""

from __future__ import annotations

import threading
import time

import yfinance as yf

from .symbols import cn_exchange

_CACHE: dict[str, tuple[float, dict]] = {}
_LOCK = threading.Lock()
_TTL = 6 * 3600.0  # 基本面 6 小时缓存足矣

_CURRENCY = {"US": "USD", "HK": "HKD", "CN": "CNY", "KR": "KRW"}


def _yahoo_symbols(symbol: str) -> list[str]:
    """归一化 MARKET:CODE → 候选雅虎代码（韩股板别未知，故 .KS/.KQ 都试）。"""
    market, _, code = symbol.partition(":")
    if market == "US":
        return [code.upper().replace(".", "-")]  # BRK.B → BRK-B
    if market == "HK":
        digits = "".join(c for c in code if c.isdigit())
        return [f"{int(digits):04d}.HK"] if digits else []
    if market == "CN":
        suffix = {"SSE": "SS", "SZSE": "SZ", "BSE": "BJ"}[cn_exchange(code)]  # 沪/深/北交所
        return [f"{code}.{suffix}"]
    if market == "KR":
        return [f"{code}.KS", f"{code}.KQ"]  # KOSPI / KOSDAQ
    return []


def get_fundamentals(symbol: str) -> dict:
    now = time.time()
    with _LOCK:
        hit = _CACHE.get(symbol)
        if hit and now - hit[0] < _TTL:
            return hit[1]
    out: dict = {
        "market_cap": None,
        "pe": None,
        "revenue": None,
        "net_income": None,
        "net_margin": None,
        "eps": None,
        "currency": _CURRENCY.get(symbol.partition(":")[0], ""),
    }
    for ysym in _yahoo_symbols(symbol):
        try:
            info = yf.Ticker(ysym).info
        except Exception:  # noqa: BLE001 — 限流/网络 → 试下一个候选或留空
            continue
        if info and (info.get("marketCap") or info.get("totalRevenue")):
            out["market_cap"] = info.get("marketCap")
            out["pe"] = info.get("trailingPE")
            out["revenue"] = info.get("totalRevenue")
            out["net_income"] = info.get("netIncomeToCommon")
            out["eps"] = info.get("trailingEps")
            if info.get("currency"):
                out["currency"] = info["currency"]
            break
    # 雅虎缺 trailingPE（韩股常见）时，用 市值/净利润 兜底（= P/E），净利润为正才算
    if out["pe"] is None and out["market_cap"] and out["net_income"] and out["net_income"] > 0:
        out["pe"] = out["market_cap"] / out["net_income"]
    if out["revenue"] and out["net_income"] is not None:
        out["net_margin"] = out["net_income"] / out["revenue"]
    with _LOCK:
        _CACHE[symbol] = (now, out)
    return out


# ───────────────────────── 历史财报（趋势表）─────────────────────────
_FIN_CACHE: dict[str, tuple[float, dict]] = {}


def _report_links(symbol: str, ysym: str) -> list[dict]:
    """财报来源/目录链接：雅虎财报页（通用）+ 各市场官方披露入口（尽力而为）。"""
    market, _, code = symbol.partition(":")
    links = [{"label": "完整财报", "url": f"https://finance.yahoo.com/quote/{ysym}/financials"}]
    if market == "US":
        links.append(
            {
                "label": "SEC 公告",
                "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&ticker={code}&type=10-K&dateb=&owner=include&count=40",
            }
        )
    elif market == "CN":
        links.append(
            {
                "label": "巨潮公告",
                "url": f"http://www.cninfo.com.cn/new/fulltextSearch?keyWord={code}",
            }
        )
    elif market == "HK":
        links.append(
            {"label": "披露易", "url": "https://www1.hkexnews.hk/search/titlesearch.xhtml"}
        )
    elif market == "KR":
        links.append({"label": "DART", "url": "https://dart.fss.or.kr/"})
    return links


def _num(series, col) -> float | None:
    if series is None or col not in series.index:
        return None
    v = series.get(col)
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f  # NaN → None


def _growth(cur: float | None, prev: float | None) -> float | None:
    """同比增长率；基期需为正才有意义（亏损/缺失 → None）。"""
    if cur is None or prev is None or prev <= 0:
        return None
    return (cur - prev) / prev


def _period_label(c, quarter: bool) -> str:
    """列日期 → 期次标签：季度 2026Q1（按自然季）/ 年度 2025。"""
    if not hasattr(c, "month"):
        s = str(c)
        return s[:7] if quarter else s[:4]
    return f"{c.year}Q{(c.month - 1) // 3 + 1}" if quarter else str(c.year)


def get_financials(symbol: str, period: str = "quarter", limit: int = 8) -> dict:
    """近若干期财报关键项（最新在前）：营收/营收增长/净利/净利率/EPS/EPS增长/自由现金流。

    period：`quarter`（季度，默认）| `annual`（年度）。增长率按**同比**——季度 vs 去年同季
    （回退 4 列）、年度 vs 上一年（回退 1 列）——以避开季节性误导（§11 暴露不确定性）。
    yfinance 免费季度仅约 5–7 期；年度约 4–5 年。
    """
    quarter = period != "annual"
    lag = 4 if quarter else 1  # 同比基期相隔列数（季度回退 4 列＝去年同季）
    cap = limit if quarter else min(limit, 6)
    key = f"{symbol}:{period}"
    now = time.time()
    with _LOCK:
        hit = _FIN_CACHE.get(key)
        if hit and now - hit[0] < _TTL:
            return hit[1]
    out: dict = {
        "period": "quarter" if quarter else "annual",
        "currency": _CURRENCY.get(symbol.partition(":")[0], ""),
        "periods": [],
        "links": [],
    }
    for ysym in _yahoo_symbols(symbol):
        try:
            t = yf.Ticker(ysym)
            inc = t.quarterly_income_stmt if quarter else t.income_stmt
            cf = t.quarterly_cashflow if quarter else t.cashflow
        except Exception:  # noqa: BLE001
            continue
        if inc is None or inc.empty:
            continue

        def pick(df, names):
            for n in names:
                if df is not None and not df.empty and n in df.index:
                    return df.loc[n]
            return None

        rev = pick(inc, ["Total Revenue"])
        ni = pick(inc, ["Net Income", "Net Income Common Stockholders"])
        eps = pick(inc, ["Diluted EPS", "Basic EPS"])
        fcf = pick(cf, ["Free Cash Flow"])
        cols = list(inc.columns)
        rows = []
        for i, c in enumerate(cols[:cap]):
            older = cols[i + lag] if i + lag < len(cols) else None
            rv, nv, ev, fv = _num(rev, c), _num(ni, c), _num(eps, c), _num(fcf, c)
            rows.append(
                {
                    "period": _period_label(c, quarter),
                    "revenue": rv,
                    "revenue_growth": _growth(rv, _num(rev, older)) if older is not None else None,
                    "net_income": nv,
                    "net_margin": (nv / rv) if (nv is not None and rv) else None,
                    "eps": ev,
                    "eps_growth": _growth(ev, _num(eps, older)) if older is not None else None,
                    "fcf": fv,
                }
            )
        if rows:
            out["periods"] = rows
            out["links"] = _report_links(symbol, ysym)
            break
    with _LOCK:
        _FIN_CACHE[key] = (now, out)
    return out
