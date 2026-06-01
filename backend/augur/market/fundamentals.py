"""基本面（市值/营收/利润/P-E）via yfinance（CLAUDE.md §7）。

yfinance 一库覆盖四市场（雅虎财经）。`.info` 较慢且偶发限流 → 内存 TTL 缓存（基本面是慢变量）。
数字为各自**本币**（USD/HKD/CNY/KRW），单位是「元」级原值，前端再按亿/万亿格式化。
缺数据（如亏损股无 P/E）一律置 None，前端显示「—」（暴露不确定性，§11）。
"""

from __future__ import annotations

import threading
import time

import yfinance as yf

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
        suffix = "SS" if code[:1] in ("6", "9") else "SZ"  # 沪 .SS / 深 .SZ
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
    with _LOCK:
        _CACHE[symbol] = (now, out)
    return out
