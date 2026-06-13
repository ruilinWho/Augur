"""PyInstaller 打包入口：独立后端进程，直接用 uvicorn 跑 FastAPI app。

frozen（PyInstaller）模式下不用 import-string / reload / workers——直接传 `app` 对象、
单进程跑。开发期仍走 `uv run uvicorn augur.main:app --reload --port 8788`；本文件只服务
打包后的独立后端（Tauri 外壳会 spawn 它）。端口 8788 与前端约定一致。
"""

from __future__ import annotations

import multiprocessing
import os
import threading
import time

import uvicorn

from augur.main import app


def _watch_parent_death() -> None:
    """父进程（Tauri 外壳）退出 → 本后端立即自杀，避免残留占住 8788。

    Tauri 的 RunEvent kill 是优雅快路径，但崩溃 / 强退 / 某些 quit 路径不触发它（实测
    osascript quit 即不触发）；故再加这层兜底：外壳一旦消失，本进程被 launchd(1) 收养，
    getppid() 变化 → 退出。仅打包后端（本入口）启用；dev 用 `uvicorn augur.main:app`
    直跑、不经此文件，不受影响。
    """
    initial_ppid = os.getppid()
    while True:
        time.sleep(1.0)
        if os.getppid() != initial_ppid:
            os._exit(0)


def main() -> None:
    # 端口默认 8788（前端 .env.production / Tauri 约定）；AUGUR_PORT 可覆盖（测试避端口冲突）。
    port = int(os.environ.get("AUGUR_PORT", "8788"))
    # 外壳死亡兜底：守护线程盯父进程，外壳一退出就收尾本后端。
    threading.Thread(target=_watch_parent_death, name="parent-watchdog", daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    multiprocessing.freeze_support()  # PyInstaller + macOS spawn 安全（即便当前无多进程）
    main()
