"""按市场选适配器（AGENTS.md §7）。韩股 → pykrx；其余 → FDR。"""

from __future__ import annotations

from .base import MarketAdapter
from .fdr_adapter import FdrAdapter
from .pykrx_adapter import PykrxAdapter

_fdr = FdrAdapter()
_pykrx = PykrxAdapter()


def get_adapter(market: str) -> MarketAdapter:
    if market == "KR":
        return _pykrx
    return _fdr  # US / HK / CN
