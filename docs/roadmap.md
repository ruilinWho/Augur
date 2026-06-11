# Roadmap — Augur

This document tracks product direction and the remaining work. It is not a changelog — historical implementation context lives in ADRs and `docs/memory/`. Keep this page short enough to scan before starting work.

## Product Position

Augur is a local-first, decision-grade investment research workbench for a single user. It helps that user follow global information flows, inspect individual stocks, generate cited research, and keep a durable record of thinking. It never trades, never places orders, and never manages money.

The product is organized around five surfaces:

- **View (看)** — inspect price, fundamentals, financial trends, related information, and decision-journal markers.
- **Research (研)** — generate or import single-stock research reports with citations and personal comments.
- **Know (知)** — ingest, clean, cluster, translate, and summarize daily market information into decision-grade briefs, opportunities, risks, and stock narratives.
- **Discover (寻)** — surface non-watchlist tickers that recur in the Know stream, with evidence and author triage.
- **Note (记)** — free-form Markdown notes that are not tied to a ticker.

## Built (Available Today)

Everything in this section is implemented and in daily use.

### View (看)

- US, Hong Kong, China A-share, and Korea equities, normalized as `MARKET:CODE`.
- Candlestick charts with calm paper-like styling and market-specific up/down color conventions.
- Quote header focused on current price, change, 52-week position, market cap, P/E, net margin, and freshness.
- Fundamentals and financial-trend tables, with quarterly and annual views.
- Stock-bound decision-journal entries and chart markers.
- AI-summarized "related information" card per stock (news plus social heat).

### Research (研)

- Single-stock report generation from Augur's deterministic local context plus the `deep_research` LLM role: streaming Markdown, saved reports, clickable sources, permanent decision-boundary notice.
- Imported external reports with sorting, editing, and personal comments.
- Prompt templates with `{STOCK}/{NAME}/{MARKET}/{SYMBOL}` placeholders, filled per stock and copied from both Research and View. See [ADR-0014](decisions/0014-prompt-templates.md).
- Pluggable Skills (`resources/skills/<slug>/SKILL.md`, drop-a-folder, enable/disable in Settings); ships the supply-chain bottleneck Skill plus a scorecard endpoint. See [ADR-0017](decisions/0017-pluggable-skills.md).
- Web-research capture (MVP): a userscript copies the current ChatGPT/Claude conversation into clean Markdown for paste-import — no session automation, no data sent to any server. See [ADR-0016](decisions/0016-web-research-capture.md).

### Know (知)

- Ingestion of curated RSS/API sources, Bloomberg RSS, Eastmoney, Cailian Press, and ticker-directed Yahoo news.
- **All social/forum sources flow through TikHub** (one shared `TIKHUB_KEY`): X, Xiaohongshu, Threads, and Reddit — keyword search plus per-stock dedicated subreddit feeds.
- Private WeChat-public-account RSS can be configured from Settings as a separate **Blog** lane in Info sections; the tokenized URL lives only in ignored runtime config and feeds `source_prefix="博客·"`.
- Pipeline: translation, relevance filtering, deterministic stock linking, LLM stock tagging, and grounding, with a global `feed` lane and a per-stock `ticker` lane.
- Daily snapshots and a single integrated daily report that combines news, blogs, and all social/forum lanes into one card for Summary and Decision, with opportunities, risks, counter-evidence, and follow-up questions in the same narrative.
- Summary/Decision show a title-line “since last refresh” freshness chip; manual refresh, one-click refresh+generate, and scheduled auto refresh automatically advance the read baseline. The older social-pulse endpoint remains only as a compatibility/debug read API.
- Single-stock narrative timelines, and per-stock source tracking: X accounts (twtapi with TikHub fallback), Xiaohongshu/Threads keyword sources (TikHub), Reddit communities (TikHub, dedicated subreddit auto-resolved on first refresh), and RSS/Atom feeds.
- Source health tracking, source testing, runtime source configuration, and Chinese diagnostics for credential/quota/adapter failures.

### Discover (寻)

- Candidate pool aggregated from non-watchlist LLM stock tags in the Know stream, with cross-language/share-class alias dedup, mention-count and day-span ranking, and a `new`/`dismissed`/`promoted` triage state machine. Zero extra LLM cost. See [ADR-0015](decisions/0015-discovery-pillar.md).
- Cheap-LLM "worth following?" judgment plus a one-line reason per candidate; theme-level and market-level mute preferences.
- Momentum signal pill (近月大涨且放量), lazily loaded and decoupled from the list.
- Evidence is deduplicated, multi-source-aggregated (`+N`), and translation-refreshed at read time.

### Note (记)

- Markdown long-form notes, pinned notes, preview/edit mode, debounced autosave, and shared Markdown rendering across notes, generated reports, and imported research.

### Settings & Infrastructure

- Dynamic LLM connections, role routing (`chat`/`deep_research`/`summarize`/`cheap`), connection tests, source tests, source-health dashboard, auto-refresh schedule, and token-usage logging.
- One-click API-config export/import to share setup with a contributor — **only live source keys** are included; retired-source keys are filtered out and auto-pruned from local config on startup.
- SQLite WAL/busy-timeout, Parquet cache hardening, SSE error handling, local-only CORS, and background scheduler jobs.
- All runtime secrets live only in ignored local files (`backend/.env`, `data/config.local.json`) — never in git, never logged.

## Not Yet Built

The remaining work, roughly in priority order. Nothing here is shipped; "actively shaped" means partially designed, not done.

### Next (actively shaped)

1. **Official Deep Research jobs** — run OpenAI Deep Research and Gemini Deep Research as asynchronous jobs: store provider job IDs, poll or stream progress, normalize citations, and save the report back into Augur. Keep the existing local-gather path as the fallback engine. See [ADR-0011](decisions/0011-research-deep-research-api-strategy.md).
2. **Stronger stock-source verification** — independent probes plus Chinese diagnostics for X handles, Reddit communities, RSS/Atom feeds, company IR/news pages, and region-specific filings, instead of marking a source verified the moment one item is fetched.
3. **Account-following for Xiaohongshu / Threads** — currently keyword-search only; follow specific accounts once the TikHub user-posts endpoints for those platforms are wired.
4. **Discover-feeding Skills** — `surface=xun` candidate-generator Skills; multi-step Skill workflows (earnings prep, counter-evidence scan, post-earnings review, industry comparison, new-listing cold start); an in-UI scorecard form.

### Later (accepted, not started)

- **Decision reflection loop** — surface changed beliefs, missing counter-evidence, unreviewed decisions, and overdue follow-ups across reports, notes, journals, and generated opportunities.
- **Section-level intelligence** — briefs, risks, and opportunities grouped by watchlist section, not only by market/theme/ticker.
- **Catalyst calendar** — earnings dates, product launches, macro releases, regulatory dates, lockups, and user-defined events.
- **Counter-evidence radar** — per-thesis invalidation conditions that can be triggered by new information.
- **Source reliability scoring** — originality, repetition, error rate, title-noise rate, and historical usefulness by source.
- **Discover ranking depth** — a second ranking key (independent-source count), unresolved-entity candidates, and opportunity-card cross-feed.
- **Portfolio-style research view** — read-only exposure and concentration analysis across watchlists, without brokerage integration.
- **Exports** — Markdown/PDF exports for research reports, notes, and daily snapshots.
- **Native macOS app** — Tauri shell, Python sidecar, Keychain-backed secrets, and application data under `~/Library/Application Support/Augur/`.

## Known Limitations

Honest constraints to keep in mind before relying on Augur for a real decision.

- **Social data is single-sourced.** X, Xiaohongshu, Threads, and Reddit all flow through one paid aggregator (TikHub). If TikHub degrades, the social lanes go empty — adapters fail gracefully, but there is no second provider. WeChat was retired because TikHub's `wechat_mp/web/*` endpoint group is broken server-side; Reddit's public JSON is IP-blocked, so Reddit is TikHub-only. See [tikhub-source-quirks](memory/tikhub-source-quirks.md).
- **Market data rides free providers** (FinanceDataReader, akshare, yfinance, pykrx); they can lag, gap, or break.
- **Automated test coverage is thin** — regression safety leans on manual and live verification, not an integration suite.
- **LLM-dependent features degrade** without a configured model (briefs, summaries, and tagging fall back to empty or raw output).

## Non-Goals

- No trade execution.
- No brokerage account integration unless explicitly re-scoped as read-only research data.
- No multi-user SaaS architecture.
- No telemetry.
- No secret or runtime data committed to git.

## Where To Put Details

- Architecture and module boundaries: [architecture.md](architecture.md)
- UI rules and visual system: [design-system.md](design-system.md)
- Durable decisions: [decisions/](decisions/)
- Source quirks, dead ends, and implementation memory: [memory/](memory/)
