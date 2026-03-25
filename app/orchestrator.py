from __future__ import annotations

import json
import logging
from contextvars import ContextVar

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.llm.prompts import build_agent_system_prompt
from app.runtime.tool_models import ToolCallSummary, ToolInvocationRecord
from app.runtime.tool_registry import ToolRegistry, ToolRegistryError
from app.schemas.api import MessageSummary, QueryResponse

logger = logging.getLogger("enterprise_agent.orchestrator")


class AgentOrchestrator:
    """统一编排 LLM、LangGraph checkpoint 和工具执行。"""

    def __init__(
        self,
        chat_model: BaseChatModel,
        llm_provider_name: str,
        tool_registry: ToolRegistry,
        checkpointer: InMemorySaver,
        middleware: tuple[SummarizationMiddleware, ...],
        agent_recursion_limit: int = 25,
    ) -> None:
        self.chat_model = chat_model
        self.llm_provider_name = llm_provider_name
        self.tool_registry = tool_registry
        self.checkpointer = checkpointer
        self.middleware = middleware
        self.agent_recursion_limit = agent_recursion_limit
        self.mcp_transport_label = "initializing"
        self._initialized = False
        self._agent = None
        self._tool_records_var: ContextVar[list[ToolInvocationRecord] | None] = ContextVar(
            "agent_tool_records",
            default=None,
        )

    @staticmethod
    def _stringify(payload: object) -> str:
        try:
            text = json.dumps(payload, ensure_ascii=False, default=str)
        except TypeError:
            text = str(payload)

        if len(text) > 800:
            return f"{text[:800]}..."
        return text

    def _log(self, stage: str, message: str, payload: object | None = None) -> None:
        if payload is None:
            logger.info("[%s] %s", stage, message)
            return
        logger.info("[%s] %s | payload=%s", stage, message, self._stringify(payload))

    def initialize(self) -> None:
        if self._initialized:
            return

        self.tool_registry.initialize()
        self.mcp_transport_label = self.tool_registry.describe_transport()
        self._agent = self._build_agent()
        self._initialized = True

    def _assert_ready(self) -> None:
        if not self._initialized or self._agent is None:
            raise RuntimeError("AgentOrchestrator 尚未初始化，请在启动阶段先调用 initialize()")

    def _record_tool(self, record: ToolInvocationRecord) -> None:
        records = self._tool_records_var.get()
        if records is not None:
            records.append(record)

    def _get_recorded_tools(self) -> list[ToolInvocationRecord]:
        records = self._tool_records_var.get()
        return records if records is not None else []

    def _build_agent(self):
        # agent 可见的 tools 统一由聚合 registry 提供。
        # 当前包含本地工具和 MCP tools。
        tools = self.tool_registry.get_tools(self._record_tool)
        return create_agent(
            model=self.chat_model,
            tools=tools,
            system_prompt=build_agent_system_prompt(),
            middleware=self.middleware,
            checkpointer=self.checkpointer,
            name="enterprise-data-agent",
        )

    @staticmethod
    def _extract_answer(messages: list[BaseMessage]) -> str:
        """从 LangGraph 返回的消息流里提取最终自然语言回答。"""

        for message in reversed(messages):
            if isinstance(message, AIMessage) and not message.tool_calls:
                content = message.content
                if isinstance(content, str) and content.strip():
                    return content.strip()
                if isinstance(content, list):
                    parts = [item.get("text", "") for item in content if isinstance(item, dict)]
                    text = "".join(parts).strip()
                    if text:
                        return text
        raise ValueError("LLM 未返回最终回答")

    def _build_message_summary(self) -> MessageSummary:
        records = self._get_recorded_tools()
        return MessageSummary(
            tool_calls=[
                ToolCallSummary(
                    name=record.name,
                    kind=record.kind,
                    arguments=record.arguments,
                    response=record.response,
                )
                for record in records
            ],
        )

    def _build_response(
        self,
        *,
        thread_id: str,
        question: str,
        output_messages: list[BaseMessage],
    ) -> QueryResponse:
        return QueryResponse(
            thread_id=thread_id,
            question=question,
            answer=self._extract_answer(output_messages),
            llm_provider=self.llm_provider_name,
            mcp_transport=self.mcp_transport_label,
            message_summary=self._build_message_summary(),
        )

    async def handle_question(self, thread_id: str, question: str) -> QueryResponse:
        """处理单轮用户问题。

        多轮记忆、历史摘要和 tool call 循环都交给 LangGraph agent 完成，
        这里负责本轮输入、日志和响应整形。
        """
        self._assert_ready()

        human_message = HumanMessage(content=question)
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": self.agent_recursion_limit,
        }
        self._log("start", "收到用户问题", {"thread_id": thread_id, "question": question})

        token = self._tool_records_var.set([])
        try:
            result = await self._agent.ainvoke(
                {"messages": [human_message]},
                config=config,
            )

            response = self._build_response(
                thread_id=thread_id,
                question=question,
                output_messages=result["messages"],
            )
            self._log(
                "finish",
                "请求处理完成",
                {"thread_id": thread_id, "tool_call_count": len(response.message_summary.tool_calls)},
            )
            return response
        except (ToolRegistryError, ValueError) as exc:
            self._log("error", f"请求处理失败: {exc}")
            raise
        finally:
            self._tool_records_var.reset(token)
