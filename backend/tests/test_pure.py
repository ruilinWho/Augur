"""纯函数回归测试（零网络）——守住呈现给作者的数字/标签不悄悄漂移。

跑：`cd backend && uv run pytest`。架构把 I/O 挡在纯逻辑外（CLAUDE.md §5），这些都可离线测。
"""

from __future__ import annotations

from datetime import datetime

import httpx
import pytest

from augur.market import search
from augur.market.fundamentals import _growth, _period_label, _yahoo_symbols
from augur.market.symbols import cn_exchange, parse_symbol
from augur.news import edgar, source_test, stock_sources
from augur.news.grounding import simplify as _simplify
from augur.news.service import _norm_url, _parse_json_lenient
from augur.settings_router import _llm_key_url


# ───────────────────────── symbols ─────────────────────────
def test_cn_exchange():
    assert cn_exchange("600519") == "SSE"  # 沪
    assert cn_exchange("900901") == "SSE"  # 沪 B
    assert cn_exchange("000001") == "SZSE"  # 深
    assert cn_exchange("300308") == "SZSE"  # 创业板
    assert cn_exchange("200012") == "SZSE"  # 深 B
    assert cn_exchange("830799") == "BSE"  # 北交所
    assert cn_exchange("430718") == "BSE"  # 北交所


def test_parse_symbol_ok():
    s = parse_symbol("us:aapl")
    assert s.market == "US" and s.code == "aapl" and s.canonical == "US:aapl"


@pytest.mark.parametrize("bad", ["AAPL", "XX:600519", "US:"])
def test_parse_symbol_bad(bad):
    with pytest.raises(ValueError):
        parse_symbol(bad)


# ───────────────────────── 展示名清洗（美股去公司后缀）─────────────────────────
@pytest.mark.parametrize(
    "raw,clean",
    [
        ("Redwire Corp", "Redwire"),
        ("Apple Inc.", "Apple"),
        ("Micron Technology", "Micron"),
        ("Planet Labs PBC", "Planet Labs"),
        ("Credo Technology Group Holding", "Credo"),
        ("Vishay Intertechnology", "Vishay Intertechnology"),  # 词内 technology 不误切
        ("贵州茅台", "贵州茅台"),  # CJK 不受影响
    ],
)
def test_clean_name(raw, clean):
    assert search._clean_name(raw) == clean


# ───────────────────────── 财报口径 ─────────────────────────
def test_growth():
    assert _growth(120, 100) == pytest.approx(0.2)
    assert _growth(80, 100) == pytest.approx(-0.2)
    assert _growth(100, 0) is None  # 基期 0 无意义
    assert _growth(100, -5) is None  # 基期亏损无意义
    assert _growth(None, 100) is None


def test_period_label():
    assert _period_label(datetime(2026, 3, 31), quarter=True) == "2026Q1"
    assert _period_label(datetime(2026, 12, 31), quarter=True) == "2026Q4"
    assert _period_label(datetime(2025, 6, 30), quarter=False) == "2025"


def test_yahoo_symbols():
    assert _yahoo_symbols("US:BRK.B") == ["BRK-B"]
    assert _yahoo_symbols("HK:00700") == ["0700.HK"]
    assert _yahoo_symbols("CN:600519") == ["600519.SS"]
    assert _yahoo_symbols("CN:000001") == ["000001.SZ"]
    assert _yahoo_symbols("CN:830799") == ["830799.BJ"]  # 北交所
    assert _yahoo_symbols("KR:005930") == ["005930.KS", "005930.KQ"]


# ───────────────────────── EDGAR 确定性中文标签 ─────────────────────────
def test_form_zh():
    assert edgar._form_zh("8-K") == "重大事件"
    assert edgar._form_zh("10-Q") == "季报"
    assert edgar._form_zh("10-K/A") == "年报·修订"
    assert edgar._form_zh("424B5") == "招股说明书"  # 前缀兜底


def test_items_zh():
    assert edgar._items_zh("2.02,9.01") == "经营成果与财务状况（财报）；财务报表与附件"
    assert edgar._items_zh("") == ""


# ───────────────────────── 新闻服务纯助手 ─────────────────────────
def test_parse_json_lenient():
    assert _parse_json_lenient('{"a": 1}') == {"a": 1}
    assert _parse_json_lenient('```json\n{"a": 1}\n```') == {"a": 1}
    assert _parse_json_lenient('前言 {"a": 1} 后语') == {"a": 1}
    assert _parse_json_lenient("不是 json") == {}


def test_norm_url():
    assert _norm_url("https://A.com/p/?x=1") == "https://a.com/p"
    assert _norm_url("") == ""


def test_simplify():
    assert _simplify("Apple Inc.") == "appleinc"
    assert _simplify("英伟达（NVDA）") == "英伟达nvda"


def test_source_test_diagnostics_are_user_facing():
    assert (
        source_test.diagnose_problem(
            "twtapi", RuntimeError("TwtapiFatal: twtapi 月度调用额度已用完，请升级套餐或更换 key")
        )
        == "X：月度额度已用完，需要等额度重置、升级套餐或更换 key。"
    )
    assert (
        source_test.diagnose_problem(
            "twtapi",
            RuntimeError("RuntimeError: 抱歉，您没有接口(stock_basic)访问权限"),
        )
        == "X：当前凭证没有这个接口权限，可能需要充值、开通套餐或提高积分。"
    )
    assert (
        source_test.diagnose_problem("xueqiu", RuntimeError("关注用户 0 个；抓取适配器待接入"))
        == "雪球：还没有接入抓取适配器。"
    )


def test_source_test_diagnostics_for_http_status():
    req = httpx.Request("GET", "https://example.test")
    resp = httpx.Response(401, request=req)
    exc = httpx.HTTPStatusError("unauthorized", request=req, response=resp)
    assert (
        source_test.diagnose_problem("twtapi", exc)
        == "X：凭证无效，或当前套餐没有这个接口权限。"
    )
    rss_resp = httpx.Response(403, request=req)
    rss_exc = httpx.HTTPStatusError("forbidden", request=req, response=rss_resp)
    assert (
        source_test.diagnose_problem("feeds_rss", rss_exc)
        == "RSS：源站拒绝访问，可能是 feed 下线、反爬或需要更新 UA/适配器。"
    )


def test_llm_key_url_falls_back_to_base_origin():
    assert (
        _llm_key_url({"name": "Custom Relay", "base_url": "https://relay.example.com/v1"})
        == "https://relay.example.com"
    )
    assert (
        _llm_key_url({"name": "DeepSeek", "base_url": "https://api.deepseek.com"})
        == "https://platform.deepseek.com/api_keys"
    )


def test_stock_source_ref_parsing():
    assert stock_sources._x_handle("@nvidia") == "nvidia"
    assert stock_sources._x_handle("https://x.com/nvidia/status/1") == "nvidia"
    assert stock_sources._subreddit("r/NVDA_Stock") == "NVDA_Stock"
    assert stock_sources._subreddit("https://www.reddit.com/r/NVDA_Stock/new/") == "NVDA_Stock"
    assert stock_sources._feed_url("https://example.com/feed.xml") == "https://example.com/feed.xml"
    assert stock_sources._feed_url("https://x.com/nvidia") == ""
