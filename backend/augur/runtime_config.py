"""运行时可配置项的本地存储：LLM 连接列表 / 角色路由 / 数据信源 key——供「设置」页 UI 改。

护栏（CLAUDE.md §11）：**密钥永不入 git、永不打日志**。存 gitignored `data/config.local.json`
（0600）。作者明确要求**本地单用户「设置」UI 直接回显明文 key**（"反正只有我自己用"）——故
GET 会带明文，仅在 localhost 后端↔前端间流动；硬护栏（不入 git/日志）不变。

LLM 模型 = **可动态增删的连接列表**：每个连接 `{id, name, base_url, api_key, model}`（一律按
OpenAI 兼容，覆盖 DeepSeek / 中转站 / OpenRouter / 国产模型）。4 个角色
chat/deep_research/summarize/cheap 各指到一个连接。首次加载若无连接，**自动从旧 `.env`
（AUGUR_ROLE_* + 厂商 key）迁成连接**，不中断作者现有配置。

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
    """明文取某数据信源 key——**仅供本地单用户「设置」UI 回显**（作者明确要求直接看原文）。

    护栏不变：key 只在 localhost 后端↔前端间流动，**永不打日志、永不入 git**（data/ 被忽略）。
    """
    return _raw_secret(name)


# ───────────────────────── API 配置一键导出/导入（分享给 contributor）─────────────────────────
def export_api_config() -> dict:
    """导出全部 API 配置（LLM 连接 + 角色路由 + 数据信源 secret）为可分享 JSON。

    单用户本地工具：**明文**导出（作者明确「只有我自己用」），用于把整套配置发给 contributor
    一键导入、快速迭代。护栏不变：永不打日志、永不入 git。
    """
    data = _read()
    return {
        "_augur_config": "api-keys-v1",
        "llm_connections": data.get("llm_connections") or [],
        "llm_roles": data.get("llm_roles") or {},
        "secrets": data.get("secrets") or {},
    }


def import_api_config(payload: dict) -> dict:
    """从导出 JSON 导入：覆盖 LLM 连接/角色路由、合并数据信源 secret，其余本地设置保留。

    导入后立即把 secret 注入 os.environ（各适配器即时可用）。返回 {connections, secrets} 计数。
    """
    if not isinstance(payload, dict):
        raise ValueError("配置文件格式不对（应为 JSON 对象）")
    has_any = any(
        isinstance(payload.get(k), (list, dict))
        for k in ("llm_connections", "llm_roles", "secrets")
    )
    if not has_any:
        raise ValueError("这个文件里没有可导入的 API 配置（llm_connections / secrets）")
    with _lock:
        data = _read()
        if isinstance(payload.get("llm_connections"), list):
            data["llm_connections"] = payload["llm_connections"]
        if isinstance(payload.get("llm_roles"), dict):
            data["llm_roles"] = payload["llm_roles"]
        if isinstance(payload.get("secrets"), dict):
            merged = data.get("secrets") or {}
            merged.update({k: str(v) for k, v in payload["secrets"].items() if v})
            data["secrets"] = merged
        _write(data)
        for k, v in (data.get("secrets") or {}).items():
            if v:
                os.environ[k] = str(v)
        return {
            "connections": len(data.get("llm_connections") or []),
            "secrets": len(data.get("secrets") or {}),
        }


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


def reorder_connections(ordered_ids: list[str]) -> None:
    """按给定 id 顺序重排连接列表（未列出的保持原相对序、附在末尾，防丢）。"""
    with _lock:
        data = _read()
        conns = data.get("llm_connections") or []
        by_id = {c.get("id"): c for c in conns}
        seen: set[str] = set()
        new: list[dict] = []
        for cid in ordered_ids:
            c = by_id.get(cid)
            if c is not None and cid not in seen:
                new.append(c)
                seen.add(cid)
        for c in conns:  # 任何未被列出的连接（防丢）原序补在后面
            if c.get("id") not in seen:
                new.append(c)
        data["llm_connections"] = new
        _write(data)


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


# ───────────────────────── 应用偏好（非密钥的普通设置）─────────────────────────
# data["prefs"][key] = JSON 可序列化值。供「设置」UI 改调度等非密钥项；gitignored、即时生效。
def get_pref(key: str, default=None):
    return (_read().get("prefs") or {}).get(key, default)


def set_pref(key: str, value) -> None:
    with _lock:
        data = _read()
        data.setdefault("prefs", {})[key] = value
        _write(data)


# 白天自动「全部生成」（刷新+蒸馏）的调度配置。作者可在「设置 · 自动」里改。
# 默认：开启、11:00–23:00 每个整点跑一次（作者指定）。end 含端点。
_AUTO_REFRESH_DEFAULT = {"enabled": True, "start_hour": 11, "end_hour": 23}


def _is_int(v) -> bool:
    # bool 是 int 的子类——排除它，否则 JSON 里手写的 start_hour:true 会被当成 1 混进来
    return isinstance(v, int) and not isinstance(v, bool)


def get_auto_refresh() -> dict:
    """读自动刷新配置（缺字段回退默认，read-with-fallback、非破坏式）。"""
    cur = get_pref("auto_refresh") or {}
    out = dict(_AUTO_REFRESH_DEFAULT)
    if isinstance(cur.get("enabled"), bool):
        out["enabled"] = cur["enabled"]
    for k in ("start_hour", "end_hour"):
        if _is_int(cur.get(k)):
            out[k] = cur[k]
    return out


def set_auto_refresh(patch: dict) -> dict:
    """合并更新自动刷新配置（只认已知字段、夹紧小时范围）。返回最新完整配置。"""
    cur = get_auto_refresh()
    if "enabled" in patch:
        cur["enabled"] = bool(patch["enabled"])
    for k in ("start_hour", "end_hour"):
        if k in patch and _is_int(patch[k]):
            cur[k] = max(0, min(23, patch[k]))
    if cur["start_hour"] > cur["end_hour"]:  # 防呆：起>止则对调
        cur["start_hour"], cur["end_hour"] = cur["end_hour"], cur["start_hour"]
    set_pref("auto_refresh", cur)
    return cur


# 「要事/机会」单次喂给 LLM 的当日条目上限（日报不受此限）。默认 1000；0=不限。
_CLUSTER_MAX_DEFAULT = 1000


def get_cluster_input_max() -> int:
    """读蒸馏条数上限（默认 1000；0=不限）。非法值回退默认。"""
    n = get_pref("cluster_input_max")
    if _is_int(n) and n >= 0:
        return min(n, 20000)  # 给个极宽的安全上界，防手写配置写出天文数字撑爆上下文
    return _CLUSTER_MAX_DEFAULT


def set_cluster_input_max(n: int) -> int:
    """设蒸馏条数上限（0=不限；正值夹紧到 [50, 20000]）。返回落库值。"""
    if not _is_int(n) or n < 0:
        n = _CLUSTER_MAX_DEFAULT
    elif n > 0:
        n = max(50, min(n, 20000))
    set_pref("cluster_input_max", n)
    return n


# 「今日要事」(晨读 Top) 显示条数。默认 5（原写死 3，作者要可配）。
_BRIEF_TOP_DEFAULT = 5


def get_brief_top_n() -> int:
    """读今日要事显示条数（默认 5）。非法值回退默认。"""
    n = get_pref("brief_top_n")
    if _is_int(n) and n >= 1:
        return min(n, 50)
    return _BRIEF_TOP_DEFAULT


def set_brief_top_n(n: int) -> int:
    """设今日要事显示条数（夹紧到 [1, 50]）。返回落库值。"""
    n = _BRIEF_TOP_DEFAULT if not _is_int(n) else max(1, min(n, 50))
    set_pref("brief_top_n", n)
    return n


# 「社媒热度」(资讯·总结/决策的 social_pulse) 每平台显示条数。默认 4。
_SOCIAL_PULSE_DEFAULT = 4


def get_social_pulse_n() -> int:
    """读社媒热度每平台条数（默认 4）。非法值回退默认。"""
    n = get_pref("social_pulse_n")
    if _is_int(n) and n >= 1:
        return min(n, 20)
    return _SOCIAL_PULSE_DEFAULT


def set_social_pulse_n(n: int) -> int:
    """设社媒热度每平台条数（夹紧到 [1, 20]）。返回落库值。"""
    n = _SOCIAL_PULSE_DEFAULT if not _is_int(n) else max(1, min(n, 20))
    set_pref("social_pulse_n", n)
    return n


# 「寻」每个候选展示的证据新闻条数。默认 6。
_DISCOVERY_NEWS_DEFAULT = 6


def get_discovery_news_n() -> int:
    """读寻·每候选证据条数（默认 6）。非法值回退默认。"""
    n = get_pref("discovery_news_n")
    if _is_int(n) and n >= 1:
        return min(n, 30)
    return _DISCOVERY_NEWS_DEFAULT


def set_discovery_news_n(n: int) -> int:
    """设寻·每候选证据条数（夹紧到 [1, 30]）。返回落库值。"""
    n = _DISCOVERY_NEWS_DEFAULT if not _is_int(n) else max(1, min(n, 30))
    set_pref("discovery_news_n", n)
    return n


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
