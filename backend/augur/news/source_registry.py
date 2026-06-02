"""数据/新闻信源「接口」注册表——驱动「设置」页的信源配置区（CLAUDE.md §1「知」）。

把需要凭证或属于「待接入」的高价值信源登记于此：免费已接（Bloomberg RSS）、免费待接
（财联社/东财，非官方 API，适配器后续）、付费待主人买 key（X 桥/Reuters/iFinD/Choice）、
不可用（Wind 需 Windows 终端、DM 仅 FICC）。`status_list()` 计算每条的可用状态供前端展示。

调研依据见 ADR-0006（X）+ 后续 ADR（Bloomberg/Reuters/中文终端可行性）。普通 RSS 源仍在
`feeds.yaml`；这里只登记**需 key 或需专用适配器**的源，便于主人在 UI 里配 key、看状态。
"""

from __future__ import annotations

from .. import runtime_config

# access 取值：free_rss 免费RSS已接 · free_api 免费非官方API待接 ·
#              paid_api 付费API待key · paid_terminal 付费终端(headless难) · unavailable 不可用
SOURCES: list[dict] = [
    {
        "id": "bloomberg",
        "name": "Bloomberg · 科技/市场",
        "category": "国际 · 精英二手",
        "access": "free_rss",
        "key_env": None,
        "payment": "免费",
        "note": "彭博官方 RSS（technology/markets），已接入 feeds.yaml；未公开文档，带回退。",
    },
    {
        "id": "x_bridge",
        "name": "X(Twitter) 官方号",
        "category": "社媒一手",
        "access": "paid_api",
        "key_env": "TWITTERAPI_KEY",
        "payment": "信用卡 / 加密(USDT)·无支付宝",
        "note": "经 TwitterAPI.io 桥拉官方号推文（OpenAI/NVIDIA/@sama…）。配 key 后启用；"
        "无支付宝/微信，国内走加密(USDT)或虚拟卡；权衡见 ADR-0006/0007。",
    },
    {
        "id": "cls",
        "name": "财联社 CLS",
        "category": "中文 · 科技 newswire",
        "access": "free_api",
        "key_env": None,
        "active": True,
        "payment": "免费",
        "note": "科创电报，免费非官方 API（带 sign）；最佳中文科技实时源，已接入（cls.py）。",
    },
    {
        "id": "eastmoney_news",
        "name": "东方财富 · 资讯",
        "category": "中文 · 科技",
        "access": "free_api",
        "key_env": None,
        "active": True,
        "payment": "免费",
        "note": "免费关键词资讯 JSON（人工智能/半导体/算力…），已接入（eastmoney_news.py）。",
    },
]
# 已按主人意见**移除太贵的数据源**（仅保留免费/极廉）：
#   Reuters（仅 LSEG/Refinitiv 企业合约，五位数/年）、万得 Wind（~¥39,800/年且需 Windows 终端）、
#   同花顺 iFinD / 东财 Choice（~¥30k/年机构终端）。需要时可经 ADR-0007 记录的路径再接。
#   保留：Bloomberg（免费 RSS）、财联社/东财（免费 API）、X（TwitterAPI.io 桥，约 $几/月）。


def status_list() -> list[dict]:
    """每条信源 + 计算后的状态（供前端徽标）。"""
    out: list[dict] = []
    for s in SOURCES:
        key_env = s["key_env"]
        if s["access"] == "free_rss":
            status, configured = "已接入", True
        elif s["access"] == "free_api":
            configured = bool(s.get("active"))
            status = "已接入" if configured else "免费 · 待接入"
        elif s["access"] == "unavailable":
            status, configured = "不可用", False
        else:  # paid_api：看 key
            configured = bool(key_env and runtime_config.has_secret(key_env))
            status = "已配置" if configured else "待配置 key"
        out.append(
            {
                "id": s["id"],
                "name": s["name"],
                "category": s["category"],
                "access": s["access"],
                "key_env": key_env,
                "note": s["note"],
                "payment": s.get("payment", ""),  # 支付方式（中国用户视角，见 ADR-0007）
                "configured": configured,
                "status": status,
                "hint": runtime_config.secret_hint(key_env) if key_env else "",
            }
        )
    return out
