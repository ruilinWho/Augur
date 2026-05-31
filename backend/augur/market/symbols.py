"""归一化符号 MARKET:CODE（CLAUDE.md §7）。

内部一律用 `US:AAPL`、`HK:00700`、`CN:600519`、`KR:005930`。
各适配器负责把 Symbol 翻译成数据源的原生格式。
"""

from __future__ import annotations

from dataclasses import dataclass

MARKETS = ("US", "HK", "CN", "KR")


@dataclass(frozen=True)
class Symbol:
    market: str  # US / HK / CN / KR
    code: str  # 市场内代码，如 AAPL / 00700 / 600519 / 005930

    @property
    def canonical(self) -> str:
        return f"{self.market}:{self.code}"


def parse_symbol(s: str) -> Symbol:
    if ":" not in s:
        raise ValueError(f"符号须为 MARKET:CODE 形式，收到 {s!r}")
    market, _, code = s.partition(":")
    market = market.strip().upper()
    code = code.strip()
    if market not in MARKETS:
        raise ValueError(f"未知市场 {market!r}，应为 {MARKETS} 之一")
    if not code:
        raise ValueError(f"代码不能为空：{s!r}")
    return Symbol(market=market, code=code)
