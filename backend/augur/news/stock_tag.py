"""新闻自动标股（不限自选）——作者：「看到新闻去看相应的股票，即使不在自选，才叫发现机会」。

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
from . import _batch, grounding

_BATCH = 20
_MAX_ROUNDS = 80  # 单次最多几批（×_BATCH=1600 条上界；作者"不心疼 token"，循环到清空积压）
_MAX_FAILS = 5  # 连续几批标不出就停（LLM 多半挂了；少于此则跳过毒批继续清队列）
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


def _select_pending(limit: int, offset: int = 0) -> list[tuple[int, str]]:
    conn = get_conn()
    try:
        # offset：跳过「队首一直标不出的毒批」，否则它会永久堵住后面更老的相关条目。
        rows = conn.execute(
            "SELECT id, COALESCE(NULLIF(title_zh, ''), title) AS t FROM news_items "
            "WHERE tagged = 0 AND lane = 'feed' AND relevance = 1 "
            "ORDER BY COALESCE(published_at, fetched_at) ASC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [(r["id"], r["t"]) for r in rows]
    finally:
        conn.close()


def _tag_batch(batch: list[tuple[int, str]]) -> tuple[int, int]:
    """一批 → (标记条数, 接地挂钩对数)。

    解析失败 → (0, 0)（不标 tagged，下轮重试）；解析成功即把整批标 tagged=1（即便某条 0 公司），
    标记条数=len(batch)。供 tag_pending 据「标记条数」判停（0=顽固/失败，停；>0=继续清积压）。
    """
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
        return (0, 0)
    if not isinstance(data, dict):
        return (0, 0)
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
        return (len(batch), pairs)
    finally:
        conn.close()


def tag_pending() -> dict:
    """批量给相关新闻标股（接地到真实代码），**循环到清空**（作者：彻底标，别漏，新闻卡都能发现机会）。

    每轮取一批最老未标的；标出即落 tagged=1（下轮自然跳过）。整批标不出（顽固/网络失败）→ 停，
    避免空转。cheap 未配置 → 静默跳过。返回 {tagged, pairs}。
    """
    try:
        gateway.check_ready("cheap")
    except gateway.LLMNotConfigured:
        return {"tagged": 0, "pairs": 0}
    tagged = pairs = 0
    offset = fails = 0
    window = _BATCH * _batch.WORKERS  # 每轮取这么多、切成多批**并发**标（作者：尽量并行）
    for _ in range(_MAX_ROUNDS):
        items = _select_pending(window, offset)
        if not items:
            break
        results = _batch.map_batches(items, _BATCH, _tag_batch)
        marked = sum(m for m, _ in results)
        if marked == 0:
            # 整窗没标出（顽固条目或网络/JSON 失败）：跳过这窗继续标后面的，别让毒批堵死队列。
            fails += 1
            if fails >= _MAX_FAILS:
                break  # 连续多窗失败＝LLM 多半挂了 → 停，下次 refresh 再试
            offset += window
            continue
        tagged += marked
        pairs += sum(p for _, p in results)
        fails = 0
        offset = 0  # 成功 → 已标项离开 pending，回到队首
    return {"tagged": tagged, "pairs": pairs}
