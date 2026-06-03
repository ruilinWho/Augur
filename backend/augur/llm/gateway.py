"""统一 LLM 网关（CLAUDE.md §6）：一切走 litellm，模型来自**可动态增删的连接列表**。

每个角色（chat/deep_research/summarize/cheap）指到一个**连接** `{name, base_url, api_key, model}`
（在「设置 · 模型」里增删/指派，存 runtime_config）。连接一律按 **OpenAI 兼容**调用
（litellm `model="openai/<model>"` + `api_base` + `api_key`）——覆盖 DeepSeek / 中转站 /
OpenRouter / 国产模型 / OpenAI 本身。原生 Anthropic 走中转站即可（主人现状）。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator

import litellm

from .. import runtime_config
from ..storage import get_conn

litellm.drop_params = True  # 忽略个别厂商不支持的参数
# §11 硬护栏：key 绝不进日志。显式关掉 litellm 的 verbose/debug（默认通常静默，但不依赖默认）。
litellm.suppress_debug_info = True
logging.getLogger("LiteLLM").setLevel(logging.WARNING)

ROLES = ("chat", "deep_research", "summarize", "cheap")
# 联网检索只注入到这些角色：研·Deep Research / 用户对话。cheap(翻译/相关性)、summarize(日报/
# 聚类/机会) 是内部批量调用，不需要联网——注入只会变慢、增 token、触发无谓搜索（§6：联网仅供
# 研·Deep Research 与 知·个股·信源调研）。故即便连接开了 web_search，这两个角色也不注入。
_WEB_SEARCH_ROLES = {"deep_research", "chat"}


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


def _kwargs(conn: dict, role: str = "") -> dict:
    kw = {
        "model": f"openai/{conn['model']}",  # 一律 OpenAI 兼容
        "api_key": conn["api_key"],
        "api_base": conn["base_url"],
    }
    # 联网检索（连接级开关 × 角色白名单）：Qwen/百炼 OpenAI 兼容用 extra_body.enable_search；
    # search_strategy=max（全面，可改 agent 多轮）。其他厂商若不识别，会被服务端忽略/报错——
    # 故该开关只该开在支持联网的连接上（设置页提示）。且只在研/对话角色注入（_WEB_SEARCH_ROLES）。
    if conn.get("web_search") and role in _WEB_SEARCH_ROLES:
        kw["extra_body"] = {
            "enable_search": True,
            "search_options": {"search_strategy": "max", "forced_search": True},
        }
    return kw


def resolve_role(role: str) -> tuple[str, str]:
    """→ (连接名, model)。供日志/落库取 model 名用。"""
    conn = _conn_for_role(role)
    return conn.get("name", ""), conn.get("model", "")


def stream_chat(messages: list[dict], role: str = "chat") -> Iterator[str]:
    """流式返回文本增量（面向用户总是流式，§6）。末尾把 token 用量落库。"""
    conn = _conn_for_role(role)
    kwargs = _kwargs(conn, role)
    usage = None
    # include_usage：让兼容 OpenAI 的厂商在末 chunk 带回 usage（不支持的会被 drop_params 忽略）
    for chunk in litellm.completion(
        messages=messages, stream=True, stream_options={"include_usage": True}, **kwargs
    ):
        if getattr(chunk, "usage", None):
            usage = chunk.usage  # 末尾 usage-only chunk（其 choices 为空）
        if chunk.choices:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    if usage is not None:
        pt = getattr(usage, "prompt_tokens", None)
        ct = getattr(usage, "completion_tokens", None)
        _record_usage(role, conn, pt, ct, _cost(kwargs.get("model"), pt, ct))


def complete(messages: list[dict], role: str = "summarize", **extra) -> str:
    """非流式补全：返回完整文本。用于批量翻译、相关性、机会识别等内部调用。落库 token 用量。"""
    conn = _conn_for_role(role)
    kwargs = _kwargs(conn, role)
    kwargs.update(extra)
    resp = litellm.completion(messages=messages, stream=False, **kwargs)
    usage = getattr(resp, "usage", None)
    pt = getattr(usage, "prompt_tokens", None) if usage else None
    ct = getattr(usage, "completion_tokens", None) if usage else None
    _record_usage(role, conn, pt, ct, _cost(kwargs.get("model"), pt, ct, resp))
    return resp.choices[0].message.content or ""


def _cost(model: str | None, pt: int | None, ct: int | None, resp=None) -> float | None:
    """尽力估算美元成本（litellm 价表覆盖时）；中转/国产模型多半算不出 → None（仍记 token）。"""
    try:
        if resp is not None:
            return litellm.completion_cost(completion_response=resp)
        return litellm.completion_cost(
            model=model, prompt_tokens=pt or 0, completion_tokens=ct or 0
        )
    except Exception:  # noqa: BLE001 — 估价失败不阻断、不影响记 token
        return None


def _record_usage(
    role: str, conn: dict, pt: int | None, ct: int | None, cost: float | None
) -> None:
    """把一次调用的 token 用量落库（§6「总是把 token 用量记到 data/db 以便看成本」）。
    任何失败只静默跳过——记账绝不影响主流程（同 news 的 _record_health 容错风格）。
    """
    if pt is None and ct is None:
        return
    try:
        db = get_conn()
        try:
            db.execute(
                "INSERT INTO llm_usage "
                "(role, provider, model, prompt_tokens, completion_tokens, cost_usd) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (role, conn.get("name", ""), conn.get("model", ""), pt, ct, cost),
            )
            db.commit()
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        pass


def usage_summary(days: int = 30) -> dict:
    """最近 days 天的 token 用量按 角色/模型 聚合（设置页看成本）。"""
    db = get_conn()
    try:
        since = (f"-{int(days)} days",)
        rows = db.execute(
            "SELECT role, model, COUNT(*) AS calls, "
            "SUM(COALESCE(prompt_tokens,0)) AS prompt_tokens, "
            "SUM(COALESCE(completion_tokens,0)) AS completion_tokens, "
            "SUM(COALESCE(cost_usd,0)) AS cost_usd "
            "FROM llm_usage WHERE ts >= datetime('now', ?) "
            "GROUP BY role, model ORDER BY (prompt_tokens + completion_tokens) DESC",
            since,
        ).fetchall()
        tot = db.execute(
            "SELECT COUNT(*) AS calls, SUM(COALESCE(prompt_tokens,0)) AS prompt_tokens, "
            "SUM(COALESCE(completion_tokens,0)) AS completion_tokens, "
            "SUM(COALESCE(cost_usd,0)) AS cost_usd "
            "FROM llm_usage WHERE ts >= datetime('now', ?)",
            since,
        ).fetchone()
        return {
            "days": days,
            "total": dict(tot) if tot else {},
            "by_role_model": [dict(r) for r in rows],
        }
    finally:
        db.close()


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
        msg = str(e)[:200]
        if api_key and api_key in msg:  # 部分厂商把 key 片段写进错误体，回前端前脱敏
            msg = msg.replace(api_key, f"····{api_key[-4:]}")
        return {"ok": False, "error": f"{type(e).__name__}: {msg}"}
