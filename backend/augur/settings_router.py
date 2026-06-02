"""「设置」域 HTTP 路由：在 UI 里配置 API（LLM 厂商 key/base + 角色路由 + 数据信源 key）。

护栏（§11）：密钥经 `runtime_config` 落到 gitignored `data/config.local.json`，**只回脱敏状态**、
从不回传明文、绝不打日志。POST 仅接受**凭证形状**的 env 名（白名单 + 后缀模式），杜绝写入
任意环境变量（如 PATH）。改动即时生效（注入 os.environ，gateway/适配器走 os.getenv）。
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import runtime_config
from .llm import gateway
from .news import source_registry

router = APIRouter(prefix="/settings", tags=["settings"])

# 允许设置的 env 名：已知厂商/信源用到的，或形如 *_API_KEY/_BASE_URL/_KEY/_TOKEN/_SECRET
_NAME_OK = re.compile(r"^[A-Z][A-Z0-9_]*(_API_KEY|_BASE_URL|_KEY|_TOKEN|_SECRET|_URL)$")


def _allowed_names() -> set[str]:
    names: set[str] = set()
    for cfg in gateway.PROVIDERS.values():
        names.add(cfg["key_env"])
        names.add(cfg["base_env"])
    for s in source_registry.SOURCES:
        if s.get("key_env"):
            names.add(s["key_env"])
    return names


class SecretIn(BaseModel):
    name: str
    value: str | None = None  # 空/None = 清除


class RoleIn(BaseModel):
    role: str
    spec: str = ""  # "provider:model"；空 = 清除（回退 .env）


@router.get("/config")
async def get_config() -> dict:
    """设置页快照：LLM 角色/厂商状态 + 数据信源状态（全脱敏，无明文 key）。"""
    return {
        "llm": {"roles": gateway.roles_status(), "providers": gateway.providers_status()},
        "sources": source_registry.status_list(),
    }


@router.post("/secret")
async def set_secret(body: SecretIn) -> dict:
    """设置/清除一个 API key 或 base_url（写 gitignored 本地存储，即时生效）。"""
    name = (body.name or "").strip()
    if not (_NAME_OK.match(name) or name in _allowed_names()):
        raise HTTPException(status_code=400, detail=f"不允许的配置项名：{name!r}")
    runtime_config.set_secret(name, body.value)
    return {
        "name": name,
        "configured": runtime_config.has_secret(name),
        "hint": runtime_config.secret_hint(name),
    }


@router.post("/role")
async def set_role(body: RoleIn) -> dict:
    """设置/清除某 LLM 角色的 provider:model 路由（空=回退 .env）。"""
    role = (body.role or "").strip()
    if role not in ("chat", "deep_research", "summarize", "cheap"):
        raise HTTPException(status_code=400, detail=f"未知角色：{role!r}")
    runtime_config.set_role(role, body.spec or "")
    return {"roles": gateway.roles_status()}
