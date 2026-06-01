"""Augur 后端入口：FastAPI app、路由装配、lifespan。

本地运行：`uv run uvicorn augur.main:app --reload --port 8788`（在 backend/ 下）。
"""

from __future__ import annotations

import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .journal import router as journal_router
from .llm import router as llm_router
from .market import listings
from .market import router as market_router
from .market import search as search_mod
from .storage import init_db
from .watchlist import router as watchlist_router


def _warm_listings() -> None:
    """后台预热标的目录：先用磁盘缓存让检索即刻可用，再回源刷新缺失/过期市场。"""
    search_mod.build_index()  # 有缓存就立即可搜（冷启动则为空，ready=False）
    listings.ensure_all()  # 构建缺失 / 刷新过期（重型网络调用，故置后台）
    search_mod.build_index()  # 用新数据重建索引


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    threading.Thread(target=_warm_listings, name="warm-listings", daemon=True).start()
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
app.include_router(llm_router)
app.include_router(journal_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": "augur"}
