from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

MCP_SERVER_ENV_FILE = Path(__file__).resolve().with_name(".env")


class McpServerSettings(BaseSettings):
    """MCP mock 服务自身的配置。

    服务端默认从 `mcp_server/.env` 读取环境变量。
    """

    model_config = SettingsConfigDict(
        env_file=MCP_SERVER_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    host: str = Field(default="127.0.0.1", alias="MCP_HOST")
    port: int = Field(default=9001, alias="MCP_PORT")
    path: str = Field(default="/mcp", alias="MCP_PATH")


@lru_cache(maxsize=1)
def get_settings() -> McpServerSettings:
    return McpServerSettings()
