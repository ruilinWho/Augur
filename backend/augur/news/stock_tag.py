"""新闻自动标股（不限自选）——主人：「看到新闻去看相应的股票，即使不在自选，才叫发现机会」。

对**已判相关**(relevance=1)、未标股(tagged=0)的 feed 条目，批量让 cheap LLM 识别它主要涉及的
上市公司（名+市场+code 猜测），再经 `grounding` **确定性接地**到真实 MARKET:CODE（防编造：只认
本地目录∪东财的真实命中）。写入 news_item_symbols（matched_by='llm'）。

与 linker 分工：linker 确定性挂**自选股**（零幻觉）；stock_tag 补「**不在自选但相关**」的票，
让新闻卡的股票 chip 不再只显自选。失败静默降级、不阻断摄取。每条只标一次（tagged=1）。
"""

from __future__ import annotations

import json
import re

from ..config import get_settings
from ..llm import gateway
from ..storage import get_conn
from . import grounding

_BATCH = 20
_MAX_PER_RUN = 200  # 单次最多标多少条（控 token；"不心疼 token" 但仍给个上界）
_MAX_PER_ITEM = 3  # 一条新闻最多标几只（避免清单体新闻拉一长串）


def _load_prompt() -> str:
    return (get_settings().resources_dir / "prompts" / "news_stock_tag.md").read_text(
        encoding="utf-8"
    )


def _strip_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s)
    return s.strip()


def _select_pending(limit: int) -> list[tuple[int, str]]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, COALESCE(NULLIF(title_zh, ''), title) AS t FROM news_items "
            "WHERE tagged = 0 AND lane = 'feed' AND relevance = 1 "
            "ORDER BY COALESCE(published_at, fetched_at) ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [(r["id"], r["t"]) for r in rows]
    finally:
        conn.close()


def _tag_batch(batch: list[tuple[int, str]]) -> int:
    """一批 → 接地后的挂钩对数。解析失败 → 0（不标 tagged，下轮重试）；解析成功即标 tagged=1。"""
    numbered = "\n".join(f"{i + 1}. {t}" for i, (_id, t) in enumerate(batch))
    prompt = _load_prompt().replace("{{LINES}}", numbered)
    try:
        raw = gateway.complete(
            [{"role": "user", "content": prompt}],
            role="cheap",
            response_format={"type": "json_object"},
        )
        data = json.loads(_strip_fence(raw))
    except Exception:  # noqa: BLE001 — 网络/JSON 失败 → 整批跳过、下轮重试
        return 0
    if not isinstance(data, dict):
        return 0
    conn = get_conn()
    pairs = 0
    try:
        for i, (nid, _t) in enumerate(batch):
            companies = data.get(str(i + 1)) or []
            seen: set[str] = set()
            if isinstance(companies, list):
                for c in companies[:_MAX_PER_ITEM]:
                    if not isinstance(c, dict):
                        continue
                    sym, disp, resolved = grounding.resolve_company(
                        c.get("name", ""), c.get("market", ""), c.get("code_guess", "")
                    )
                    if resolved and sym and sym not in seen:
                        seen.add(sym)
                        conn.execute(
                            "INSERT OR IGNORE INTO news_item_symbols "
                            "(news_id, symbol, name, confidence, matched_by) "
                            "VALUES (?, ?, ?, 'med', 'llm')",
                            (nid, sym, disp),
                        )
                        pairs += 1
            conn.execute("UPDATE news_items SET tagged = 1 WHERE id = ?", (nid,))
        conn.commit()
        return pairs
    finally:
        conn.close()


def tag_pending() -> dict:
    """批量给相关新闻标股（接地到真实代码）。cheap 未配置 → 静默跳过。返回 {tagged, pairs}。"""
    try:
        gateway.check_ready("cheap")
    except gateway.LLMNotConfigured:
        return {"tagged": 0, "pairs": 0}
    pending = _select_pending(_MAX_PER_RUN)
    pairs = 0
    for k in range(0, len(pending), _BATCH):
        pairs += _tag_batch(pending[k : k + _BATCH])
    return {"tagged": len(pending), "pairs": pairs}
