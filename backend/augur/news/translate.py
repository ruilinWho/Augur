"""新闻英文/韩文标题 → 中文（cheap 角色批量翻译，缓存到 news_items.title_zh）。

CLAUDE.md §5/§6：复用 LLM 网关 cheap 角色（已在 .env 配置＝主人授权的出站目的地），
不引入 DeepL/Google 等新数据外发面。批量编号清单 in/out、落库缓存（每条只翻一次：
WHERE title_zh IS NULL）、失败静默降级（前端回退原文），绝不阻断摄取/日报。
lang='zh' 的条目跳过翻译、直接 title_zh=title。
"""

from __future__ import annotations

import json
import re

from ..config import get_settings
from ..llm import gateway
from ..storage import get_conn

_BATCH = 40  # 每批标题数（控对齐风险与 token）
_MAX_PER_RUN = 160  # 单次最多翻多少条（防首次对存量大表一次性打爆）


def _load_prompt() -> str:
    path = get_settings().resources_dir / "prompts" / "news_title_zh.md"
    return path.read_text(encoding="utf-8")


def _strip_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s)
    return s.strip()


def _passthrough_zh() -> int:
    """中文源无需翻译：title_zh = title。"""
    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE news_items SET title_zh = title "
            "WHERE title_zh IS NULL AND lang = 'zh'"
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def _select_pending(limit: int) -> list[tuple[int, str]]:
    conn = get_conn()
    try:
        # 与 feed 同序（按发布时间）：让用户最先看到的条目最先被翻译
        rows = conn.execute(
            "SELECT id, title FROM news_items WHERE title_zh IS NULL AND lang != 'zh' "
            "ORDER BY COALESCE(published_at, fetched_at) DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [(r["id"], r["title"]) for r in rows]
    finally:
        conn.close()


def _save(pairs: list[tuple[str, int]]) -> None:
    conn = get_conn()
    try:
        conn.executemany("UPDATE news_items SET title_zh = ? WHERE id = ?", pairs)
        conn.commit()
    finally:
        conn.close()


def _translate_batch(batch: list[tuple[int, str]]) -> list[tuple[str, int]]:
    """一批 → [(zh, id)]。编号 in/out 对齐；解析失败 → []（整批跳过，下轮重试）。"""
    numbered = "\n".join(f"{i + 1}. {title}" for i, (_id, title) in enumerate(batch))
    prompt = _load_prompt().replace("{{LINES}}", numbered)
    try:
        raw = gateway.complete(
            [{"role": "user", "content": prompt}],
            role="cheap",
            response_format={"type": "json_object"},
        )
        data = json.loads(_strip_fence(raw))
    except Exception:  # noqa: BLE001 — 网络/JSON 失败 → 整批跳过，下轮重试
        return []
    if not isinstance(data, dict):
        return []
    out: list[tuple[str, int]] = []
    for i, (_id, _title) in enumerate(batch):
        zh = data.get(str(i + 1))
        if isinstance(zh, str) and zh.strip():
            out.append((zh.strip()[:500], _id))
    return out


def translate_pending() -> int:
    """把待翻译标题批量翻成中文（lang!='zh' 且 title_zh 为空）。返回成功翻译条数。

    cheap 角色未配置 → 静默跳过返回 0（前端纯显示原文，不报错、不阻断）。
    """
    try:
        gateway.check_ready("cheap")
    except gateway.LLMNotConfigured:
        return 0
    _passthrough_zh()
    pending = _select_pending(_MAX_PER_RUN)
    done = 0
    for k in range(0, len(pending), _BATCH):
        pairs = _translate_batch(pending[k : k + _BATCH])
        if pairs:
            _save(pairs)
            done += len(pairs)
    return done
