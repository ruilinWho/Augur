"""信源可用性测试（设置·数据信源 的「测试」按钮）。

对每个信源做一次**轻量真实探活**：能测的真打一下（行情栈 / 财联社 / 东财 / X /
RSS / Bloomberg / Reddit），返回 {ok, latency_ms, count?, note?} 或 {ok:false, error}。
失败不抛、回错文。
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import httpx

from .. import runtime_config

_CUTOFF_DAYS = 30
_SOURCE_NAMES = {
    "market_data": "内置行情栈",
    "cls": "财联社",
    "eastmoney_news": "东方财富",
    "tikhub_twitter": "推特",
    "bloomberg": "Bloomberg",
    "feeds_rss": "RSS",
    "tikhub_reddit": "Reddit · TikHub",
    "xiaohongshu": "小红书",
    "tikhub_threads": "Threads",
}


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
    return {"ok": False, "error": msg}


def _label(source_id: str) -> str:
    return _SOURCE_NAMES.get(source_id, source_id)


def _http_problem(source_id: str, status: int) -> str:
    name = _label(source_id)
    if status in (401, 403):
        if source_id == "feeds_rss":
            return f"{name}：源站拒绝访问，可能是 feed 下线、反爬或需要更新 UA/适配器。"
        return f"{name}：凭证无效，或当前套餐没有这个接口权限。"
    if status == 402:
        return f"{name}：余额不足，或当前套餐没有开通这个接口。"
    if status == 404:
        return f"{name}：接口地址不可用，适配器需要更新。"
    if status == 429:
        return f"{name}：额度或频率限制已触发，稍后再试或升级套餐。"
    if status >= 500:
        return f"{name}：对方服务临时不可用。"
    return f"{name}：接口返回状态码 {status}，暂时无法完成测试。"


def diagnose_problem(source_id: str, exc: Exception) -> str:
    """把第三方库/HTTP 的异常翻成作者能直接决策的中文问题。"""

    name = _label(source_id)
    if isinstance(exc, httpx.HTTPStatusError):
        return _http_problem(source_id, exc.response.status_code)
    if isinstance(exc, httpx.TimeoutException):
        return f"{name}：网络连接超时。"
    if isinstance(exc, httpx.TransportError):
        return f"{name}：网络连接失败，可能是网络、代理或对方服务不可达。"

    msg = str(exc).strip()
    # 兜底清洗：即使某处仍传入 "RuntimeError: xxx"，也不要把异常类型展示给作者。
    for prefix in (
        "RuntimeError: ",
        "TwtapiFatal: ",
        "TwtapiError: ",
        "TikhubFatal: ",
        "TikhubError: ",
        "HTTPStatusError: ",
        "ConnectError: ",
        "ReadTimeout: ",
        "TimeoutException: ",
    ):
        if msg.startswith(prefix):
            msg = msg[len(prefix) :].strip()

    if not msg:
        return f"{name}：测试失败，暂时无法判断具体原因。"

    lower = msg.lower()
    if "未配置" in msg or "没有配置" in msg:
        return f"{name}：没有配置凭证或账号，请先填写后再测试。"
    if "TikHub 端点当前失败" in msg:
        return f"{name}：{msg}"
    if "请求参数不符合文档" in msg:
        return f"{name}：请求参数不符合文档，适配器需要更新。"
    if "待接入" in msg or "未接入" in msg or "适配器" in msg:
        return f"{name}：还没有接入抓取适配器。"
    if "月度调用额度已用完" in msg or "monthly call limit" in lower:
        return f"{name}：月度额度已用完，需要等额度重置、升级套餐或更换 key。"
    if "429" in msg or "频率" in msg or "限流" in msg or "rate limit" in lower:
        return f"{name}：额度或频率限制已触发，稍后再试或升级套餐。"
    if "401" in msg or "403" in msg or "无效" in msg or "unauthorized" in lower:
        return f"{name}：凭证无效，或当前套餐没有这个接口权限。"
    if (
        "余额" in msg
        or "积分" in msg
        or "没有接口" in msg
        or "访问权限" in msg
        or "没有权限" in msg
        or "无权限" in msg
        or "permission" in lower
        or "套餐" in msg
    ):
        return f"{name}：当前凭证没有这个接口权限，可能需要充值、开通套餐或提高积分。"
    if "账号" in msg or "user_id" in msg:
        return f"{name}：配置的账号无法解析，请检查账号名是否存在。"
    if "返回为空" in msg or "拉取为空" in msg:
        return f"{name}：接口可达，但这次没有返回可用数据。"
    if "errno" in lower or "签名失效" in msg or "反爬" in msg:
        return f"{name}：接口签名或反爬参数失效，需要更新适配器。"
    if "json" in lower or "非列表数据" in msg:
        return f"{name}：接口返回格式变了，需要更新适配器。"

    return f"{name}：测试失败，{msg}"


def _test_feeds(only_bloomberg: bool) -> dict:
    """从 feeds.yaml 取一个代表性 feed 试拉（RSS 聚合 / Bloomberg）。"""
    from . import ingest, sources

    feeds = sources.load_feeds()
    if only_bloomberg:
        feeds = [f for f in feeds if "bloomberg" in (f.get("name", "").lower())]
    if not feeds:
        return _err("RSS：没有可测试的 feed 配置。")
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
                return _err("内置行情栈：接口可达，但这次没有返回可用行情；可能是雅虎临时限流。")
            return _ok(t0, len(df), "yfinance 行情栈可用")

        if source_id == "cls":
            from . import cls

            return _ok(t0, len(cls.fetch_cls(_cutoff())), "财联社电报可达")

        if source_id == "eastmoney_news":
            from . import eastmoney_news

            return _ok(t0, len(eastmoney_news.fetch_eastmoney(_cutoff())), "东财资讯可达")

        if source_id == "bloomberg":
            return _test_feeds(only_bloomberg=True)

        if source_id == "feeds_rss":
            return _test_feeds(only_bloomberg=False)

        if source_id in {
            "tikhub_twitter",
            "xiaohongshu",
            "tikhub_threads",
            "tikhub_reddit",
        }:
            if not runtime_config.has_secret("TIKHUB_KEY"):
                return _err(f"{_label(source_id)}：没有配置 TIKHUB_KEY，请先填写后再测试。")
            from . import tikhub

            got = tikhub.ping_source(source_id)
            return _ok(t0, got, f"{_label(source_id)} 可达")

        return _err(f"{source_id}：没有接入这个信源。")
    except Exception as e:  # noqa: BLE001 — 任何失败都回给前端展示
        return _err(diagnose_problem(source_id, e))
