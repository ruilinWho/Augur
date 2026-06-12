"""新闻主题分类（规则优先，AGENTS.md §1「知」/ M3）。

规则法零成本、可解释、ingest 同步完成：对「标题 + 摘要」匹配关键词 → topics（多标签），
theme 取命中里优先级最高者；都没命中则回退信源 category，再不行 other。关键词在
resources/sources/themes.yaml（版本化、作者可编辑）。把泛 tech/markets 源里的前沿内容
正确归到 ai/chips/robotics/space。

⚠️ ASCII 关键词用**词边界**匹配（\\b），否则 "AI" 会子串命中 "again/Thailand/email"、
"Arm" 命中 "harm/farm" 等——这是踩过的坑。CJK 关键词（如 芯片）无词边界、用子串即可。
LLM 兜底分类留待后续，不在此 store-time 纯逻辑路径。
"""

from __future__ import annotations

import json
import re
from functools import lru_cache

import yaml

from ..config import get_settings
from ..storage import get_conn

# 兜底回退用的合法主题集合（与 db.py 注释、service.THEME_ORDER、前端保持一致）
VALID_THEMES = {
    "ai",
    "chips",
    "robotics",
    "space",
    "tech",
    "markets",
    "macro",
    "crypto",
    "world",
    "other",
}


@lru_cache
def _theme_rules() -> list[tuple[str, re.Pattern | None, list[str]]]:
    """[(theme, ASCII 词边界正则|None, [CJK 子串…]), …]，按 yaml 顺序＝优先级。缺文件→[]。"""
    path = get_settings().resources_dir / "sources" / "themes.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[tuple[str, re.Pattern | None, list[str]]] = []
    for theme, kws in (data.get("themes") or {}).items():
        words = [str(k) for k in (kws or [])]
        ascii_kw = [k.lower() for k in words if k.isascii()]
        cjk_kw = [k.lower() for k in words if not k.isascii()]
        pat = None
        if ascii_kw:
            alt = "|".join(re.escape(k) for k in ascii_kw)
            pat = re.compile(rf"\b(?:{alt})\b")  # text 已小写，无需 IGNORECASE
        out.append((str(theme), pat, cjk_kw))
    return out


def classify_rule(title: str, summary: str = "", category: str = "") -> tuple[str, list[str]]:
    """→ (theme, topics)。纯函数、无 I/O。topics 为所有命中主题（按优先级），theme 为首选。"""
    text = f"{title} {summary}".lower()
    hits = [
        theme
        for theme, pat, cjk in _theme_rules()
        if (pat and pat.search(text)) or any(k in text for k in cjk)
    ]
    if hits:
        return hits[0], hits
    fallback = category if category in VALID_THEMES else "other"
    return fallback, ([fallback] if fallback != "other" else [])


def backfill_rules() -> int:
    """给历史未分类（classified_by='')的条目补规则分类。幂等、零成本（只扫未分类行）。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, title, summary, category FROM news_items WHERE classified_by = ''"
        ).fetchall()
        updates = []
        for r in rows:
            theme, topics = classify_rule(r["title"], r["summary"] or "", r["category"] or "")
            updates.append((theme, json.dumps(topics, ensure_ascii=False), "rule", r["id"]))
        if updates:
            conn.executemany(
                "UPDATE news_items SET theme = ?, topics = ?, classified_by = ? WHERE id = ?",
                updates,
            )
            conn.commit()
        return len(updates)
    finally:
        conn.close()
