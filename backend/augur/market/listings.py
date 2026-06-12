"""股票代码目录：构建 + 磁盘缓存（AGENTS.md §7 缓存优先、尊重限流）。

各市场列表来源：
  · US / CN / KR → FinanceDataReader（StockListing）
  · CN 中文名      → akshare（stock_info_a_code_name，尽力而为）
  · HK            → akshare（eastmoney，本机偶发被代理拦截 → 降级，靠 aliases 兜底）

列表是重型网络调用（美股列表 ~70s），故缓存为 Parquet 到 data/cache/listings/，带 TTL。
**逐市场 try/except**：任一源失败只影响该市场；过期也先用旧缓存，后台再刷新。

统一目录列：symbol(MARKET:CODE) · market · code · name(本地语优先) · name_en(英文，可空)。
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import pandas as pd

from ..config import get_settings

_COLUMNS = ["symbol", "market", "code", "name", "name_en"]
_TTL_SEC = 7 * 24 * 3600  # 列表一周刷新一次足矣（标的增删是慢变量）
_WS = re.compile(r"\s+")


def _dir() -> Path:
    return get_settings().cache_dir / "listings"


def _path(market: str) -> Path:
    return _dir() / f"{market}.parquet"


def _clean(s: object) -> str:
    return _WS.sub("", str(s)) if s is not None else ""


def is_fresh(market: str) -> bool:
    p = _path(market)
    return p.exists() and (time.time() - p.stat().st_mtime) < _TTL_SEC


# ───────────────────────── 各市场构建器（命中网络）─────────────────────────
def _fdr_listing(name: str) -> pd.DataFrame:
    import FinanceDataReader as fdr

    return fdr.StockListing(name)


def _build_us() -> pd.DataFrame:
    frames = []
    for ex in ("NASDAQ", "NYSE"):
        df = _fdr_listing(ex)[["Symbol", "Name"]].rename(
            columns={"Symbol": "code", "Name": "name_en"}
        )
        frames.append(df)
    out = pd.concat(frames, ignore_index=True).drop_duplicates("code")
    out["market"] = "US"
    out["code"] = out["code"].astype(str).str.strip().str.upper()
    out["name_en"] = out["name_en"].astype(str).str.strip()
    out["name"] = out["name_en"]
    out["symbol"] = "US:" + out["code"]
    return out[_COLUMNS]


def _build_cn() -> pd.DataFrame:
    frames = []
    for ex in ("SSE", "SZSE"):
        df = _fdr_listing(ex)[["Symbol", "Name"]].rename(
            columns={"Symbol": "code", "Name": "name_en"}
        )
        frames.append(df)
    out = pd.concat(frames, ignore_index=True).drop_duplicates("code")
    out["code"] = out["code"].astype(str).str.strip()
    out["name_en"] = out["name_en"].astype(str).str.strip()
    out["name"] = out["name_en"]
    # 中文名（尽力而为）——A 股用户基本按中文名检索
    try:
        import akshare as ak

        zh = ak.stock_info_a_code_name().rename(columns={"name": "name_zh"})
        zh["code"] = zh["code"].astype(str).str.strip()
        zh["name_zh"] = zh["name_zh"].map(_clean)
        out = out.merge(zh[["code", "name_zh"]], on="code", how="left")
        out["name"] = out["name_zh"].where(out["name_zh"].astype(bool), out["name_en"])
        out = out.drop(columns=["name_zh"])
    except Exception as e:  # noqa: BLE001 — 降级到英文名，不致命
        print(f"[listings] CN 中文名补全失败，降级英文名：{type(e).__name__}: {e}")
    out["market"] = "CN"
    out["symbol"] = "CN:" + out["code"]
    return out[_COLUMNS]


def _build_kr() -> pd.DataFrame:
    frames = []
    for ex in ("KOSPI", "KOSDAQ"):
        df = _fdr_listing(ex)[["Code", "Name"]].rename(columns={"Code": "code", "Name": "name"})
        frames.append(df)
    out = pd.concat(frames, ignore_index=True).drop_duplicates("code")
    out["code"] = out["code"].astype(str).str.strip()
    out["name"] = out["name"].astype(str).str.strip()
    out["name_en"] = ""
    out["market"] = "KR"
    out["symbol"] = "KR:" + out["code"]
    return out[_COLUMNS]


def _build_hk() -> pd.DataFrame:
    import akshare as ak

    # eastmoney 优先（带中文名）；本机偶发代理拦截 → 抛错由上层降级
    df = ak.stock_hk_spot_em()
    df = df.rename(columns={"代码": "code", "名称": "name"})[["code", "name"]]
    df["code"] = df["code"].astype(str).str.strip().str.zfill(5)
    df["name"] = df["name"].astype(str).str.strip()
    df = df.drop_duplicates("code")
    df["name_en"] = ""
    df["market"] = "HK"
    df["symbol"] = "HK:" + df["code"]
    return df[_COLUMNS]


_BUILDERS = {"US": _build_us, "CN": _build_cn, "KR": _build_kr, "HK": _build_hk}


# ───────────────────────── 缓存读写 ─────────────────────────
def load_cached(market: str) -> pd.DataFrame | None:
    p = _path(market)
    if not p.exists():
        return None
    try:
        return pd.read_parquet(p)
    except Exception:
        return None


def build_market(market: str, *, force: bool = False) -> pd.DataFrame:
    """构建单市场目录：缓存新鲜则直接返回；否则回源构建并落盘。

    回源失败时退回旧缓存（若有），再不行返回空表——绝不让单市场失败拖垮整体。
    """
    if not force and is_fresh(market):
        cached = load_cached(market)
        if cached is not None:
            return cached
    builder = _BUILDERS.get(market)
    if builder is None:
        return pd.DataFrame(columns=_COLUMNS)
    try:
        df = builder()
        p = _path(market)
        p.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(p)
        print(f"[listings] {market} 目录已构建：{len(df)} 条")
        return df
    except Exception as e:  # noqa: BLE001
        stale = load_cached(market)
        if stale is not None:
            print(f"[listings] {market} 回源失败，沿用旧缓存：{type(e).__name__}: {e}")
            return stale
        print(f"[listings] {market} 目录构建失败（无缓存可退）：{type(e).__name__}: {e}")
        return pd.DataFrame(columns=_COLUMNS)


def ensure_all(*, force: bool = False) -> dict[str, int]:
    """构建/刷新全部市场目录，返回 {market: 行数}。供启动预热与定时刷新调用。"""
    counts: dict[str, int] = {}
    for market in _BUILDERS:
        counts[market] = len(build_market(market, force=force))
    return counts
