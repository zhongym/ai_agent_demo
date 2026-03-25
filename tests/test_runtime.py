from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from langchain_core.tools import BaseTool

from app.runtime.local_tool_registry import LocalToolRegistry
from app.runtime.mcp_tool_registry import McpToolRegistry
from app.runtime.skill_registry import SkillRegistry
from app.runtime.tool_registry import ToolRegistry


def test_local_tool_registry_collects_configured_run_skill() -> None:
    skill_registry = SkillRegistry.from_directory("/Users/zhongym/ai_agent/app/skills")
    tool_registry = LocalToolRegistry(
        "app.local_tools",
        tool_factory_kwargs={"skill_registry": skill_registry},
    )
    tool_registry.initialize()

    tools_by_name = {tool.name: tool for tool in tool_registry.get_tools(lambda record: None)}
    run_skill = tools_by_name["run_skill"]
    schema = run_skill.args_schema.model_json_schema()

    assert schema["required"] == ["skill"]
    assert schema["properties"]["skill"]["type"] == "string"
    assert "args" in schema["properties"]
    assert "- sales_inventory_snapshot:" in run_skill.description
    assert "- image_ocr_extract:" in run_skill.description
    assert set(tools_by_name) == {"get_time", "run_shell_command", "run_skill"}


@pytest.mark.anyio
async def test_local_tool_registry_exposes_run_skill_and_mcp_tools() -> None:
    skill_registry = SkillRegistry.from_directory("/Users/zhongym/ai_agent/app/skills")
    tool_registry = ToolRegistry(
        [
            LocalToolRegistry(
                "app.local_tools",
                tool_factory_kwargs={"skill_registry": skill_registry},
            ),
            McpToolRegistry("/Users/zhongym/ai_agent/app/config/mcp_services.yaml"),
        ]
    )
    tool_registry.initialize()

    names = {tool.name for tool in tool_registry.get_tools(lambda record: None)}

    assert "run_skill" in names
    assert "run_shell_command" in names
    assert "data_center_query_metric" in names
    assert "data_center_search_products" in names


@pytest.mark.anyio
async def test_local_tool_registry_wraps_run_skill_and_records_invocation() -> None:
    records = []
    skill_registry = SkillRegistry.from_directory("/Users/zhongym/ai_agent/app/skills")
    tool_registry = LocalToolRegistry(
        "app.local_tools",
        tool_factory_kwargs={"skill_registry": skill_registry},
    )
    tool_registry.initialize()

    tools = {tool.name: tool for tool in tool_registry.get_tools(records.append)}
    result = await tools["run_skill"].ainvoke({"skill": "sales_inventory_snapshot", "args": "指标=销售额 时间=本月"})
    payload = json.loads(result)

    assert payload["skill_name"] == "sales_inventory_snapshot"
    assert payload["args"] == "指标=销售额 时间=本月"
    assert records[0].name == "run_skill"
    assert records[0].kind == "skill"
    assert records[0].arguments == {"skill": "sales_inventory_snapshot", "args": "指标=销售额 时间=本月"}
    assert records[0].response["skill_name"] == "sales_inventory_snapshot"


@pytest.mark.anyio
async def test_local_shell_command_tool_executes_commands_and_records_invocation() -> None:
    records = []
    skill_registry = SkillRegistry.from_directory("/Users/zhongym/ai_agent/app/skills")
    tool_registry = LocalToolRegistry(
        "app.local_tools",
        tool_factory_kwargs={"skill_registry": skill_registry},
    )
    tool_registry.initialize()

    tools = {tool.name: tool for tool in tool_registry.get_tools(records.append)}
    result = await tools["run_shell_command"].ainvoke(
        {
            "commands": [
                ".venv/bin/python -c \"from pathlib import Path; Path('note.txt').write_text('hello', encoding='utf-8')\"",
                ".venv/bin/python -c \"print(open('note.txt', encoding='utf-8').read())\"",
            ]
        }
    )

    assert result["success"] is True
    assert result["items"][0]["exit_code"] == 0
    assert result["items"][1]["stdout"].strip() == "hello"
    assert records[0].name == "run_shell_command"
    assert records[0].kind == "local"
    assert records[0].arguments["commands"][0].startswith(".venv/bin/python -c")


@pytest.mark.anyio
async def test_local_shell_command_tool_can_write_and_execute_python_script() -> None:
    skill_registry = SkillRegistry.from_directory("/Users/zhongym/ai_agent/app/skills")
    tool_registry = LocalToolRegistry(
        "app.local_tools",
        tool_factory_kwargs={"skill_registry": skill_registry},
    )
    tool_registry.initialize()

    tools = {tool.name: tool for tool in tool_registry.get_tools(lambda record: None)}
    result = await tools["run_shell_command"].ainvoke(
        {
            "commands": [
                ".venv/bin/python -c \"from pathlib import Path; Path('runner.py').write_text('print(\\\"script-ok\\\")\\n', encoding='utf-8')\"",
                ".venv/bin/python runner.py",
            ]
        }
    )

    assert result["success"] is True
    assert result["items"][1]["stdout"].strip() == "script-ok"


@pytest.mark.anyio
async def test_local_shell_command_tool_supports_project_working_directory() -> None:
    skill_registry = SkillRegistry.from_directory("/Users/zhongym/ai_agent/app/skills")
    tool_registry = LocalToolRegistry(
        "app.local_tools",
        tool_factory_kwargs={"skill_registry": skill_registry},
    )
    tool_registry.initialize()

    tools = {tool.name: tool for tool in tool_registry.get_tools(lambda record: None)}
    result = await tools["run_shell_command"].ainvoke(
        {
            "commands": [
                ".venv/bin/python -c \"from pathlib import Path; print(Path('README.md').exists())\"",
            ],
            "working_directory": ".",
        }
    )

    assert result["success"] is True
    assert result["items"][0]["stdout"].strip() == "True"


@pytest.mark.anyio
async def test_local_shell_command_tool_rejects_non_whitelisted_commands() -> None:
    skill_registry = SkillRegistry.from_directory("/Users/zhongym/ai_agent/app/skills")
    tool_registry = LocalToolRegistry(
        "app.local_tools",
        tool_factory_kwargs={"skill_registry": skill_registry},
    )
    tool_registry.initialize()

    tools = {tool.name: tool for tool in tool_registry.get_tools(lambda record: None)}
    result = await tools["run_shell_command"].ainvoke({"commands": ["rm -rf /"]})

    assert result["success"] is False
    assert result["items"][0]["exit_code"] == -1
    assert "不允许的命令前缀" in result["items"][0]["stderr"]

@pytest.mark.anyio
async def test_local_time_context_tool_returns_realtime_ranges() -> None:
    skill_registry = SkillRegistry.from_directory("/Users/zhongym/ai_agent/app/skills")
    tool_registry = LocalToolRegistry(
        "app.local_tools",
        tool_factory_kwargs={"skill_registry": skill_registry},
    )
    tool_registry.initialize()

    tools = {tool.name: tool for tool in tool_registry.get_tools(lambda record: None)}
    result = await tools["get_time"].ainvoke({})
    today = date.today()
    first_day_this_month = today.replace(day=1)
    last_day_previous_month = first_day_this_month - timedelta(days=1)
    first_day_previous_month = last_day_previous_month.replace(day=1)

    assert result["current_date"] == today.isoformat()
    assert result["today"]["start_date"] == today.isoformat()
    assert result["today"]["end_date"] == today.isoformat()
    assert result["current_month"]["start_date"] == first_day_this_month.isoformat()
    assert result["current_month"]["end_date"] == today.isoformat()
    assert result["previous_month"]["start_date"] == first_day_previous_month.isoformat()
    assert result["previous_month"]["end_date"] == last_day_previous_month.isoformat()
    assert result["last_30_days"]["start_date"] == (today - timedelta(days=29)).isoformat()
    assert result["last_30_days"]["end_date"] == today.isoformat()


@pytest.mark.anyio
async def test_mcp_tools_are_exposed_as_langchain_tools() -> None:
    tool_registry = McpToolRegistry(
        "/Users/zhongym/ai_agent/app/config/mcp_services.yaml",
    )
    tool_registry.initialize()

    tools = tool_registry.get_tools(lambda record: None)
    names = {tool.name for tool in tools}

    assert {
        "data_center_query_metric",
        "data_center_top_products",
        "data_center_search_products",
    } <= names
    assert all(isinstance(tool, BaseTool) for tool in tools)

    tools_by_name = {tool.name: tool for tool in tools}
    assert tools_by_name["data_center_query_metric"].description == "查询企业经营指标"
    assert set(tools_by_name["data_center_query_metric"].metadata["_meta"]["fastmcp"]["tags"]) == {
        "sales",
        "metrics",
        "kpi",
    }
