from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from langchain_core.tools.structured import StructuredTool
from pydantic import BaseModel, Field

from app.runtime.skill_registry import SkillRegistry
from app.runtime.skill_models import SkillSpec

MAX_DESCRIPTION_LENGTH = 120


def _trim_description(text: str) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= MAX_DESCRIPTION_LENGTH:
        return normalized
    return f"{normalized[: MAX_DESCRIPTION_LENGTH - 3]}..."


def _build_run_skill_description(skills: list[SkillSpec]) -> str:
    """把所有可用 Skill 压缩成一段给 LLM 的工具描述。"""

    skill_lines = [f"- {skill.name}: {_trim_description(skill.description)}" for skill in skills]
    return "\n".join(
        [
            "在主对话中执行一个 skill。",
            "",
            "当某个 skill 明显适用于当前任务时，必须先调用这个工具，然后才能继续调用 MCP tools。",
            "不要只在文本里提到 skill 名称而不实际调用工具。",
            "如果任务与某个 skill 匹配，run_skill 必须是本轮的第一个业务动作。",
            "如果意图不明确，先向用户澄清，不要盲目调用。",
            "",
            "调用示例：",
            '- `skill: "sales_inventory_snapshot", args: "指标=销售额 时间=本月 前3个"`',
            '- `skill: "image_ocr_extract", args: "请识别这张图里的文字 https://example.com/a.png"`',
            "",
            "可用 skills：",
            *skill_lines,
        ]
    )


class RunSkillInput(BaseModel):
    """run_skill 的入参结构。"""

    skill: str = Field(description="要执行的 skill 名称。")
    args: str | None = Field(default=None, description="传给 skill 的原始补充说明。")


def build_run_skill_tool(skill_registry: SkillRegistry) -> StructuredTool:
    """创建注入了 SkillRegistry 的 run_skill 本地工具。

    这里使用闭包绑定依赖，避免再通过模块级全局变量回写工具描述或共享运行时状态。
    """

    @tool(
        "run_skill",
        description=_build_run_skill_description(skill_registry.list()),
        args_schema=RunSkillInput,
        parse_docstring=False,
        extras={"local_tool": {"kind": "skill", "tool_result": "json"}},
    )
    async def run_skill(skill: str, args: str | None = None) -> dict[str, Any]:
        spec = skill_registry.get(skill)
        return {
            "skill_name": spec.name,
            "description": spec.description,
            "content_markdown": spec.body,
            "args": args,
        }

    return run_skill
