"""news 域纯逻辑：摄取触发、条目查询、趋势日报生成（LLM summarize 角色）。

I/O（网络在 ingest、磁盘在 storage、LLM 在 gateway）挡在外层，便于测试（CLAUDE.md §5）。
日报口径：只基于当日抓到的标题蒸馏，暴露不确定性、标注信源（§11）。一天一份，重生成覆盖。
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from zoneinfo import ZoneInfo

from ..config import get_settings
from ..llm import gateway
from ..storage import get_conn
from . import ingest

_DIGEST_INPUT_MAX = 100  # 喂给 LLM 的标题条数上限（控 token）


def _today() -> str:
    return datetime.now(ZoneInfo(get_settings().tz)).strftime("%Y-%m-%d")


def refresh() -> dict:
    """抓取所有信源并落库。"""
    return ingest.ingest_all()


def recent_items(limit: int = 60, category: str | None = None) -> list[dict]:
    """最近条目（按发布时间倒序，缺发布时间用抓取时间兜底）。"""
    conn = get_conn()
    try:
        sql = "SELECT * FROM news_items"
        args: list = []
        if category:
            sql += " WHERE category = ?"
            args.append(category)
        sql += " ORDER BY COALESCE(published_at, fetched_at) DESC LIMIT ?"
        args.append(limit)
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
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
    return "\n".join(f"- [{it['source']}] {it['title']}" for it in items)


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
