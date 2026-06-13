# PyInstaller spec — Augur 独立后端（onedir）。
# 跑：在 backend/ 下 `uv run pyinstaller augur.spec --noconfirm`
# 产物：dist/augur-backend/augur-backend（可执行）+ _internal/（依赖 + resources）
import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas: list = []
binaries: list = []
hiddenimports: list = []

# 重依赖：动态导入 + 数据文件多，逐个 collect_all（这套栈打包的已知必需）。
# curl_cffi：yfinance 的 HTTP 后端，含编译扩展 + cacert.pem 数据文件，PyInstaller 不自动带全。
for pkg in ("litellm", "akshare", "curl_cffi"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# 补可能被动态 import 的 submodule / 模块
hiddenimports += collect_submodules("pyarrow")
hiddenimports += collect_submodules("uvicorn")
# tiktoken 的编码（cl100k_base 等）经 tiktoken_ext 命名空间 entry-point 动态加载，PyInstaller
# 抓不到 → 启动时 litellm import 即 `ValueError: Unknown encoding cl100k_base. Plugins found: []`。
# 离线 blob 已随 collect_all('litellm') 进 bundle（litellm_core_utils/tokenizers），故只缺插件登记。
hiddenimports += collect_submodules("tiktoken_ext")
hiddenimports += ["tiktoken_ext", "tiktoken_ext.openai_public"]
hiddenimports += [
    "yfinance",
    "FinanceDataReader",
    "pykrx",
    "apscheduler.schedulers.background",
    "apscheduler.triggers.cron",
    "apscheduler.triggers.interval",
    "apscheduler.executors.pool",
]

# resources 随后端打进 bundle（排除源材料 zip / 模板）。SPECPATH = .../backend。
_repo = os.path.dirname(SPECPATH)  # 仓库根  # noqa: F821 (SPECPATH 由 PyInstaller 注入)
for sub in ("prompts", "skills", "sources", "fonts", "userscripts"):
    src = os.path.join(_repo, "resources", sub)
    if os.path.isdir(src):
        datas.append((src, os.path.join("resources", sub)))

a = Analysis(  # noqa: F821
    ["run_server.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "_pytest", "ruff"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="augur-backend",
    console=True,  # 控制台程序：stdout/stderr 交给 Tauri 捕获作日志
    target_arch="arm64",
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    name="augur-backend",
)
