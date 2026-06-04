"""信源清单加载（resources/sources/feeds.yaml）。

版本化的输入（CLAUDE.md §3：亲手编写 → resources/）。容忍缺失/残缺条目。
"""

from __future__ import annotations

from functools import lru_cache

import yaml

from .. import runtime_config
from ..config import get_settings


@lru_cache
def load_feeds() -> list[dict]:
    """读取并归一化信源列表；文件缺失/为空 → []。"""
    path = get_settings().resources_dir / "sources" / "feeds.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[dict] = []
    bloomberg_channels = {
        str(x).strip().lower()
        for x in runtime_config.get_source_config("bloomberg", "channels", ["科技", "Markets"])
        if str(x).strip()
    }
    for f in data.get("feeds", []) or []:
        url = str(f.get("url", "")).strip()
        if not url:
            continue
        name = str(f.get("name") or url).strip()
        category = str(f.get("category", "")).strip()
        if name.startswith("Bloomberg"):
            hay = f"{name} {category}".lower()
            if bloomberg_channels and not any(ch.lower() in hay for ch in bloomberg_channels):
                continue
            name = "Bloomberg"
        if name.startswith("The Elec"):
            name = "The Elec"
        out.append(
            {
                "name": name,
                "url": url,
                "lang": str(f.get("lang", "")).strip(),
                "category": category,
            }
        )
    return out
