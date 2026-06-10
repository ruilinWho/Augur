"""Skill 注册表：扫描 resources/skills/*/SKILL.md，解析 frontmatter + 正文。

frontmatter（YAML）字段：name、summary、surface（yan/xun）、slug（默认=目录名）。
正文 = frontmatter 之后的全部 markdown（含 {STOCK}/{NAME}/{MARKET}/{SYMBOL} 占位符）。
缓存按目录 mtime 失效——丢一个文件夹进去即可见（真·可插拔），无需重启。
"""

from __future__ import annotations

import threading
from pathlib import Path

import yaml

from ..config import get_settings

_LOCK = threading.Lock()
_CACHE: dict[str, dict] | None = None
_CACHE_SIG: float = -1.0


def _skills_dir() -> Path:
    return get_settings().resources_dir / "skills"


def _parse(md: str) -> tuple[dict, str]:
    """拆 frontmatter（YAML）与正文。无 frontmatter → ({}, 全文)。"""
    if md.startswith("---"):
        end = md.find("\n---", 3)
        if end != -1:
            fm_raw = md[3:end].strip()
            body = md[end + 4 :].lstrip("\n")
            try:
                fm = yaml.safe_load(fm_raw) or {}
            except yaml.YAMLError:
                fm = {}
            if isinstance(fm, dict):
                return fm, body
    return {}, md


def _dir_signature(d: Path) -> float:
    """目录及其下 SKILL.md 的最大 mtime——用于缓存失效。"""
    sig = 0.0
    if not d.is_dir():
        return sig
    for sub in d.iterdir():
        if sub.is_dir():
            f = sub / "SKILL.md"
            if f.exists():
                sig = max(sig, f.stat().st_mtime, sub.stat().st_mtime)
    return max(sig, d.stat().st_mtime)


def _load() -> dict[str, dict]:
    out: dict[str, dict] = {}
    base = _skills_dir()
    if not base.is_dir():
        return out
    for sub in sorted(base.iterdir()):
        if not sub.is_dir():
            continue
        f = sub / "SKILL.md"
        if not f.exists():
            continue
        try:
            fm, body = _parse(f.read_text(encoding="utf-8"))
        except OSError:
            continue
        slug = str(fm.get("slug") or sub.name).strip()
        surface = str(fm.get("surface") or "yan").strip()
        out[slug] = {
            "slug": slug,
            "name": str(fm.get("name") or slug).strip(),
            "summary": str(fm.get("summary") or "").strip(),
            "surface": surface if surface in ("yan", "xun") else "yan",
            "body": body.strip(),
            "has_scorecard": (sub / "scorecard.json").exists()
            or "评分卡" in body
            or "scorecard" in body.lower(),
        }
    return out


def all_skills() -> dict[str, dict]:
    """全部 skill（slug→dict），按目录 mtime 缓存。"""
    global _CACHE, _CACHE_SIG
    sig = _dir_signature(_skills_dir())
    with _LOCK:
        if _CACHE is None or sig != _CACHE_SIG:
            _CACHE = _load()
            _CACHE_SIG = sig
        return dict(_CACHE)


def get(slug: str) -> dict | None:
    return all_skills().get(slug)
