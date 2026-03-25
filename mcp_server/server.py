from __future__ import annotations

import os

from fastmcp import FastMCP

from mcp_server.settings import get_settings
from mcp_server.tools.catalog_tool import register_catalog_tools
from mcp_server.tools.inventory_tool import register_inventory_tools
from mcp_server.tools.metrics_tool import register_metrics_tools


def create_mcp_server() -> FastMCP:
    """创建并注册所有 mock MCP tools。"""

    server = FastMCP("enterprise-data-mock")
    register_metrics_tools(server)
    register_inventory_tools(server)
    register_catalog_tools(server)
    return server


mcp = create_mcp_server()


def main() -> None:
    if os.getenv("MCP_TRANSPORT") == "stdio":
        # 被 agent 以子进程方式拉起时走 stdio。
        mcp.run(
            transport="stdio",
            show_banner=False,
        )
        return

    settings = get_settings()
    # 单独调试 mock 服务时走 HTTP，便于本地联调。
    mcp.run(
        transport="http",
        host=settings.host,
        port=settings.port,
        path=settings.path,
        show_banner=False,
    )


if __name__ == "__main__":
    main()
