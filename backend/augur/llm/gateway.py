"""统一 LLM 网关（CLAUDE.md §6）：一切走 litellm。

角色（chat/deep_research/summarize/cheap）→ "provider:model"（在 .env 配置）。
厂商是配置出来的：已知厂商用 litellm 原生前缀；未知厂商按 OpenAI 兼容处理，
base_url 取 <PROVIDER>_BASE_URL —— 支持任意中转站。
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import litellm

from ..config import get_settings

litellm.drop_params = True  # 忽略个别厂商不支持的参数

# 已知厂商 → {litellm 前缀, key 环境变量, base_url 环境变量}
PROVIDERS: dict[str, dict[str, str]] = {
    "anthropic": {
        "prefix": "anthropic",
        "key_env": "ANTHROPIC_API_KEY",
        "base_env": "ANTHROPIC_BASE_URL",
    },
    "openai": {"prefix": "openai", "key_env": "OPENAI_API_KEY", "base_env": "OPENAI_BASE_URL"},
    "deepseek": {
        "prefix": "deepseek",
        "key_env": "DEEPSEEK_API_KEY",
        "base_env": "DEEPSEEK_BASE_URL",
    },
    "relay": {"prefix": "openai", "key_env": "RELAY_API_KEY", "base_env": "RELAY_BASE_URL"},
}

_ROLE_ATTR = {
    "chat": "role_chat",
    "deep_research": "role_deep_research",
    "summarize": "role_summarize",
    "cheap": "role_cheap",
}


class LLMNotConfigured(RuntimeError):
    """角色未配置 / 厂商缺 API key。"""


def _provider_cfg(provider: str) -> dict[str, str]:
    if provider in PROVIDERS:
        return PROVIDERS[provider]
    # 未知厂商：按 OpenAI 兼容中转处理
    return {
        "prefix": "openai",
        "key_env": f"{provider.upper()}_API_KEY",
        "base_env": f"{provider.upper()}_BASE_URL",
    }


def resolve_role(role: str) -> tuple[str, str]:
    attr = _ROLE_ATTR.get(role)
    if attr is None:
        raise LLMNotConfigured(f"未知角色 {role!r}")
    spec = getattr(get_settings(), attr, "")
    if not spec or ":" not in spec:
        raise LLMNotConfigured(
            f"角色 {role!r} 未配置（设 AUGUR_ROLE_{role.upper()}=provider:model）"
        )
    provider, _, model = spec.partition(":")
    return provider.strip(), model.strip()


def _build_kwargs(role: str) -> dict[str, str]:
    provider, model = resolve_role(role)
    cfg = _provider_cfg(provider)
    api_key = os.getenv(cfg["key_env"])
    if not api_key:
        raise LLMNotConfigured(f"厂商 {provider!r} 缺 API key（设 {cfg['key_env']}）")
    kwargs = {"model": f"{cfg['prefix']}/{model}", "api_key": api_key}
    base = os.getenv(cfg["base_env"])
    if base:
        kwargs["api_base"] = base
    return kwargs


def stream_chat(messages: list[dict], role: str = "chat") -> Iterator[str]:
    """流式返回文本增量（面向用户总是流式，§6）。"""
    kwargs = _build_kwargs(role)
    for chunk in litellm.completion(messages=messages, stream=True, **kwargs):
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def complete(messages: list[dict], role: str = "summarize", **extra) -> str:
    """非流式补全：返回完整文本。用于批量翻译、投资机会识别等需要整段结果的内部调用。"""
    kwargs = _build_kwargs(role)
    kwargs.update(extra)
    resp = litellm.completion(messages=messages, stream=False, **kwargs)
    return resp.choices[0].message.content or ""


def check_ready(role: str) -> None:
    """校验角色可用（已配置 + 有 key），否则抛 LLMNotConfigured（流式前先调）。"""
    _build_kwargs(role)


def roles_status() -> list[dict]:
    """各角色的配置状态（无需 key 即可调用，用于设置页展示）。"""
    settings = get_settings()
    out: list[dict] = []
    for role, attr in _ROLE_ATTR.items():
        spec = getattr(settings, attr, "")
        provider = model = None
        configured = False
        if spec and ":" in spec:
            provider, _, model = (p.strip() for p in spec.partition(":"))
            configured = bool(os.getenv(_provider_cfg(provider)["key_env"]))
        out.append({"role": role, "provider": provider, "model": model, "configured": configured})
    return out
