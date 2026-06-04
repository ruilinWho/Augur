<div align="center">

# Augur

**本地优先、LLM 驱动的个人多市场投资研究工作台**
*A local-first, LLM-powered personal investment research workbench for macOS.*

</div>

---

Augur 不是交易终端，而是一个本地运行的**研究**工具。它把四件事合在一处：

- **看 · View**：美股 / 港股 / A 股 / 韩股 K 线、报价、基本面快照、财报趋势、判断日记 marker。
- **研 · Research**：用确定性数据 + LLM 对单支股票生成带引用的深度研究报告，也支持导入他人研报并写评论。
- **知 · Know**：聚合 RSS/API/X/定向 ticker 新闻，分类、翻译、过滤噪音，蒸馏成每日趋势、要事、机会和个股叙事。
- **记 · Note**：与个股无关的自由长文笔记，用于市场随想、方法论、复盘思考。

底座是两级自选分区、统一 LLM 网关和本地 SQLite/Parquet 存储。Augur 永不下单、不动钱，也不把本地数据发往任何地方，除非作者明确配置的 LLM 或数据源需要。

## Tech Stack

`Python 3.13 + FastAPI` · `React 19 + TypeScript + Vite 8` · `litellm` · `FinanceDataReader / akshare / yfinance / pykrx` · `Lightweight Charts v5` · `Tailwind CSS v4` · `SQLite + Parquet` · `Tauri 2 (Phase 2)`

## Status

当前主线：**M1 / M1.5 / M1.6 / M2 已完成，M3「知」推进中，M3.5 优化与第 4 支柱「记」已落地**。

已能本地跑通四市场 K 线、自选分区、基本面/财报、单股研究、趋势日报、今日要事/机会、个股叙事、导入研报、自由笔记、动态 LLM/信源设置。实时状态看 [docs/roadmap.md](docs/roadmap.md)。

## Local Run

```bash
# backend
cd backend
uv sync
uv run uvicorn augur.main:app --reload --port 8788

# frontend
cd frontend
npm install
npm run dev
```

密钥放在 `backend/.env` 或设置页写入的 `data/config.local.json`；两者都被 git 忽略。

## For Developers And LLMs

Start with [AGENTS.md](AGENTS.md) — it is the project constitution. Then:

- Architecture → [docs/architecture.md](docs/architecture.md)
- Roadmap & status → [docs/roadmap.md](docs/roadmap.md)
- Design system → [docs/design-system.md](docs/design-system.md)
- Decisions (ADRs) → [docs/decisions/](docs/decisions/)
- Cross-session memory → [docs/memory/](docs/memory/)

## Guardrails

Research only. **Never** trades or moves money. Secrets stay out of git. Free data may be delayed or imperfect; every research output should expose freshness, uncertainty, and sources.
