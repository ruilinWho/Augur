"""新闻投资相关性过滤（cheap 角色批量判，落 news_items.relevance）。

主人反馈「知」里仍有与投资无关的新闻；规则法 `filter.py` 滤不掉的更隐蔽的，交给**便宜小模型**
判（CLAUDE.md §6，复用 cheap 角色＝主人授权的出站目的地，不引入新外发面）。批量编号清单 in/out、
落库（每条只判一次：WHERE relevance=0）、失败静默降级（保留=不丢、下轮重试，绝不阻断摄取）。
relevance：0 未判 / 1 投资相关保留 / 2 无关丢弃。判据见 resources/prompts/news_relevance.md。
"""

from __future__ import annotations

import json
import re

from ..config import get_settings
from ..llm import gateway
from ..storage import get_conn

_BATCH = 40  # 每批条数（控对齐风险与 token）
_MAX_PER_RUN = 400  # 单次最多判多少条（"不心疼 token"；从严 prompt 后多判些）
_KEEP = {"true", "keep", "yes", "1", "相关", "保留"}
_DROP = {"false", "drop", "no", "0", "无关", "丢弃"}


def _load_prompt() -> str:
    return (get_settings().resources_dir / "prompts" / "news_relevance.md").read_text(
        encoding="utf-8"
    )


def _strip_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s)
    return s.strip()


def _select_pending(limit: int) -> list[tuple[int, str, str, str]]:
    conn = get_conn()
    try:
        # ASC（最老未判优先）：单轮插入 >_MAX_PER_RUN 条时，DESC 会让最老一批永远排在末尾
        # 永不被选中 → 因「未判=保留」直接泄入信息流，从严过滤对存量尾部失效。最老的即将滑出
        # 可见窗口反而更该先判，几轮 refresh 自然清空积压。
        rows = conn.execute(
            "SELECT id, COALESCE(NULLIF(title_zh, ''), title) AS t, source, theme "
            "FROM news_items WHERE relevance = 0 AND lane = 'feed' "
            "ORDER BY COALESCE(published_at, fetched_at) ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [(r["id"], r["t"], r["source"], r["theme"]) for r in rows]
    finally:
        conn.close()


def _save(pairs: list[tuple[int, int]]) -> None:
    conn = get_conn()
    try:
        conn.executemany("UPDATE news_items SET relevance = ? WHERE id = ?", pairs)
        conn.commit()
    finally:
        conn.close()


def _coerce(v) -> int | None:
    """LLM 值 → 1 保留 / 2 丢弃 / None 不确定（保持未判，下轮重试）。"""
    if v is True:
        return 1
    if v is False:
        return 2
    if isinstance(v, (int, float)):
        return 1 if v else 2
    if isinstance(v, str):
        s = v.strip().lower()
        if s in _KEEP:
            return 1
        if s in _DROP:
            return 2
    return None


def _judge_batch(batch: list[tuple[int, str, str, str]]) -> list[tuple[int, int]]:
    """一批 → [(relevance, id)]。编号 in/out 对齐；解析失败 → []（整批跳过，下轮重试）。"""
    numbered = "\n".join(
        f"{i + 1}. [{src}/{theme or '?'}] {t}" for i, (_id, t, src, theme) in enumerate(batch)
    )
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
    out: list[tuple[int, int]] = []
    for i, (_id, _t, _s, _th) in enumerate(batch):
        rel = _coerce(data.get(str(i + 1)))
        if rel is not None:
            out.append((rel, _id))
    return out


def judge_pending() -> dict:
    """批量判定未判条目的投资相关性。返回 {judged, dropped}。cheap 未配置 → 静默跳过。"""
    try:
        gateway.check_ready("cheap")
    except gateway.LLMNotConfigured:
        return {"judged": 0, "dropped": 0}
    pending = _select_pending(_MAX_PER_RUN)
    judged = dropped = 0
    for k in range(0, len(pending), _BATCH):
        pairs = _judge_batch(pending[k : k + _BATCH])
        if pairs:
            _save(pairs)
            judged += len(pairs)
            dropped += sum(1 for rel, _ in pairs if rel == 2)
    return {"judged": judged, "dropped": dropped}
