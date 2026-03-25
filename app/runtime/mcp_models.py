from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class McpServiceConfig(BaseModel):
    """MCP 客户端配置。

    这里只保留 agent 侧真正会消费的字段，不再承接旧的 inprocess 配置。
    """

    alias: str
    enabled: bool = True
    transport: Literal["http", "stdio"]
    url: str | None = None
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    cwd: str | None = None
    timeout_seconds: float | None = None
