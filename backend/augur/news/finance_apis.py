"""可选财经数据源的轻量探活。

这些源不替代 Augur 的内置行情栈；它们用于「设置 · 数据 / 信源」里验证作者配置的
第三方财经 key 是否真的可用。只打一两个低成本接口，避免无意义消耗额度。
"""

from __future__ import annotations

import httpx

from .. import runtime_config

_TIMEOUT = 20.0


def _secret(name: str, label: str) -> str:
    v = runtime_config.get_secret(name)
    if not v:
        raise RuntimeError(f"没有配置：请先填写 {label}。")
    return v


def test_tushare() -> tuple[int, str]:
    """Tushare Pro HTTP API 探活。

    官方 Pro API 是统一 POST `https://api.tushare.pro`，body 带 token/api_name/params/fields。
    优先用最基础的 `stock_basic`，因为它比行情 daily 更少依赖行情权限；若 token 积分/权限不足，
    Tushare 会返回 code/msg，上层会翻成面向作者的中文问题诊断。
    """

    token = _secret("TUSHARE_TOKEN", "Tushare token")
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
        msg = str(data.get("msg") or data.get("detail") or "")
        if "没有接口" in msg or "访问权限" in msg:
            raise RuntimeError("当前 token 没有 stock_basic 接口访问权限")
        if "积分" in msg or "余额" in msg:
            raise RuntimeError("当前 token 的积分或余额不足")
        raise RuntimeError("Tushare token 无效，或当前套餐没有这个接口权限")
    items = ((data.get("data") or {}).get("items") or []) if isinstance(data, dict) else []
    return len(items), "Tushare Pro HTTP API 可达"


def test_biying() -> tuple[int, str]:
    """必盈 A 股股票列表探活。"""

    licence = _secret("BIYING_API_LICENCE", "必盈 licence")
    r = httpx.get(f"https://api.biyingapi.com/hslt/list/{licence}", timeout=_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise RuntimeError("必盈接口返回格式变了，或 licence 无效")
    return len(data), "必盈股票列表 API 可达"


def test_itick() -> tuple[int, str]:
    """iTick 单股票报价探活。"""

    key = _secret("ITICK_API_KEY", "iTick API key")
    r = httpx.get(
        "https://api.itick.org/stock/quote",
        params={"region": "US", "code": "AAPL"},
        headers={"accept": "application/json", "token": key},
        timeout=_TIMEOUT,
    )
    if r.status_code in (401, 403):
        raise RuntimeError("iTick API key 无效，或当前套餐没有股票报价接口权限")
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError("iTick 当前套餐没有股票报价接口权限，或接口额度不足")
    if not data.get("data"):
        raise RuntimeError("iTick 报价返回为空")
    return 1, "iTick 股票报价 API 可达"
