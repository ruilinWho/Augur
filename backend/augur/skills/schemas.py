"""skills 域 Pydantic 模型。"""

from __future__ import annotations

from pydantic import BaseModel


class SkillMeta(BaseModel):
    slug: str
    name: str = ""
    summary: str = ""
    surface: str = "yan"  # 挂哪个表面：yan（研）/ xun（寻）
    enabled: bool = True
    has_scorecard: bool = False


class Skill(SkillMeta):
    body: str = ""  # markdown 正文（含占位符）


class EnablePatch(BaseModel):
    enabled: bool
