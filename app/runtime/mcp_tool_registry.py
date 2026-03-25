from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import yaml
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.interceptors import MCPToolCallRequest, MCPToolCallResult
from mcp.types import CallToolResult, TextContent

from app.runtime.mcp_models import McpServiceConfig
from app.runtime.tool_models import ToolInvocationRecord
from app.runtime.tool_registry import ToolRegistryError, ToolSourceRegistry

logger = logging.getLogger("enterprise_agent.mcp_tool_registry")


class McpToolRegistry(ToolSourceRegistry):
    """管理 MCP tools 的发现、调用与结果记录。"""

    def __init__(
        self,
        config_path: str | Path,
        default_timeout_seconds: float = 10.0,
    ) -> None:
        self.config_path = Path(config_path).resolve()
        self.default_timeout_seconds = default_timeout_seconds
        self.service_configs = self._load_config()
        self._connections: dict[str, dict[str, Any]] = {}
        self._tool_names: set[str] = set()
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return

        self._connections = {
            alias: self._build_connection(service)
            for alias, service in self.service_configs.items()
            if service.enabled
        }
        tools = self._run_async_blocking(self._load_tools_async())
        self._tool_names = self._extract_tool_names(tools)
        self._initialized = True

    def get_tools(self, recorder: Callable[[ToolInvocationRecord], None]) -> list[BaseTool]:
        self._assert_ready()

        tools = self._run_async_blocking(
            self._load_tools_async(tool_interceptors=[self._build_recording_interceptor(recorder)])
        )
        tool_names = self._extract_tool_names(tools)
        if tool_names != self._tool_names:
            raise ToolRegistryError("MCP tools 集合在初始化后发生变化")
        return tools

    def describe_source(self) -> str:
        descriptions = [
            f"{alias}:{self._build_connection(service)['transport']}"
            for alias, service in self.service_configs.items()
            if service.enabled
        ]
        return ", ".join(descriptions) or "no-enabled-mcp"

    def _load_config(self) -> dict[str, McpServiceConfig]:
        raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        services = raw.get("services", {})
        result: dict[str, McpServiceConfig] = {}
        for alias, payload in services.items():
            result[alias] = McpServiceConfig.model_validate({"alias": alias, **payload})
        return result

    async def _load_tools_async(
        self,
        tool_interceptors: list[Callable[[MCPToolCallRequest, Callable[[MCPToolCallRequest], Awaitable[MCPToolCallResult]]], Awaitable[MCPToolCallResult]]] | None = None,
    ) -> list[BaseTool]:
        client = MultiServerMCPClient(
            self._connections,
            tool_interceptors=tool_interceptors,
            tool_name_prefix=True,
        )
        tools = await client.get_tools()
        return sorted(tools, key=lambda tool: tool.name)

    @staticmethod
    def _run_async_blocking(awaitable: Any) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(awaitable)

        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(awaitable)).result()

    def _build_connection(self, service: McpServiceConfig) -> dict[str, Any]:
        # agent 侧只负责把配置翻译成 MultiServerMCPClient 认识的连接参数。
        if service.transport == "http":
            if not service.url:
                raise ToolRegistryError(f"MCP 服务 {service.alias} 缺少 url")
            return {
                "transport": "http",
                "url": service.url,
                "timeout": service.timeout_seconds or self.default_timeout_seconds,
            }

        if service.transport == "stdio":
            if not service.command:
                raise ToolRegistryError(f"MCP 服务 {service.alias} 缺少 command")
            if service.args is None:
                raise ToolRegistryError(f"MCP 服务 {service.alias} 缺少 args")
            connection: dict[str, Any] = {
                "transport": "stdio",
                "command": service.command,
                "args": service.args,
            }
            if service.env is not None:
                connection["env"] = service.env
            if service.cwd is not None:
                connection["cwd"] = service.cwd
            return connection

        raise ToolRegistryError(f"不支持的 MCP transport: {service.transport}")

    @staticmethod
    def _extract_tool_names(tools: list[BaseTool]) -> set[str]:
        names = {tool.name for tool in tools}
        if len(names) != len(tools):
            raise ToolRegistryError("MCP tool name 冲突")
        return names

    def _build_recording_interceptor(
        self,
        recorder: Callable[[ToolInvocationRecord], None],
    ) -> Callable[[MCPToolCallRequest, Callable[[MCPToolCallRequest], Awaitable[MCPToolCallResult]]], Awaitable[MCPToolCallResult]]:
        async def interceptor(
            request: MCPToolCallRequest,
            handler: Callable[[MCPToolCallRequest], Awaitable[MCPToolCallResult]],
        ) -> MCPToolCallResult:
            result = await handler(request)
            recorder(
                ToolInvocationRecord(
                    name=self._prefixed_tool_name(request.server_name, request.name),
                    kind="mcp",
                    arguments=request.args,
                    response=self._normalize_call_result(result),
                )
            )
            return result

        return interceptor

    @staticmethod
    def _prefixed_tool_name(server_name: str, tool_name: str) -> str:
        return f"{server_name}_{tool_name}"

    def _normalize_call_result(self, result: MCPToolCallResult) -> Any:
        # LangChain MCP adapter 返回的结果可能是原始 CallToolResult，
        # 也可能已经是普通对象。这里统一折叠成便于记录和测试断言的结构。
        if isinstance(result, CallToolResult):
            structured_content = getattr(result, "structuredContent", None)
            if structured_content is not None:
                return structured_content
            return self._normalize_content_blocks(result.content)
        return result

    @staticmethod
    def _normalize_content_blocks(content: list[Any]) -> Any:
        text_parts = []
        for item in content:
            if isinstance(item, TextContent):
                text_parts.append(item.text)
            elif isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        if text_parts:
            return McpToolRegistry._maybe_parse_json("\n".join(part for part in text_parts if part))
        return content

    @staticmethod
    def _maybe_parse_json(text: str) -> Any:
        stripped = text.strip()
        if not stripped:
            return text
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return text

    def _assert_ready(self) -> None:
        if not self._initialized:
            raise ToolRegistryError("McpToolRegistry 尚未初始化，请先调用 initialize()")
