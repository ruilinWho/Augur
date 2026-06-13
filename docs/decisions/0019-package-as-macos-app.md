# ADR-0019 — 打包为可分发 macOS app（PyInstaller 独立后端 + Tauri 2 外壳）

日期：2026-06-13 · 状态：已采纳

## 背景

作者认为功能已够，想把 Augur 打成 macOS app **分发给朋友双击即用**。这推翻了早期「只自己用、靠仓库 + uv 跑」的假设——朋友的 Mac 没有 Python / uv / 仓库，后端必须**完整独立打包**。最大风险是 PyInstaller 能否干净打通 `litellm / pyarrow / akshare / yfinance` 这套科学栈（动态导入 + 数据文件多）；故第一步是可行性闸门，打不通就回头重选路。

## 决策

1. **后端 = PyInstaller onedir 独立二进制**（`backend/augur.spec`，非 onefile——启动快、易调、对外壳友好）。入口 [run_server.py](../../backend/run_server.py)：frozen 下不走 import-string/reload，直接 `uvicorn.run(app)` 单进程，端口 8788。
2. **frozen 双模式**（[config.py](../../backend/augur/config.py)）：
   - 数据目录由外壳注入 `AUGUR_DATA_DIR`（`~/Library/Application Support/Augur`，可写、跨更新保留）；开发期回退仓库 `data/`。
   - 资源走 `sys._MEIPASS/resources`（prompts/skills/sources/fonts/userscripts 随 onedir 进 bundle，只读）；开发期用仓库 `resources/`。
   - 打包模式跳过 `load_dotenv`——朋友靠「配置分享」导入 LLM key 到 `config.local.json`，不带 `.env`。
3. **外壳 = Tauri 2 原生窗口**：WKWebView 加载打进 app 的 Vite 静态前端；`setup()` 用 resource resolver 定位 bundle 内 onedir 并 `std::process::Command` spawn（**手动 spawn，非 Tauri `externalBin` sidecar**——后者只认单文件 + target-triple 后缀，不适配「二进制 + `_internal/` 目录」的 onedir）；注入 `AUGUR_DATA_DIR`，`RunEvent::ExitRequested` 时 kill；spawn 失败弹原生错误不白屏。CORS 放行 `tauri://localhost`。
4. **暂不签名**（省 $99/年）：朋友首开靠 `xattr -dr com.apple.quarantine` 解除隔离，用 `首次打开.command` 脚本 + 图文兜底。日后要无摩擦再补签名。
5. **LLM key 靠「配置分享」**：作者导出 `augur-config.json` 给朋友导入（零开发）。取舍：JSON 内 key 明文、付费额度共用（成本/限流作者扛）；建议给朋友单独低额 key。

## 打包坑（已解，记录备查）

- **tiktoken 编码插件**：`litellm` import 时 `tiktoken.get_encoding("cl100k_base")`，而编码定义经 `tiktoken_ext` 命名空间 entry-point 动态加载，PyInstaller 抓不到 → 启动即 `ValueError: Unknown encoding cl100k_base. Plugins found: []`。修：spec 里 `collect_submodules("tiktoken_ext")` + 显式 hiddenimport。离线 blob 已随 `collect_all('litellm')` 进 bundle（`litellm_core_utils/tokenizers`，litellm 把 `TIKTOKEN_CACHE_DIR` 指向它），故**首启无需联网**。
- **curl_cffi**（yfinance 的 HTTP 后端）：含编译扩展 + `cacert.pem` 数据文件 → `collect_all("curl_cffi")`。
- `litellm.proxy`（缺 orjson）、`botocore`（Bedrock/SageMaker）缺失只是 warning，不用即无害。

## 后果

- **闸门已过**：frozen 二进制在空 `AUGUR_DATA_DIR` + 注入测试 key 下跑通 `/health`、行情（FDR/pykrx/akshare）、检索 build_index、SEC EDGAR、财报、LLM 真实调用（deepseek + relay·claude）。科学栈可干净打通，方案成立。
- **体积 ~360MB+**：科学栈本质重，`pyarrow`（122M，仅 parquet 行情缓存用）是大头，瘦身（换 fastparquet 等）留后续，不阻塞首版。
- **未签名摩擦**：首开需 `xattr`；macOS 升级偶尔需重做。
- **数据隔离**：分发的 app 必须用空 `~/Library/Application Support/Augur/`，绝不带作者的 `data/db`。
