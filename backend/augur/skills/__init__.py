"""skills 域：可插拔投研技能（resources/skills/ 文件夹驱动）。

一个 Skill = `resources/skills/<slug>/SKILL.md`（frontmatter 元信息 + markdown 正文，
含 {STOCK}/{NAME}/{MARKET}/{SYMBOL} 占位符）。丢一个文件夹进去就多一个研究技能：
在「研」的「复制 Prompt」里按当前标的填充复制，服务外部网页 Deep Research。
区别于「模板」（用户自存、SQLite、随手增改）——Skill 是版本化、方法论级、可带确定性脚本。
"""

from .router import router

__all__ = ["router"]
