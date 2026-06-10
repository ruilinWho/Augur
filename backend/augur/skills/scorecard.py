"""供应链卡点评分卡（移植自 Serenity skill 的 serenity_scorecard.py，零依赖）。

8 个正向因子加权（合计 100）− 8 个惩罚项（×2）→ clamp[0,100] + 分级。
打分本身由 LLM/人给（主观），本模块只做确定性汇总。供「研」的卡点类 Skill 调用。
"""

from __future__ import annotations

from typing import Any

WEIGHTS: dict[str, int] = {
    "demand_inflection": 15,  # 需求拐点
    "architecture_coupling": 10,  # 与系统架构耦合度
    "chokepoint_severity": 15,  # 卡点严重度
    "supplier_concentration": 12,  # 供应商集中度
    "expansion_difficulty": 12,  # 扩产难度
    "evidence_quality": 15,  # 证据强度
    "valuation_disconnect": 11,  # 估值错配
    "catalyst_timing": 10,  # 催化剂时点
}
PENALTY_MULTIPLIER = 2.0
PENALTY_KEYS = [
    "dilution_financing",  # 稀释/融资
    "governance",  # 治理
    "geopolitics",  # 地缘
    "liquidity",  # 流动性
    "hype_risk",  # 炒作风险
    "accounting_quality",  # 会计质量
    "cyclicality",  # 周期性
    "alternative_design_risk",  # 被替代设计风险
]


def template() -> dict:
    return {
        "ticker": "",
        "company": "",
        "market": "US/HK/A-share/Taiwan/Japan/Korea/Europe",
        "factors": {k: 0 for k in WEIGHTS},
        "penalties": {k: 0 for k in PENALTY_KEYS},
        "evidence": [{"claim": "", "source": "", "strength": "primary/media/analysis/social"}],
        "what_could_weaken_view": ["", "", ""],
    }


def _num_0_to_5(value: Any, label: str) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} 必须是 0–5 的数字") from None
    if n < 0 or n > 5:
        raise ValueError(f"{label} 必须在 0–5 之间，收到 {n}")
    return n


def score(data: dict) -> dict:
    """对一份卡点评分输入打分。返回含 final_score/verdict/明细 的结果。"""
    factors = data.get("factors") or {}
    penalties = data.get("penalties") or {}

    factor_details: dict[str, dict] = {}
    total = 0.0
    for key, weight in WEIGHTS.items():
        rating = _num_0_to_5(factors.get(key, 0), f"factors.{key}")
        pts = rating / 5.0 * weight
        factor_details[key] = {"rating": rating, "weight": weight, "points": round(pts, 2)}
        total += pts

    penalty_details: dict[str, dict] = {}
    penalty_total = 0.0
    for key, value in penalties.items():
        rating = _num_0_to_5(value, f"penalties.{key}")
        pts = rating * PENALTY_MULTIPLIER
        penalty_details[key] = {"rating": rating, "points": round(pts, 2)}
        penalty_total += pts

    final = max(0.0, min(100.0, total - penalty_total))
    if final >= 85:
        verdict = "Top research priority / 最高优先研究"
    elif final >= 70:
        verdict = "High research priority / 高优先"
    elif final >= 55:
        verdict = "Worth tracking / 值得跟踪"
    else:
        verdict = "Early lead / 早期线索"

    return {
        "ticker": data.get("ticker", ""),
        "company": data.get("company", ""),
        "market": data.get("market", ""),
        "raw_factor_points": round(total, 2),
        "penalty_points": round(penalty_total, 2),
        "final_score": round(final, 2),
        "verdict": verdict,
        "factor_details": factor_details,
        "penalty_details": penalty_details,
        "kill_switches": data.get("what_could_weaken_view") or data.get("kill_switches") or [],
        "evidence": data.get("evidence") or [],
    }
