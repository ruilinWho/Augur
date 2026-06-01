"""应用配置：从 .env / 环境变量读取。路径解析到仓库根的 data/ resources/。

约定见 CLAUDE.md §6。厂商 API key / base_url 用各自的环境变量（如 ANTHROPIC_API_KEY），
由 litellm 网关直接读取；这里只管应用级设置与角色路由。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent  # .../backend
REPO_ROOT = BACKEND_DIR.parent  # 仓库根

# 把 backend/.env 灌进 os.environ：litellm/gateway 直接 os.getenv 读厂商 key（DEEPSEEK_API_KEY、
# RELAY_API_KEY/RELAY_BASE_URL…），而 pydantic-settings 只认 AUGUR_ 前缀，故这里显式加载一次。
load_dotenv(BACKEND_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_prefix="AUGUR_",
        extra="ignore",
    )

    port: int = 8788
    tz: str = "Asia/Shanghai"

    # 角色 → "provider:model"（详见 §6）。为空表示未配置。
    role_chat: str = ""
    role_deep_research: str = ""
    role_summarize: str = ""
    role_cheap: str = ""

    @property
    def data_dir(self) -> Path:
        return REPO_ROOT / "data"

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
        return REPO_ROOT / "resources"


@lru_cache
def get_settings() -> Settings:
    return Settings()
