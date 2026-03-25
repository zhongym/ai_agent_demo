from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel


class CurrentTimeContextInput(BaseModel):
    """本地时间工具无需入参，这里保留空 schema 便于稳定生成 tool 定义。"""


def _format_utc_offset(now: datetime) -> str:
    raw = now.strftime("%z")
    if len(raw) == 5:
        return f"{raw[:3]}:{raw[3:]}"
    return raw or "+00:00"


def _build_date_range(label: str, start_date: str, end_date: str) -> dict[str, str]:
    return {
        "label": label,
        "start_date": start_date,
        "end_date": end_date,
    }


@tool(
    "get_time",
    description="获取当前本地日期时间，以及今日、本月、上个月、近30天等常用相对时间范围。处理相对日期前应先调用。",
    args_schema=CurrentTimeContextInput,
    parse_docstring=False,
    extras={"local_tool": {"kind": "local", "tool_result": "identity"}},
)
async def get_time() -> dict[str, Any]:
    """本地时间上下文工具。

    这类信息不需要经过 MCP 服务，直接在 agent 进程内获取更简单、时延也更低。
    """

    now = datetime.now().astimezone()
    today = now.date()
    first_day_this_month = today.replace(day=1)
    last_day_previous_month = first_day_this_month - timedelta(days=1)
    first_day_previous_month = last_day_previous_month.replace(day=1)

    return {
        "current_date": today.isoformat(),
        "current_datetime": now.isoformat(timespec="seconds"),
        "timezone": now.tzname() or "local",
        "utc_offset": _format_utc_offset(now),
        "today": _build_date_range("今日", today.isoformat(), today.isoformat()),
        "current_month": _build_date_range("本月", first_day_this_month.isoformat(), today.isoformat()),
        "previous_month": _build_date_range(
            "上个月",
            first_day_previous_month.isoformat(),
            last_day_previous_month.isoformat(),
        ),
        "last_30_days": _build_date_range(
            "近30天",
            (today - timedelta(days=29)).isoformat(),
            today.isoformat(),
        ),
    }
