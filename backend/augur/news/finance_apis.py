"""可选财经数据源的轻量探活。

这些源不替代 Augur 的内置行情栈；它们用于「设置 · 数据 / 信源」里验证作者配置的
第三方财经 key 是否真的可用。只打一两个低成本接口，避免无意义消耗额度。
"""

from __future__ import annotations

import httpx

from .. import runtime_config

_TIMEOUT = 20.0


def _secret(name: str) -> str:
    v = runtime_config.get_secret(name)
    if not v:
        raise RuntimeError(f"未配置 {name}")
    return v


def test_tushare() -> tuple[int, str]:
    """Tushare Pro HTTP API 探活。

    官方 Pro API 是统一 POST `https://api.tushare.pro`，body 带 token/api_name/params/fields。
    优先用最基础的 `stock_basic`，因为它比行情 daily 更少依赖行情权限；若 token 积分/权限不足，
    Tushare 会返回 code/msg，原样压缩给前端。
    """

    token = _secret("TUSHARE_TOKEN")
    body = {
        "api_name": "stock_basic",
        "token": token,
        "params": {"exchange": "", "list_status": "L"},
        "fields": "ts_code,symbol,name,area,industry,list_date",
    }
    r = httpx.post("https://api.tushare.pro", json=body, timeout=_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        msg = data.get("msg") or data.get("detail") or "Tushare 返回错误"
        raise RuntimeError(f"Tushare 权限不足或 token 无效：{msg}")
    items = ((data.get("data") or {}).get("items") or []) if isinstance(data, dict) else []
    return len(items), "Tushare Pro HTTP API 可达"


def test_biying() -> tuple[int, str]:
    """必盈 A 股股票列表探活。"""

    licence = _secret("BIYING_API_LICENCE")
    r = httpx.get(f"https://api.biyingapi.com/hslt/list/{licence}", timeout=_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise RuntimeError("必盈返回非列表数据，licence 可能无效")
    return len(data), "必盈股票列表 API 可达"


def test_itick() -> tuple[int, str]:
    """iTick 单股票报价探活。"""

    key = _secret("ITICK_API_KEY")
    r = httpx.get(
        "https://api.itick.org/stock/quote",
        params={"region": "US", "code": "AAPL"},
        headers={"accept": "application/json", "token": key},
        timeout=_TIMEOUT,
    )
    if r.status_code in (401, 403):
        raise RuntimeError(f"iTick API key 无效或无权限（HTTP {r.status_code}）")
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"iTick 返回错误：{data.get('msg') or data.get('message') or data}")
    if not data.get("data"):
        raise RuntimeError("iTick 报价返回为空")
    return 1, "iTick 股票报价 API 可达"
