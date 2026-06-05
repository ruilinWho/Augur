"""数据/新闻信源「接口」注册表——驱动「设置」页的信源配置区（CLAUDE.md §1「知」）。

按作者要求把所有信源分三类（`group`）：**财经**（行情/基本面数据，喂 看/研）、
**新闻**（RSS/中文 newswire/官方资讯，喂 知）、**论坛**（社媒/社区情绪信号）。
免费已接的内置栈（行情数据、RSS 聚合）以只读聚合行呈现；需 key/token 的源留配置槽。

候选源可行性调研结论见 ADR-0007/0012。Tushare/必盈/iTick 曾作为候选行情源登记，
但作者要求从设置页移除；Reddit 已用 public JSON 接入；雪球/小红书属登录型或不稳定
抓取源，先登记配置槽与 UI lane，不伪装已接入。
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
        "setup": "内置可用，无需额外 API key。",
        "best_use": "四市场 K 线、报价与基础财务兜底，优先喂「看」和「研」。",
        "boundary": "免费源偶发限流或缺字段；高阶基本面仍需单独数据源接入。",
    },
    # ──────────── 新闻 · RSS / 中文 newswire / 官方资讯 ────────────
    {
        "id": "feeds_rss",
        "name": "RSS",  # status_list 动态补条数
        "group": "news",
        "access": "free_rss",
        "payment": "免费",
        "note": "详见 feeds.yaml",
        "setup": "版本化信源写在 resources/sources/feeds.yaml。",
        "best_use": "一手机构、公司 IR、官方研究博客和精英二手源的主新闻流。",
        "boundary": "RSS 源可能下线、反爬或改版；健康度会记录最近失败原因。",
    },
    {
        "id": "bloomberg",
        "name": "Bloomberg",
        "group": "news",
        "access": "free_rss",
        "payment": "免费",
        "note": "官方 RSS",
        "setup": "无需 key；频道在本页配置。",
        "best_use": "市场/科技高密度新闻，适合作为全球新闻 lane 的二手确认源。",
        "boundary": "RSS 只覆盖公开免费栏目，不等同 Bloomberg 终端或付费 API。",
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
        "setup": "无需 key；内置签名适配器会轻量抓取。",
        "best_use": "A 股科技、半导体、政策和产业链快讯。",
        "boundary": "网页接口有反爬/签名变化风险；失败会进入信源健康度。",
    },
    {
        "id": "eastmoney_news",
        "name": "东方财富",
        "group": "news",
        "access": "free_api",
        "active": True,
        "payment": "免费",
        "note": "关键词资讯",
        "setup": "无需 key；关键词在本页配置。",
        "best_use": "按主题或个股关键词补中文资讯，适合发现 A/H/中概相关线索。",
        "boundary": "JSONP 网页接口可能变化；只作为弱补充，不作为唯一依据。",
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
        "docs_url": "https://twtapi.io/docs/endpoints/user_tweets",
        "official_url": "https://docs.x.com/x-api/getting-started/getting-access",
        "payment": "月付·有免费试用",
        "note": "官方号推文·twtapi 桥",
        "setup": "Augur 当前填 TWTAPI_KEY；X 官方 key 在 console.x.com，但不是当前适配器凭证。",
        "best_use": "追踪官方号、大 V、公司号和每股专属 X 账号；后续可扩展 search/mentions。",
        "boundary": "twtapi 是非官方桥；额度、鉴权或端点变化会以中文诊断暴露。",
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
        "docs_url": "https://pypi.org/project/pysnowball/",
        "payment": "免费·需登录",
        "note": "社区情绪·需登录",
        "secret_label": "完整 Cookie header",
        "secret_placeholder": "xq_a_token=...; u=...; xq_r_token=...; device_id=...",
        "secret_help": "从浏览器 Network 里的请求复制整段 Cookie header；不要只复制某一个值。",
        "setup": (
            "轻量测试会访问讨论搜索 JSON；请从浏览器请求复制完整 Cookie header 到 "
            "XUEQIU_TOKEN，至少包含 xq_a_token 和 u。"
        ),
        "best_use": "关注大 V、按个股/关键词追踪讨论，适合 A/H/中概社区情绪和反证线索。",
        "boundary": "登录 Cookie 会失效且暴露账号足迹；当前只接入内容探活，未并入自动抓取。",
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
        "docs_url": "https://developers.reddit.com/docs/capabilities/server/reddit-api",
        "official_url": "https://developers.reddit.com/new",
        "setup": "当前 public JSON 无需 key；重度抓取、写入或私有能力再走官方 Devvit/OAuth。",
        "best_use": "追踪 subreddit 新帖、个股子版、WSB/ValueInvesting 等弱信号。",
        "boundary": "轻量只读可用；放大抓取规模前要走官方路径并尊重限流。",
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
        "docs_url": "https://school.xiaohongshu.com/en/open/quick-start/how-to-get-app-key.html",
        "official_url": "https://school.xiaohongshu.com/en/open/index.html",
        "payment": "免费·需登录",
        "note": "消费/情绪信号·待接入",
        "setup": (
            "当前配置槽是登录 Cookie；官方 Ark App Key 主要面向商家开放平台，"
            "不等于公开笔记搜索。"
        ),
        "best_use": "只在拿到稳定合规接口后追踪消费、品牌、散户情绪、关注用户和关键词。",
        "boundary": "匿名抓取和浏览器 Cookie 不稳定且风险高；目前不接真实抓取。",
        "config": [
            {"field": "accounts", "type": "accounts", "label": "关注用户"},
            {"field": "keywords", "type": "tags", "label": "个股 / 关键词"},
        ],
    },
]
# 调研结论（ADR-0007）：行情类候选（必盈/iTick/Tushare）被 FDR/akshare/yfinance/pykrx 免费
#   覆盖且增隐私外泄；作者已要求从设置页移除。雪球需周级失效的
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
                "docs_url": s.get("docs_url", ""),
                "official_url": s.get("official_url", ""),
                "secret_label": s.get("secret_label", ""),
                "secret_placeholder": s.get("secret_placeholder", ""),
                "secret_help": s.get("secret_help", ""),
                "setup": s.get("setup", ""),
                "best_use": s.get("best_use", ""),
                "boundary": s.get("boundary", ""),
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
