from __future__ import annotations

from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import InMemorySaver

from app.settings import Settings
from app.llm.factory import build_chat_model
from app.orchestrator import AgentOrchestrator
from app.runtime.local_tool_registry import LocalToolRegistry
from app.runtime.mcp_tool_registry import McpToolRegistry
from app.runtime.skill_registry import SkillRegistry
from app.runtime.tool_registry import ToolRegistry


def _build_tool_registry(settings: Settings) -> ToolRegistry:
    """构建 agent 侧可见的全部工具来源。"""

    skill_registry = SkillRegistry.from_directory(settings.resolve_path(settings.skills_dir))
    local_tool_registry = LocalToolRegistry(
        "app.local_tools",
        tool_factory_kwargs={"skill_registry": skill_registry},
    )
    mcp_tool_registry = McpToolRegistry(
        config_path=settings.resolve_path(settings.mcp_services_config),
        default_timeout_seconds=settings.mcp_timeout_seconds,
    )
    return ToolRegistry([local_tool_registry, mcp_tool_registry])


def _build_middleware(settings: Settings, model: BaseChatModel) -> tuple[SummarizationMiddleware, ...]:
    """构建 LangGraph agent 中间件。"""

    return (
        SummarizationMiddleware(
            model=model,
            trigger=[
                ("messages", settings.summary_trigger_messages),
                ("tokens", settings.summary_trigger_tokens),
            ],
            keep=("messages", settings.summary_keep_messages),
        ),
    )


def build_orchestrator(
    settings: Settings,
    *,
    chat_model: BaseChatModel | None = None,
) -> AgentOrchestrator:
    """同步装配并初始化一个可直接对外提供服务的 orchestrator。"""

    tool_registry = _build_tool_registry(settings)
    chat_bundle = build_chat_model(settings) if chat_model is None else None
    model = chat_model or chat_bundle.model

    orchestrator = AgentOrchestrator(
        chat_model=model,
        llm_provider_name=chat_bundle.provider_name if chat_bundle else "test-langchain",
        tool_registry=tool_registry,
        checkpointer=InMemorySaver(),
        middleware=_build_middleware(settings, model),
        agent_recursion_limit=settings.agent_recursion_limit,
    )
    orchestrator.initialize()
    return orchestrator
