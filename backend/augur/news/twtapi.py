"""twtapi（twtapi.com）适配器：拉 X/Twitter 官方账号近期推文，归一进「知」摄取。

主人选定 twtapi 作 X 桥（有免费试用 + 月付，免国际卡；见 ADR-0007 §5）。key 走
`runtime_config` 的 `TWTAPI_KEY`（gitignored，UI/.env 可配、注入 os.environ）；无 key → 返回 []。

两步（端点经实测，docs 为 SPA 仅给 base/鉴权）：
  ① `GET /api/v1/twitter/UserResultByScreenName?username=<handle>` → `data.user_results.rest_id`
  ② `GET /api/v1/twitter/UserTweets?user_id=<rest_id>&count=N` → Twitter GraphQL 原始时间线
解析时间线：递归取 `__typename=='Tweet'` 对象，按 `legacy.user_id_str==本人` 过滤（去掉转推/引用的
他人推文）、按 `rest_id` 去重；文本取 `note_tweet`（长推）或 `legacy.full_text`。失败一律降级返回 []
（暴露不确定性、不抛、单账号失败不连累其余）。归一为 news_items 同形，复用 classify + 噪音过滤；
英文标题由既有 translate 步翻中。账号清单见 resources/sources/x_accounts.yaml。
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import UTC, datetime, timedelta

import httpx
import yaml

from .. import runtime_config
from ..config import get_settings
from . import classify
from . import filter as noise_filter
from ._http import UA as _UA

_BASE = "https://api.twtapi.com/api/v1/twitter"
_TIMEOUT = 20.0
_PER_ACCOUNT = 12  # 每账号取近 N 条
_TCO_RE = re.compile(r"https?://t\.co/\w+")
_WS_RE = re.compile(r"\s+")

# screen_name → (rest_id, ts)；进程内缓存 user_id 解析（极少变），省一半调用
_UID_CACHE: dict[str, tuple[str, float]] = {}
_UID_TTL = 24 * 3600.0


def _key() -> str:
    return (os.environ.get("TWTAPI_KEY") or "").strip()


def _norm_accounts(raw: list) -> list[dict]:
    """归一账号列表：每项 {screen_name(去@), category}；丢弃残缺。"""
    out: list[dict] = []
    seen: set[str] = set()
    for a in raw or []:
        if not isinstance(a, dict):
            continue
        sn = str(a.get("screen_name", "")).strip().lstrip("@")
        if not sn or sn.lower() in seen:
            continue
        seen.add(sn.lower())
        cat = str(a.get("category", "tech")).strip() or "tech"
        out.append({"screen_name": sn, "category": cat})
    return out


def default_accounts() -> list[dict]:
    """内置默认账号清单（resources/sources/x_accounts.yaml）；缺失/残缺 → []。"""
    path = get_settings().resources_dir / "sources" / "x_accounts.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _norm_accounts(data.get("accounts") or [])


def accounts() -> list[dict]:
    """生效账号清单：主人在「设置」里配的优先，否则用 yaml 默认。"""
    cfg = runtime_config.get_source_config("twtapi", "accounts")
    return _norm_accounts(cfg) if cfg is not None else default_accounts()


def source_names() -> set[str]:
    """该适配器会产生的所有 source 名（供 ingest prune 豁免，否则不在 feeds.yaml 会被误删）。"""
    return {f"X·{a['screen_name']}" for a in accounts()}


def _get(client: httpx.Client, path: str, params: dict) -> dict:
    r = client.get(f"{_BASE}/{path}", params=params)
    r.raise_for_status()
    return r.json()


def _resolve_user_id(client: httpx.Client, screen_name: str) -> str | None:
    now = time.time()
    hit = _UID_CACHE.get(screen_name.lower())
    if hit and now - hit[1] < _UID_TTL:
        return hit[0]
    d = _get(client, "UserResultByScreenName", {"username": screen_name})
    rid = ((d.get("data") or {}).get("user_results") or {}).get("rest_id")
    if rid:
        _UID_CACHE[screen_name.lower()] = (str(rid), now)
        return str(rid)
    return None


def ping() -> int:
    """轻量探活：解析一个账号的 user_id（验证 key + 连通）。成功返回 1，失败抛异常。"""
    if not _key():
        raise RuntimeError("未配置 TWTAPI_KEY")
    accs = accounts()
    if not accs:
        raise RuntimeError("没有配置 X 账号")
    headers = {"X-API-Key": _key(), "User-Agent": _UA}
    with httpx.Client(timeout=_TIMEOUT, headers=headers, follow_redirects=True) as c:
        rid = _resolve_user_id(c, accs[0]["screen_name"])
    if not rid:
        raise RuntimeError("解析账号失败（key 可能无效）")
    return 1


def _walk_tweets(obj, out: list[dict], depth: int = 0) -> None:
    """递归收集 Twitter GraphQL 里的 Tweet 结果对象。带深度上限——第三方桥转发的结构不受控，
    异常深/自引用结构下默认递归深度可栈溢出（正常时间线远不及 40 层）。"""
    if depth > 40:
        return
    if isinstance(obj, dict):
        if obj.get("__typename") == "Tweet" and "rest_id" in obj:
            out.append(obj)
        for v in obj.values():
            _walk_tweets(v, out, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _walk_tweets(v, out, depth + 1)


def _tweet_text(t: dict) -> str:
    """取推文文本：优先 note_tweet（长推），否则 legacy.full_text；去 t.co 媒体链接、压空白。"""
    nt = ((t.get("note_tweet") or {}).get("note_tweet_results") or {}).get("result") or {}
    raw = nt.get("text") or (t.get("legacy") or {}).get("full_text") or ""
    return _WS_RE.sub(" ", _TCO_RE.sub("", raw)).strip()


def _parse_dt(s: str) -> datetime | None:
    try:  # "Wed May 20 19:06:41 +0000 2026"
        dt = datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y").astimezone(UTC)
    except (ValueError, TypeError):
        return None
    if dt > datetime.now(UTC) + timedelta(hours=1):  # 坏时钟/未来时间 → 当无时间，免置顶
        return None
    return dt


def _fetch_account(client: httpx.Client, acc: dict, cutoff: datetime | None) -> list[dict]:
    sn, cat = acc["screen_name"], acc["category"]
    uid = _resolve_user_id(client, sn)
    if not uid:
        return []
    d = _get(client, "UserTweets", {"user_id": uid, "count": _PER_ACCOUNT})
    raw: list[dict] = []
    _walk_tweets(d, raw)
    seen: set[str] = set()
    items: list[dict] = []
    for t in raw:
        rid = str(t.get("rest_id") or "")
        leg = t.get("legacy") or {}
        if not rid or rid in seen or str(leg.get("user_id_str") or "") != uid:
            continue  # 去重 + 只留本人推文（剔除转推/引用的他人推文）
        seen.add(rid)
        text = _tweet_text(t)
        if not text or noise_filter.is_noise(text):
            continue
        dt = _parse_dt(leg.get("created_at") or "")
        if cutoff is not None and dt is not None and dt < cutoff:
            continue
        lang = (leg.get("lang") or "").strip() or "en"
        theme, topics = classify.classify_rule(text, "", cat)
        items.append(
            {
                "source": f"X·{sn}",
                "title": text[:500],
                "url": f"https://x.com/{sn}/status/{rid}",
                "summary": "",
                "lang": lang if lang in ("en", "zh", "ko", "ja") else "en",
                "category": cat,
                "published_at": dt.isoformat() if dt else None,
                "theme": theme,
                "topics": json.dumps(topics, ensure_ascii=False),
                "classified_by": "rule",
            }
        )
    return items


def fetch_all(cutoff: datetime | None = None) -> list[dict]:
    """拉清单内全部 X 官方账号近期推文 → 归一化条目。无 key → []；单账号失败跳过、不抛。"""
    if not _key():
        return []
    accs = accounts()
    if not accs:
        return []
    headers = {"X-API-Key": _key(), "User-Agent": _UA}
    items: list[dict] = []
    with httpx.Client(timeout=_TIMEOUT, headers=headers, follow_redirects=True) as c:
        for acc in accs:
            try:
                items.extend(_fetch_account(c, acc, cutoff))
            except Exception:  # noqa: BLE001 — 单账号失败（限流/失效）不连累其余
                continue
    return items
