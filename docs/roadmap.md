# Roadmap — Augur

This document tracks the product direction and active work for Augur. It is intentionally not a changelog. Historical implementation context belongs in ADRs or `docs/memory/`; this page should stay short enough to scan before starting work.

Status legend: **Available** means implemented in the app; **In progress** means partially implemented or actively being shaped; **Planned** means accepted product direction but not yet built.

## Product Position

Augur is a local-first, decision-grade investment research workbench. It helps one user follow global information flows, inspect individual stocks, generate cited research, and keep a durable record of thinking. It never trades, never places orders, and never manages money.

The product is organized around four surfaces:

- **View**: inspect price, fundamentals, financial trends, related information, and decision journal markers.
- **Research**: generate or import single-stock research reports with citations and personal comments.
- **Know**: ingest, clean, cluster, translate, and summarize daily market information into decision-grade briefs, opportunities, risks, and stock narratives.
- **Discover (寻)**: surface non-watchlist tickers that recur in the Know stream, ranked by mention count and day span, with author triage (add to watchlist / dismiss).
- **Note**: keep free-form Markdown notes that are not tied to a ticker.

## Current Capabilities

### View

- **Available**: US, Hong Kong, China A-share, and Korea equity symbols normalized as `MARKET:CODE`.
- **Available**: candlestick charts with calm paper-like styling, market-specific up/down color conventions, and responsive layout.
- **Available**: quote and header information focused on current price, change, 52-week position, market cap, P/E, net margin, and freshness.
- **Available**: fundamentals and financial trend tables, with quarterly and annual views.
- **Available**: stock-bound decision journal entries and chart markers.
- **Available**: AI summarized related-news card and social heat summary.

### Research

- **Available**: single-stock report generation from Augur's deterministic local context plus the configured `deep_research` LLM role.
- **Available**: streaming Markdown output, saved reports, clickable sources, and a permanent decision-boundary notice.
- **Available**: imported external research reports, sorting, editing, and personal comments.
- **Available**: prompt templates with `{STOCK}/{NAME}/{MARKET}/{SYMBOL}` placeholders, managed in Settings, filled per stock and copied from the Research surface for external web Deep Research. See [ADR-0014](decisions/0014-prompt-templates.md).
- **In progress**: official Deep Research job architecture. See [ADR-0011](decisions/0011-research-deep-research-api-strategy.md).

### Know

- **Available**: curated RSS/API source ingestion, X via twtapi, Reddit public JSON, TikHub-backed source lanes, Bloomberg RSS, Eastmoney, Cailian Press, and ticker-directed Yahoo news.
- **Available**: source health tracking, source testing, runtime source configuration, and Chinese diagnostics for common credential/quota/adapter failures.
- **Available**: translation, relevance filtering, stock linking, LLM stock tagging, deterministic grounding, and lane separation between global feed and ticker-directed data.
- **Available**: daily snapshots, market briefs, clustered key points, opportunity cards, risk/counter-evidence framing, and stock chips that jump to View or Research.
- **Available**: single-stock narrative timelines and stock-specific source tracking for enabled X accounts (twtapi with TikHub fallback), Xiaohongshu/Threads keyword sources (TikHub), Reddit communities, and RSS/Atom feeds.
- **In progress**: account-following (not just keyword search) for Xiaohongshu/Threads, stronger source verification, and more first-party company/regulatory feeds.

### Discover (寻)

- **Available**: candidate pool aggregated from non-watchlist LLM stock tags in the Know stream, with cross-language/share-class alias dedup, mention-count and day-span ranking, evidence links, and a `new`/`dismissed`/`promoted` triage state machine. Zero extra LLM cost. See [ADR-0015](decisions/0015-discovery-pillar.md).
- **Planned**: second ranking key (independent-source count), unresolved-entity candidates, opportunity-card cross-feed, and Skills-based candidate generators.

### Note

- **Available**: Markdown long-form notes, pinned notes, preview/edit mode, and debounced autosave.
- **Available**: shared Markdown rendering across notes, generated reports, and imported research.

### Settings And Infrastructure

- **Available**: dynamic LLM connections, role routing, connection tests, source tests, source health dashboard, auto-refresh schedule, and token usage logging.
- **Available**: SQLite WAL/busy timeout, Parquet cache hardening, SSE error handling, local CORS for development, and background scheduler jobs.
- **Available**: all runtime secrets are stored in ignored local files, never in git.

## Active Work

1. **Research engines**

   Add first-class research jobs that can run OpenAI Deep Research and Gemini Deep Research as asynchronous tasks, store provider job IDs, poll or stream progress, normalize citations, and save the final report back into Augur. Keep Augur's existing local-gather research path as the fallback engine.

2. **Research templates and workflows**

   - **Available**: prompt templates (user-authored, SQLite) and pluggable **Skills** (`resources/skills/<slug>/SKILL.md`, drop-a-folder, enable/disable in Settings) both feed the Research surface's copy-prompt entry. Ships the "供应链卡点研究" Skill (distilled Serenity methodology) and a ported bottleneck scorecard (`POST /skills/scorecard`). See [ADR-0017](decisions/0017-pluggable-skills.md).
   - **Planned**: `surface=xun` candidate-generator Skills feeding Discover; multi-step workflows (earnings prep, counter-evidence scan); in-UI scorecard form; running a Skill as the system prompt for local generation.

3. **External Research capture**

   - **Available (MVP)**: imported reports carry `engine` + `source_url`; a userscript (`resources/userscripts/augur-capture.user.js`) reads the current ChatGPT/Claude conversation via same-origin internal APIs into clean Markdown on the clipboard for paste-import. No session automation, no data sent to any server. See [ADR-0016](decisions/0016-web-research-capture.md).
   - **Planned**: promote `engine` into a research-job state (`awaiting_paste`) sharing one jobs table with the official-API track; structured citations for imported reports; Gemini Deep Research via its official API (`deep-research-preview-04-2026`).

4. **Stock-specific source quality**

   Improve verification for discovered stock sources: X handles, Reddit communities, RSS/Atom feeds, company IR/news pages, and region-specific filings. Enabled sources should feed the ticker lane without pretending unsupported sources are live.

5. **Decision reflection loop**

   Add a reflection layer over research reports, notes, journals, generated opportunities, read history, and stale catalysts. The goal is to surface changed beliefs, missing counter-evidence, unreviewed decisions, and overdue follow-ups.

## Planned Directions

- **Skills (expansion)**: the pluggable Skills framework ships (see Active Work #2); next are multi-step workflows such as counter-evidence scan, earnings prep, post-earnings review, industry comparison, new listing cold start, and stock-source discovery.
- **Section-level intelligence**: daily briefs, risks, and opportunities grouped by watchlist section instead of only by market/theme/ticker.
- **Catalyst calendar**: earnings dates, product launches, macro releases, regulatory dates, lockups, and user-defined events.
- **Counter-evidence radar**: per-thesis invalidation conditions that can be triggered by new information.
- **Source reliability scoring**: originality, repetition, error rate, title-noise rate, and historical usefulness by source.
- **Portfolio-style research view**: read-only exposure and concentration analysis across watchlists without brokerage integration.
- **Exports**: Markdown/PDF exports for research reports, notes, and daily snapshots.
- **Native macOS app**: Tauri shell, Python sidecar, Keychain-backed secrets, and application data under `~/Library/Application Support/Augur/`.

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
