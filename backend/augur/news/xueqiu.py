"""雪球只读内容探活适配器。

雪球没有稳定公开内容 API；这里不抓持仓、不读组合，只用登录 Cookie 轻量验证
“讨论/搜索 JSON 接口是否可访问”。作者常只复制 `xq_a_token` 的值，所以适配器
兼容纯 token 与完整 Cookie 两种输入。
"""

from __future__ import annotations

import json
import re

import httpx

from .. import runtime_config

_HOME = "https://xueqiu.com/"
_SEARCH = "https://xueqiu.com/statuses/search.json"
_QUOTE = "https://stock.xueqiu.com/v5/stock/quote.json"
_TIMEOUT = 15.0
_TOKEN_RE = re.compile(r"^[A-Za-z0-9._~-]{16,}$")
_WAF_MARKERS = ("_waf_", "renderData", "acw_sc__", "window.__NUXT__")


class XueqiuError(RuntimeError):
    """雪球可解释错误。"""


class XueqiuCookieError(XueqiuError):
    """Cookie 缺失、过期或不足。"""


class XueqiuWafError(XueqiuError):
    """雪球返回风控网页壳，而非 JSON。"""


def _raw_cookie() -> str:
    return runtime_config.get_secret("XUEQIU_TOKEN").strip()


def cookie_names(raw: str) -> list[str]:
    """提取 Cookie 键名；纯 token 没有键名，返回 []。供诊断/测试用。"""
    out: list[str] = []
    for part in raw.split(";"):
        if "=" not in part:
            continue
        name = part.split("=", 1)[0].strip()
        if name:
            out.append(name)
    return out


def cookie_header(raw: str) -> str:
    """归一 XUEQIU_TOKEN：完整 Cookie 原样用；纯值当作 xq_a_token。"""
    raw = raw.strip()
    if not raw:
        return ""
    if raw.lower().startswith("cookie:"):
        raw = raw.split(":", 1)[1].strip()
    if "=" in raw:
        return raw
    if _TOKEN_RE.match(raw):
        return f"xq_a_token={raw}"
    return raw


def _headers(cookie: str) -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": _HOME,
        "Cookie": cookie,
    }


def _looks_like_waf(text: str) -> bool:
    low = text[:2000].lower()
    return "<html" in low or "<textarea" in low or any(m.lower() in low for m in _WAF_MARKERS)


def _json(resp: httpx.Response) -> dict:
    if resp.status_code in (401, 403):
        raise XueqiuCookieError(f"雪球登录 Cookie 无效或已过期（HTTP {resp.status_code}）。")
    if resp.status_code == 429:
        raise XueqiuError("雪球触发频率限制，稍后再试。")
    resp.raise_for_status()
    text = resp.text or ""
    ctype = resp.headers.get("content-type", "")
    if "json" not in ctype.lower() and _looks_like_waf(text):
        raise XueqiuWafError(
            "雪球返回了风控网页壳，不是 JSON。通常是 Cookie 不完整；请复制浏览器请求里的"
            "完整 Cookie header，至少包含 xq_a_token 和 u，若有 xq_r_token/device_id 也一并保留。"
        )
    try:
        data = resp.json()
    except json.JSONDecodeError as e:
        if _looks_like_waf(text):
            raise XueqiuWafError(
                "雪球返回了风控网页壳，不是 JSON；请改填完整 Cookie header。"
            ) from e
        raise XueqiuError("雪球接口返回格式变了，需要更新适配器。") from e
    if not isinstance(data, dict):
        raise XueqiuError("雪球接口返回格式变了，需要更新适配器。")
    code = data.get("error_code")
    if code not in (None, 0, "0"):
        desc = str(data.get("error_description") or data.get("error") or data)
        if code in (400016, "400016"):
            raise XueqiuCookieError("雪球登录 Cookie 无效或已过期，请重新登录后复制。")
        raise XueqiuError(f"雪球接口返回错误：{desc}")
    return data


def _search_count(data: dict) -> int:
    for key in ("list", "statuses", "items"):
        val = data.get(key)
        if isinstance(val, list):
            return len(val)
    if isinstance(data.get("data"), dict):
        return _search_count(data["data"])
    return 0


def ping() -> tuple[int, str]:
    """验证 cookie 是否可访问雪球内容 JSON。成功返回 (条数, 说明)。"""
    raw = _raw_cookie()
    if not raw:
        raise XueqiuCookieError("未配置 XUEQIU_TOKEN。")
    cookie = cookie_header(raw)
    names = set(cookie_names(cookie))
    if "xq_a_token" not in names:
        raise XueqiuCookieError(
            "XUEQIU_TOKEN 里没有 xq_a_token。请从浏览器请求复制完整 Cookie，"
            "或至少填 xq_a_token 的值。"
        )
    note = (
        "完整 Cookie 探活"
        if {"xq_a_token", "u"}.issubset(names)
        else "仅 xq_a_token 探活"
    )
    with httpx.Client(
        timeout=_TIMEOUT,
        headers=_headers(cookie),
        follow_redirects=True,
    ) as client:
        # 先访问首页，让雪球补辅助 cookie；不读取页面内容。
        client.get(_HOME)
        # 行情接口通常较宽松，只作为网络/基础 Cookie 热身，不代表论坛内容可用。
        _json(client.get(_QUOTE, params={"symbol": "SH600519", "extend": "detail"}))
        data = _json(
            client.get(
                _SEARCH,
                params={
                    "q": "贵州茅台",
                    "count": 1,
                    "page": 1,
                    "sort": "time",
                    "source": "all",
                    "hl": 0,
                    "comment": 0,
                },
            )
        )
    return _search_count(data), note
