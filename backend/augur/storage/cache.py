"""Parquet 行情缓存：data/cache/ohlcv/<MARKET>/<CODE>/<interval>.parquet。

列式、可丢弃可重建。缓存优先 + 只追加尾巴的逻辑在 market/service.py。
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from ..config import get_settings


def _path(market: str, code: str, interval: str) -> Path:
    safe_code = code.replace("/", "_").replace(":", "_")
    return get_settings().cache_dir / "ohlcv" / market / safe_code / f"{interval}.parquet"


def load(market: str, code: str, interval: str) -> pd.DataFrame | None:
    p = _path(market, code, interval)
    if not p.exists():
        return None
    try:
        return pd.read_parquet(p)
    except Exception:
        # 损坏的半截文件（中途崩溃/磁盘满留下）→ 删掉，避免每次读都失败再回源（§11 尊重限流）
        p.unlink(missing_ok=True)
        return None


def save(market: str, code: str, interval: str, df: pd.DataFrame) -> None:
    """原子写：先写同目录临时文件再 os.replace（同卷 rename 原子），避免中途崩溃留半截文件。"""
    p = _path(market, code, interval)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".parquet.tmp")
    df.to_parquet(tmp)
    os.replace(tmp, p)
