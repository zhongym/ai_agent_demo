from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ToolRecordKind = Literal["skill", "mcp", "local"]


class ToolCallSummary(BaseModel):
    """返回给 API 调用方的工具调用摘要。"""

    name: str
    kind: ToolRecordKind
    arguments: dict[str, Any] = Field(default_factory=dict)
    response: Any = None


class ToolInvocationRecord(BaseModel):
    """当前请求上下文中的一次工具调用记录。"""

    name: str
    kind: ToolRecordKind
    arguments: dict[str, Any] = Field(default_factory=dict)
    response: Any
