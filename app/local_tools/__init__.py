from __future__ import annotations

from langchain_core.tools.structured import StructuredTool

from app.local_tools.run_skill import build_run_skill_tool
from app.local_tools.time import get_time
from app.runtime.skill_registry import SkillRegistry


def build_local_tools(*, skill_registry: SkillRegistry) -> list[StructuredTool]:
    """返回需要业务依赖注入的本地工具列表。"""

    return [build_run_skill_tool(skill_registry)]


__all__ = ["build_local_tools", "get_time"]
