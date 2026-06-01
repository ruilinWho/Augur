"""标的检索：本地内存索引 + 东方财富实时联想（CLAUDE.md §7）。

两路融合，用同一个打分器统一排序，按 symbol 去重：
  · 本地索引 = 各市场目录 parquet（listings.py）+ 跨语言别名种子（aliases.yaml）。
    覆盖美股英文名 + 韩股（东财不收韩股）+ 海力士/三星这类跨语言别名；离线可用、毫秒级。
  · 东财 suggest = searchapi.eastmoney.com 实时联想。港股 + A股最全最新（含拼音），
    新上市的 MiniMax / 智谱 也搜得到；但美股噪声大（ETF/票据靠前）、无韩股 —— 故只作补充。
带 TTL 缓存 + 超时 + 失败降级（断网/被墙 → 仅本地），尊重限流（CLAUDE.md §4/§11）。

打分（高→低）：代码精确 > 名称精确 > 代码/名称前缀 > 子串（越靠前越短越优）> 词首 > 子序列。
线程：build_index() 在启动后台线程跑；search() 同步只读 + 一次联想，置于 threadpool。
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field

import httpx

from ..config import get_settings
from . import listings

_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub(" ", str(s).strip().lower())


@dataclass
class _Rec:
    symbol: str
    market: str
    code: str
    name: str  # 主显示名（本地语优先）
    sub: str  # 次要显示（英文名 / 中文别名 / 行业）
    code_l: str
    names_l: list[str] = field(default_factory=list)  # 去重后的可搜索名（已小写）


_INDEX: list[_Rec] = []
_READY = False
_LOCK = threading.Lock()


def _load_aliases() -> dict[str, dict]:
    """读 resources/sources/aliases.yaml → {symbol: {cn, names[]}}。缺文件/解析失败 → 空。"""
    path = get_settings().resources_dir / "sources" / "aliases.yaml"
    if not path.exists():
        return {}
    try:
        import yaml

        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except Exception as e:  # noqa: BLE001
        print(f"[search] 别名种子解析失败：{type(e).__name__}: {e}")
        return {}
    out: dict[str, dict] = {}
    for entry in raw:
        if not isinstance(entry, dict) or "symbol" not in entry:
            continue
        sym = str(entry["symbol"]).strip()
        names = [str(n).strip() for n in (entry.get("names") or []) if str(n).strip()]
        out[sym] = {"cn": str(entry.get("cn") or "").strip(), "names": names}
    return out


def build_index() -> int:
    """从磁盘目录 + 别名种子重建内存索引。返回索引条数。可重复调用（刷新）。"""
    global _INDEX, _READY
    aliases = _load_aliases()
    recs: list[_Rec] = []
    seen: set[str] = set()
    for market in ("US", "HK", "CN", "KR"):
        df = listings.load_cached(market)
        if df is None or df.empty:
            continue
        for row in df.itertuples(index=False):
            symbol = row.symbol
            if symbol in seen:
                continue
            seen.add(symbol)
            name = (row.name or "").strip() or row.code
            name_en = (getattr(row, "name_en", "") or "").strip()
            extra = aliases.pop(symbol, None)
            cn = extra["cn"] if extra else ""
            alias_names = extra["names"] if extra else []
            # 次要显示：中文别名 > 英文名（且与主名不同）
            sub = cn if (cn and cn != name) else (name_en if name_en and name_en != name else "")
            names_l = {_norm(n) for n in (name, name_en, cn, *alias_names) if n}
            recs.append(
                _Rec(
                    symbol=symbol,
                    market=row.market,
                    code=row.code,
                    name=name,
                    sub=sub,
                    code_l=row.code.lower(),
                    names_l=[n for n in names_l if n],
                )
            )
    # 仅存在于别名种子、目录里没有的标的（如代理拦截导致港股目录缺失）——也要可搜到
    for symbol, extra in aliases.items():
        try:
            market, code = symbol.split(":", 1)
        except ValueError:
            continue
        cn = extra["cn"]
        name = cn or code
        names_l = {_norm(n) for n in (cn, *extra["names"], code) if n}
        recs.append(
            _Rec(
                symbol=symbol,
                market=market,
                code=code,
                name=name,
                sub=cn if cn and cn != name else "",
                code_l=code.lower(),
                names_l=[n for n in names_l if n],
            )
        )
    with _LOCK:
        _INDEX = recs
        _READY = True
    print(f"[search] 索引就绪：{len(recs)} 条")
    return len(recs)


def ready() -> bool:
    return _READY


def _subseq(q: str, s: str) -> bool:
    """q 是否为 s 的子序列（轻量模糊，容忍中间缺字）。"""
    it = iter(s)
    return all(ch in it for ch in q)


def _score(rec: _Rec, q: str) -> int:
    code = rec.code_l
    if code == q:
        return 1000
    best = 0
    for n in rec.names_l:
        if n == q:
            best = max(best, 900)
        elif n.startswith(q):
            best = max(best, 780)
        elif q in n:
            pos = n.find(q)
            best = max(best, 640 - min(pos, 30) - min(len(n), 60) // 5)
    if code.startswith(q):
        best = max(best, 820)
    elif q in code:
        best = max(best, 560)
    if best:
        return best
    # 词首（英文名按空格分词）
    for n in rec.names_l:
        if any(tok.startswith(q) for tok in n.split(" ")):
            return 460
    # 子序列模糊（仅 q≥2，避免噪声）
    if len(q) >= 2 and any(_subseq(q, n) for n in rec.names_l):
        return 180
    return 0


# ───────────────────────── 东方财富实时联想（港股/A股最全最新）─────────────────────────
_EM_URL = "https://searchapi.eastmoney.com/api/suggest/get"
_EM_TOKEN = "D43BF722C8E33BDC906FB84D85E326E8"  # 东财公开 suggest token
_EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.eastmoney.com/",
}
# Classify → 我方市场（其余如 LSE 英股 / OTCFUND 基金 / 期货 / 板块 一律丢弃）
_EM_MKT = {"HK": "HK", "AStock": "CN", "UsStock": "US"}
# 衍生品/票据噪声标记（东财联想会混入杠杆 ETF、牛熊证、债券票据）
_EM_NOISE = (
    "ETF",
    "ETN",
    "做多",
    "做空",
    "两倍",
    "三倍",
    "反向",
    "杠杆",
    "牛证",
    "熊证",
    "Notes",
    "Bond",
)
# 港股二级计价/人民币柜台后缀（与主柜台重复）；-W/-SW/-S 是同股不同权/二次上市，保留
_EM_DROP_SUFFIX = ("-R", "-WR", "-WS", "-RS")
_EM_TTL = 1800.0  # 同一 query 30 分钟内走缓存，别狂打数据源
_em_cache: dict[str, tuple[float, list[dict]]] = {}
_em_lock = threading.Lock()


def _em_suggest(q: str) -> list[dict]:
    """调东财 suggest，返回原始条目（缓存 + 超时 + 失败降级为空）。"""
    now = time.time()
    with _em_lock:
        hit = _em_cache.get(q)
        if hit and now - hit[0] < _EM_TTL:
            return hit[1]
    try:
        r = httpx.get(
            _EM_URL,
            params={"input": q, "type": "14", "token": _EM_TOKEN, "count": "15"},
            headers=_EM_HEADERS,
            timeout=4.0,
        )
        data = (r.json().get("QuotationCodeTable") or {}).get("Data") or []
    except Exception as e:  # noqa: BLE001 — 断网/被墙/超时 → 静默降级到本地
        print(f"[search] 东财联想失败（降级本地）：{type(e).__name__}: {str(e)[:80]}")
        data = []
    with _em_lock:
        _em_cache[q] = (now, data)
        if len(_em_cache) > 500:
            oldest = min(_em_cache, key=lambda k: _em_cache[k][0])
            _em_cache.pop(oldest, None)
    return data


def _map_em(item: dict) -> _Rec | None:
    mkt = _EM_MKT.get(item.get("Classify", ""))
    if not mkt:
        return None
    name = (item.get("Name") or "").strip()
    code = (item.get("Code") or "").strip()
    if not name or not code or any(tok in name for tok in _EM_NOISE):
        return None
    if name.endswith(_EM_DROP_SUFFIX):  # 人民币/二级柜台 dup
        return None
    if mkt == "US":
        if any(ch.isdigit() for ch in code):  # AAPL22/AAPL24… 票据，丢
            return None
        code = code.upper()
    elif mkt == "HK":
        # 港股认购/认沽证（如「智谱法巴六十购A」）；A股「苏宁易购」含购，故仅限港股过滤
        if "购" in name or "沽" in name:
            return None
        code = code.zfill(5)
    pinyin = (item.get("PinYin") or "").strip().lower()
    names_l = [_norm(name)] + ([pinyin] if pinyin else [])
    return _Rec(
        symbol=f"{mkt}:{code}",
        market=mkt,
        code=code,
        name=name,
        sub="",
        code_l=code.lower(),
        names_l=[n for n in names_l if n],
    )


def _live_recs(q: str) -> list[_Rec]:
    out: list[_Rec] = []
    seen: set[str] = set()
    for item in _em_suggest(q):
        rec = _map_em(item)
        if rec and rec.symbol not in seen:
            seen.add(rec.symbol)
            out.append(rec)
    return out


def search(query: str, market: str | None = None, limit: int = 20) -> list[dict]:
    """模糊检索：本地索引 ∪ 东财实时联想，统一打分去重。market 非 ALL 时限定该市场。"""
    q = _norm(query)
    if not q:
        return []
    mkt = (market or "").upper()
    scope = None if mkt in ("", "ALL") else mkt
    with _LOCK:
        index = _INDEX
    # 本地优先级略高（含英文名/韩股/别名，且离线可靠）；东财补全港股/A股/新股
    best: dict[str, tuple[int, int, _Rec]] = {}
    for rec in (*index, *_live_recs(q)):
        if scope and rec.market != scope:
            continue
        s = _score(rec, q)
        if not s:
            continue
        prev = best.get(rec.symbol)
        if prev is None or s > prev[0]:
            best[rec.symbol] = (s, len(rec.name), rec)
    ranked = sorted(best.values(), key=lambda t: (-t[0], t[1]))
    return [
        {"symbol": r.symbol, "market": r.market, "code": r.code, "name": r.name, "sub": r.sub}
        for _, _, r in ranked[:limit]
    ]
