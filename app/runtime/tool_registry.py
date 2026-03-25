from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol

from langchain_core.tools import BaseTool

from app.runtime.tool_models import ToolInvocationRecord


class ToolRegistryError(RuntimeError):
    pass


class ToolSourceRegistry(Protocol):
    """统一的工具来源接口。"""

    def initialize(self) -> None:
        ...

    def get_tools(self, recorder: Callable[[ToolInvocationRecord], None]) -> list[BaseTool]:
        ...

    def describe_source(self) -> str:
        ...


class ToolRegistry:
    """聚合多个工具来源并对外暴露统一工具集合。"""

    def __init__(self, registries: Iterable[ToolSourceRegistry]) -> None:
        self._registries = list(registries)
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        for registry in self._registries:
            registry.initialize()
        self._initialized = True

    def get_tools(self, recorder: Callable[[ToolInvocationRecord], None]) -> list[BaseTool]:
        self._assert_ready()

        tools: list[BaseTool] = []
        seen_names: set[str] = set()
        for registry in self._registries:
            for tool in registry.get_tools(recorder):
                if tool.name in seen_names:
                    raise ToolRegistryError(f"tool name 冲突: {tool.name}")
                seen_names.add(tool.name)
                tools.append(tool)
        return tools

    def describe_transport(self) -> str:
        descriptions = []
        for registry in self._registries:
            description = registry.describe_source()
            if description:
                descriptions.append(description)
        return ", ".join(descriptions) or "no-enabled-tool-source"

    def _assert_ready(self) -> None:
        if not self._initialized:
            raise ToolRegistryError("ToolRegistry 尚未初始化，请先调用 initialize()")
