"""运行时可配置项的本地存储：API key / base_url / LLM 角色路由——供「设置」页在 UI 里改。

护栏（CLAUDE.md §11）：**密钥永不入库**。存到 gitignored 的 `data/config.local.json`
（文件权限 0600），**绝不打日志**，GET 只回脱敏状态（末 4 位），POST 从不回传明文。
加载时把 secrets 注入 `os.environ`，使 litellm/gateway 与各信源适配器在**不重启**下即时读到
（它们都走 `os.getenv`）。`.env` 仍支持：进程启动时 .env 已在 env 里；UI 存的值会覆盖之
（UI 优先，便于即时改）。单用户本地工具，读文件成本可忽略，故每次读盘取最新值。
"""

from __future__ import annotations

import json
import os
import threading

from .config import get_settings

_lock = threading.Lock()


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


def load() -> None:
    """启动时调用：把已存 secrets 注入 os.environ（UI 优先于 .env，即时生效）。"""
    with _lock:
        for k, v in (_read().get("secrets") or {}).items():
            if v:
                os.environ[k] = str(v)


def get_role(role: str) -> str | None:
    """UI 设的角色路由（provider:model）；未设 → None（gateway 回退 settings.role_*）。"""
    return (_read().get("roles") or {}).get(role) or None


def set_role(role: str, spec: str) -> None:
    with _lock:
        data = _read()
        roles = data.setdefault("roles", {})
        if spec.strip():
            roles[role] = spec.strip()
        else:
            roles.pop(role, None)
        _write(data)


def set_secret(name: str, value: str | None) -> None:
    """写入/清除一个密钥（即时注入/移除 os.environ）。value 空 → 清除。"""
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
    """脱敏提示：末 4 位，从不回传明文。空 → ''。"""
    v = _raw_secret(name)
    return f"····{v[-4:]}" if len(v) >= 4 else ("已配置" if v else "")
