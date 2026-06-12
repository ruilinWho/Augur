"""信源清单加载（resources/sources/feeds.yaml + 私有运行时 RSS）。

版本化的输入（AGENTS.md §3：亲手编写 → resources/）。容忍缺失/残缺条目。
带 token 的私有 RSS URL 不能写进 `resources/`，通过 `data/config.local.json` 注入。
"""

from __future__ import annotations

from functools import lru_cache

import yaml

from .. import runtime_config
from ..config import get_settings

BLOG_RSS_SOURCE_ID = "wechat_blogs"
BLOG_RSS_SECRET = "WECHAT_BLOG_RSS_URL"
BLOG_SOURCE_PREFIX = "博客·"
BLOG_SOURCE_NAME = f"{BLOG_SOURCE_PREFIX}微信公众号"
BLOG_CATEGORY = "blog"


def _private_blog_feeds() -> list[dict]:
    """运行时配置的私有微信公众号 RSS。URL 往往带 token，只能来自 gitignored 配置。"""
    url = runtime_config.get_secret(BLOG_RSS_SECRET).strip()
    if not url:
        return []
    return [
        {
            "name": BLOG_SOURCE_NAME,
            "url": url,
            "lang": "zh",
            "category": BLOG_CATEGORY,
        }
    ]


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
    out.extend(_private_blog_feeds())
    return out
