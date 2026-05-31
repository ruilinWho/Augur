<div align="center">

# 🔮 Augur

**本地优先、LLM 驱动的个人多市场投资研究工作台**
*A local-first, LLM-powered personal investment research workbench for macOS.*

</div>

---

Augur 不是交易终端，而是一个**研究**工具。它把三件事合在一处：

- **看 · View** — 美股 / 港股 / A股 / 韩股的 K 线，赏心悦目地渲染。
- **研 · Research** — 用 LLM + Deep Research 对单支股票做深度分析。
- **知 · Know** — 每天聚合全球顶级信源，由 LLM 蒸馏成**趋势日报**。

底座是一个统一、可自配 `base_url` 的 LLM 网关（OpenAI / Anthropic / DeepSeek / 中转站皆可）。
界面贴合 Anthropic 的设计哲学，字体与行距可调。

## Tech stack

`Python + FastAPI` · `React + TypeScript + Vite` · `litellm` · `FinanceDataReader / akshare / yfinance / pykrx` · `Lightweight Charts` · `Tauri 2 (Phase 2)`

## Status

🚧 **M0 — Scaffolding.** Structure, docs, and conventions are in place; runtime code lands in M1.
See [docs/roadmap.md](docs/roadmap.md) for the live status board.

## For developers (human or LLM)

Start with [CLAUDE.md](CLAUDE.md) — it is the project constitution. Then:

- Architecture → [docs/architecture.md](docs/architecture.md)
- Roadmap & status → [docs/roadmap.md](docs/roadmap.md)
- Design system → [docs/design-system.md](docs/design-system.md)
- Decisions (ADRs) → [docs/decisions/](docs/decisions/)

## Guardrails

Research only — **never** trades or moves money. Secrets stay out of git. Free data may be delayed/imperfect; always check freshness and sources.
