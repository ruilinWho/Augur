"""统一 LLM 网关（CLAUDE.md §6）：一切走 litellm，模型来自**可动态增删的连接列表**。

每个角色（chat/deep_research/summarize/cheap）指到一个**连接** `{name, base_url, api_key, model}`
（在「设置 · 模型」里增删/指派，存 runtime_config）。连接一律按 **OpenAI 兼容**调用
（litellm `model="openai/<model>"` + `api_base` + `api_key`）——覆盖 DeepSeek / 中转站 /
OpenRouter / 国产模型 / OpenAI 本身。原生 Anthropic 走中转站即可（主人现状）。
"""

from __future__ import annotations

import time
from collections.abc import Iterator

import litellm

from .. import runtime_config

litellm.drop_params = True  # 忽略个别厂商不支持的参数

ROLES = ("chat", "deep_research", "summarize", "cheap")


class LLMNotConfigured(RuntimeError):
    """角色未指连接 / 连接缺 key/base/model。"""


def _conn_for_role(role: str) -> dict:
    if role not in ROLES:
        raise LLMNotConfigured(f"未知角色 {role!r}")
    conn = runtime_config.get_connection(runtime_config.get_role_target(role))
    if not conn:
        raise LLMNotConfigured(f"角色 {role!r} 未指定连接（到「设置 · 模型」配）")
    for field, label in (("model", "model"), ("api_key", "api_key"), ("base_url", "base_url")):
        if not conn.get(field):
            raise LLMNotConfigured(f"连接「{conn.get('name') or '?'}」缺 {label}")
    return conn


def _kwargs(conn: dict) -> dict:
    return {
        "model": f"openai/{conn['model']}",  # 一律 OpenAI 兼容
        "api_key": conn["api_key"],
        "api_base": conn["base_url"],
    }


def resolve_role(role: str) -> tuple[str, str]:
    """→ (连接名, model)。供日志/落库取 model 名用。"""
    conn = _conn_for_role(role)
    return conn.get("name", ""), conn.get("model", "")


def stream_chat(messages: list[dict], role: str = "chat") -> Iterator[str]:
    """流式返回文本增量（面向用户总是流式，§6）。"""
    kwargs = _kwargs(_conn_for_role(role))
    for chunk in litellm.completion(messages=messages, stream=True, **kwargs):
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def complete(messages: list[dict], role: str = "summarize", **extra) -> str:
    """非流式补全：返回完整文本。用于批量翻译、相关性、机会识别等内部调用。"""
    kwargs = _kwargs(_conn_for_role(role))
    kwargs.update(extra)
    resp = litellm.completion(messages=messages, stream=False, **kwargs)
    return resp.choices[0].message.content or ""


def check_ready(role: str) -> None:
    """校验角色可用（已指连接 + 连接完整），否则抛 LLMNotConfigured（流式前先调）。"""
    _conn_for_role(role)


def roles_status() -> list[dict]:
    """各角色 → 所指连接 + 是否可用（设置页展示，无需 key 即可调）。"""
    out: list[dict] = []
    for role in ROLES:
        cid = runtime_config.get_role_target(role)
        conn = runtime_config.get_connection(cid)
        ok = bool(conn and conn.get("model") and conn.get("api_key") and conn.get("base_url"))
        out.append(
            {
                "role": role,
                "connection_id": cid,
                "connection_name": conn.get("name") if conn else None,
                "configured": ok,
            }
        )
    return out


def test_connection(base_url: str, api_key: str, model: str) -> dict:
    """发个极小请求验证连接是否可用。→ {ok, latency_ms, reply} 或 {ok:false, error}。"""
    if not (base_url and api_key and model):
        return {"ok": False, "error": "base_url / api_key / model 不能为空"}
    try:
        t0 = time.monotonic()
        resp = litellm.completion(
            model=f"openai/{model}",
            api_key=api_key,
            api_base=base_url,
            messages=[{"role": "user", "content": "ping (reply with: ok)"}],
            max_tokens=8,
            timeout=20,
        )
        dt = int((time.monotonic() - t0) * 1000)
        reply = (resp.choices[0].message.content or "").strip()
        return {"ok": True, "latency_ms": dt, "reply": reply[:60]}
    except Exception as e:  # noqa: BLE001 — 任何失败都回给前端展示
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
