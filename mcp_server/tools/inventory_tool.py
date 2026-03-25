from __future__ import annotations

from datetime import datetime

from fastmcp import FastMCP

from mcp_server.tools.schemas import InventoryItem, InventoryResult

INVENTORY_ITEMS = [
    {
        "sku": "LN-RUN-001",
        "name": "李宁轻云跑鞋",
        "stock": 520,
        "sellable_stock": 488,
        "warehouse": "华东一仓",
        "category": "跑鞋",
        "brand": "李宁",
    },
    {
        "sku": "ANTA-TRAIN-101",
        "name": "安踏氮科技训练鞋",
        "stock": 460,
        "sellable_stock": 441,
        "warehouse": "华南二仓",
        "category": "训练鞋",
        "brand": "安踏",
    },
    {
        "sku": "NIKE-RUN-888",
        "name": "耐克飞影跑鞋",
        "stock": 398,
        "sellable_stock": 372,
        "warehouse": "华北一仓",
        "category": "跑鞋",
        "brand": "耐克",
    },
    {
        "sku": "LN-BASKET-009",
        "name": "李宁驭帅篮球鞋",
        "stock": 356,
        "sellable_stock": 331,
        "warehouse": "华东一仓",
        "category": "篮球鞋",
        "brand": "李宁",
    },
    {
        "sku": "ADI-RUN-660",
        "name": "阿迪达斯轻动跑鞋",
        "stock": 315,
        "sellable_stock": 302,
        "warehouse": "西南仓",
        "category": "跑鞋",
        "brand": "阿迪达斯",
    },
]


def _current_updated_at() -> str:
    return datetime.now().isoformat(timespec="seconds")


def register_inventory_tools(server: FastMCP) -> None:
    """注册库存榜单类 MCP tools。"""

    @server.tool(
        name="top_products",
        description="查询库存数据。",
        tags={"inventory", "ranking", "stock"},
    )
    def top_products(
        scope: str = "全部商品",
        rank_by: str = "stock",
        top_k: int = 5,
        warehouse: str | None = None,
    ) -> InventoryResult:
        items = INVENTORY_ITEMS
        if warehouse:
            items = [item for item in items if item["warehouse"] == warehouse]

        sorted_items = sorted(items, key=lambda item: item.get(rank_by, item["stock"]), reverse=True)
        top_items = [InventoryItem(**item) for item in sorted_items[:top_k]]
        return InventoryResult(
            scope=scope,
            rank_by=rank_by,
            items=top_items,
            updated_at=_current_updated_at(),
        )
