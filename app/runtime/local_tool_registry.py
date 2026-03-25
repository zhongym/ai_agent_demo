from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from types import ModuleType
from typing import Any

from langchain_core.tools import BaseTool
from langchain_core.tools.structured import StructuredTool

from app.runtime.tool_models import ToolInvocationRecord, ToolRecordKind
from app.runtime.tool_registry import ToolRegistryError, ToolSourceRegistry

ToolRecorder = Callable[[ToolInvocationRecord], None]


def _default_record_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """去掉 None 值，避免工具记录里充满无意义空字段。"""

    return {key: value for key, value in arguments.items() if value is not None}


def _build_tool_input(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str | dict[str, Any]:
    """把 LangChain wrapper 入口统一折叠成 base tool 能理解的输入结构。"""

    if kwargs:
        return kwargs
    if not args:
        return {}
    if len(args) == 1:
        return args[0]
    raise ToolRegistryError("LocalToolRegistry 只支持零参数、字符串输入或关键字参数输入")


def _record_tool_invocation(
    *,
    recorder: ToolRecorder,
    tool_name: str,
    record_kind: ToolRecordKind,
    tool_input: str | dict[str, Any],
    result: Any,
) -> None:
    """把一次本地工具调用写入当前请求的 recorder。"""

    arguments = tool_input if isinstance(tool_input, dict) else {"input": tool_input}
    recorder(
        ToolInvocationRecord(
            name=tool_name,
            kind=record_kind,
            arguments=_default_record_arguments(arguments),
            response=result,
        )
    )


def _serialize_tool_result(result: Any, tool_result_format: str) -> Any:
    """按工具声明的格式把结果返回给 agent。"""

    if tool_result_format == "identity":
        return result
    if tool_result_format == "json":
        return json.dumps(result, ensure_ascii=False)
    raise ToolRegistryError(f"不支持的本地 tool 输出格式: {tool_result_format}")


class LocalToolRegistry(ToolSourceRegistry):
    """管理本地 LangChain tools。

    本地工具分成两类：
    1. 直接在模块里导出的静态 StructuredTool
    2. 通过 build_local_tools(...) 按依赖动态构造的 StructuredTool
    """

    def __init__(
        self,
        module_path: str,
        *,
        tool_factory_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self.module_path = module_path
        self.tool_factory_kwargs = dict(tool_factory_kwargs or {})
        self._base_tools: list[StructuredTool] = []
        self._tool_names: set[str] = set()
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return

        module = importlib.import_module(self.module_path)
        self._base_tools = self._load_tools(module)
        self._tool_names = self._extract_tool_names(self._base_tools)
        self._initialized = True

    def get_tools(self, recorder: ToolRecorder) -> list[BaseTool]:
        self._assert_ready()

        tools = [self._build_recording_wrapper(tool_instance, recorder) for tool_instance in self._base_tools]
        tool_names = self._extract_tool_names(tools)
        if tool_names != self._tool_names:
            raise ToolRegistryError("Local tools 集合在初始化后发生变化")
        return sorted(tools, key=lambda tool_instance: tool_instance.name)

    def describe_source(self) -> str:
        return ""

    def _load_tools(self, module: ModuleType) -> list[StructuredTool]:
        static_tools = self._collect_static_tools(module)
        factory_tools = self._collect_factory_tools(module)
        return sorted([*static_tools, *factory_tools], key=lambda tool_instance: tool_instance.name)

    @staticmethod
    def _collect_static_tools(module: ModuleType) -> list[StructuredTool]:
        tools = [value for value in vars(module).values() if isinstance(value, StructuredTool)]
        return sorted(tools, key=lambda tool_instance: tool_instance.name)

    def _collect_factory_tools(self, module: ModuleType) -> list[StructuredTool]:
        builder = getattr(module, "build_local_tools", None)
        if builder is None:
            return []

        # 依赖注入型工具通过显式工厂创建，避免模块级全局状态污染测试和运行时。
        tools = builder(**self.tool_factory_kwargs)
        if not isinstance(tools, list) or not all(isinstance(tool, StructuredTool) for tool in tools):
            raise ToolRegistryError("build_local_tools 必须返回 StructuredTool 列表")
        return sorted(tools, key=lambda tool_instance: tool_instance.name)

    @staticmethod
    def _extract_tool_names(tools: list[BaseTool]) -> set[str]:
        names = {tool_instance.name for tool_instance in tools}
        if len(names) != len(tools):
            raise ToolRegistryError("Local tool name 冲突")
        return names

    def _build_recording_wrapper(self, base_tool: StructuredTool, recorder: ToolRecorder) -> StructuredTool:
        local_config = self._get_local_tool_config(base_tool)
        record_kind = self._get_record_kind(local_config)
        tool_result_format = self._get_tool_result_format(local_config)

        def invoke_recorded(*args: Any, **kwargs: Any) -> Any:
            tool_input = _build_tool_input(args, kwargs)
            result = base_tool.invoke(tool_input)
            _record_tool_invocation(
                recorder=recorder,
                tool_name=base_tool.name,
                record_kind=record_kind,
                tool_input=tool_input,
                result=result,
            )
            return _serialize_tool_result(result, tool_result_format)

        async def ainvoke_recorded(*args: Any, **kwargs: Any) -> Any:
            tool_input = _build_tool_input(args, kwargs)
            result = await base_tool.ainvoke(tool_input)
            _record_tool_invocation(
                recorder=recorder,
                tool_name=base_tool.name,
                record_kind=record_kind,
                tool_input=tool_input,
                result=result,
            )
            return _serialize_tool_result(result, tool_result_format)

        return StructuredTool.from_function(
            func=invoke_recorded,
            coroutine=ainvoke_recorded,
            name=base_tool.name,
            description=base_tool.description,
            args_schema=base_tool.args_schema,
            return_direct=getattr(base_tool, "return_direct", False),
            response_format=getattr(base_tool, "response_format", "content"),
            extras=getattr(base_tool, "extras", None),
            metadata=dict(base_tool.metadata) if getattr(base_tool, "metadata", None) is not None else None,
            tags=list(base_tool.tags) if getattr(base_tool, "tags", None) is not None else None,
        )

    @staticmethod
    def _get_local_tool_config(base_tool: BaseTool) -> dict[str, Any]:
        extras = getattr(base_tool, "extras", None) or {}
        config = extras.get("local_tool", {})
        return config if isinstance(config, dict) else {}

    @staticmethod
    def _get_record_kind(local_config: dict[str, Any]) -> ToolRecordKind:
        kind = local_config.get("kind", "local")
        if kind not in {"local", "skill"}:
            raise ToolRegistryError(f"不支持的本地 tool kind: {kind}")
        return kind

    @staticmethod
    def _get_tool_result_format(local_config: dict[str, Any]) -> str:
        tool_result_format = local_config.get("tool_result", "identity")
        if tool_result_format not in {"identity", "json"}:
            raise ToolRegistryError(f"不支持的本地 tool 输出格式: {tool_result_format}")
        return tool_result_format

    def _assert_ready(self) -> None:
        if not self._initialized:
            raise ToolRegistryError("LocalToolRegistry 尚未初始化，请先调用 initialize()")
