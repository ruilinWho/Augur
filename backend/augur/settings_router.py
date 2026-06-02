"""「设置」域 HTTP 路由：UI 里配 LLM 连接（动态列表）/ 角色路由 / 数据信源 key。

护栏（§11）：密钥经 `runtime_config` 落 gitignored `data/config.local.json`，**只回脱敏状态**、
从不回明文、绝不打日志。数据信源 secret 仅接受**凭证形状**的 env 名（白名单 + 后缀模式）。
LLM 连接的 base_url/model 非密可回显；api_key 只回布尔/脱敏。改动即时生效。
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from . import runtime_config
from .llm import gateway
from .news import source_registry

router = APIRouter(prefix="/settings", tags=["settings"])

# 数据信源 secret 允许的 env 名：注册表用到的，或形如 *_API_KEY/_BASE_URL/_KEY/_TOKEN/_SECRET/_URL
_NAME_OK = re.compile(r"^[A-Z][A-Z0-9_]*(_API_KEY|_BASE_URL|_KEY|_TOKEN|_SECRET|_URL)$")


def _allowed_names() -> set[str]:
    return {s["key_env"] for s in source_registry.SOURCES if s.get("key_env")}


# ───────────────────────── 快照 ─────────────────────────
@router.get("/config")
async def get_config() -> dict:
    """设置页快照：LLM 连接列表 + 角色路由 + 数据信源状态（全脱敏，无明文 key）。"""
    return {
        "llm": {
            "connections": runtime_config.list_connections(),
            "roles": gateway.roles_status(),
        },
        "sources": source_registry.status_list(),
    }


# ───────────────────────── LLM 连接 ─────────────────────────
class ConnIn(BaseModel):
    id: str | None = None
    name: str = ""
    base_url: str = ""
    api_key: str | None = None  # 留空＝不改已存的 key
    model: str = ""


@router.post("/llm/connection")
async def upsert_connection(body: ConnIn) -> dict:
    """新增/更新一个 LLM 连接（OpenAI 兼容：name/base_url/api_key/model）。返回 id。"""
    cid = await run_in_threadpool(runtime_config.upsert_connection, body.model_dump())
    return {"id": cid}


@router.delete("/llm/connection/{cid}", status_code=204)
async def delete_connection(cid: str) -> None:
    """删除一个连接（并解除任何指向它的角色）。"""
    await run_in_threadpool(runtime_config.delete_connection, cid)


class RoleIn(BaseModel):
    role: str
    connection_id: str | None = None  # None/空＝解除


@router.post("/llm/role")
async def set_role(body: RoleIn) -> dict:
    """把某角色指到某连接（或解除）。"""
    if body.role not in runtime_config.ROLES:
        raise HTTPException(status_code=422, detail=f"未知角色 {body.role!r}")
    await run_in_threadpool(runtime_config.set_role_target, body.role, body.connection_id)
    return {"roles": gateway.roles_status()}


class TestIn(BaseModel):
    connection_id: str | None = None  # 给了就用其存储值兜底（key 留空＝用已存）
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None


@router.post("/llm/test")
async def test_connection(body: TestIn) -> dict:
    """测试连接：发个极小请求验证通不通（带延迟/报错）。"""
    base = (body.base_url or "").strip()
    key = (body.api_key or "").strip()
    model = (body.model or "").strip()
    if body.connection_id:
        stored = runtime_config.get_connection(body.connection_id) or {}
        base = base or stored.get("base_url", "")
        key = key or stored.get("api_key", "")
        model = model or stored.get("model", "")
    return await run_in_threadpool(gateway.test_connection, base, key, model)


# ───────────────────────── 数据信源 key ─────────────────────────
class SecretIn(BaseModel):
    name: str
    value: str | None = None  # 空/None = 清除


@router.post("/secret")
async def set_secret(body: SecretIn) -> dict:
    """设置/清除一个数据信源 API key（写 gitignored 本地存储，即时生效）。"""
    name = (body.name or "").strip()
    if not (_NAME_OK.match(name) or name in _allowed_names()):
        raise HTTPException(status_code=400, detail=f"不允许的配置项名：{name!r}")
    runtime_config.set_secret(name, body.value)
    return {
        "name": name,
        "configured": runtime_config.has_secret(name),
        "hint": runtime_config.secret_hint(name),
    }
