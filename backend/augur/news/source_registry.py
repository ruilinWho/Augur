"""数据/新闻信源「接口」注册表——驱动「设置」页的信源配置区（CLAUDE.md §1「知」）。

按作者要求把所有信源分三类（`group`）：**财经**（行情/基本面数据，喂 看/研）、
**新闻**（RSS/中文 newswire/官方资讯，喂 知）、**论坛**（社媒/社区情绪信号）。
免费已接的内置栈（行情数据、RSS 聚合）以只读聚合行呈现；需 key/token 的源留配置槽。

候选源可行性调研结论见 ADR-0007/0012。Tushare/必盈/iTick 曾作为候选行情源登记，
但作者要求从设置页移除；雪球登录 Cookie 抓取已失效、随之退役；Reddit 已用
public JSON 接入；TikHub 作为共享 paid API provider 接 推特（唯一推特源）、小红书、Threads、
Reddit 搜索。twtapi 桥（旧推特源）已退役，仅每股专属信源还用。微信公众文章源已删除（TikHub
`wechat_mp/web/*` 整组服务端长期 400，见 docs/memory/tikhub-source-quirks.md）。
普通 RSS 源仍在 `feeds.yaml`；这里只登记需 key/token 或需专用适配器、或作分类总览的源。
"""

from __future__ import annotations

from .. import runtime_config
from . import eastmoney_news, sources, tikhub

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
        "id": "tikhub_twitter",
        "name": "推特",
        "group": "news",
        "access": "paid_api",
        "key_env": "TIKHUB_KEY",
        "cred": "key",
        "key_url": "https://docs.tikhub.io/",
        "docs_url": "https://docs.tikhub.io/215701673e0",
        "official_url": "https://docs.tikhub.io/",
        "payment": "预付余额",
        "note": "TikHub 搜索/账号",
        "setup": (
            "在 TikHub 后台充值并复制 Bearer Token，填入 TIKHUB_KEY；"
            "与小红书/Threads 共享。"
        ),
        "best_use": "唯一推特源：按关键词搜索 + 关注账户，追踪 AI/半导体话题与个股大众观点。",
        "boundary": "TikHub 是第三方桥；只能作为弱信号，必须经 Augur 摘要、去噪与反证合成。",
        "config": [
            {"field": "accounts", "type": "accounts", "label": "关注账户"},
            {"field": "keywords", "type": "tags", "label": "个股 / 关键词"},
        ],
    },
    # ──────────── 论坛 · 社媒 / 社区情绪 ────────────
    # 注：reddit.com 直连 public JSON 已被按 IP 封 403，直连源已删除；Reddit 全走 TikHub（下）。
    {
        "id": "tikhub_reddit",
        "name": "Reddit · TikHub",
        "group": "forum",
        "access": "paid_api",
        "key_env": "TIKHUB_KEY",
        "cred": "key",
        "key_url": "https://docs.tikhub.io/",
        "docs_url": "https://docs.tikhub.io/369454687e0",
        "official_url": "https://docs.tikhub.io/",
        "payment": "预付余额",
        "note": "关键词搜索",
        "setup": "填同一份 TIKHUB_KEY；公共 subreddit 仍由 Reddit 源独立承担。",
        "best_use": "补足 public subreddit JSON 看不到的全站关键词搜索和个股讨论热度。",
        "boundary": "搜索结果比 subreddit 流更噪，需要继续走 LLM 去重、相关性过滤和股票接地。",
        "config": [{"field": "keywords", "type": "tags", "label": "个股 / 关键词"}],
    },
    {
        "id": "xiaohongshu",
        "name": "小红书",
        "group": "forum",
        "access": "paid_api",
        "key_env": "TIKHUB_KEY",
        "cred": "key",
        "key_url": "https://docs.tikhub.io/",
        "docs_url": "https://docs.tikhub.io/420136398e0",
        "official_url": "https://docs.tikhub.io/",
        "payment": "预付余额",
        "note": "笔记搜索",
        "setup": "填同一份 TIKHUB_KEY；Augur 使用 TikHub 小红书 App V2 搜索笔记接口。",
        "best_use": "搜索消费、品牌、散户情绪和产品口碑，尤其适合中概/消费/AI 端侧热门叙事。",
        "boundary": "小红书信号偏消费口碑和情绪，不等于财务事实；只展示 AI 摘要后的判断。",
        "config": [{"field": "keywords", "type": "tags", "label": "个股 / 关键词"}],
    },
    {
        "id": "tikhub_threads",
        "name": "Threads",
        "group": "forum",
        "access": "paid_api",
        "key_env": "TIKHUB_KEY",
        "cred": "key",
        "key_url": "https://docs.tikhub.io/",
        "docs_url": "https://docs.tikhub.io/381269441e0",
        "official_url": "https://docs.tikhub.io/",
        "payment": "预付余额",
        "note": "热门内容搜索",
        "setup": "填同一份 TIKHUB_KEY；按关键词拉 Threads 热门内容。",
        "best_use": "观察海外散户/科技圈对主题和产品的温和社媒反馈。",
        "boundary": "Threads 覆盖面和金融密度有限，适合作旁证，不单独形成投资动作。",
        "config": [{"field": "keywords", "type": "tags", "label": "个股 / 关键词"}],
    },
]
# 调研结论（ADR-0007）：行情类候选（必盈/iTick/Tushare）被 FDR/akshare/yfinance/pykrx 免费
#   覆盖且增隐私外泄；作者已要求从设置页移除。雪球的登录 Cookie 抓取已失效（风控墙
#   拦内容 JSON），2026-06-05 退役、从设置页与探活注册中移除。TikHub 接入见 ADR-0013。
#   **推特唯一源＝TikHub**（2026-06-11）：twtapi 桥（旧「推特」/X·）作为全局源已退役、
#   从注册表与 ingest 移除；TikHub 升为唯一「推特」源（搜索+账号，仍 X· 前缀）。
#   twtapi.py 仅每股专属信源（按 X 账号拉，twtapi 失败回退 TikHub）还在用。

# 三类显示顺序与中文标签（前端分组用）
GROUPS: list[dict] = [
    {"id": "finance", "label": "财经", "blurb": "行情 · 基本面数据"},
    {"id": "news", "label": "新闻", "blurb": "RSS · newswire · 官方资讯"},
    {"id": "forum", "label": "论坛", "blurb": "社媒 · 社区情绪"},
]

# 信源可配置项「生效值」解析器（(source_id, field) → 返回当前生效列表的函数）
_CONFIG_VALUE = {
    ("tikhub_twitter", "accounts"): tikhub.twitter_accounts,
    ("tikhub_twitter", "keywords"): tikhub.twitter_keywords,
    ("bloomberg", "channels"): lambda: runtime_config.get_source_config(
        "bloomberg", "channels", ["科技", "Markets"]
    ),
    ("eastmoney_news", "keywords"): eastmoney_news.keywords,
    ("tikhub_reddit", "keywords"): tikhub.reddit_keywords,
    ("xiaohongshu", "keywords"): tikhub.xiaohongshu_keywords,
    ("tikhub_threads", "keywords"): tikhub.threads_keywords,
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
            k = str(k).strip()[:40]
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
