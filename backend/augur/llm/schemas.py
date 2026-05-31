"""llm 域的 Pydantic 模型。"""

from __future__ import annotations

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # user / assistant / system
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    role: str = "chat"  # 网关角色（chat/deep_research/summarize/cheap）


class RoleStatus(BaseModel):
    role: str
    provider: str | None
    model: str | None
    configured: bool
