"""skills 域纯逻辑：列举/读取 Skill、启用状态、渲染占位符、评分卡。

启用状态存 runtime_config.prefs['skills_disabled']（禁用 slug 列表，默认全启用——
"丢一个文件夹进去就可用"）。渲染占位符与「模板」同契约：{STOCK}/{NAME}/{MARKET}/{SYMBOL}。
"""

from __future__ import annotations

from .. import runtime_config
from ..market import search
from . import registry, scorecard

_MARKET_LABEL = {"US": "美股", "HK": "港股", "CN": "A股", "KR": "韩股"}


def _disabled() -> set[str]:
    return set(runtime_config.get_pref("skills_disabled", []) or [])


def _meta(s: dict, disabled: set[str]) -> dict:
    return {
        "slug": s["slug"],
        "name": s["name"],
        "summary": s["summary"],
        "surface": s["surface"],
        "enabled": s["slug"] not in disabled,
        "has_scorecard": s["has_scorecard"],
    }


def list_skills(surface: str | None = None, only_enabled: bool = False) -> list[dict]:
    disabled = _disabled()
    out = []
    for s in registry.all_skills().values():
        if surface and s["surface"] != surface:
            continue
        m = _meta(s, disabled)
        if only_enabled and not m["enabled"]:
            continue
        out.append(m)
    out.sort(key=lambda m: (not m["enabled"], m["name"]))
    return out


def get_skill(slug: str) -> dict | None:
    s = registry.get(slug)
    if not s:
        return None
    out = _meta(s, _disabled())
    out["body"] = s["body"]
    return out


def set_enabled(slug: str, enabled: bool) -> dict:
    if registry.get(slug) is None:
        raise ValueError(f"技能 {slug} 不存在")
    disabled = _disabled()
    if enabled:
        disabled.discard(slug)
    else:
        disabled.add(slug)
    runtime_config.set_pref("skills_disabled", sorted(disabled))
    return get_skill(slug)  # type: ignore[return-value]


def render(slug: str, symbol: str) -> dict:
    """把 Skill 正文按当前标的填充占位符（与「模板」同契约）。"""
    s = registry.get(slug)
    if not s:
        raise ValueError(f"技能 {slug} 不存在")
    market, _, code = symbol.partition(":")
    name = search.display_name(symbol) or code
    body = (
        s["body"]
        .replace("{SYMBOL}", symbol)
        .replace("{STOCK}", code or symbol)
        .replace("{MARKET}", _MARKET_LABEL.get(market, market))
        .replace("{NAME}", name)
    )
    return {"slug": slug, "name": s["name"], "symbol": symbol, "prompt": body}


def run_scorecard(payload: dict) -> dict:
    """跑卡点评分卡（确定性汇总主观打分）。"""
    return scorecard.score(payload)


def scorecard_template() -> dict:
    return scorecard.template()
