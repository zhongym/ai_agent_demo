from __future__ import annotations

from pydantic import BaseModel, Field

from app.runtime.tool_models import ToolCallSummary


class QueryRequest(BaseModel):
    """对外查询请求。"""

    thread_id: str = Field(min_length=1, description="线程 ID，用于串联 LangGraph checkpoint 历史")
    question: str = Field(min_length=2, description="用户自然语言问题")


class MessageSummary(BaseModel):
    """本轮请求中发生的工具调用摘要。"""

    tool_calls: list[ToolCallSummary] = Field(default_factory=list)


class QueryResponse(BaseModel):
    """对外查询响应。"""

    thread_id: str
    question: str
    answer: str
    llm_provider: str
    mcp_transport: str
    message_summary: MessageSummary
