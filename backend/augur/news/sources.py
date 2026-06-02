"""信源清单加载（resources/sources/feeds.yaml）。

版本化的输入（CLAUDE.md §3：亲手编写 → resources/）。容忍缺失/残缺条目。
"""

from __future__ import annotations

from functools import lru_cache

import yaml

from ..config import get_settings


@lru_cache
def load_feeds() -> list[dict]:
    """读取并归一化信源列表；文件缺失/为空 → []。"""
    path = get_settings().resources_dir / "sources" / "feeds.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[dict] = []
    for f in data.get("feeds", []) or []:
        url = str(f.get("url", "")).strip()
        if not url:
            continue
        out.append(
            {
                "name": str(f.get("name") or url).strip(),
                "url": url,
                "lang": str(f.get("lang", "")).strip(),
                "category": str(f.get("category", "")).strip(),
            }
        )
    return out
