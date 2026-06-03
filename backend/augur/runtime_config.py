"""运行时可配置项的本地存储：LLM 连接列表 / 角色路由 / 数据信源 key——供「设置」页 UI 改。

护栏（CLAUDE.md §11）：**密钥永不入 git、永不打日志**。存 gitignored `data/config.local.json`
（0600）。主人明确要求**本地单用户「设置」UI 直接回显明文 key**（"反正只有我自己用"）——故
GET 会带明文，仅在 localhost 后端↔前端间流动；硬护栏（不入 git/日志）不变。

LLM 模型 = **可动态增删的连接列表**：每个连接 `{id, name, base_url, api_key, model}`（一律按
OpenAI 兼容，覆盖 DeepSeek / 中转站 / OpenRouter / 国产模型）。4 个角色
chat/deep_research/summarize/cheap 各指到一个连接。首次加载若无连接，**自动从旧 `.env`
（AUGUR_ROLE_* + 厂商 key）迁成连接**，不中断主人现有配置。

数据信源 key（X 桥等）仍走 `secrets`：加载时注入 `os.environ`，使各适配器 `os.getenv`
在不重启下即时可见。单用户本地工具，读文件成本可忽略，每次读盘取最新值。
"""

from __future__ import annotations

import json
import os
import threading
from uuid import uuid4

from .config import get_settings

_lock = threading.Lock()
ROLES = ("chat", "deep_research", "summarize", "cheap")

# 旧固定厂商 → (key_env, base_env, 默认 base)；仅一次性迁移用
_LEGACY_ENV = {
    "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
    "openai": ("OPENAI_API_KEY", "OPENAI_BASE_URL", "https://api.openai.com/v1"),
    "deepseek": ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    "relay": ("RELAY_API_KEY", "RELAY_BASE_URL", ""),
}


def _path():
    return get_settings().data_dir / "config.local.json"


def _read() -> dict:
    p = _path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")) or {}
    except (json.JSONDecodeError, OSError):
        return {}


def _write(data: dict) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)
    try:
        p.chmod(0o600)  # 仅本人可读（含密钥）
    except OSError:
        pass


def _hint(v: str) -> str:
    """脱敏：末 4 位；从不回明文。"""
    v = str(v or "")
    return f"····{v[-4:]}" if len(v) >= 4 else ("已配置" if v else "")


# ───────────────────────── 一次性迁移：旧 roles → 连接 ─────────────────────────
def _seed_from_legacy(data: dict) -> bool:
    """无 llm_connections 时，从旧 roles(provider:model)+厂商 env/secrets 迁成连接。写了→True。"""
    if data.get("llm_connections") is not None:
        return False
    s = get_settings()
    old_roles = data.get("roles") or {}
    secrets = data.get("secrets") or {}
    conns: list[dict] = []
    role_map: dict[str, str] = {}
    by_sig: dict[tuple, str] = {}
    for role in ROLES:
        spec = old_roles.get(role) or getattr(s, f"role_{role}", "")
        if not spec or ":" not in spec:
            continue
        provider, _, model = (x.strip() for x in spec.partition(":"))
        key_env, base_env, default_base = _LEGACY_ENV.get(
            provider, (f"{provider.upper()}_API_KEY", f"{provider.upper()}_BASE_URL", "")
        )
        api_key = os.getenv(key_env) or secrets.get(key_env) or ""
        base = os.getenv(base_env) or secrets.get(base_env) or default_base
        sig = (base, model, api_key)
        if sig in by_sig:
            role_map[role] = by_sig[sig]
            continue
        cid = uuid4().hex[:8]
        conns.append(
            {
                "id": cid,
                "name": f"{provider} · {model}"[:48],
                "base_url": base,
                "api_key": api_key,
                "model": model,
            }
        )
        by_sig[sig] = cid
        role_map[role] = cid
    data["llm_connections"] = conns  # 即便为空也写，标记"已迁移"，避免每次启动重试
    data["llm_roles"] = role_map
    data.pop("roles", None)
    return True


def load() -> None:
    """启动时：注入数据信源 secrets 到 os.environ；首次把旧 LLM 配置迁成连接。"""
    with _lock:
        data = _read()
        for k, v in (data.get("secrets") or {}).items():
            if v:
                os.environ[k] = str(v)
        if _seed_from_legacy(data):
            _write(data)


# ───────────────────────── 数据信源 secrets（X 桥等）─────────────────────────
def set_secret(name: str, value: str | None) -> None:
    with _lock:
        data = _read()
        secrets = data.setdefault("secrets", {})
        if value and value.strip():
            secrets[name] = value.strip()
            os.environ[name] = value.strip()
        else:
            secrets.pop(name, None)
            os.environ.pop(name, None)
        _write(data)


def _raw_secret(name: str) -> str:
    return str(os.getenv(name) or (_read().get("secrets") or {}).get(name) or "")


def has_secret(name: str) -> bool:
    return bool(_raw_secret(name))


def secret_hint(name: str) -> str:
    return _hint(_raw_secret(name))


def get_secret(name: str) -> str:
    """明文取某数据信源 key——**仅供本地单用户「设置」UI 回显**（主人明确要求直接看原文）。

    护栏不变：key 只在 localhost 后端↔前端间流动，**永不打日志、永不入 git**（data/ 被忽略）。
    """
    return _raw_secret(name)


# ───────────────────────── LLM 连接（动态列表）─────────────────────────
def list_connections() -> list[dict]:
    """脱敏的连接列表（不含明文 key）。"""
    out: list[dict] = []
    for c in _read().get("llm_connections") or []:
        out.append(
            {
                "id": c.get("id"),
                "name": c.get("name", ""),
                "base_url": c.get("base_url", ""),
                "model": c.get("model", ""),
                "key_configured": bool(c.get("api_key")),
                "key_hint": _hint(c.get("api_key", "")),
                "api_key": c.get("api_key", ""),  # 明文回显（仅本地单用户 UI；不入日志/git）
                "web_search": bool(c.get("web_search")),  # 联网检索（Qwen enable_search 等）
            }
        )
    return out


def get_connection(cid: str | None) -> dict | None:
    """完整连接（含 api_key）——仅 gateway 内部用。"""
    if not cid:
        return None
    for c in _read().get("llm_connections") or []:
        if c.get("id") == cid:
            return c
    return None


def upsert_connection(payload: dict) -> str:
    """新增/更新一个连接（api_key 留空＝不改已存的）。返回 id。"""
    with _lock:
        data = _read()
        conns = data.setdefault("llm_connections", [])
        cid = (payload.get("id") or "").strip()
        cur = next((c for c in conns if c.get("id") == cid), None) if cid else None
        if cur is None:
            cid = uuid4().hex[:8]
            cur = {"id": cid, "name": "", "base_url": "", "api_key": "", "model": ""}
            conns.append(cur)
        cur["name"] = (payload.get("name") or cur.get("name") or "未命名").strip()
        if payload.get("base_url") is not None:
            cur["base_url"] = str(payload["base_url"]).strip()
        if payload.get("model") is not None:
            cur["model"] = str(payload["model"]).strip()
        if payload.get("api_key"):  # 留空＝不改
            cur["api_key"] = str(payload["api_key"]).strip()
        if payload.get("web_search") is not None:
            cur["web_search"] = bool(payload["web_search"])
        _write(data)
        return cid


def delete_connection(cid: str) -> None:
    with _lock:
        data = _read()
        data["llm_connections"] = [
            c for c in (data.get("llm_connections") or []) if c.get("id") != cid
        ]
        roles = data.get("llm_roles") or {}
        for r in list(roles):
            if roles[r] == cid:
                roles.pop(r)
        _write(data)


# ───────────────────────── 信源可配置项（账户 / 关键词 等）─────────────────────────
# 通用：data["source_config"][<source_id>][<field>] = 值（list/str…，JSON 可序列化）。
# 未设 → 适配器用内置默认（read-with-fallback，非破坏式）。gitignored、即时生效。
def get_source_config(source_id: str, field: str, default=None):
    sc = (_read().get("source_config") or {}).get(source_id) or {}
    v = sc.get(field)
    return v if v is not None else default


def set_source_config(source_id: str, field: str, value) -> None:
    with _lock:
        data = _read()
        sc = data.setdefault("source_config", {})
        sc.setdefault(source_id, {})[field] = value
        _write(data)


def get_role_target(role: str) -> str | None:
    return (_read().get("llm_roles") or {}).get(role)


def set_role_target(role: str, cid: str | None) -> None:
    with _lock:
        data = _read()
        roles = data.setdefault("llm_roles", {})
        if cid:
            roles[role] = cid
        else:
            roles.pop(role, None)
        _write(data)
