from __future__ import annotations

import logging

from fastapi import FastAPI

from app.bootstrap import build_orchestrator
from app.orchestrator import AgentOrchestrator
from app.settings import Settings, get_settings
from app.schemas.api import QueryRequest, QueryResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def create_app(settings: Settings | None = None, orchestrator: AgentOrchestrator | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    app_orchestrator = orchestrator or build_orchestrator(app_settings)
    app = FastAPI(title=app_settings.app_name)

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "name": app_settings.app_name,
            "message": "访问 POST /query 发起带 thread_id 的多轮查询。",
        }

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "llm_provider": app_orchestrator.llm_provider_name,
            "mcp_transport": app_orchestrator.mcp_transport_label,
        }

    @app.post("/query", response_model=QueryResponse)
    async def query(request: QueryRequest) -> QueryResponse:
        return await app_orchestrator.handle_question(request.thread_id, request.question)

    return app


app = create_app()
