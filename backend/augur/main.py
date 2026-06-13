"""Augur 后端入口：FastAPI app、路由装配、lifespan。

本地运行：`uv run uvicorn augur.main:app --reload --port 8788`（在 backend/ 下）。
"""

from __future__ import annotations

import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import runtime_config
from .discovery import router as discovery_router
from .journal import router as journal_router
from .llm import router as llm_router
from .market import listings
from .market import router as market_router
from .market import search as search_mod
from .news import router as news_router
from .news import scheduler as news_scheduler
from .news import source_registry
from .notes import router as notes_router
from .research import router as research_router
from .settings_router import router as settings_router
from .skills import router as skills_router
from .storage import init_db
from .templates import router as templates_router
from .theses import router as theses_router
from .watchlist import router as watchlist_router


def _warm_listings() -> None:
    """后台预热标的目录：先用磁盘缓存让检索即刻可用，再回源刷新缺失/过期市场。"""
    search_mod.build_index()  # 有缓存就立即可搜（冷启动则为空，ready=False）
    listings.ensure_all()  # 构建缺失 / 刷新过期（重型网络调用，故置后台）
    search_mod.build_index()  # 用新数据重建索引


log = logging.getLogger("augur")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    runtime_config.load()  # 把 UI 存的 API key 注入 os.environ（gateway/适配器即时可见）
    # 自愈：清掉退役信源（雪球/Tushare/必盈/iTick 等）在 config.local.json 里的遗留 key——
    # 它们已无任何代码引用，留着只会污染「配置分享」导出。退役一个源即自动清，无需手动。
    pruned = runtime_config.prune_secrets(source_registry.live_secret_names())
    if pruned:
        log.info("已清理退役信源遗留 secret：%s", ", ".join(sorted(pruned)))
    init_db()
    threading.Thread(target=_warm_listings, name="warm-listings", daemon=True).start()
    news_scheduler.start()  # 每日抓取 +（若 LLM 就绪）生成趋势日报
    yield
    news_scheduler.stop()


app = FastAPI(title="Augur", version="0.1.0", lifespan=lifespan)

# 跨域：放行任意本地端口（Vite 5173 被占自动改 5174）+ Tauri 打包外壳的 tauri:// 协议
# （macOS WKWebView origin = tauri://localhost）。仍仅限本地源，不破坏 §11「本地优先且私密」。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["tauri://localhost", "http://tauri.localhost"],  # Tauri 打包外壳 webview
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market_router)
app.include_router(watchlist_router)
app.include_router(llm_router)
app.include_router(journal_router)
app.include_router(theses_router)
app.include_router(news_router)
app.include_router(research_router)
app.include_router(notes_router)
app.include_router(templates_router)
app.include_router(discovery_router)
app.include_router(skills_router)
app.include_router(settings_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": "augur"}
