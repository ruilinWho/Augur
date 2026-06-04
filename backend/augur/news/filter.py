"""噪音过滤（CLAUDE.md §1「知」/ M3）：滤掉对投资判断无意义的纯盘面/价格波动新闻。

作者要求：「涨了/跌了多少」「价格变了多少」「股票行情」这类信息没意义，应筛掉；
保留会对投资产生影响的实质信息。规则法（零成本、可解释，§6 不必每条调 LLM）：
- 硬噪音：行情列表 / 涨停跌停 / 收评午评 / 盘前盘后复盘 等纯盘面 → 一律滤。
- 软噪音：大盘/指数/个股「涨跌/收高收低/创新高」综述、纯百分比波动 → 滤，
  **但若标题含基本面信号（营收/利润/增长/订单/产能/财报/HBM 价格…）则保留**（那是实质信息）。
关键词在本模块（作者可调）。摄取时滤、不落库。
"""

from __future__ import annotations

import re

from ..storage import get_conn

# 硬噪音：出现即滤（纯盘面，无实质）
_HARD = re.compile(
    r"行情"
    r"|涨停|跌停|跌停板|涨停板"
    r"|收评|午评|早评|晚评|复盘|盘前必读|盘后总结|每日复盘"
    r"|stock prices?\b"
)

# 价格波动/市场综述（软噪音：无基本面信号才滤）
_MOVE = re.compile(
    r"(股价|股市|大盘|指数|创业板|科创板|A股|美股|港股|韩股|日股)\s*"
    r".{0,10}(涨|跌|收涨|收跌|大涨|大跌|新高|新低|反弹|回调|高开|低开)"
    r"|(上涨|下跌|涨|跌|大涨|大跌)\s*\d+(\.\d+)?\s*%"
    r"|\b(stocks?|shares?|index|indexes|indices|dow|nasdaq|s&p|nikkei|kospi|kosdaq|"
    r"hang\s*seng|ftse|equities|markets?|wall\s*street)\b"
    r".{0,30}\b(rose|fell|gain(ed|s)?|drop(ped|s)?|slid|slip(ped|s)?|jump(ed|s)?|"
    r"climb(ed|s)?|tumbl(ed|es)?|rall(y|ied|ies)|rebound(ed|s)?|edg(ed|es)|"
    r"clos(e|ed|ing)|end(ed|s)?|finish(ed|es)?|higher|lower|record\s+(high|low))"
    r"|\b(up|down|rose|fell|gain(ed|s)?|drop(ped|s)?)\s+\d+(\.\d+)?\s*(%|percent)",
    re.IGNORECASE,
)

# 基本面/宏观/风险信号：含这些则即便有涨跌字样也保留（实质信息，不算噪音）
_SIGNAL = re.compile(
    # 公司基本面
    r"营收|收入|利润|净利|毛利|增长|出货|产能|订单|营业额|交付|签约|中标|招标"
    r"|财报|业绩|指引|预期|融资|收购|并购|发布|推出|量产|投产|扩产|涨价|降价|合约价|报价"
    r"|减持|增持|回购|裁员|算力|芯片|半导体"
    # 宏观 / 政策 / 风险（影响投资判断）
    r"|通胀|物价|利率|降息|加息|美联储|关税|警告|风险|拥挤|泡沫|杠杆|做空|危机|制裁|出口管制"
    r"|revenue|sales|profit|margin|growth|shipment|capacity|order|guidance|earnings|"
    r"results|forecast|launch|unveil|acquir|merger|funding|raise|IPO|contract|deal|chip|wafer"
    r"|inflation|consumer prices|CPI|PPI|rate cut|rate hike|\bfed\b|tariff|warn|risk|"
    r"bubble|leverage|buyback|layoff|sanction|export control",
    re.IGNORECASE,
)


def is_noise(title: str) -> bool:
    """纯盘面/价格波动且无基本面信号 → True（摄取时滤掉）。"""
    t = title or ""
    if _HARD.search(t):
        return True
    if _MOVE.search(t) and not _SIGNAL.search(t):
        return True
    return False


def purge_noise() -> int:
    """删除库中已存的噪音条目（规则更新后清理历史；摄取已在源头滤）。返回删除数。"""
    conn = get_conn()
    try:
        rows = conn.execute("SELECT id, title FROM news_items").fetchall()
        ids = [(r["id"],) for r in rows if is_noise(r["title"])]
        if ids:
            conn.executemany("DELETE FROM news_items WHERE id = ?", ids)
            conn.commit()
        return len(ids)
    finally:
        conn.close()
