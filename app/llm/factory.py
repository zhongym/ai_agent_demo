from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.settings import Settings

logger = logging.getLogger("enterprise_agent.llm_http")
DEFAULT_LLM_PROVIDER_NAME = "bailian-langchain"


@dataclass
class ChatModelBundle:
    model: BaseChatModel
    provider_name: str


def _decode_http_payload(payload: bytes) -> str:
    if not payload:
        return ""
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        return payload.decode("utf-8", errors="replace")


def _parse_http_payload(payload: str) -> object:
    if not payload:
        return {}
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return payload


def _build_payload_logging_http_client(enabled: bool) -> httpx.AsyncClient | None:
    if not enabled:
        return None

    async def log_request(request: httpx.Request) -> None:
        try:
            body = _parse_http_payload(_decode_http_payload(await request.aread()))
            logger.info(
                "llm.request | payload=%s",
                json.dumps(
                    {
                        "method": request.method,
                        "url": str(request.url),
                        "body": body,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )
        except Exception as exc:
            logger.exception("记录 LLM 请求日志失败: %s", exc)

    async def log_response(response: httpx.Response) -> None:
        try:
            body = _parse_http_payload(_decode_http_payload(await response.aread()))
            logger.info(
                "llm.response | payload=%s",
                json.dumps(
                    {
                        "status_code": response.status_code,
                        "url": str(response.request.url),
                        "body": body,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )
        except Exception as exc:
            logger.exception("记录 LLM 响应日志失败: %s", exc)

    # 只在调试 LLM 请求时创建独立的异步 client，避免默认路径额外持有资源。
    return httpx.AsyncClient(
        event_hooks={
            "request": [log_request],
            "response": [log_response],
        }
    )


def build_chat_model(settings: Settings) -> ChatModelBundle:
    api_key = settings.dashscope_api_key or "missing-dashscope-api-key"
    model = ChatOpenAI(
        model=settings.bailian_model,
        api_key=api_key,
        base_url=settings.bailian_base_url,
        temperature=0.2,
        http_async_client=_build_payload_logging_http_client(settings.llm_log_payloads),
    )
    return ChatModelBundle(model=model, provider_name=DEFAULT_LLM_PROVIDER_NAME)
