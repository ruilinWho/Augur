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
    category     TEXT    NOT NULL DEFAULT '',        -- 信源粗类（也作 theme 分类回退输入）
    published_at TEXT,                               -- ISO8601（可空：部分源无时间）
    fetched_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    theme        TEXT    NOT NULL DEFAULT '',        -- 主题主类（classify，见 classify.py）
    topics       TEXT    NOT NULL DEFAULT '[]',       -- 细标签 JSON 数组（多值）
    classified_by TEXT   NOT NULL DEFAULT '',         -- ''=未分类 / rule / llm
    title_zh     TEXT,                                -- 中文标题（cheap 翻译缓存；NULL=未翻）
    relevance    INTEGER NOT NULL DEFAULT 0,  -- 0未判/1保留/2丢弃 见 relevance.py
    linked       INTEGER NOT NULL DEFAULT 0,  -- 0未挂钩/1已挂钩 ticker 见 linker.py
    lane         TEXT    NOT NULL DEFAULT 'feed'  -- feed=RSS聚合流 / ticker=自选股定向抓取
);

-- 新闻↔标的挂钩（每条新闻确定性接地到 MARKET:CODE）——三支柱融合地基（linker.py）
CREATE TABLE IF NOT EXISTS news_item_symbols (
    news_id    INTEGER NOT NULL,
    symbol     TEXT    NOT NULL,                  -- MARKET:CODE
    name       TEXT    NOT NULL DEFAULT '',       -- 展示名（快照）
    confidence TEXT    NOT NULL DEFAULT 'med',    -- high/med
    matched_by TEXT    NOT NULL DEFAULT '',       -- 命中方式（term/code/targeted）
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (news_id, symbol)
);

-- 信源健康度（每次抓取的成功/失败/条数/最近成功时间）——纯统计，无 LLM
CREATE TABLE IF NOT EXISTS source_health (
    source       TEXT    PRIMARY KEY,
    ok_count     INTEGER NOT NULL DEFAULT 0,
    fail_count   INTEGER NOT NULL DEFAULT 0,
    last_count   INTEGER NOT NULL DEFAULT 0,      -- 最近一次抓到条数
    last_ok_at   TEXT,
    last_fail_at TEXT,
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
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

-- 今日投资机会（M3）：LLM 从当日新闻抽取机会 + 确定性接地到 MARKET:CODE，一天一批（重生成覆盖）
CREATE TABLE IF NOT EXISTS news_opportunities (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date  TEXT    NOT NULL,                  -- 'YYYY-MM-DD'，与 news_reports 对齐
    rank         INTEGER NOT NULL DEFAULT 0,        -- 当日内排序（confidence 高→低）
    title        TEXT    NOT NULL,
    thesis       TEXT    NOT NULL DEFAULT '',
    theme        TEXT    NOT NULL DEFAULT '',
    confidence   TEXT    NOT NULL DEFAULT 'low',    -- low/med/high
    caveats      TEXT    NOT NULL DEFAULT '',
    related      TEXT    NOT NULL DEFAULT '[]',     -- JSON：[{symbol,name,market,resolved,...}]
    evidence     TEXT    NOT NULL DEFAULT '[]',     -- JSON：[{news_id,title,source,url}]
    model        TEXT    NOT NULL DEFAULT '',
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_opp_date ON news_opportunities(report_date, rank);

-- 新闻「要点」：LLM 去重聚类 + 按投资重要性排序（一天一份/主题，重生成覆盖）
CREATE TABLE IF NOT EXISTS news_clusters (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date  TEXT    NOT NULL,                  -- 'YYYY-MM-DD'
    theme        TEXT    NOT NULL DEFAULT '',       -- ''=全部，否则某主题
    body         TEXT    NOT NULL DEFAULT '[]',     -- JSON：[{headline,importance,why,members[]}]
    model        TEXT    NOT NULL DEFAULT '',
    item_count   INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(report_date, theme)
);

-- 每股专属信源画像（M3「知·个股」）：LLM（最好联网）调研出某股该看哪些源 → 你策展 mark。
-- 每只股一套、各不相同（官网/IR/官方X/大V/Reddit/雪球/财经站）。enabled 由主人拍板。
CREATE TABLE IF NOT EXISTS stock_sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT    NOT NULL,                  -- MARKET:CODE
    kind        TEXT    NOT NULL,                  -- official/ir/official_x/influencer_x/reddit/...
    name        TEXT    NOT NULL,
    ref         TEXT    NOT NULL DEFAULT '',       -- URL / @handle / r/sub
    note        TEXT    NOT NULL DEFAULT '',
    enabled     INTEGER NOT NULL DEFAULT 0,        -- 0待确认/1已启用（主人拍板）
    verified    INTEGER NOT NULL DEFAULT 0,        -- 0未验证/1已验证（X句柄/子版/URL 探活）
    added_by    TEXT    NOT NULL DEFAULT 'llm',    -- llm/manual
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(symbol, kind, ref)
);
CREATE INDEX IF NOT EXISTS idx_stock_sources_symbol ON stock_sources(symbol);

-- 标的叙事时间线（M3「知·个股」）：LLM 把某股定向抓取的新闻融成「当前主线 + 时间线」，
-- 一股一份（重生成覆盖）。区别于 research_reports（深度研究）——这是轻量、增量的「在发生什么」。
CREATE TABLE IF NOT EXISTS stock_narratives (
    symbol      TEXT    PRIMARY KEY,            -- MARKET:CODE
    name        TEXT    NOT NULL DEFAULT '',
    summary     TEXT    NOT NULL DEFAULT '',     -- 当前主线（一段中文综述）
    timeline    TEXT    NOT NULL DEFAULT '[]',   -- JSON：[{date,title,importance,refs[]}]
    model       TEXT    NOT NULL DEFAULT '',
    item_count  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- 单股深度研究报告（M2「研」）：LLM 综合行情/基本面/财务/新闻/申报 → 带引用的报告，一股一份覆盖
CREATE TABLE IF NOT EXISTS research_reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT    NOT NULL UNIQUE,            -- MARKET:CODE（一股一份，重生成覆盖）
    name        TEXT    NOT NULL DEFAULT '',
    body        TEXT    NOT NULL DEFAULT '',
    sources     TEXT    NOT NULL DEFAULT '[]',      -- JSON：引用来源 [{n,title,source,url}]
    model       TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
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


# 幂等迁移：给**已存在**的表补列（CREATE TABLE IF NOT EXISTS 不会改已建的表）。
# 主人机器上 augur.db 已有数据，故新列必须靠 PRAGMA 探测 + ALTER 补，而非只改 SCHEMA 字符串。
# 新增列时在此追加一行 (表, 列, 列定义)；与 SCHEMA 里的定义保持一致。
_MIGRATIONS: list[tuple[str, str, str]] = [
    ("news_items", "theme", "TEXT NOT NULL DEFAULT ''"),
    ("news_items", "topics", "TEXT NOT NULL DEFAULT '[]'"),
    ("news_items", "classified_by", "TEXT NOT NULL DEFAULT ''"),
    ("news_items", "title_zh", "TEXT"),
    ("news_items", "relevance", "INTEGER NOT NULL DEFAULT 0"),
    ("news_items", "linked", "INTEGER NOT NULL DEFAULT 0"),
    ("news_items", "lane", "TEXT NOT NULL DEFAULT 'feed'"),
]


def _migrate(conn: sqlite3.Connection) -> None:
    for table, col, ddl in _MIGRATIONS:
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    # 新列上的索引须在补列之后建（不能放进 SCHEMA：已存在的表 executescript 时还没这列）
    conn.execute("CREATE INDEX IF NOT EXISTS idx_news_theme ON news_items(theme)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_news_lane ON news_items(lane)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_nis_symbol ON news_item_symbols(symbol)")
    conn.commit()


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate(conn)
    finally:
        conn.close()
