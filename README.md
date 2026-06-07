# Augur

Augur is a local-first, LLM-powered investment research workbench for macOS.

It is built for one user who wants to follow multiple equity markets, read market-moving information with less noise, generate cited research, and keep a durable record of investment thinking. Augur is research software only: it never places orders, never moves money, and never connects to a brokerage account.

## What Augur Does

Augur is organized around four product surfaces:

- **View**: multi-market candlestick charts for US, Hong Kong, China A-share, and Korea equities, with quotes, fundamentals, financial trends, 52-week position, related-news summaries, and decision journal markers.
- **Research**: single-stock research reports generated from deterministic local context plus an LLM, with citations, imported reports, and personal comments.
- **Know**: a daily market intelligence layer that ingests curated RSS/API sources, X, Reddit, TikHub-backed social sources, ticker-specific news, and stock-specific sources; it translates, filters, clusters, tags stocks, and distills decision-grade daily briefs, opportunities, risks, and narratives.
- **Note**: long-form Markdown notes for market thoughts, investing process, and retrospectives that are not tied to a single ticker.

The common foundation is a two-level watchlist taxonomy, a configurable LLM gateway, local SQLite metadata, and Parquet market-data caches.

## Features

- Local-first storage under `data/`, with `resources/` reserved for versioned human-authored inputs.
- Normalized multi-market symbols such as `US:AAPL`, `HK:00700`, `CN:600519`, and `KR:005930`.
- Two-level watchlist sections with drag-and-drop organization and market filters.
- Candlestick charts using a calm paper-like design language rather than trading-terminal noise.
- Fundamentals and financial trend tables backed primarily by yfinance, with market-specific adapters and caches.
- LLM gateway based on dynamic OpenAI-compatible connections and role routing (`chat`, `deep_research`, `summarize`, `cheap`).
- Streaming research and news distillation, with token usage logged locally.
- Source health checks and runtime configuration from the Settings UI.
- News ingestion, translation, relevance filtering, stock grounding, daily snapshots, opportunity cards, and single-stock narrative timelines.
- Free-form Markdown notes and stock-bound decision journals.

## Tech Stack

| Layer | Stack |
|---|---|
| Backend | Python 3.13, FastAPI, uv, APScheduler |
| Market data | FinanceDataReader, akshare, yfinance, pykrx |
| LLM | litellm, OpenAI-compatible provider routing |
| Storage | SQLite, Parquet, pyarrow |
| Frontend | React 19, TypeScript, Vite 8, TanStack Query, Zustand, Zod |
| UI | Tailwind CSS v4, Motion, dnd-kit |
| Charts | Lightweight Charts v5 |
| Desktop packaging | Planned Tauri 2 shell with a Python sidecar |

## Getting Started

Prerequisites:

- macOS
- Python 3.13
- `uv`
- Node.js 20.19 or newer
- npm

Start the backend:

```bash
cd backend
uv sync
uv run uvicorn augur.main:app --reload --port 8788
```

Start the frontend:

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server runs on `http://localhost:5173` and proxies API requests to the FastAPI backend on `http://localhost:8788`.

## Configuration

Secrets must stay out of git.

Augur reads configuration from two local, ignored locations:

- `backend/.env`
- `data/config.local.json`, written by the Settings UI and applied at runtime

LLM connections, role routing, source credentials, source-specific options, and scheduler settings can be managed from the app. Runtime settings take precedence over `.env` values and do not require a backend restart.

## Project Structure

```text
Augur/
├── AGENTS.md            Project constitution for coding agents
├── README.md            Human-facing project entry point
├── backend/             FastAPI service and domain modules
├── frontend/            React/Vite application
├── resources/           Versioned prompts, source lists, fonts, aliases
├── data/                Runtime data, ignored by git
└── docs/                Architecture, roadmap, design system, ADRs, memory
```

The key rule is simple: manually authored inputs belong in `resources/`; generated, cached, fetched, or private runtime data belongs in `data/`.

## Documentation

- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Design system](docs/design-system.md)
- [Architecture decisions](docs/decisions/)
- [Project memory](docs/memory/)
- [Agent instructions](AGENTS.md)

## Roadmap

Near-term work is tracked in [docs/roadmap.md](docs/roadmap.md). Current priorities include official Deep Research job integration, richer research templates and workflows, stock-specific source verification, section-level intelligence, and eventually native macOS packaging.

## Guardrails

Augur is not a trading terminal. It does not place trades, manage positions, or execute financial transactions.

Investment outputs must remain traceable: cite sources, expose freshness, show uncertainty, and state counter-evidence or invalidation conditions. Free data sources can be delayed, incomplete, or wrong, and LLMs can hallucinate.
