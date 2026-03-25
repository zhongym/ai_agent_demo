from __future__ import annotations

from datetime import datetime

from fastmcp import FastMCP

from mcp_server.tools.schemas import MetricResult

METRIC_LABELS = {
    "sales_amount": "销售额",
    "order_count": "订单量",
    "avg_order_value": "客单价",
}

METRIC_VALUES = {
    "sales_amount": 125800,
    "order_count": 3142,
    "avg_order_value": 401,
}


def _current_updated_at() -> str:
    return datetime.now().isoformat(timespec="seconds")


def register_metrics_tools(server: FastMCP) -> None:
    """注册指标查询类 MCP tools。"""

    @server.tool(
        name="query_metric",
        description="查询企业经营指标",
        tags={"sales", "metrics", "kpi"},
    )
    def query_metric(
        metric: str,
        time_range_label: str,
        start_date: str,
        end_date: str,
        filters: dict | None = None,
    ) -> MetricResult:
        _ = filters or {}
        metric_label = METRIC_LABELS.get(metric, metric)
        value = METRIC_VALUES.get(metric, 0)
        return MetricResult(
            metric=metric,
            metric_label=metric_label,
            time_range_label=time_range_label,
            start_date=start_date,
            end_date=end_date,
            value=value,
            updated_at=_current_updated_at(),
        )
