"""纯函数回归测试（零网络）——守住呈现给作者的数字/标签不悄悄漂移。

跑：`cd backend && uv run pytest`。架构把 I/O 挡在纯逻辑外（CLAUDE.md §5），这些都可离线测。
"""

from __future__ import annotations

from datetime import datetime

import httpx
import pytest

from augur.journal import service as journal_service
from augur.market import search
from augur.market.fundamentals import _growth, _period_label, _yahoo_symbols
from augur.market.symbols import cn_exchange, parse_symbol
from augur.news import (
    edgar,
    source_registry,
    source_test,
    sources,
    stock_sources,
    tikhub,
)
from augur.news import (
    service as news_service,
)
from augur.news.grounding import simplify as _simplify
from augur.news.service import _norm_url, _parse_json_lenient
from augur.settings_router import _llm_key_url
from augur.theses import service as theses_service


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


def test_reflection_news_events_preserve_refs():
    events, by_n = journal_service._build_news_events(
        {
            "timeline": [
                {
                    "date": "2026-06-01",
                    "title": "英伟达发布新芯片",
                    "importance": "high",
                    "refs": [
                        {
                            "source": "Reuters",
                            "title": "Nvidia announces new chip",
                            "url": "https://example.test/nvda",
                        }
                    ],
                }
            ]
        }
    )
    assert events[0]["kind"] == "news"
    assert events[0]["refs"][0]["source"] == "Reuters"
    assert by_n[1]["title"] == "英伟达发布新芯片"


def test_reflection_disclosure_events_preserve_refs_and_body():
    events, by_n = journal_service._build_disclosure_events(
        {
            "events": [
                {
                    "kind": "transcript",
                    "date": "2026-06-02",
                    "title": "2026 Q1 电话会纪要",
                    "source": "FMP Transcript",
                    "summary": "Management discussed capex and margin pressure.",
                    "importance": "critical",
                    "url": "",
                }
            ]
        },
        3,
    )
    assert events[0]["kind"] == "disclosure"
    assert events[0]["refs"][0]["source"] == "FMP Transcript"
    assert "capex" in events[0]["body"]
    assert by_n[3]["title"] == "2026 Q1 电话会纪要"


def test_filing_is_earnings():
    assert news_service._filing_is_earnings({"form": "10-Q", "title": "季报"})
    assert news_service._filing_is_earnings(
        {"form": "8-K", "title": "重大事件 · 经营成果与财务状况（财报）"}
    )
    assert not news_service._filing_is_earnings({"form": "DEF 14A", "title": "股东大会委托书"})


def test_simplify():
    assert _simplify("Apple Inc.") == "appleinc"
    assert _simplify("英伟达（NVDA）") == "英伟达nvda"


def test_source_test_diagnostics_are_user_facing():
    assert (
        source_test.diagnose_problem(
            "tikhub_twitter", RuntimeError("月度调用额度已用完，请升级套餐或更换 key")
        )
        == "推特：月度额度已用完，需要等额度重置、升级套餐或更换 key。"
    )
    assert (
        source_test.diagnose_problem(
            "tikhub_twitter",
            RuntimeError("RuntimeError: 抱歉，您没有接口(stock_basic)访问权限"),
        )
        == "推特：当前凭证没有这个接口权限，可能需要充值、开通套餐或提高积分。"
    )


def test_source_test_diagnostics_for_http_status():
    req = httpx.Request("GET", "https://example.test")
    resp = httpx.Response(401, request=req)
    exc = httpx.HTTPStatusError("unauthorized", request=req, response=resp)
    assert (
        source_test.diagnose_problem("tikhub_twitter", exc)
        == "推特：凭证无效，或当前套餐没有这个接口权限。"
    )
    rss_resp = httpx.Response(403, request=req)
    rss_exc = httpx.HTTPStatusError("forbidden", request=req, response=rss_resp)
    assert (
        source_test.diagnose_problem("feeds_rss", rss_exc)
        == "RSS：源站拒绝访问，可能是 feed 下线、反爬或需要更新 UA/适配器。"
    )


def test_tikhub_items_from_nested_payload():
    now = int(datetime(2026, 6, 1).timestamp())
    data = {
        "code": 200,
        "data": {
            "timeline": [
                {
                    "tweet_id": "1",
                    "full_text": "NVIDIA Blackwell demand looks strong",
                    "created_at": now,
                    "user": {"screen_name": "analyst"},
                    "url": "https://x.com/analyst/status/1",
                }
            ]
        },
    }
    items = tikhub._items_from_response(
        data,
        source="X·搜索·NVDA",
        platform="twitter",
        lang="en",
        category="markets",
        cutoff=None,
        limit=5,
    )
    assert items and items[0]["source"] == "X·搜索·NVDA"
    assert items[0]["url"] == "https://x.com/analyst/status/1"
    assert "analyst" in items[0]["summary"]


def test_tikhub_reddit_items_from_app_search_payload():
    data = {
        "code": 200,
        "data": {
            "search": {
                "dynamic": {
                    "components": {
                        "main": {
                            "edges": [
                                {
                                    "node": {
                                        "children": [
                                            {"__typename": "Filter", "title": "排序方式"},
                                            {
                                                "__typename": "SearchPost",
                                                "post": {
                                                    "id": "t3_abc",
                                                    "createdAt": "2026-06-06T03:20:47.650000+0000",
                                                    "postTitle": (
                                                        "NVDA Blackwell supply looks tight"
                                                    ),
                                                    "url": "https://www.reddit.com/r/stocks/comments/abc/",
                                                    "content": {
                                                        "markdown": (
                                                            "Investors are debating margins."
                                                        )
                                                    },
                                                },
                                                "behaviors": {
                                                    "community": {"name": "r/stocks"},
                                                    "profile": {"name": "poster"},
                                                },
                                            },
                                        ]
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        },
    }
    items = tikhub._items_from_response(
        data,
        source="Reddit·TikHub·NVDA",
        platform="reddit",
        lang="en",
        category="forum",
        cutoff=None,
        limit=5,
    )
    assert len(items) == 1
    assert items[0]["title"] == "NVDA Blackwell supply looks tight"
    assert items[0]["url"] == "https://www.reddit.com/r/stocks/comments/abc/"
    assert "r/stocks" in items[0]["summary"]
    assert "排序方式" not in items[0]["title"]


def test_tikhub_reddit_uses_documented_search_params(monkeypatch):
    captured: dict = {}

    def fake_tags(source_id, field, fallback=None):
        assert source_id == "tikhub_reddit"
        assert field == "keywords"
        return ["NVDA"]

    def fake_fetch(path, **kwargs):
        captured["path"] = path
        captured["params"] = kwargs["params"]
        return []

    monkeypatch.setattr(tikhub, "_tags", fake_tags)
    monkeypatch.setattr(tikhub, "_fetch_search", fake_fetch)
    tikhub.fetch_reddit(None)
    assert captured["path"] == "/api/v1/reddit/app/fetch_dynamic_search"
    assert captured["params"]["query"] == "NVDA"
    assert captured["params"]["search_type"] == "post"
    assert captured["params"]["sort"] == "NEW"
    assert captured["params"]["time_range"] == "week"
    assert "keyword" not in captured["params"]


def test_private_blog_rss_feed_loaded_from_runtime_config(monkeypatch):
    sources.load_feeds.cache_clear()

    def fake_secret(name: str) -> str:
        return "https://example.test/rss?token=secret" if name == sources.BLOG_RSS_SECRET else ""

    monkeypatch.setattr(sources.runtime_config, "get_secret", fake_secret)
    try:
        feeds = sources.load_feeds()
    finally:
        sources.load_feeds.cache_clear()
    blog = next((f for f in feeds if f["name"] == sources.BLOG_SOURCE_NAME), None)
    assert blog is not None
    assert blog["url"] == "https://example.test/rss?token=secret"
    assert blog["category"] == sources.BLOG_CATEGORY


def test_private_blog_rss_secret_is_exportable_live_secret():
    assert sources.BLOG_RSS_SECRET in source_registry.live_secret_names()


def test_fmp_secret_is_exportable_live_secret():
    from augur.news import fmp

    assert fmp.FMP_SECRET in source_registry.live_secret_names()


def test_digest_items_include_all_social_lanes(monkeypatch):
    calls: list[str | None] = []

    def fake_items_for_day(day=None, theme=None, source_prefix=None, category=None):
        calls.append(source_prefix)
        if source_prefix is None:
            return [{"id": 1, "source": "博客·微信公众号", "published_at": "2026-06-11T09:00:00"}]
        return [
            {
                "id": len(calls) + 10,
                "source": source_prefix + "样本",
                "fetched_at": "2026-06-11T10:00:00",
            }
        ]

    monkeypatch.setattr(news_service, "items_for_day", fake_items_for_day)
    items = news_service.digest_items_for_day("2026-06-11")
    assert calls == [None, "X·", "小红书·", "Threads·", "Reddit·"]
    assert {it["source"] for it in items} == {
        "博客·微信公众号",
        "X·样本",
        "小红书·样本",
        "Threads·样本",
        "Reddit·样本",
    }


def test_news_read_state_counts_by_fetched_at(monkeypatch):
    captured: dict = {}

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, sql, args):
            captured["sql"] = sql
            captured["args"] = args
            return self

        def fetchone(self):
            return {"n": 7}

    monkeypatch.setattr(
        news_service.runtime_config, "get_news_read_at", lambda: "2026-06-11 01:02:03"
    )
    monkeypatch.setattr(news_service, "get_conn", lambda: FakeConn())

    state = news_service.news_read_state()
    assert state == {"last_read_at": "2026-06-11 01:02:03", "fresh_count": 7}
    assert "fetched_at" in captured["sql"]
    assert captured["args"] == ("2026-06-11 01:02:03",)


def test_tikhub_stock_social_search_keeps_working_when_one_source_fails(monkeypatch):
    def fake_fetch(queries, *, source_prefix, **kwargs):
        if source_prefix == "X·搜索·":
            raise tikhub.TikhubError("TikHub 端点当前失败")
        return [
            {
                "source": f"{source_prefix}{queries[0]}",
                "title": f"{source_prefix} signal",
                "url": f"https://example.test/{source_prefix}",
                "summary": "",
            }
        ]

    monkeypatch.setattr(tikhub, "_fetch_queries_limited", fake_fetch)
    items = tikhub.social_search_for_stock(["NVDA"])
    sources = {it["source"].split("·", 1)[0] for it in items}
    assert "小红书" in sources
    assert "Threads" in sources
    assert "Reddit" in sources


def test_source_test_diagnostics_for_tikhub_key():
    assert (
        source_test.diagnose_problem(
            "tikhub_twitter", RuntimeError("TikhubFatal: TIKHUB_KEY 无效或无权限（HTTP 401）")
        )
        == "推特：凭证无效，或当前套餐没有这个接口权限。"
    )
    assert (
        source_test.diagnose_problem(
            "tikhub_twitter",
            RuntimeError("TikhubError: TikHub 端点当前失败（服务端返回 400，未扣费）：请求失败"),
        )
        == "推特：TikHub 端点当前失败（服务端返回 400，未扣费）：请求失败"
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


# ───────────────────────── 分区级日报纯助手 ─────────────────────────
def test_section_digest_block_dedups_shared_news_across_stocks():
    # 同一条新闻（id=100）挂到分区内两只票 → 共用同一全局 [n]；只挂一只的另起编号
    shared = {"id": 100, "source": "Reuters", "title_zh": "英伟达与博通合作", "summary": ""}
    only_nvda = {"id": 101, "source": "Bloomberg", "title_zh": "英伟达发新卡", "summary": ""}
    stocks = [("US:NVDA", "英伟达", "GPU"), ("US:AVGO", "博通", "光通信")]
    items_by_sym = {"US:NVDA": [only_nvda, shared], "US:AVGO": [shared]}
    block, by_n = news_service._section_digest_block(stocks, items_by_sym)
    assert set(by_n) == {1, 2}  # 两条不同新闻 → 两个编号
    shared_n = next(n for n, it in by_n.items() if it["id"] == 100)
    assert block.count(f"[{shared_n}]") == 2  # 共享编号在两只票分组里各出现一次
    assert "## 英伟达 · US:NVDA（GPU）" in block
    assert "## 博通 · US:AVGO（光通信）" in block


def test_assemble_section_report_rejects_unknown_symbols_and_sorts():
    stocks = [("US:NVDA", "英伟达", "GPU"), ("US:AMD", "AMD", "GPU"), ("KR:000660", "SK海力士", "")]
    by_n = {
        1: {"id": 1, "source": "Reuters", "url": "https://r.test/1"},
        2: {"id": 2, "source": "Bloomberg", "url": "https://b.test/2"},
    }
    data = {
        "pulse": "算力链今天很热 [1]",
        "movers": [
            {"symbol": "US:AMD", "importance": "med", "headline": "AMD 平平", "points": []},
            {
                "symbol": "US:NVDA",
                "importance": "critical",
                "headline": "英伟达放量 [2]",
                "points": [{"text": "需求强劲", "refs": [2]}],
            },
            {"symbol": "US:FAKE", "importance": "high", "headline": "编造的票", "points": []},
        ],
    }
    out = news_service._assemble_section_report(7, "半导体", 3, stocks, data, by_n)
    syms = [m["symbol"] for m in out["movers"]]
    assert syms == ["US:NVDA", "US:AMD"]  # 编造的 US:FAKE 丢弃；critical 排在 med 前
    assert out["importance"] == "critical"  # 聚合重要性 = 最热 mover
    assert out["pulse"] == "算力链今天很热"  # 裸引用被剥掉
    assert out["quiet"] == ["SK海力士"]  # 无 mover 的票进 quiet（按 stocks 顺序）
    nvda = out["movers"][0]
    assert nvda["sub"] == "GPU" and nvda["market"] == "US"
    assert nvda["headline"] == "英伟达放量"  # 标题里泄漏的 [2] 被剥掉
    assert nvda["points"][0]["refs"][0]["url"] == "https://b.test/2"  # refs 映射回原始链接


# ───────────────────────── 反证雷达纯助手 ─────────────────────────
def test_thesis_conditions_assign_stable_ids_strip_and_cap():
    conds = theses_service._conditions_from_texts(["  失去大客户  ", "", "毛利率连续下滑", "   "])
    assert conds == [{"id": 1, "text": "失去大客户"}, {"id": 2, "text": "毛利率连续下滑"}]
    many = theses_service._conditions_from_texts([f"条件{i}" for i in range(20)])
    assert len(many) == theses_service._MAX_CONDITIONS  # 封顶
    assert [c["id"] for c in many] == list(range(1, theses_service._MAX_CONDITIONS + 1))
    assert theses_service._conditions_from_texts("not a list") == []


def test_thesis_map_refs_resolves_dedups_and_skips_invalid():
    by_n = {
        1: {"source": "Reuters", "url": "https://r.test/1"},
        2: {"source": "Bloomberg", "url": "https://b.test/2"},
        3: {"source": "NoUrl", "url": ""},
    }
    # 编号→source/url；容忍字符串数字；去重；跳过无 url / 越界 / 非数字
    refs = theses_service._map_refs([1, "2", 2, 3, 99, "x"], by_n)
    assert refs == [
        {"source": "Reuters", "url": "https://r.test/1"},
        {"source": "Bloomberg", "url": "https://b.test/2"},
    ]
    assert theses_service._map_refs(None, by_n) == []
    big = {i: {"source": f"s{i}", "url": f"https://x/{i}"} for i in range(1, 10)}
    assert len(theses_service._map_refs(list(range(1, 10)), big, cap=3)) == 3  # 封顶
