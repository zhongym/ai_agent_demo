from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class MetricResult(BaseModel):
    """指标查询结果。"""

    metric: str
    metric_label: str
    time_range_label: str
    start_date: str
    end_date: str
    value: float
    currency: str = "CNY"
    source: str = "mock"
    updated_at: str


class InventoryItem(BaseModel):
    """库存榜单中的单个商品。"""

    sku: str
    name: str
    stock: int
    sellable_stock: int
    warehouse: str
    category: str
    brand: str


class InventoryResult(BaseModel):
    """库存查询结果。"""

    scope: str
    rank_by: str
    items: list[InventoryItem]
    source: str = "mock"
    updated_at: str


class ProductItem(BaseModel):
    """商品搜索结果中的单个商品。"""

    sku: str
    name: str
    brand: str
    category: str
    price: int
    stock: int
    score: float
    monthly_sales: int
    reason: str


class ProductSearchResult(BaseModel):
    """商品搜索结果。"""

    filters: dict[str, Any]
    items: list[ProductItem]
    source: str = "mock"
    updated_at: str
