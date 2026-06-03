"""数据/新闻信源「接口」注册表——驱动「设置」页的信源配置区（CLAUDE.md §1「知」）。

按主人要求把所有信源分三类（`group`）：**财经**（行情/基本面数据，喂 看/研）、
**新闻**（RSS/中文 newswire/官方资讯，喂 知）、**论坛**（社媒/社区情绪信号）。
免费已接的内置栈（行情数据、RSS 聚合）以只读聚合行呈现；需 key/token 的源留配置槽。

候选源可行性调研（twtapi/必盈/iTick/Tushare/雪球）结论见 ADR-0007：均与现有免费栈
重叠或有隐私权衡，故标为「可选·待配置」由主人定夺，不默认启用、不写适配器（先登记留槽）。
普通 RSS 源仍在 `feeds.yaml`；这里只登记需 key/token 或需专用适配器、或作分类总览的源。
"""

from __future__ import annotations

from .. import runtime_config
from . import sources

# access：builtin 内置已接 · free_rss 免费RSS已接 · free_api 免费API · paid_api 付费API
# group：finance 财经（行情/基本面）· news 新闻 · forum 论坛（社媒/社区）
# cred：需要的凭证类型（key / token），决定配置槽文案；无则不显配置槽
SOURCES: list[dict] = [
    # ──────────── 财经 · 行情 / 基本面数据 ────────────
    {
        "id": "market_data",
        "name": "行情 / 基本面数据",
        "group": "finance",
        "access": "builtin",
        "payment": "免费",
        "note": "FDR·akshare·yfinance·pykrx",
    },
    {
        "id": "tushare_pro",
        "name": "Tushare Pro",
        "group": "finance",
        "access": "paid_api",
        "key_env": "TUSHARE_TOKEN",
        "cred": "token",
        "payment": "积分制·充值",
        "note": "A股·免费档薄·已被覆盖",
    },
    {
        "id": "biyingapi",
        "name": "必盈 BiYing",
        "group": "finance",
        "access": "paid_api",
        "key_env": "BIYING_API_LICENCE",
        "cred": "key",
        "payment": "未明示·疑微信",
        "note": "A/港行情·已被覆盖",
    },
    {
        "id": "itick",
        "name": "iTick",
        "group": "finance",
        "access": "paid_api",
        "key_env": "ITICK_API_KEY",
        "cred": "key",
        "payment": "USD·国际卡",
        "note": "全球行情·免费档严",
    },
    # ──────────── 新闻 · RSS / 中文 newswire / 官方资讯 ────────────
    {
        "id": "feeds_rss",
        "name": "RSS 新闻源",  # status_list 动态补条数
        "group": "news",
        "access": "free_rss",
        "payment": "免费",
        "note": "详见 feeds.yaml",
    },
    {
        "id": "bloomberg",
        "name": "Bloomberg · 科技/市场",
        "group": "news",
        "access": "free_rss",
        "payment": "免费",
        "note": "官方 RSS",
    },
    {
        "id": "cls",
        "name": "财联社 CLS",
        "group": "news",
        "access": "free_api",
        "active": True,
        "payment": "免费",
        "note": "科创电报",
    },
    {
        "id": "eastmoney_news",
        "name": "东方财富 · 资讯",
        "group": "news",
        "access": "free_api",
        "active": True,
        "payment": "免费",
        "note": "关键词资讯",
    },
    {
        "id": "twtapi",
        "name": "X(Twitter) 官方号",
        "group": "news",
        "access": "paid_api",
        "key_env": "TWTAPI_KEY",
        "cred": "key",
        "payment": "月付·有免费试用",
        "note": "官方号推文·twtapi 桥",
    },
    # ──────────── 论坛 · 社媒 / 社区情绪 ────────────
    {
        "id": "xueqiu",
        "name": "雪球 Xueqiu",
        "group": "forum",
        "access": "free_api",
        "key_env": "XUEQIU_TOKEN",
        "cred": "token",
        "payment": "免费·需登录",
        "note": "社区情绪·需登录·泄持仓",
    },
]
# 调研结论（ADR-0007）：行情类候选（必盈/iTick/Tushare）被 FDR/akshare/yfinance/pykrx 免费
#   覆盖且增隐私外泄；雪球需周级失效的登录 token 且把持仓查询绑真实账号泄露（违 §11）。故均登记
#   留槽、由主人定夺。**Twitter 桥选 twtapi**（而非 TwitterAPI.io）：主人无国际银行卡、付不了
#   TwitterAPI.io，twtapi 有免费试用+月付套餐，故采 twtapi。已移除太贵源见 ADR-0007。

# 三类显示顺序与中文标签（前端分组用）
GROUPS: list[dict] = [
    {"id": "finance", "label": "财经", "blurb": "行情 · 基本面数据"},
    {"id": "news", "label": "新闻", "blurb": "RSS · newswire · 官方资讯"},
    {"id": "forum", "label": "论坛", "blurb": "社媒 · 社区情绪"},
]


def status_list() -> list[dict]:
    """每条信源 + 计算后的状态（供前端按 group 分组、显徽标）。"""
    rss_n = len(sources.load_feeds())
    out: list[dict] = []
    for s in SOURCES:
        key_env = s.get("key_env")
        access = s["access"]
        cred = s.get("cred", "key")
        if access in ("builtin", "free_rss"):
            configured, status = True, "已接入"
        elif access == "free_api" and not key_env:
            configured = bool(s.get("active"))
            status = "已接入" if configured else "免费 · 待接入"
        elif access == "unavailable":
            configured, status = False, "不可用"
        elif key_env:  # 需凭证（key/token），免费或付费皆可
            configured = runtime_config.has_secret(key_env)
            status = "已配置" if configured else f"待配置 {'token' if cred == 'token' else 'key'}"
        else:
            configured, status = False, "待接入"
        name = s["name"]
        if s["id"] == "feeds_rss":
            name = f"{name} · {rss_n}"  # 动态条数，不写死
        out.append(
            {
                "id": s["id"],
                "name": name,
                "group": s["group"],
                "access": access,
                "key_env": key_env,
                "cred": cred if key_env else "",
                "note": s["note"],
                "payment": s.get("payment", ""),  # 支付方式（中国用户视角，见 ADR-0007）
                "configured": configured,
                "status": status,
                "hint": runtime_config.secret_hint(key_env) if key_env else "",
            }
        )
    return out


def groups() -> list[dict]:
    """三类标签 + 顺序（供前端分组渲染）。"""
    return GROUPS
