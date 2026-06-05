"""「设置」域 HTTP 路由：UI 里配 LLM 连接（动态列表）/ 角色路由 / 数据信源 key。

护栏（§11）：密钥经 `runtime_config` 落 gitignored `data/config.local.json`，**绝不入 git、
绝不打日志**。本地单用户 UI **以明文回显** LLM 连接 api_key 与数据信源 key（作者明确要求
「反正只有我自己用」——key 仅在 localhost 后端↔前端间流动，见 §6）。数据信源 secret 仅接受
**凭证形状**的 env 名（白名单 + 后缀模式）。改动即时生效，无需重启。
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from . import runtime_config
from .llm import gateway
from .news import ingest, source_registry, source_test, sources

router = APIRouter(prefix="/settings", tags=["settings"])

# 数据信源 secret 允许的 env 名：注册表用到的，或形如 *_API_KEY/_BASE_URL/_KEY/_TOKEN/_SECRET/_URL
_NAME_OK = re.compile(r"^[A-Z][A-Z0-9_]*(_API_KEY|_BASE_URL|_KEY|_TOKEN|_SECRET|_URL)$")


def _allowed_names() -> set[str]:
    return {s["key_env"] for s in source_registry.SOURCES if s.get("key_env")}


def _llm_key_url(conn: dict) -> str:
    """按连接名/base/model 猜测 API key 控制台；猜不到就留空，不误导。"""
    base = str(conn.get("base_url", "") or "")
    hay = " ".join(str(conn.get(k, "")) for k in ("name", "base_url", "model")).lower()
    pairs = (
        ("deepseek", "https://platform.deepseek.com/api_keys"),
        ("openrouter", "https://openrouter.ai/keys"),
        ("siliconflow", "https://cloud.siliconflow.cn/account/ak"),
        ("dashscope", "https://bailian.console.aliyun.com/"),
        ("aliyun", "https://bailian.console.aliyun.com/"),
        ("qwen", "https://bailian.console.aliyun.com/"),
        ("bigmodel", "https://bigmodel.cn/usercenter/apikeys"),
        ("zhipu", "https://bigmodel.cn/usercenter/apikeys"),
        ("moonshot", "https://platform.moonshot.cn/console/api-keys"),
        ("kimi", "https://platform.moonshot.cn/console/api-keys"),
        ("openai", "https://platform.openai.com/api-keys"),
    )
    for needle, url in pairs:
        if needle in hay:
            return url
    try:
        u = urlparse(base)
        if u.scheme in {"http", "https"} and u.netloc:
            return f"{u.scheme}://{u.netloc}"
    except Exception:  # noqa: BLE001
        return ""
    return ""


def _diagnose_llm_error(err: str) -> str:
    msg = str(err or "").strip()
    for prefix in (
        "APIConnectionError: ",
        "AuthenticationError: ",
        "RateLimitError: ",
        "BadRequestError: ",
        "Timeout: ",
        "HTTPStatusError: ",
    ):
        if msg.startswith(prefix):
            msg = msg[len(prefix) :].strip()
    low = msg.lower()
    if "不能为空" in msg:
        return "模型连接：base_url / API key / model 还没填完整。"
    if any(x in low for x in ("401", "403", "unauthorized", "invalid api key", "forbidden")):
        return "模型连接：API key 无效，或当前 key 没有调用这个模型的权限。"
    if any(x in low for x in ("402", "insufficient balance", "insufficient quota", "quota")):
        return "模型连接：余额或额度不足，需要充值、升级额度或更换 key。"
    if any(x in low for x in ("429", "rate limit", "too many requests")):
        return "模型连接：频率限制已触发，稍后再试或升级限额。"
    if any(x in low for x in ("timeout", "timed out")):
        return "模型连接：网络连接超时。"
    if any(x in low for x in ("connection", "connect", "dns", "ssl")):
        return "模型连接：base_url 网络不可达，可能是地址、代理或证书问题。"
    if any(x in low for x in ("model", "not found", "does not exist")):
        return "模型连接：模型 id 不存在，或这个 key 没有该模型权限。"
    return f"模型连接：测试失败，{msg}" if msg else "模型连接：测试失败，暂时无法判断具体原因。"


def _state_from_result(result: dict, configured: bool) -> str:
    if result.get("ok"):
        return "ok"
    if not configured:
        return "missing_key"
    msg = str(result.get("error") or "")
    if "还没有接入" in msg or "没有接入" in msg:
        return "not_integrated"
    if "月度额度" in msg or "频率限制" in msg or "限额" in msg:
        return "quota"
    if "余额" in msg or "权限" in msg or "积分" in msg or "套餐" in msg:
        return "permission"
    return "failed"


def _status_for_state(state: str) -> str:
    return {
        "ok": "已接通",
        "missing_key": "未配置",
        "not_integrated": "未接入",
        "quota": "额度受限",
        "permission": "权限 / 余额",
        "failed": "异常",
    }.get(state, "异常")


def _audit_llm_connections() -> list[dict]:
    conns = runtime_config.list_connections()  # 含明文 key，仅用于本地测试；返回值不带 key
    out: list[dict] = []

    def _one(conn: dict) -> dict:
        configured = bool(conn.get("base_url") and conn.get("model") and conn.get("api_key"))
        result = gateway.test_connection(
            conn.get("base_url", ""), conn.get("api_key", ""), conn.get("model", "")
        )
        if not result.get("ok"):
            result["error"] = _diagnose_llm_error(str(result.get("error") or ""))
        state = _state_from_result(result, configured)
        return {
            "id": conn.get("id", ""),
            "kind": "llm",
            "name": conn.get("name") or conn.get("model") or "未命名模型连接",
            "group": "model",
            "configured": configured,
            "status": _status_for_state(state),
            "state": state,
            "base_url": conn.get("base_url", ""),
            "model": conn.get("model", ""),
            "key_url": _llm_key_url(conn),
            "result": result,
        }

    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(_one, c) for c in conns]
        for fut in as_completed(futs):
            out.append(fut.result())
    out.sort(key=lambda x: (x["state"] == "ok", x["name"]))
    return out


def _source_missing_result(s: dict) -> dict:
    label = "登录 token" if s.get("cred") == "token" else "API key"
    return {"ok": False, "error": f"{s['name']}：没有配置{label}。"}


def _audit_sources() -> list[dict]:
    rows = source_registry.status_list()
    out: list[dict] = []

    def _one(s: dict) -> dict:
        configured = bool(s.get("configured"))
        if s.get("key_env") and not configured:
            result = _source_missing_result(s)
        else:
            result = source_test.test_source(s["id"])
        state = _state_from_result(result, configured)
        return {
            "id": s["id"],
            "kind": "source",
            "name": s["name"],
            "group": s.get("group", ""),
            "configured": configured,
            "status": _status_for_state(state),
            "state": state,
            "key_env": s.get("key_env") or "",
            "cred": s.get("cred") or "",
            "key_url": s.get("key_url") or "",
            "docs_url": s.get("docs_url") or "",
            "official_url": s.get("official_url") or "",
            "setup": s.get("setup") or "",
            "best_use": s.get("best_use") or "",
            "boundary": s.get("boundary") or "",
            "result": result,
        }

    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(_one, s) for s in rows]
        for fut in as_completed(futs):
            out.append(fut.result())
    out.sort(key=lambda x: (x["state"] == "ok", x["group"], x["name"]))
    return out


def _summary(llm: list[dict], src: list[dict], health: list[dict]) -> dict:
    items = [*llm, *src]
    states = [x.get("state", "") for x in items]
    bad_health = [
        h
        for h in health
        if h.get("last_fail_at")
        and (not h.get("last_ok_at") or h["last_fail_at"] > h["last_ok_at"])
    ]
    return {
        "total": len(items),
        "ok": states.count("ok"),
        "missing_key": states.count("missing_key"),
        "quota": states.count("quota"),
        "permission": states.count("permission"),
        "not_integrated": states.count("not_integrated"),
        "failed": states.count("failed"),
        "health_sources": len(health),
        "health_failed": len(bad_health),
    }


def _audit_all() -> dict:
    llm = _audit_llm_connections()
    src = _audit_sources()
    health = ingest.source_health()
    return {"llm": llm, "sources": src, "health": health, "summary": _summary(llm, src, health)}


# ───────────────────────── 快照 ─────────────────────────
@router.get("/config")
async def get_config() -> dict:
    """设置页快照：LLM 连接列表 + 角色路由 + 数据信源状态。本地单用户 UI 明文回显 key（§6/§11）。"""
    return {
        "llm": {
            "connections": runtime_config.list_connections(),
            "roles": gateway.roles_status(),
        },
        "sources": source_registry.status_list(),
        "source_groups": source_registry.groups(),
    }


# ───────────────────────── LLM 连接 ─────────────────────────
class ConnIn(BaseModel):
    id: str | None = None
    name: str = ""
    base_url: str = ""
    api_key: str | None = None  # 留空＝不改已存的 key
    model: str = ""
    web_search: bool | None = None  # 联网检索（Qwen enable_search 等）


@router.post("/llm/connection")
async def upsert_connection(body: ConnIn) -> dict:
    """新增/更新一个 LLM 连接（OpenAI 兼容：name/base_url/api_key/model）。返回 id。"""
    cid = await run_in_threadpool(runtime_config.upsert_connection, body.model_dump())
    return {"id": cid}


@router.delete("/llm/connection/{cid}", status_code=204)
async def delete_connection(cid: str) -> None:
    """删除一个连接（并解除任何指向它的角色）。"""
    await run_in_threadpool(runtime_config.delete_connection, cid)


class ReorderIn(BaseModel):
    ordered_ids: list[str]


@router.post("/llm/connections/reorder")
async def reorder_connections(body: ReorderIn) -> dict:
    """按拖拽后的 id 顺序重排连接列表。返回重排后的脱敏列表。"""
    await run_in_threadpool(runtime_config.reorder_connections, body.ordered_ids)
    return {"connections": runtime_config.list_connections()}


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


@router.post("/llm/test-all")
async def test_all_connections() -> dict[str, dict]:
    """并发测试所有连接（各发极小请求）。返回 {连接id: {ok, latency_ms, reply?/error?}}。"""

    def _run() -> dict[str, dict]:
        conns = runtime_config.list_connections()  # 含明文 key（仅本地）
        out: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = {
                ex.submit(gateway.test_connection, c["base_url"], c["api_key"], c["model"]): c["id"]
                for c in conns
            }
            for fut in as_completed(futs):
                out[futs[fut]] = fut.result()
        return out

    return await run_in_threadpool(_run)


@router.post("/test-all")
async def test_everything() -> dict:
    """设置 · 全部：模型连接 + 数据信源 + 最近摄取健康度的一次性体检。"""
    return await run_in_threadpool(_audit_all)


# ───────────────────────── 数据信源 key ─────────────────────────
class SecretIn(BaseModel):
    name: str
    value: str | None = None  # 空/None = 清除


class SourceConfigIn(BaseModel):
    id: str
    field: str
    value: list  # accounts: [{screen_name,category}] · tags: [str]


@router.post("/source/config")
async def set_source_config(body: SourceConfigIn) -> dict:
    """设置某信源的可配置项（账户/关键词等，写 gitignored 本地存储，即时生效）。"""
    fields = source_registry.config_fields(body.id)
    if body.field not in fields:
        raise HTTPException(status_code=400, detail=f"未知信源配置项：{body.id}.{body.field}")
    clean = source_registry.sanitize_config(fields[body.field], body.value)
    await run_in_threadpool(runtime_config.set_source_config, body.id, body.field, clean)
    if body.id == "bloomberg":
        sources.load_feeds.cache_clear()
    return {"id": body.id, "field": body.field, "value": clean}


@router.post("/source/test")
async def test_source(id: str) -> dict:
    """测试某数据信源是否可用（轻量真实探活）。→ {ok, latency_ms, count?, note?} | {ok:false}。"""
    return await run_in_threadpool(source_test.test_source, id)


@router.post("/source/test-all")
async def test_all_sources() -> list[dict]:
    """批量测试所有登记信源；缺 key 的源不打外网，直接标未配置。"""
    return await run_in_threadpool(_audit_sources)


# ───────────────────────── 自动刷新调度（白天每小时「全部生成」）─────────────────────────
class ScheduleIn(BaseModel):
    enabled: bool | None = None
    start_hour: int | None = None
    end_hour: int | None = None
    cluster_input_max: int | None = None  # 要事/机会喂 LLM 的当日条数上限（0=不限）
    brief_top_n: int | None = None  # 今日要事显示条数


def _schedule_snapshot() -> dict:
    return {
        **runtime_config.get_auto_refresh(),
        "cluster_input_max": runtime_config.get_cluster_input_max(),
        "brief_top_n": runtime_config.get_brief_top_n(),
    }


@router.get("/schedule")
async def get_schedule() -> dict:
    """读「知·生成」配置：{enabled, start_hour, end_hour, cluster_input_max}。"""
    return await run_in_threadpool(_schedule_snapshot)


@router.post("/schedule")
async def set_schedule(body: ScheduleIn) -> dict:
    """改「知·生成」配置（即时生效，运行时读取，无需重启）。返回最新完整配置。"""

    _own = {"cluster_input_max", "brief_top_n"}  # 非 auto_refresh 的独立字段

    def _apply() -> dict:
        patch = {k: v for k, v in body.model_dump().items() if v is not None and k not in _own}
        if patch:
            runtime_config.set_auto_refresh(patch)
        if body.cluster_input_max is not None:
            runtime_config.set_cluster_input_max(body.cluster_input_max)
        if body.brief_top_n is not None:
            runtime_config.set_brief_top_n(body.brief_top_n)
        return _schedule_snapshot()

    return await run_in_threadpool(_apply)


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
