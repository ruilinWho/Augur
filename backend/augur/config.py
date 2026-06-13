"""应用配置：从 .env / 环境变量读取。

开发期路径解析到仓库 data/ resources/；**打包（PyInstaller）后**解析到用户目录 +
bundle 内只读资源。约定见 AGENTS.md §6 / ADR-0008。**LLM 连接与角色现由 `runtime_config`
（data/config.local.json）动态管理**——增删连接、角色→连接 指派都在「设置 · 模型」里，gateway
走 runtime_config。本文件只管**应用级设置**（port/tz/sec_user_agent）；下方 `role_*` 字段仅作旧
.env→连接 的**一次性迁移种子**保留（_seed_from_legacy 读一次），非现行机制。

打包模式（`sys.frozen`，见 ADR-0019）：
- 数据目录由 Tauri 注入 `AUGUR_DATA_DIR`（~/Library/Application Support/Augur，可写、跨更新保留）。
- 资源目录走 `sys._MEIPASS/resources`（随 app bundle，只读）。
- 不加载 `backend/.env`（朋友靠「配置分享」导入到 config.local.json）。
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent  # .../backend（开发期）
REPO_ROOT = BACKEND_DIR.parent  # 仓库根（开发期）

_FROZEN = getattr(sys, "frozen", False)  # PyInstaller 打包后为 True

# 把 backend/.env 灌进 os.environ：litellm/gateway 直接 os.getenv 读厂商 key（DEEPSEEK_API_KEY、
# RELAY_API_KEY/RELAY_BASE_URL…），而 pydantic-settings 只认 AUGUR_ 前缀，故这里显式加载一次。
# 打包后没有 .env（朋友靠「配置分享」导入到 config.local.json）→ 跳过加载。
if not _FROZEN:
    load_dotenv(BACKEND_DIR / ".env")


def _resolve_data_dir() -> Path:
    """运行时数据目录（可写）。打包 app 由 Tauri 注入 `AUGUR_DATA_DIR`；开发期回退仓库 data/。"""
    env = os.environ.get("AUGUR_DATA_DIR")
    if env:
        return Path(env).expanduser()
    return REPO_ROOT / "data"


def _resolve_resources_dir() -> Path:
    """版本化只读资源（prompts/skills/sources/fonts）。打包后随 bundle 进 sys._MEIPASS/resources；
    开发期用仓库 resources/。"""
    if _FROZEN and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "resources"
    return REPO_ROOT / "resources"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None if _FROZEN else BACKEND_DIR / ".env",
        env_prefix="AUGUR_",
        extra="ignore",
    )

    port: int = 8788
    tz: str = "Asia/Shanghai"

    # SEC EDGAR 公平获取要求可识别 UA（无则 403）。默认非 PII；作者可在 .env 配
    # AUGUR_SEC_USER_AGENT="你的名字 you@example.com" 以最稳妥地符合 SEC 规范。
    sec_user_agent: str = "Augur/0.1 personal-investment-research non-commercial"

    # 角色 → "provider:model"：legacy，仅供 runtime_config._seed_from_legacy 一次性迁移读取，
    # 非现行机制（现行＝动态连接，见 runtime_config）。为空表示无旧配置可迁。
    role_chat: str = ""
    role_deep_research: str = ""
    role_summarize: str = ""
    role_cheap: str = ""

    @property
    def data_dir(self) -> Path:
        return _resolve_data_dir()

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "db" / "augur.db"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def resources_dir(self) -> Path:
        return _resolve_resources_dir()


@lru_cache
def get_settings() -> Settings:
    return Settings()
