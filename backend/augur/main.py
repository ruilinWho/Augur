"""Augur 后端入口：FastAPI app、路由装配、lifespan。

本地运行：`uv run uvicorn augur.main:app --reload --port 8788`（在 backend/ 下）。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .market import router as market_router
from .storage import init_db
from .watchlist import router as watchlist_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="Augur", version="0.1.0", lifespan=lifespan)

# 开发期允许 Vite dev server 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market_router)
app.include_router(watchlist_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": "augur"}
