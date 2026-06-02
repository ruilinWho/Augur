"""SQLite：连接 + 建表。元数据（自选分区、用量等）的真相库。

运行时文件在被忽略的 data/db/augur.db。schema 见 CLAUDE.md §8 / architecture §5。
"""

from __future__ import annotations

import sqlite3

from ..config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS sections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    parent_id   INTEGER REFERENCES sections(id) ON DELETE CASCADE,  -- NULL = 一级板块
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS watchlist_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id  INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    symbol      TEXT    NOT NULL,                 -- 归一化 MARKET:CODE
    note        TEXT    NOT NULL DEFAULT '',
    sort_order  INTEGER NOT NULL DEFAULT 0,
    added_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(section_id, symbol)
);

CREATE TABLE IF NOT EXISTS llm_usage (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                TEXT NOT NULL DEFAULT (datetime('now')),
    role              TEXT,
    provider          TEXT,
    model             TEXT,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    cost_usd          REAL
);

-- 判断日记：对某标的在某日写下的决策笔记，供日后复盘（CLAUDE.md §1「研」的轻量前身）
CREATE TABLE IF NOT EXISTS journal_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT    NOT NULL,                  -- 归一化 MARKET:CODE
    entry_date  TEXT    NOT NULL,                  -- 'YYYY-MM-DD'：决策发生那天（可改）
    body        TEXT    NOT NULL DEFAULT '',       -- 笔记正文
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_journal_symbol ON journal_entries(symbol, entry_date DESC);

-- 新闻摄取（CLAUDE.md §1「知」/ M3）：从 RSS/API 拉来的条目，按 url 去重
CREATE TABLE IF NOT EXISTS news_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source       TEXT    NOT NULL,                  -- 信源名（feeds.yaml 的 name）
    title        TEXT    NOT NULL,
    url          TEXT    NOT NULL UNIQUE,           -- 去重键
    summary      TEXT    NOT NULL DEFAULT '',
    lang         TEXT    NOT NULL DEFAULT '',        -- en/zh/ko…
    category     TEXT    NOT NULL DEFAULT '',        -- markets/tech/world…
    published_at TEXT,                               -- ISO8601（可空：部分源无时间）
    fetched_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_news_published ON news_items(published_at DESC);

-- 趋势日报（M3）：LLM 把当日新闻蒸馏成一份日报，一天一份（重生成则覆盖）
CREATE TABLE IF NOT EXISTS news_reports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date  TEXT    NOT NULL UNIQUE,           -- 'YYYY-MM-DD'
    body         TEXT    NOT NULL DEFAULT '',
    model        TEXT    NOT NULL DEFAULT '',
    item_count   INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


def get_conn() -> sqlite3.Connection:
    """打开一个连接（启用外键、Row 工厂）。调用方负责关闭。"""
    settings = get_settings()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
