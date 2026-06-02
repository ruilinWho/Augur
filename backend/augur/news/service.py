"""news 域纯逻辑：摄取触发、条目查询、趋势日报生成（LLM summarize 角色）。

I/O（网络在 ingest、磁盘在 storage、LLM 在 gateway）挡在外层，便于测试（CLAUDE.md §5）。
日报口径：只基于当日抓到的标题蒸馏，暴露不确定性、标注信源（§11）。一天一份，重生成覆盖。
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from zoneinfo import ZoneInfo

from ..config import get_settings
from ..llm import gateway
from ..storage import get_conn
from . import ingest

_DIGEST_INPUT_MAX = 100  # 喂给 LLM 的标题条数上限（控 token）

# 主题展示名与排序（前沿方向在前；与 classify.VALID_THEMES / 前端一致）
THEME_LABEL = {
    "ai": "大模型 / AI",
    "chips": "芯片 / 半导体",
    "robotics": "机器人",
    "space": "航天",
    "tech": "科技",
    "markets": "行情 / 宏观",
    "crypto": "加密",
    "world": "国际",
    "other": "其他",
}
THEME_ORDER = ["ai", "chips", "robotics", "space", "tech", "markets", "crypto", "world", "other"]


def _item_out(row) -> dict:
    """row → dict，并把 topics(JSON 字符串) 反序列化为列表。"""
    d = dict(row)
    try:
        d["topics"] = json.loads(d.get("topics") or "[]")
    except (json.JSONDecodeError, TypeError):
        d["topics"] = []
    return d


def _today() -> str:
    return datetime.now(ZoneInfo(get_settings().tz)).strftime("%Y-%m-%d")


def refresh() -> dict:
    """抓取所有信源并落库。"""
    return ingest.ingest_all()


def recent_items(limit: int = 60, theme: str | None = None) -> list[dict]:
    """最近条目（按发布时间倒序，缺发布时间用抓取时间兜底）。可按 theme 过滤。"""
    conn = get_conn()
    try:
        sql = "SELECT * FROM news_items"
        args: list = []
        if theme:
            sql += " WHERE theme = ?"
            args.append(theme)
        sql += " ORDER BY COALESCE(published_at, fetched_at) DESC LIMIT ?"
        args.append(limit)
        return [_item_out(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def get_report(report_date: str | None = None) -> dict | None:
    """取某日（默认最新一份）日报全文。"""
    conn = get_conn()
    try:
        if report_date:
            row = conn.execute(
                "SELECT * FROM news_reports WHERE report_date = ?", (report_date,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM news_reports ORDER BY report_date DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_reports(limit: int = 30) -> list[dict]:
    """日报列表（含 160 字预览，不含全文）。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT report_date, item_count, model, created_at, "
            "substr(body, 1, 160) AS preview "
            "FROM news_reports ORDER BY report_date DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _load_prompt(name: str) -> str:
    path = get_settings().resources_dir / "prompts" / f"{name}.md"
    return path.read_text(encoding="utf-8")


def _headlines_block(items: list[dict]) -> str:
    """按主题分组喂给 LLM（让日报在既定主题骨架内蒸馏，更稳、更省 token）。"""
    by_theme: dict[str, list[dict]] = {}
    for it in items:
        by_theme.setdefault(it.get("theme") or "other", []).append(it)
    lines: list[str] = []
    for th in THEME_ORDER:
        group = by_theme.get(th)
        if not group:
            continue
        lines.append(f"\n## {THEME_LABEL.get(th, th)}")
        lines.extend(f"- [{it['source']}] {it['title']}" for it in group)
    return "\n".join(lines).strip()


def _save_report(report_date: str, body: str, model: str, item_count: int) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO news_reports (report_date, body, model, item_count) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(report_date) DO UPDATE SET "
            "body = excluded.body, model = excluded.model, "
            "item_count = excluded.item_count, created_at = datetime('now')",
            (report_date, body, model, item_count),
        )
        conn.commit()
    finally:
        conn.close()


def generate_report_stream(
    report_date: str | None = None, role: str = "summarize"
) -> Iterator[str]:
    """生成当日趋势日报：流式产出文本增量；完成后落库（覆盖当天）。

    无新闻条目 → ValueError（前端提示先刷新）。
    """
    rd = report_date or _today()
    items = recent_items(limit=_DIGEST_INPUT_MAX)
    if not items:
        raise ValueError("暂无新闻条目，请先刷新（POST /news/refresh）")
    prompt = (
        _load_prompt("news_digest")
        .replace("{{DATE}}", rd)
        .replace("{{HEADLINES}}", _headlines_block(items))
    )
    _, model = gateway.resolve_role(role)
    buf: list[str] = []
    for delta in gateway.stream_chat([{"role": "user", "content": prompt}], role):
        buf.append(delta)
        yield delta
    body = "".join(buf).strip()
    if body:
        _save_report(rd, body, model, len(items))
