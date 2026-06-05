"""数据/新闻信源「接口」注册表——驱动「设置」页的信源配置区（CLAUDE.md §1「知」）。

按作者要求把所有信源分三类（`group`）：**财经**（行情/基本面数据，喂 看/研）、
**新闻**（RSS/中文 newswire/官方资讯，喂 知）、**论坛**（社媒/社区情绪信号）。
免费已接的内置栈（行情数据、RSS 聚合）以只读聚合行呈现；需 key/token 的源留配置槽。

候选源可行性调研（twtapi/必盈/iTick/Tushare/雪球）结论见 ADR-0007。Tushare/必盈/iTick
目前只做设置页轻量探活，不替代内置行情栈；Reddit 已用 public JSON 接入；雪球/小红书属
登录型或不稳定抓取源，先登记配置槽与 UI lane，不伪装已接入。
普通 RSS 源仍在 `feeds.yaml`；这里只登记需 key/token 或需专用适配器、或作分类总览的源。
"""

from __future__ import annotations

from .. import runtime_config
from . import eastmoney_news, reddit, sources, twtapi

# access：builtin 内置已接 · free_rss 免费RSS已接 · free_api 免费API · paid_api 付费API
# group：finance 财经（行情/基本面）· news 新闻 · forum 论坛（社媒/社区）
# cred：需要的凭证类型（key / token），决定配置槽文案；无则不显配置槽
SOURCES: list[dict] = [
    # ──────────── 财经 · 行情 / 基本面数据 ────────────
    {
        "id": "market_data",
        "name": "内置行情栈",
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
        "key_url": "https://tushare.pro/document/1?doc_id=39",
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
        "key_url": "https://www.biyingapi.com/licencelt",
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
        "key_url": "https://docs.itick.net/en/getting-started",
        "payment": "USD·国际卡",
        "note": "全球行情·免费档严",
    },
    # ──────────── 新闻 · RSS / 中文 newswire / 官方资讯 ────────────
    {
        "id": "feeds_rss",
        "name": "RSS",  # status_list 动态补条数
        "group": "news",
        "access": "free_rss",
        "payment": "免费",
        "note": "详见 feeds.yaml",
    },
    {
        "id": "bloomberg",
        "name": "Bloomberg",
        "group": "news",
        "access": "free_rss",
        "payment": "免费",
        "note": "官方 RSS",
        "config": [{"field": "channels", "type": "tags", "label": "频道"}],
    },
    {
        "id": "cls",
        "name": "财联社",
        "group": "news",
        "access": "free_api",
        "active": True,
        "payment": "免费",
        "note": "科创电报",
    },
    {
        "id": "eastmoney_news",
        "name": "东方财富",
        "group": "news",
        "access": "free_api",
        "active": True,
        "payment": "免费",
        "note": "关键词资讯",
        "config": [{"field": "keywords", "type": "tags", "label": "检索关键词"}],
    },
    {
        "id": "twtapi",
        "name": "X",
        "group": "news",
        "access": "paid_api",
        "key_env": "TWTAPI_KEY",
        "cred": "key",
        "key_url": "https://twtapi.io/",
        "payment": "月付·有免费试用",
        "note": "官方号推文·twtapi 桥",
        "config": [{"field": "accounts", "type": "accounts", "label": "关注账户"}],
    },
    # ──────────── 论坛 · 社媒 / 社区情绪 ────────────
    {
        "id": "xueqiu",
        "name": "雪球",
        "group": "forum",
        "access": "free_api",
        "key_env": "XUEQIU_TOKEN",
        "cred": "token",
        "key_url": "https://xueqiu.com/",
        "payment": "免费·需登录",
        "note": "社区情绪·需登录",
        "config": [
            {"field": "accounts", "type": "accounts", "label": "关注用户"},
            {"field": "keywords", "type": "tags", "label": "个股 / 关键词"},
        ],
    },
    {
        "id": "reddit",
        "name": "Reddit",
        "group": "forum",
        "access": "free_api",
        "active": True,
        "payment": "免费",
        "note": "Subreddit 讨论",
        "config": [{"field": "subreddits", "type": "tags", "label": "Subreddits"}],
    },
    {
        "id": "xiaohongshu",
        "name": "小红书",
        "group": "forum",
        "access": "free_api",
        "key_env": "XHS_COOKIE",
        "cred": "token",
        "key_url": "https://www.xiaohongshu.com/",
        "payment": "免费·需登录",
        "note": "消费/情绪信号·待接入",
        "config": [
            {"field": "accounts", "type": "accounts", "label": "关注用户"},
            {"field": "keywords", "type": "tags", "label": "个股 / 关键词"},
        ],
    },
]
# 调研结论（ADR-0007）：行情类候选（必盈/iTick/Tushare）被 FDR/akshare/yfinance/pykrx 免费
#   覆盖且增隐私外泄；当前只在设置页做轻量真实探活，不默认喂行情/研究。雪球需周级失效的
#   登录 token 且把持仓查询绑真实账号泄露（违 §11），故只登记配置槽、由作者定夺。
#   **Twitter 桥选 twtapi**（而非 TwitterAPI.io）：作者无国际银行卡、付不了
#   TwitterAPI.io，twtapi 有免费试用+月付套餐，故采 twtapi。已移除太贵源见 ADR-0007。

# 三类显示顺序与中文标签（前端分组用）
GROUPS: list[dict] = [
    {"id": "finance", "label": "财经", "blurb": "行情 · 基本面数据"},
    {"id": "news", "label": "新闻", "blurb": "RSS · newswire · 官方资讯"},
    {"id": "forum", "label": "论坛", "blurb": "社媒 · 社区情绪"},
]

# 信源可配置项「生效值」解析器（(source_id, field) → 返回当前生效列表的函数）
_CONFIG_VALUE = {
    ("twtapi", "accounts"): twtapi.accounts,
    ("bloomberg", "channels"): lambda: runtime_config.get_source_config(
        "bloomberg", "channels", ["科技", "Markets"]
    ),
    ("eastmoney_news", "keywords"): eastmoney_news.keywords,
    ("reddit", "subreddits"): reddit.subreddits,
    ("xueqiu", "accounts"): lambda: runtime_config.get_source_config("xueqiu", "accounts", []),
    ("xueqiu", "keywords"): lambda: runtime_config.get_source_config("xueqiu", "keywords", []),
    ("xiaohongshu", "accounts"): lambda: runtime_config.get_source_config(
        "xiaohongshu", "accounts", []
    ),
    ("xiaohongshu", "keywords"): lambda: runtime_config.get_source_config(
        "xiaohongshu", "keywords", []
    ),
}
_ACCOUNT_CATS = {
    "ai",
    "chips",
    "space",
    "robotics",
    "tech",
    "investor",
    "macro",
    "other",
}  # 账户分类白名单


def _config_for(s: dict) -> list[dict]:
    """某源的可配置项 + 当前生效值（供前端渲染编辑器）。"""
    out: list[dict] = []
    for f in s.get("config") or []:
        resolver = _CONFIG_VALUE.get((s["id"], f["field"]))
        out.append(
            {
                "field": f["field"],
                "type": f["type"],
                "label": f["label"],
                "value": resolver() if resolver else [],
            }
        )
    return out


def config_fields(source_id: str) -> dict[str, str]:
    """某源声明的 {field: type}（供端点校验）。"""
    s = next((x for x in SOURCES if x["id"] == source_id), None)
    return {f["field"]: f["type"] for f in (s or {}).get("config") or []}


def sanitize_config(ftype: str, value) -> list:
    """按字段类型清洗写入值（accounts=账户列表 / tags=关键词列表）。"""
    if ftype == "accounts":
        out, seen = [], set()
        for a in value or []:
            if not isinstance(a, dict):
                continue
            sn = str(a.get("screen_name", "")).strip().lstrip("@")[:30]
            if not sn or sn.lower() in seen:
                continue
            seen.add(sn.lower())
            cat = str(a.get("category", "tech")).strip().lower()
            out.append({"screen_name": sn, "category": cat if cat in _ACCOUNT_CATS else "tech"})
        return out[:60]
    if ftype == "tags":
        out, seen = [], set()
        for k in value or []:
            k = str(k).strip()[:20]
            if k and k.lower() not in seen:
                seen.add(k.lower())
                out.append(k)
        return out[:40]
    return []


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
            status = "已配置" if configured else "待配置"
        else:
            configured, status = False, "待接入"
        name = s["name"]
        note = s["note"]
        if s["id"] == "feeds_rss":
            note = f"{rss_n} 个源"
        out.append(
            {
                "id": s["id"],
                "name": name,
                "group": s["group"],
                "access": access,
                "key_env": key_env,
                "cred": cred if key_env else "",
                "key_url": s.get("key_url", ""),
                "note": note,
                "payment": s.get("payment", ""),  # 支付方式（中国用户视角，见 ADR-0007）
                "configured": configured,
                "status": status,
                "hint": runtime_config.secret_hint(key_env) if key_env else "",
                "key_value": runtime_config.get_secret(key_env) if key_env else "",
                "config": _config_for(s),
            }
        )
    return out


def groups() -> list[dict]:
    """三类标签 + 顺序（供前端分组渲染）。"""
    return GROUPS
