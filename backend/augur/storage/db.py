"""SQLite：连接 + 建表。元数据（自选分区、用量等）的真相库。

运行时文件在被忽略的 data/db/augur.db。schema 见 AGENTS.md §8 / architecture §3。
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

-- 判断日记：对某标的在某日写下的决策笔记，供日后复盘（AGENTS.md §1「研」的轻量前身）
CREATE TABLE IF NOT EXISTS journal_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT    NOT NULL,                  -- 归一化 MARKET:CODE
    entry_date  TEXT    NOT NULL,                  -- 'YYYY-MM-DD'：决策发生那天（可改）
    body        TEXT    NOT NULL DEFAULT '',       -- 笔记正文
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_journal_symbol ON journal_entries(symbol, entry_date DESC);

-- 新闻摄取（AGENTS.md §1「知」/ M3）：从 RSS/API 拉来的条目，按 url 去重
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
    linked       INTEGER NOT NULL DEFAULT 0,  -- 0未挂钩/1已挂钩自选股 ticker 见 linker.py
    tagged       INTEGER NOT NULL DEFAULT 0,  -- 0未判/1已 LLM 标股（不限自选）见 stock_tag.py
    lane         TEXT    NOT NULL DEFAULT 'feed'  -- feed=RSS聚合流 / ticker=自选股定向抓取
);

-- 新闻↔标的挂钩（每条新闻确定性接地到 MARKET:CODE）——看/研/知融合地基（linker.py）
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
    last_error   TEXT    NOT NULL DEFAULT '',     -- 最近一次失败的可读原因
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
-- 每只股一套、各不相同（官网/IR/官方X/大V/Reddit/财经站）。enabled 由作者拍板。
CREATE TABLE IF NOT EXISTS stock_sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT    NOT NULL,                  -- MARKET:CODE
    kind        TEXT    NOT NULL,                  -- official/ir/official_x/influencer_x/reddit/...
    name        TEXT    NOT NULL,
    ref         TEXT    NOT NULL DEFAULT '',       -- URL / @handle / r/sub
    note        TEXT    NOT NULL DEFAULT '',
    enabled     INTEGER NOT NULL DEFAULT 0,        -- 0待确认/1已启用（作者拍板）
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

-- 导入研报（M2「研」）：作者粘贴他人写的研报（markdown），一股可多份、可拖排序、各带我的评论。
CREATE TABLE IF NOT EXISTS imported_reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT    NOT NULL,                  -- MARKET:CODE
    title       TEXT    NOT NULL DEFAULT '',
    body        TEXT    NOT NULL DEFAULT '',        -- markdown 正文
    comment     TEXT    NOT NULL DEFAULT '',        -- 我的评论
    engine      TEXT    NOT NULL DEFAULT '',        -- 回流来源引擎 chatgpt/claude/gemini/other
    source_url  TEXT    NOT NULL DEFAULT '',        -- 原始会话/分享链接
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_imported_symbol ON imported_reports(symbol);

-- 「记」（第 4 支柱）：与个股无关的长文笔记（市场随想/方法论/复盘思考），markdown 正文。
-- 区别于 journal（绑定个股的判断日记）与 imported_reports（绑定个股的他人研报）——这是自由长文。
CREATE TABLE IF NOT EXISTS notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL DEFAULT '',
    body        TEXT    NOT NULL DEFAULT '',       -- markdown 正文
    pinned      INTEGER NOT NULL DEFAULT 0,        -- 0/1 置顶（列表中置顶在前）
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(pinned DESC, updated_at DESC);

-- 「寻」候选标的（M4）：从新闻流 LLM 标股(matched_by='llm')里聚合**不在自选**、反复出现的票，
-- 跨天累积 + 证据引用 + 作者拍板状态机。喂料零新增 LLM 成本（复用 news_item_symbols）。
-- 区别于 news_opportunities（当日事件论点卡、每日覆盖）——这是标的轴、跨天累积的候选池。
CREATE TABLE IF NOT EXISTS discovery_candidates (
    symbol        TEXT    PRIMARY KEY,                -- 归一化 MARKET:CODE
    name          TEXT    NOT NULL DEFAULT '',
    mention_count INTEGER NOT NULL DEFAULT 0,          -- 被 LLM 标到的次数（同名双重上市已并）
    day_span      INTEGER NOT NULL DEFAULT 0,          -- 出现的不同天数（信号持续度）
    first_seen_at TEXT,                                -- 最早出现日（按新闻 published_at）
    last_seen_at  TEXT,                                -- 最近出现日
    evidence      TEXT    NOT NULL DEFAULT '[]',       -- JSON：[{news_id,title,source,url,date}]
    theme         TEXT    NOT NULL DEFAULT '',          -- 主导主题（从证据新闻推断，供主题级屏蔽）
    reason        TEXT    NOT NULL DEFAULT '',          -- LLM 一句话：为什么值得关注（寻·筛选+理由）
    status        TEXT    NOT NULL DEFAULT 'new',       -- new待看/dismissed忽略/promoted已入自选
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_discovery_status ON discovery_candidates(status, mention_count DESC);

-- Prompt 模板（「研」）：作者自存的 Deep Research 提示词模板。占位符 {STOCK}/{NAME}/
-- {MARKET}/{SYMBOL} 由前端按当前标的填充后复制——用于粘到外部网页 Deep Research。
CREATE TABLE IF NOT EXISTS prompt_templates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL DEFAULT '',
    body        TEXT    NOT NULL DEFAULT '',
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
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
    """打开一个连接（启用外键、Row 工厂）。调用方负责关闭。

    并发安全（AGENTS.md §11「尊重限流/激进缓存」的工程同构）：app 同时跑
    FastAPI 请求线程（同步 DB 调用丢 threadpool）+ APScheduler 后台线程（07:30 抓取
    连续多次提交）+ warm-listings 线程。默认 rollback 模式下两写相撞会立刻
    `database is locked`（busy_timeout 默认 0=不重试）。故开 WAL（读不阻塞写）
    + busy_timeout=5s（短锁竞争自动重试而非 500）。本地单用户、单文件库，零副作用。
    """
    settings = get_settings()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


# 幂等迁移：给**已存在**的表补列（CREATE TABLE IF NOT EXISTS 不会改已建的表）。
# 作者机器上 augur.db 已有数据，故新列必须靠 PRAGMA 探测 + ALTER 补，而非只改 SCHEMA 字符串。
# 新增列时在此追加一行 (表, 列, 列定义)；与 SCHEMA 里的定义保持一致。
_MIGRATIONS: list[tuple[str, str, str]] = [
    ("news_items", "theme", "TEXT NOT NULL DEFAULT ''"),
    ("news_items", "topics", "TEXT NOT NULL DEFAULT '[]'"),
    ("news_items", "classified_by", "TEXT NOT NULL DEFAULT ''"),
    ("news_items", "title_zh", "TEXT"),
    ("news_items", "relevance", "INTEGER NOT NULL DEFAULT 0"),
    ("news_items", "linked", "INTEGER NOT NULL DEFAULT 0"),
    ("news_items", "lane", "TEXT NOT NULL DEFAULT 'feed'"),
    ("news_items", "tagged", "INTEGER NOT NULL DEFAULT 0"),
    ("source_health", "last_error", "TEXT NOT NULL DEFAULT ''"),
    # 导入研报补来源元数据：网页 Deep Research 回流（ChatGPT/Claude/Gemini 订阅版无 API）
    ("imported_reports", "engine", "TEXT NOT NULL DEFAULT ''"),  # chatgpt/claude/gemini/other/''
    ("imported_reports", "source_url", "TEXT NOT NULL DEFAULT ''"),  # 原始会话/分享链接
    # 「寻」候选主导主题（从证据新闻 theme 推断）——供主题级屏蔽/偏好
    ("discovery_candidates", "theme", "TEXT NOT NULL DEFAULT ''"),
    # 「寻」候选 LLM 理由（为什么值得关注）——配合 worth 筛选
    ("discovery_candidates", "reason", "TEXT NOT NULL DEFAULT ''"),
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
