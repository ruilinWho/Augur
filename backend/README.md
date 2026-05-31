# Augur 后端

Python + FastAPI 服务：行情数据、自选分区、LLM 网关、深度研究、新闻、存储。
用 **uv** 管理。约定见 [../CLAUDE.md](../CLAUDE.md) §5–§8。

## 结构

```
augur/
├── main.py        FastAPI app、路由装配、lifespan（调度器）
├── config.py      设置 + 厂商注册表（.env / config.local.toml）
├── market/        四市场数据适配器，统一在 MarketAdapter 后
├── watchlist/     自选分区（两级板块），强制 depth ≤ 2
├── llm/           litellm 网关：角色、base_url、流式、用量
├── research/      deep-research 编排
├── news/          信源摄取 + APScheduler + 日报
└── storage/       SQLite（状态）+ Parquet（行情缓存）
```

## 计划依赖（M1 时用 `uv add` 锁定）

`fastapi` · `uvicorn[standard]` · `pydantic` / `pydantic-settings` · `litellm`
`FinanceDataReader` · `akshare` · `yfinance` · `pykrx` · `pyarrow`
`apscheduler` · `feedparser` · `httpx`
开发：`ruff` · `mypy`（或 `pyright`）· `pytest`

> 目标 Python **3.13**（2026 年新项目最稳的前沿选择）。

## 开发命令（M1 脚手架落地后可用）

```bash
uv sync                                              # 装依赖
uv run uvicorn augur.main:app --reload --port 8788   # 跑 API
uv run ruff check . && uv run ruff format .          # lint + 格式化
uv run pytest                                        # 测试
```

## 配置

复制 `.env.example` → `.env`（被忽略），填厂商 key/base_url。
绝不提交密钥（CLAUDE.md §11）。
