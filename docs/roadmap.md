# Roadmap — Augur

This document tracks the product direction and active work for Augur. It is intentionally not a changelog. Historical implementation context belongs in ADRs or `docs/memory/`; this page should stay short enough to scan before starting work.

Status legend: **Available** means implemented in the app; **In progress** means partially implemented or actively being shaped; **Planned** means accepted product direction but not yet built.

## Product Position

Augur is a local-first, decision-grade investment research workbench. It helps one user follow global information flows, inspect individual stocks, generate cited research, and keep a durable record of thinking. It never trades, never places orders, and never manages money.

The product is organized around four surfaces:

- **View**: inspect price, fundamentals, financial trends, related information, and decision journal markers.
- **Research**: generate or import single-stock research reports with citations and personal comments.
- **Know**: ingest, clean, cluster, translate, and summarize daily market information into decision-grade briefs, opportunities, risks, and stock narratives.
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
- **Available**: single-stock narrative timelines and stock-specific source tracking for enabled X accounts, Reddit communities, and RSS/Atom feeds.
- **In progress**: broader QA for TikHub-backed sources, stronger source verification, and more first-party company/regulatory feeds.

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

   Promote prompts into reusable research templates with variables, output contracts, and actions such as copy, run locally, run with a provider Deep Research engine, or import an external result. This should become the foundation for future Skills.

3. **External Research capture**

   Design a browser-companion workflow for ChatGPT, Claude, and Gemini subscription research results that do not expose a stable API. Augur should generate the prompt, track the intended task, and let the user save the completed web result back into the local database.

4. **Stock-specific source quality**

   Improve verification for discovered stock sources: X handles, Reddit communities, RSS/Atom feeds, company IR/news pages, and region-specific filings. Enabled sources should feed the ticker lane without pretending unsupported sources are live.

5. **Decision reflection loop**

   Add a reflection layer over research reports, notes, journals, generated opportunities, read history, and stale catalysts. The goal is to surface changed beliefs, missing counter-evidence, unreviewed decisions, and overdue follow-ups.

## Planned Directions

- **Skills**: reusable multi-step research workflows such as counter-evidence scan, earnings prep, post-earnings review, industry comparison, new listing cold start, and stock-source discovery.
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
