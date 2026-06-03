"""财联社 CLS——中文科技实时源（非官方 API；CLAUDE.md §1「知」/ ADR-0007）。

取**科创电报**（depth/assembled/1111，最贴近主人的前沿科技关注）。该 API 需签名：
`sign = MD5(SHA1(sorted_querystring))`，参数含 `appName=CailianpressWeb`。
⚠️ 坑（写进注释，未来会踩）：旧 `nodeapi/telegraphList` 路径 2026 已死；`sv` 与路径会
不定期轮换，置于常量便于更新。**网络/解析/反爬失败一律抛异常，由上层 ingest 捕获并记
source_health 失败**（与 fetch_feed 一致）——errno 反爬挑战也抛，避免被误记为「成功 0 条」
掩盖签名失效（§3 暴露不确定性）。归一化为 news_items 同形条目，复用 classify + 噪音过滤；
中文无需翻译。
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from urllib.parse import urlencode

import httpx

from . import classify
from . import filter as noise_filter

_UA = "Mozilla/5.0 (Augur/0.1; local research tool)"
_TIMEOUT = 12.0
_MAX = 30
# 科创电报 lane（id 1111）；params 的 sv 会轮换，挂了就更新这里
_TECH_URL = "https://www.cls.cn/v3/depth/home/assembled/1111"
_BASE = {"appName": "CailianpressWeb", "os": "web", "sv": "7.7.5"}
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _sign(params: dict[str, str]) -> tuple[str, str]:
    qs = urlencode(sorted(params.items()))
    sg = hashlib.md5(hashlib.sha1(qs.encode()).hexdigest().encode()).hexdigest()
    return qs, sg


def _clean(s: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub("", s or "")).strip()[:400]


def fetch_cls(cutoff: datetime | None = None) -> list[dict]:
    """财联社科创电报 → 归一化条目。网络/解析失败抛异常，由上层捕获。"""
    qs, sg = _sign(_BASE)
    url = f"{_TECH_URL}?{qs}&sign={sg}"
    headers = {"User-Agent": _UA, "Referer": "https://www.cls.cn/"}
    with httpx.Client(timeout=_TIMEOUT, headers=headers, follow_redirects=True) as c:
        r = c.get(url)
        r.raise_for_status()
    data = r.json()
    if data.get(
        "errno"
    ):  # 反爬挑战 / 签名失效 → 抛，让 source_health 记为失败（而非「成功 0 条」）
        raise RuntimeError(f"cls errno={data.get('errno')}（签名失效/反爬，检查 sv/path）")
    rows = (data.get("data") or {}).get("depth_list") or []
    items: list[dict] = []
    for e in rows[:_MAX]:
        title = _clean(str(e.get("title") or e.get("brief") or ""))
        cid = e.get("id")
        if not title or not cid:
            continue
        if noise_filter.is_noise(title):
            continue
        ct = e.get("ctime")
        dt = None
        if ct:
            try:
                dt = datetime.fromtimestamp(int(ct), tz=UTC)
            except (ValueError, OSError, OverflowError):
                dt = None
        if cutoff is not None and dt is not None and dt < cutoff:
            continue
        summary = _clean(str(e.get("brief") or ""))
        theme, topics = classify.classify_rule(title, summary, "tech")
        items.append(
            {
                "source": "财联社",
                "title": title[:500],
                "url": f"https://www.cls.cn/detail/{cid}",
                "summary": summary,
                "lang": "zh",
                "category": "tech",
                "published_at": dt.isoformat() if dt else None,
                "theme": theme,
                "topics": json.dumps(topics, ensure_ascii=False),
                "classified_by": "rule",
            }
        )
    return items
