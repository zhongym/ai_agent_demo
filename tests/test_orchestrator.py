from __future__ import annotations

from datetime import date

import pytest
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.bootstrap import build_orchestrator as build_runtime_orchestrator
from app.runtime.local_tool_registry import LocalToolRegistry
from app.runtime.mcp_tool_registry import McpToolRegistry
from app.orchestrator import AgentOrchestrator
from app.runtime.skill_registry import SkillRegistry
from app.runtime.tool_registry import ToolRegistry
from app.settings import Settings
from tests.fakes import ScriptedAgentChatModel


def build_test_orchestrator(
    chat_model: ScriptedAgentChatModel,
    *,
    settings: Settings | None = None,
) -> AgentOrchestrator:
    resolved_settings = settings or Settings(
        skills_dir="/Users/zhongym/ai_agent/app/skills",
        mcp_services_config="/Users/zhongym/ai_agent/app/config/mcp_services.yaml",
    )
    return build_runtime_orchestrator(
        resolved_settings,
        chat_model=chat_model,
    )


@pytest.mark.anyio
async def test_handle_question_requires_initialized_orchestrator() -> None:
    chat_model = ScriptedAgentChatModel(responses=[AIMessage(content="不会执行到这里")])
    skill_registry = SkillRegistry.from_directory("/Users/zhongym/ai_agent/app/skills")
    orchestrator = AgentOrchestrator(
        chat_model=chat_model,
        llm_provider_name="test-langchain",
        tool_registry=ToolRegistry(
            [
                LocalToolRegistry(
                    "app.local_tools",
                    tool_factory_kwargs={"skill_registry": skill_registry},
                ),
                McpToolRegistry("/Users/zhongym/ai_agent/app/config/mcp_services.yaml"),
            ]
        ),
        checkpointer=InMemorySaver(),
        middleware=(SummarizationMiddleware(model=chat_model, trigger=[("messages", 40)], keep=("messages", 20)),),
    )

    with pytest.raises(RuntimeError, match="尚未初始化"):
        await orchestrator.handle_question("thread-uninitialized", "你好")


@pytest.mark.anyio
async def test_direct_product_search_can_call_mcp_tool_without_skill() -> None:
    chat_model = ScriptedAgentChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "data_center_search_products",
                        "args": {
                            "brand": "李宁",
                            "category": "鞋",
                            "price_max": 500,
                            "use_case": None,
                            "limit": 5,
                            "sort_by": "score",
                        },
                        "id": "call_products",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="我为你筛出几款 500 元以内的李宁鞋，优先按综合得分排序。"),
        ]
    )
    orchestrator = build_test_orchestrator(chat_model)
    result = await orchestrator.handle_question("thread-product", "推荐500元以内李宁鞋")

    assert [item.name for item in result.message_summary.tool_calls] == ["data_center_search_products"]
    assert result.message_summary.tool_calls[0].response is not None
    assert all(item["brand"] == "李宁" for item in result.message_summary.tool_calls[0].response["items"])
    assert "data_center_search_products" in chat_model.bound_tool_names


@pytest.mark.anyio
async def test_session_history_is_replayed_on_next_turn() -> None:
    def second_turn(messages):
        user_messages = [msg for msg in messages if isinstance(msg, HumanMessage)]
        ai_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
        assert any("记住我关注李宁鞋" in msg.content for msg in user_messages)
        assert any("我记住了" in str(msg.content) for msg in ai_messages)
        return AIMessage(content="我记得你上轮提到李宁鞋，这轮可以继续按这个偏好帮你筛。")

    chat_model = ScriptedAgentChatModel(
        responses=[
            AIMessage(content="我记住了，你现在关注李宁鞋。"),
            second_turn,
        ]
    )
    orchestrator = build_test_orchestrator(chat_model)

    first = await orchestrator.handle_question("thread-memory", "记住我关注李宁鞋")
    second = await orchestrator.handle_question("thread-memory", "继续按这个偏好推荐")

    assert first.answer == "我记住了，你现在关注李宁鞋。"
    assert second.answer == "我记得你上轮提到李宁鞋，这轮可以继续按这个偏好帮你筛。"
    assert second.message_summary.tool_calls == []


@pytest.mark.anyio
async def test_direct_metric_query_can_use_time_context_tool_for_relative_dates() -> None:
    today = date.today()
    first_day_this_month = today.replace(day=1)

    chat_model = ScriptedAgentChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_time",
                        "args": {},
                        "id": "call_time",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "data_center_query_metric",
                        "args": {
                            "metric": "sales_amount",
                            "time_range_label": "本月",
                            "start_date": first_day_this_month.isoformat(),
                            "end_date": today.isoformat(),
                            "filters": None,
                        },
                        "id": "call_metric",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content=f"本月销售额是 125800 元，统计区间为 {first_day_this_month.isoformat()} 至 {today.isoformat()}。"),
        ]
    )
    orchestrator = build_test_orchestrator(chat_model)

    result = await orchestrator.handle_question("thread-kpi", "我这个月销售额多少")

    assert [item.name for item in result.message_summary.tool_calls] == [
        "get_time",
        "data_center_query_metric",
    ]
    assert "get_time" in chat_model.bound_tool_names


@pytest.mark.anyio
async def test_sales_inventory_snapshot_uses_two_mcp_tools() -> None:
    today = date.today()
    first_day_this_month = today.replace(day=1)

    chat_model = ScriptedAgentChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "run_skill",
                        "args": {"skill": "sales_inventory_snapshot", "args": "指标=销售额 时间=本月 前3个"},
                        "id": "call_skill",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_time",
                        "args": {},
                        "id": "call_time",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "data_center_query_metric",
                        "args": {
                            "metric": "sales_amount",
                            "time_range_label": "本月",
                            "start_date": first_day_this_month.isoformat(),
                            "end_date": today.isoformat(),
                            "filters": None,
                        },
                        "id": "call_metric",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "data_center_top_products",
                        "args": {
                            "scope": "全部商品",
                            "rank_by": "stock",
                            "top_k": 3,
                            "warehouse": None,
                        },
                        "id": "call_inventory",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="本月销售额表现稳定，库存最高的前三个商品主要集中在跑鞋类目。"),
        ]
    )
    orchestrator = build_test_orchestrator(chat_model)

    result = await orchestrator.handle_question("thread-snapshot", "给我看下本月销售额和库存最高的前3个商品")

    assert [item.name for item in result.message_summary.tool_calls] == [
        "run_skill",
        "get_time",
        "data_center_query_metric",
        "data_center_top_products",
    ]
    assert result.message_summary.tool_calls[0].response["skill_name"] == "sales_inventory_snapshot"
    assert "data_center_query_metric" in chat_model.bound_tool_names
    assert "data_center_top_products" in chat_model.bound_tool_names


@pytest.mark.anyio
async def test_image_ocr_skill_uses_run_skill_then_shell_tool() -> None:
    chat_model = ScriptedAgentChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "run_skill",
                        "args": {
                            "skill": "image_ocr_extract",
                            "args": "请识别这张图里的文字 https://example.com/receipt.png",
                        },
                        "id": "call_skill",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "run_shell_command",
                        "args": {
                            "commands": [
                                ".venv/bin/python app/skills/ocr/ocr_runner.py https://example.com/receipt.png",
                            ],
                            "working_directory": ".",
                        },
                        "id": "call_shell",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="识别完成。OCR原文为“订单号 12345”，简要整理为这是一张包含订单编号的图片。"),
        ]
    )
    orchestrator = build_test_orchestrator(chat_model)

    result = await orchestrator.handle_question("thread-ocr", "请识别这张图里的文字 https://example.com/receipt.png")

    assert [item.name for item in result.message_summary.tool_calls] == ["run_skill", "run_shell_command"]
    assert result.message_summary.tool_calls[0].response["skill_name"] == "image_ocr_extract"
    assert result.message_summary.tool_calls[1].arguments["commands"][0].startswith(".venv/bin/python app/skills/ocr/ocr_runner.py")
    assert result.message_summary.tool_calls[1].arguments["working_directory"] == "."
    assert "run_shell_command" in chat_model.bound_tool_names


@pytest.mark.anyio
async def test_summarization_middleware_compresses_history_for_same_thread() -> None:
    settings = Settings(
        skills_dir="/Users/zhongym/ai_agent/app/skills",
        mcp_services_config="/Users/zhongym/ai_agent/app/config/mcp_services.yaml",
        summary_trigger_messages=2,
        summary_trigger_tokens=999999,
        summary_keep_messages=2,
    )

    def second_turn(messages):
        human_texts = [msg.content for msg in messages if isinstance(msg, HumanMessage)]
        ai_texts = [msg.content for msg in messages if isinstance(msg, AIMessage)]

        assert "第一轮问题" not in human_texts
        assert any(
            isinstance(text, str) and text.startswith("Here is a summary of the conversation to date:")
            for text in human_texts
        )
        assert "第二轮继续" in human_texts
        assert "第一轮完成" in ai_texts
        return AIMessage(content="第二轮完成")

    chat_model = ScriptedAgentChatModel(
        responses=[
            AIMessage(content="第一轮完成"),
            AIMessage(content="这是前文摘要。"),
            second_turn,
        ]
    )
    orchestrator = build_test_orchestrator(chat_model, settings=settings)

    first = await orchestrator.handle_question("thread-summary", "第一轮问题")
    second = await orchestrator.handle_question("thread-summary", "第二轮继续")

    assert first.answer == "第一轮完成"
    assert second.answer == "第二轮完成"
    assert second.message_summary.tool_calls == []
