"""信源可用性测试（设置·数据信源 的「测试」按钮）。

对每个信源做一次**轻量真实探活**：能测的真打一下（行情栈 / 财联社 / 东财 / X / RSS /
Bloomberg / Tushare / 必盈 / iTick），返回 {ok, latency_ms, count?, note?} 或 {ok:false, error}。
失败不抛、回错文。
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from .. import runtime_config

_CUTOFF_DAYS = 30


def _cutoff() -> datetime:
    return datetime.now(UTC) - timedelta(days=_CUTOFF_DAYS)


def _ok(t0: float, count: int | None = None, note: str = "") -> dict:
    r: dict = {"ok": True, "latency_ms": int((time.monotonic() - t0) * 1000)}
    if count is not None:
        r["count"] = count
    if note:
        r["note"] = note
    return r


def _err(msg: str) -> dict:
    return {"ok": False, "error": msg[:200]}


def _test_feeds(only_bloomberg: bool) -> dict:
    """从 feeds.yaml 取一个代表性 feed 试拉（RSS 聚合 / Bloomberg）。"""
    from . import ingest, sources

    feeds = sources.load_feeds()
    if only_bloomberg:
        feeds = [f for f in feeds if "bloomberg" in (f.get("name", "").lower())]
    if not feeds:
        return _err("没有可测的 feed")
    t0 = time.monotonic()
    got = ingest.fetch_feed(feeds[0], _cutoff())
    return _ok(t0, len(got), f"试拉「{feeds[0].get('name', '')}」")


def test_source(source_id: str) -> dict:
    """探活某信源。"""
    t0 = time.monotonic()
    try:
        if source_id == "market_data":
            import yfinance as yf

            df = yf.Ticker("AAPL").history(period="5d")
            if df is None or df.empty:
                return _err("行情拉取为空（雅虎可能限流）")
            return _ok(t0, len(df), "yfinance 行情栈可用")

        if source_id == "cls":
            from . import cls

            return _ok(t0, len(cls.fetch_cls(_cutoff())), "财联社电报可达")

        if source_id == "eastmoney_news":
            from . import eastmoney_news

            return _ok(t0, len(eastmoney_news.fetch_eastmoney(_cutoff())), "东财资讯可达")

        if source_id == "twtapi":
            if not runtime_config.has_secret("TWTAPI_KEY"):
                return _err("未配置 TWTAPI_KEY")
            from . import twtapi

            twtapi.ping()  # 轻量：只解析一个账号 user_id，不拉全量时间线
            return _ok(t0, None, "X(twtapi) 可达")

        if source_id == "bloomberg":
            return _test_feeds(only_bloomberg=True)

        if source_id == "feeds_rss":
            return _test_feeds(only_bloomberg=False)

        if source_id == "reddit":
            from . import reddit

            got = reddit.fetch_reddit(_cutoff())
            return _ok(t0, len(got), "Reddit public JSON 可达")

        if source_id == "xiaohongshu":
            n = len(runtime_config.get_source_config("xiaohongshu", "accounts", []))
            return _err(f"关注用户 {n} 个；抓取适配器待接入（需登录 Cookie / 稳定方案）")

        if source_id == "xueqiu":
            n = len(runtime_config.get_source_config("xueqiu", "accounts", []))
            return _err(f"关注用户 {n} 个；抓取适配器待接入（需登录 Cookie / 稳定方案）")

        if source_id in ("tushare_pro", "biyingapi", "itick"):
            from . import finance_apis

            testers = {
                "tushare_pro": finance_apis.test_tushare,
                "biyingapi": finance_apis.test_biying,
                "itick": finance_apis.test_itick,
            }
            count, note = testers[source_id]()
            return _ok(t0, count, note)

        return _err(f"未知信源 {source_id!r}")
    except Exception as e:  # noqa: BLE001 — 任何失败都回给前端展示
        return _err(f"{type(e).__name__}: {e}")
