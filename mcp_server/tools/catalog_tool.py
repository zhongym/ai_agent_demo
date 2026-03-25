from __future__ import annotations

from datetime import datetime

from fastmcp import FastMCP

from mcp_server.tools.schemas import ProductItem, ProductSearchResult

PRODUCT_ITEMS = [
    {
        "sku": "LN-RUN-001",
        "name": "李宁轻云跑鞋",
        "brand": "李宁",
        "category": "鞋",
        "price": 399,
        "stock": 520,
        "score": 9.2,
        "monthly_sales": 920,
        "reason": "价格友好、库存充足，适合日常跑步和通勤。",
    },
    {
        "sku": "LN-RUN-002",
        "name": "李宁赤兔跑鞋",
        "brand": "李宁",
        "category": "鞋",
        "price": 459,
        "stock": 286,
        "score": 9.0,
        "monthly_sales": 850,
        "reason": "口碑稳定，综合评分高，适合入门跑者。",
    },
    {
        "sku": "LN-LIFE-010",
        "name": "李宁轻潮休闲鞋",
        "brand": "李宁",
        "category": "鞋",
        "price": 329,
        "stock": 198,
        "score": 8.7,
        "monthly_sales": 610,
        "reason": "轻便百搭，预算压力小，适合通勤。",
    },
    {
        "sku": "LN-BASKET-009",
        "name": "李宁驭帅篮球鞋",
        "brand": "李宁",
        "category": "鞋",
        "price": 699,
        "stock": 356,
        "score": 9.4,
        "monthly_sales": 430,
        "reason": "支撑和包裹表现更强，偏篮球场景。",
    },
    {
        "sku": "ANTA-RUN-100",
        "name": "安踏轻盈跑鞋",
        "brand": "安踏",
        "category": "鞋",
        "price": 369,
        "stock": 412,
        "score": 8.8,
        "monthly_sales": 700,
        "reason": "销量表现不错，性价比高。",
    },
]


def _current_updated_at() -> str:
    return datetime.now().isoformat(timespec="seconds")


def register_catalog_tools(server: FastMCP) -> None:
    """注册商品搜索类 MCP tools。"""

    @server.tool(
        name="search_products",
        description="按商品数据。",
        tags={"catalog", "recommend", "search"},
    )
    def search_products(
        brand: str | None = None,
        category: str | None = None,
        price_max: int | None = None,
        use_case: str | None = None,
        limit: int = 5,
        sort_by: str = "score",
    ) -> ProductSearchResult:
        items = PRODUCT_ITEMS

        if brand:
            items = [item for item in items if item["brand"] == brand]
        if category:
            items = [item for item in items if category in item["category"]]
        if price_max is not None:
            items = [item for item in items if item["price"] <= price_max]
        if use_case == "篮球":
            items = [item for item in items if "篮球" in item["reason"] or "篮球" in item["name"]]
        if use_case == "跑步":
            items = [item for item in items if "跑" in item["name"] or "跑步" in item["reason"]]

        sorted_items = sorted(items, key=lambda item: item.get(sort_by, item["score"]), reverse=True)
        result_items = [ProductItem(**item) for item in sorted_items[:limit]]
        return ProductSearchResult(
            filters={
                "brand": brand,
                "category": category,
                "price_max": price_max,
                "use_case": use_case,
                "limit": limit,
                "sort_by": sort_by,
            },
            items=result_items,
            updated_at=_current_updated_at(),
        )
